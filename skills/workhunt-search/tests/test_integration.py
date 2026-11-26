"""Packaging, reporting and current-contract regression tests in temporary folders."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from test_kit import OfflineCase, read_page, opportunity, board, gh_row
import adapters
import outcomes
import qualification
import records
import render
import scan
import source_registry

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


installer = module("workhunt_installer", ROOT / "tools/install_workhunt_skills.py")
refresh = module("workhunt_refresh", ROOT / "tools/refresh_workhunt_references.py")


class PackagingTests(OfflineCase):
    def test_complete_16_skill_temp_home_install_check_and_private_data_exclusion(self):
        root = self.work / "home with spaces/.agents/skills"
        result = installer.install(root)
        self.assertEqual(result["skills"], 16)
        self.assertTrue(installer.install(root, check=True)["references_verified"])
        inventory = installer.inventory(root)
        self.assertFalse(any(key.endswith((".pdf", ".docx")) or "/data/jobs.json" in key or "/data/applied_jobs.json" in key for key in inventory))
        self.assertTrue((root / "workhunt-maintain-sources/SKILL.md").is_file())

    def test_unowned_and_locally_changed_conflicts_are_not_overwritten(self):
        root = self.work / "home/.agents/skills"
        path = root / "workhunt-search/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("User-owned local instructions", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "locally modified"):
            installer.install(root)
        self.assertEqual(path.read_text("utf-8"), "User-owned local instructions")
        path.unlink()
        installer.install(root)
        path.write_text("Changed after install", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "locally modified"):
            installer.install(root)
        self.assertEqual(path.read_text("utf-8"), "Changed after install")

    def test_resolver_prefers_explicit_then_cwd_then_installed_fallback_with_spaces(self):
        other = self.work / "workspace with spaces"
        (other / "docs/skills").mkdir(parents=True)
        (other / "profile.json").write_text("{}", encoding="utf-8")
        (other / "docs/skills/WORKHUNT_CONTEXT.md").write_text("Fixture context", encoding="utf-8")
        destination = self.work / "installed home/.agents/skills"
        installer.install(destination, workspace=other)
        script = destination / "workhunt-search/scripts/resolve_workspace.py"
        for args, cwd in [(["--workspace", str(other)], self.work), ([], other / "docs"), ([], self.work)]:
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(script), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(result.stdout.strip()), other)

    def test_refresh_preserves_metadata_and_does_not_create_legacy_records(self):
        for name in installer.ENTRY_NAMES:
            (self.work / "skills" / name / "references").mkdir(parents=True)
        runtime = self.work / "skills/workhunt-search/references/runtime.md"
        runtime.write_text("Current fixture runtime", encoding="utf-8")
        metadata = self.work / "skills/workhunt-search/agents/openai.yaml"
        metadata.parent.mkdir()
        metadata.write_text("policy:\n  allow_implicit_invocation: true\n", encoding="utf-8")
        refresh.refresh(self.work)
        self.assertEqual(metadata.read_text("utf-8"), "policy:\n  allow_implicit_invocation: true\n")
        self.assertFalse(any((self.work / name).exists() for name in ("applications.json", "manual-opportunities.json", "reviews.json")))
        self.assertEqual(refresh.refresh(self.work, check=True)["changed"], [])


class CurrentIntegrationTests(OfflineCase):
    def test_actual_default_profile_selects_288_employers_19_feeds_and_existing_three(self):
        profile = records.load(ROOT / "profile.json")
        with patch.object(scan, "get", return_value=json.dumps({"companies": []})):
            boards, failures = scan.collect_boards(profile, ROOT)
        self.assertEqual(len(boards), 307)
        self.assertEqual(failures, [])
        self.assertTrue({"greenhouse:us:pontera", "greenhouse:us:triplewhale", "lever:us:oktopost"}.issubset({b["key"] for b in boards}))

    def test_disabled_override_wins_over_directory_and_extra_boards(self):
        row = {"name": "Fixture", "provider": "greenhouse", "token": "fixture", "careers_url": "https://job-boards.greenhouse.io/fixture"}
        records.save(self.work / "sources/employer-boards.json", source_registry.build_registry([row]))
        records.save(self.work / "sources/employer-overrides.json", {"boards": {"greenhouse:us:fixture": {"enabled": False}}})
        profile = {**self.profile, "directory_enabled": True, "employer_registry_enabled": True, "extra_boards": {"Fixture": row["careers_url"]}}
        with patch.object(scan, "get", return_value=json.dumps({"companies": [{"name": "Fixture", "sourceUrl": row["careers_url"]}, {"name": "Other", "sourceUrl": "https://jobs.ashbyhq.com/other"}]})):
            result, _ = scan.collect_boards(profile, self.work)
        self.assertEqual({b["key"] for b in result}, {"ashby::other"})

    def test_explicit_secondary_israel_survives_us_primary(self):
        job = opportunity(location="Chicago, us | Tel Aviv, il", country_stated="US", countries_stated=["US", "IL"])
        self.assertEqual(scan.classify(job, self.profile)["location_scope"], "israel")

    def test_response_size_limit_fails_before_parsing_truncated_data(self):
        self.no_network.stop()
        with patch.object(scan.ur, "urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = b"x" * 12_000_001
            with self.assertRaisesRegex(ValueError, "incomplete"):
                scan.get("https://example.invalid/large.csv")

    def test_unresolved_history_is_not_new(self):
        job = opportunity()
        found = {"opportunities": [{**job, "history": {"decision": "unresolved", "newness_qualified": False}}]}
        self.assertEqual(records.history_decision(job, found, {"records": []})["state"], "unresolved")

    def test_supported_listed_alternative_scores_but_unlisted_alternative_does_not(self):
        row = {"requirement": "React or Angular", "met": False, "alternative_met": True, "alternative_evidence": "Angular evidence"}
        self.assertEqual(qualification.score_requirements([row])["supported"], 0)
        row["alternative_explicitly_accepted"] = True
        self.assertEqual(qualification.score_requirements([row])["supported"], 1)

    def test_render_keeps_fixed_canonical_run_bounds_and_recorded_count(self):
        run = {"id": "fixed", "window_start": "2026-11-25T19:00:00+02:00", "window_end": "2026-11-26T19:00:00+02:00", "requested_minimum": 10, "qualified_count": 7}
        records.save(self.work / "data/jobs.json", {"opportunities": [], "search_runs": [run]})
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        first = read_page(render.render(self.work))[1]
        second = read_page(render.render(self.work))[1]
        self.assertEqual(first["search_brief"]["window_start"], run["window_start"])
        self.assertEqual(second["search_brief"], first["search_brief"])
        self.assertEqual(first["selected_run"]["qualified_count"], 7)
        self.assertEqual(first["qualified_count"], 0)

    def test_large_synthetic_identity_batch_and_relevant_canonical_merge(self):
        rows = [{"id": f"source:{i}", "url": f"https://example.invalid/{i}", "board_key": "fixture", "description": ""} for i in range(2500)]
        aliases = [{**r, "id": "alias:" + r["id"]} for r in rows]
        self.assertEqual(len(adapters.deduplicate_discoveries(rows + aliases)), 2500)
        irrelevant = scan.normalize(board(), [gh_row(id=777, title="Finance Accountant", content="Accounting", absolute_url="https://job-boards.greenhouse.io/fixture-a/jobs/777")])[0]
        relevant = opportunity()
        with patch.object(scan, "collect_boards", return_value=([board()], [])), patch.object(scan, "fetch", return_value=[irrelevant, relevant]):
            run = scan.scan(self.work, network=True)
        self.assertEqual(len(records.load(run / "all_jobs.json")), 2)
        self.assertEqual(len(records.load(self.work / "data/jobs.json")["opportunities"]), 1)

    def test_changed_preferred_source_id_is_not_a_disappearance(self):
        old = {"id": "techmap:old", "company": "Fixture", "title": "Role", "board_key": "techmap::software"}
        current = {"id": "ats:new", "company": "Fixture", "title": "Role", "board_key": "ats::fixture", "source_aliases": [{"id": old["id"]}]}
        self.assertEqual(scan.history_changes([old], [current], [old["board_key"]]), [])


class OutcomeTests(OfflineCase):
    def test_recommendation_only_status_does_not_create_application_state(self):
        report = outcomes.build_report({"opportunities": [{"id": "x", "source": "A", "status": "excluded"}], "search_runs": []}, {"records": []})
        self.assertEqual(report["by_source"]["a"]["unknown_submission"], 0)
        self.assertEqual(report["identities"][0]["submission_states"], [])
        explicit = outcomes.build_report({"opportunities": [], "search_runs": []}, {"records": [{"id": "x", "source": "A", "submission_status": "unknown"}]})
        self.assertEqual(explicit["by_source"]["a"]["unknown_submission"], 1)

    def test_distinct_identity_multi_source_and_submission_states_remain_separate(self):
        first = {"id": "a:1", "source": "A", "source_url": "https://example.invalid/1", "status": "qualified_new", "full_description_read": True,
                 "application_packet": {"preparation_state": "prepared"}}
        second = {"id": "b:1", "source": "B", "source_url": first["source_url"], "history": {"reported_in_chat": True}}
        applied = {"id": "a:1", "submission_status": "user_reported_applied", "submission_events": [{"status": "uploaded", "at": "2026-11-20T10:00:00Z", "evidence": "Upload observed"}]}
        report = outcomes.build_report({"opportunities": [first, second], "search_runs": [{"id": "old", "qualified_count": 9}]}, {"records": [applied]})
        self.assertEqual(report["unique_discovered_identities"], 1)
        for source in ("a", "b"):
            metrics = report["by_source"][source]
            self.assertEqual(metrics["discoveries"], 1)
            self.assertEqual(metrics["saved_qualified_new"], 1)
            self.assertEqual(metrics["prepared"], 1)
            self.assertEqual(metrics["uploaded"], 1)
            self.assertEqual(metrics["user_reported_submitted"], 1)
            self.assertEqual(metrics["submitted_observed"], 0)
            self.assertEqual(metrics["receipt_observed"], 0)
        self.assertEqual(report["recorded_runs"][0]["qualified_count"], 9)

    def test_receipt_without_evidence_is_not_observed_and_report_never_changes_inputs(self):
        records.save(self.work / "data/jobs.json", {"opportunities": [{"id": "x", "source": "A"}], "search_runs": []})
        records.save(self.work / "data/applied_jobs.json", {"records": [{"id": "x", "submission": {"status": "receipt_observed"}}]})
        before = {p.name: p.read_bytes() for p in (self.work / "data").iterdir()}
        report = outcomes.write_report(self.work, self.work / "output/outcomes.md")
        self.assertEqual(report["by_source"]["a"]["receipt_observed"], 0)
        self.assertEqual(report["by_source"]["a"]["unverified_submission_claim"], 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.work / "data").iterdir()})


class PacketCommandTests(OfflineCase):
    def test_prepare_cli_emits_unsent_artifact_and_record_event_has_no_transport(self):
        import hashlib
        cv = self.work / "fixture.pdf"
        cv.write_bytes(b"synthetic local CV")
        records.save(self.work / "cv-manifest.json", {"versions": [{"language": "en", "roles": ["development"], "selection_status": "current", "path": cv.name, "sha256": hashlib.sha256(cv.read_bytes()).hexdigest()}]})
        job = opportunity()
        records.save(self.work / "data/jobs.json", {"opportunities": [job], "search_runs": []})
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        request = self.work / "request.json"
        records.save(request, {"opportunity_id": job["id"], "language": "en", "role": "development", "drafts": [{"text": "Fixture draft"}]})
        script = ROOT / "skills/workhunt-search/scripts/packets.py"
        output = self.work / "packet.json"
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(script), "prepare", str(self.work), "--input", str(request), "--output", str(output)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(records.load(output)["submission_state"], "not_sent")
        self.assertNotIn("application_packet", records.load(self.work / "data/jobs.json")["opportunities"][0])
        records.save(request, {"identity": {"id": job["id"]}, "event": {"status": "user_reported_submitted", "at": "2026-11-20T10:00:00Z", "evidence": "Synthetic user report"}})
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(script), "record-event", str(self.work), "--input", str(request)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(records.load(self.work / "data/applied_jobs.json")["records"][0]["submission"]["status"], "user_reported_submitted")


if __name__ == "__main__":
    unittest.main()
