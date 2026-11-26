"""Regression reproductions for the six-defect audit; local fixtures only."""
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from test_kit import OfflineCase, opportunity, read_page
from test_sources import smart_board, smart_detail
from test_integration import installer
import adapters
import outcomes
import packets
import qualification
import records
import render
import scan


class PersistentSubmissionTests(OfflineCase):
    def test_renderer_displays_latest_event_only_record_and_keeps_applied_gate(self):
        job = opportunity()
        records.save(self.work / "data/jobs.json", {"opportunities": [job], "search_runs": []})
        records.save(self.work / "data/applied_jobs.json", {"records": [{"id": job["id"], "submission_events": [
            {"status": "uploaded", "at": "2026-11-24T10:00:00Z", "evidence": "Later supplementary upload"},
            {"status": "submitted_observed", "at": "2026-11-22T10:00:00Z", "evidence": "Earlier observed submission"}]}]})
        page = render.render(self.work)
        self.assertNotIn(b"\r\n", page.read_bytes())
        row = read_page(page)[1]["jobs"][0]
        self.assertEqual(row["application_state"], "uploaded")
        self.assertEqual(row["review"]["history_check"]["state"], "already_applied")

    def test_legacy_flat_status_snapshot_is_preserved_before_first_upload(self):
        for status in ("submitted_observed", "user_reported_submitted"):
            with self.subTest(status=status):
                original = {"id": "x", "status": status, "at": "2026-11-22T10:00:00Z", "evidence": "Historical supplied evidence"}
                records.save(self.work / "data/applied_jobs.json", {"records": [original]})
                packets.record_submission_event(self.work, {"id": "x"}, {"status": "uploaded", "at": "2026-11-24T10:00:00Z", "evidence": "Supplementary upload", "authorization": "Fixture authorization"})
                reloaded = records.load(self.work / "data/applied_jobs.json")
                self.assertEqual(records.history_decision({"id": "x"}, {}, reloaded)["state"], "already_applied")
                self.assertEqual(records.application_state(reloaded["records"][0]), "uploaded")
                with self.subTest(existing_log=True):
                    original["submission_events"] = [{"status": "uploaded", "at": "2026-11-24T10:00:00Z", "evidence": "Pre-existing supplementary upload"}]
                    self.assertTrue(records.application_evidence(original)["ever_applied"])
                    records.save(self.work / "data/applied_jobs.json", {"records": [original]})
                    packets.record_submission_event(self.work, {"id": "x"}, {"status": "uploaded", "at": "2026-11-25T10:00:00Z", "evidence": "Another upload", "authorization": "Fixture scope"})
                    saved = records.load(self.work / "data/applied_jobs.json")
                    self.assertEqual(records.history_decision({"id": "x"}, {}, saved)["state"], "already_applied")

    def submitted(self):
        return {"status": "submitted_observed", "at": "2026-11-22T10:00:00Z", "evidence": "Observed exact fixture submission", "authorization": "Fixture authorized application"}

    def test_earlier_and_later_uploads_never_clear_saved_submission(self):
        for uploaded_at, latest in [("2026-11-20T10:00:00Z", "submitted_observed"), ("2026-11-24T10:00:00Z", "uploaded")]:
            with self.subTest(uploaded_at=uploaded_at):
                records.save(self.work / "data/applied_jobs.json", {"records": [{"id": "x", "submission": self.submitted()}]})
                packets.record_submission_event(self.work, {"id": "x"}, {"status": "uploaded", "at": uploaded_at, "evidence": "Supplementary attachment upload", "authorization": "Fixture upload authorization"})
                reloaded = records.load(self.work / "data/applied_jobs.json")
                self.assertEqual(records.history_decision({"id": "x"}, {}, reloaded)["state"], "already_applied")
                self.assertEqual(records.application_state(reloaded["records"][0]), latest)

    def test_event_only_history_and_legacy_flat_snapshot_survive_reload(self):
        flat = {"id": "x", "submission_status": "submitted_observed", "submitted_at": "2026-11-22T10:00:00Z", "evidence": "Observed fixture receipt"}
        records.save(self.work / "data/applied_jobs.json", {"records": [flat]})
        packets.record_submission_event(self.work, {"id": "x"}, {"status": "uploaded", "at": "2026-11-24T10:00:00Z", "evidence": "Supplement", "authorization": "Fixture scope"})
        saved = records.load(self.work / "data/applied_jobs.json")
        self.assertEqual(records.history_decision({"id": "x"}, {}, saved)["state"], "already_applied")
        event_only = {"records": [{"id": "y", "submission_events": [self.submitted()]}]}
        self.assertEqual(records.history_decision({"id": "y"}, {}, event_only)["state"], "already_applied")

    def test_invalid_future_and_unsupported_events_do_not_establish_applied(self):
        for event in [{"status": "submitted_observed"}, {"status": "user_reported_submitted", "at": "2099-01-01T00:00:00Z", "evidence": "Future claim"}, {"status": "sent", "at": "2026-11-20T00:00:00Z", "evidence": "Unsupported state"}]:
            with self.subTest(event=event):
                row = {"id": "x", "submission_events": [event]}
                self.assertEqual(records.history_decision(row, {}, {"records": [row]})["state"], "new")


class AliasPersistenceTests(OfflineCase):
    def test_alias_suppression_survives_canonical_merge_and_reload_in_both_stores(self):
        for location in ("applied", "jobs"):
            with self.subTest(location=location):
                original = {"id": "A", "url": "https://fixture.invalid/A", "review": {"reason": "Keep assessment"}}
                counterpart = {"id": "B", "url": "https://other.invalid/B", "suppress_from_new_results": True, "review": {"reason": "Keep B assessment"}}
                found = {"opportunities": [original] + ([counterpart] if location == "jobs" else []), "search_runs": []}
                applied = {"records": [counterpart] if location == "applied" else []}
                incoming = {"id": "A", "url": original["url"], "description": "Full description", "source_aliases": [{"id": "B", "url": counterpart["url"], "aliases": ["older-B"]}]}
                self.assertEqual(records.history_decision(incoming, found, applied)["state"], "suppressed")
                merged = records.merge_discovery(found, [incoming], {"id": "fixture", "checked_at": "2026-11-26T12:00:00Z"})
                self.assertEqual(records.history_decision(merged["opportunities"][0], merged, applied)["state"], "suppressed")
                records.save(self.work / "merged.json", merged)
                reloaded = records.load(self.work / "merged.json")
                self.assertEqual(records.history_decision({"id": "older-B"}, reloaded, applied)["state"], "suppressed")
                self.assertEqual(reloaded["opportunities"][0]["review"], original["review"])
                if location == "jobs":
                    self.assertEqual(len(records.identity_groups(reloaded["opportunities"])), 1)
                    self.assertEqual(reloaded["opportunities"][1]["review"], counterpart["review"])


class IndependentReportFactsTests(OfflineCase):
    def test_reported_applied_and_suppressed_are_orthogonal(self):
        variants = [{"reported_at": "2026-11-22T10:00:00Z"}, {"history": {"reported_at": "2026-11-22T10:00:00Z"}}, {"history": {"reported_in_chat": True}}, {"history": {"previously_presented_in_chat": True}}, {"history": {"previous_report_time": "2026-11-22T10:00:00Z"}}, {"status": "previously_reported"}]
        for fields in variants:
            with self.subTest(fields=fields):
                row = {"id": "x", "source": "Fixture", "suppress_from_new_results": True, **fields}
                report = outcomes.build_report({"opportunities": [row]}, {"records": [{"id": "x", "submission_status": "user_reported_applied"}]})
                metrics = report["identities"][0]["metrics"]
                self.assertTrue(metrics["previously_reported"])
                self.assertTrue(metrics["suppressed"])
                self.assertTrue(metrics["user_reported_submitted"])

    def test_canonical_qualified_login_counts_but_generic_or_unevidenced_login_does_not(self):
        variants = [({"status": "login_required", "exact_vacancy_accepting_applications": True, "evidence": "Exact vacancy Apply leads to login"}, True),
                    ({"status": "login_required", "evidence": "Generic sign-in"}, False),
                    ({"status": "login_required", "exact_vacancy_accepting_applications": True}, False),
                    ({"status": "qualified_login", "evidence": "Historical exact vacancy acceptance"}, True),
                    ({"status": "qualified_login"}, False)]
        for route, expected in variants:
            with self.subTest(route=route):
                report = outcomes.build_report({"opportunities": [{"id": "x", "source": "Fixture", "route": route}]}, {"records": []})
                self.assertEqual(report["identities"][0]["metrics"]["route_evidence_recorded"], expected)

    def test_explicit_five_overrides_default_ten_without_moving_window(self):
        run = {"id": "explicit-five", "requested_minimum": 5, "window_start": "2026-11-25T20:00:00+02:00", "window_end": "2026-11-26T20:00:00+02:00", "qualified_count": 0}
        records.save(self.work / "data/jobs.json", {"opportunities": [], "search_runs": [run]})
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        result = read_page(render.render(self.work))[1]
        self.assertEqual(result["shortfall"], 5)
        self.assertEqual(result["search_brief"]["requested_minimum"], 5)
        self.assertEqual(result["search_brief"]["window_start"], run["window_start"])
        self.assertEqual(self.profile["search_brief"]["requested_minimum"], 10)


class ManifestOwnershipTests(OfflineCase):
    def git(self, *args):
        command = ["git", "-c", "core.hooksPath=" + str(self.work / "no-hooks"), "-c", "core.autocrlf=false", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args]
        result = subprocess.run(command, cwd=self.work, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_committing_local_customization_does_not_override_manifest_ownership(self):
        self.git("init")
        root = self.work / ".agents/skills"
        key = "fixture/SKILL.md"
        original = self.work / "canonical.md"
        original.write_bytes(b"Canonical source\n")
        package = ({key: b"Generated package\n"}, {key: original}, {"fixture": original.parent})
        with patch.object(installer, "package", return_value=package):
            installer.install(root, project=self.work, adopt_project=True)
            self.git("add", ".")
            self.git("commit", "-m", "Fixture initial install")
            target = root / key
            target.write_bytes(b"User customization\n")
            with self.assertRaisesRegex(ValueError, "locally modified"):
                installer.install(root, project=self.work, adopt_project=True)
            self.git("add", ".")
            self.git("commit", "-m", "Fixture committed customization")
            with self.assertRaisesRegex(ValueError, "locally modified"):
                installer.install(root, project=self.work, adopt_project=True)
            self.assertEqual(target.read_bytes(), b"User customization\n")


class MalformedDetailTests(OfflineCase):
    def test_mismatched_detail_cannot_supply_inactive_fact(self):
        replies = [json.dumps({"totalFound": 1, "offset": 0, "content": [{"id": "1", "active": True}]}), json.dumps(smart_detail("other", jobAd=[1], active=False))]
        with patch.object(scan, "get", side_effect=replies):
            result = scan.fetch(smart_board())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["job_id"], "1")
        self.assertIs(result[0]["active"], True)
        self.assertFalse(result[0]["description_complete"])
        self.assertTrue(result.errors)

    def test_bad_jobad_preserves_valid_peer_and_inactive_fact_as_partial(self):
        for malformed in ([{"unexpected": True}], "unexpected", 17, {"sections": []}, {"sections": {"jobDescription": "unexpected"}}):
            with self.subTest(jobAd=malformed):
                details = [smart_detail("1"), smart_detail("2", jobAd=malformed, active=False)]
                replies = [json.dumps({"totalFound": 2, "offset": 0, "content": [{"id": "1", "name": "First"}, {"id": "2", "name": "Second"}]}), *(json.dumps(v) for v in details)]
                with patch.object(scan, "get", side_effect=replies):
                    result = scan.fetch(smart_board())
                self.assertEqual(len(result), 2)
                self.assertTrue(result[0]["description_complete"])
                self.assertFalse(result[1]["description_complete"])
                self.assertIs(result[1]["active"], False)
                self.assertTrue(result.errors)
                self.assertIs(adapters.smart_normalize(smart_board(), [details[1]], scan.plain)[0]["active"], False)

    def test_bad_optional_structures_are_record_local_not_board_fatal(self):
        row = smart_detail("2", locations="bad", secondaryLocations=4, typeOfEmployment=["bad"], workplaceType=["bad"], active=False)
        row["jobAd"]["sections"]["additionalInformation"]["text"] = {"bad": "text"}
        with patch.object(scan, "get", side_effect=[json.dumps({"totalFound": 1, "offset": 0, "content": [{"id": "2"}]}), json.dumps(row)]):
            result = scan.fetch(smart_board())
        self.assertEqual(len(result), 1)
        self.assertIs(result[0]["active"], False)
        self.assertFalse(result[0]["description_complete"])
        self.assertTrue(result.errors)


class ManualPolicyBoundaryTests(OfflineCase):
    def test_private_manual_policy_does_not_extend_automated_window(self):
        profile = copy.deepcopy(self.profile)
        profile["search_brief"]["manual_source_freshness_hours"] = {"employer_registry": 48}
        profile["search_brief"]["manual_freshness_policy"] = {"evidence": "Synthetic explicit manual-only preference"}
        anchor = dt.datetime(2026, 11, 26, 12, tzinfo=dt.timezone.utc)
        brief = qualification.search_brief(profile, anchor, execution_context="collector")
        self.assertEqual(records.timestamp(brief["window_end"]) - records.timestamp(brief["window_start"]), dt.timedelta(hours=24))
        self.assertEqual(brief["manual_source_freshness_hours"], {"employer_registry": 48})
        saved = {"window_start": (anchor - dt.timedelta(hours=48)).isoformat(), "window_end": anchor.isoformat()}
        manual = qualification.search_brief(profile, anchor, saved)
        self.assertEqual(manual["source_windows"]["other"]["hours"], 48)
        collector = qualification.search_brief(profile, anchor, saved, execution_context="collector")
        self.assertEqual(collector["source_windows"]["other"]["hours"], 24)
        root = Path(__file__).resolve().parents[3]
        for path in [root / "templates/profile.template.json", root / "skills/workhunt-search/assets/profile.example.json", root / "skills/workhunt-configure-profile/assets/profile.template.json"]:
            shared = json.loads(path.read_text(encoding="utf-8"))["search_brief"]
            self.assertEqual(shared["manual_source_freshness_hours"], {})
            self.assertEqual(shared["manual_freshness_policy"], {})
            self.assertTrue({"source_windows", "window_start", "window_end"}.isdisjoint(shared))


if __name__ == "__main__":
    unittest.main()
