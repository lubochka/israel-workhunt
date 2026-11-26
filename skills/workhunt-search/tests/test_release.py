"""Release-specific offline invariants. Synthetic CV text exists only in temporary storage."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from test_kit import OfflineCase, ReviewTests, synthetic_profile, board, gh_row
import scan
import render
import records
import qualification
import profile_config
import source_registry

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


setup = module("configure_profile", ROOT / "skills/workhunt-configure-profile/scripts/configure_profile.py")
refresh = module("refresh_references", ROOT / "tools/refresh_workhunt_references.py")
installer = module("install_skills", ROOT / "tools/install_workhunt_skills.py")
exporter = module("export_release", ROOT / "tools/export_release.py")


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob("*") if p.is_file()}


class ReleaseConfigurationTests(OfflineCase):
    def test_unconfigured_empty_and_match_all_rejected_before_network_or_output(self):
        variants = [json.loads((ROOT / "templates/profile.template.json").read_text())]
        for field in ("title", "stack_all"):
            for pattern in ("", ".*", ".+", "^.*$", "\\b", "\\w+", "developer|"):
                profile = synthetic_profile()
                profile["tracks"]["development"][field] = [pattern] if field == "stack_all" else pattern
                variants.append(profile)
        for location in ("", ".*", ".+", "\\w+"):
            profile = synthetic_profile(); profile["location_pattern"] = location; variants.append(profile)
        for key, value in [("stack_all", []), ("title", None)]:
            profile = synthetic_profile(); profile["tracks"]["development"][key] = value; variants.append(profile)
        profile = synthetic_profile(); profile["search_brief"]["tracks"] = []; variants.append(profile)
        profile = synthetic_profile(); profile["eligible_countries"] = []; variants.append(profile)
        with patch.object(scan, "get", side_effect=AssertionError("No network")) as network, patch.object(socket, "create_connection", side_effect=AssertionError("No sockets")):
            for value in variants:
                scan.save(self.work / "profile.json", value)
                with self.subTest(profile=value), self.assertRaisesRegex(ValueError, "Configure .workhunt/profile.json"):
                    scan.scan(self.work, network=True)
            network.assert_not_called()
        self.assertFalse((self.work / "runs").exists())

    def test_missing_private_profile_does_not_read_root_legacy_profile(self):
        (self.work / "profile.json").unlink()
        scan.save(self.work.parent / "profile.json", synthetic_profile())
        with self.assertRaisesRegex(ValueError, "private profile is missing"):
            scan.scan(self.work.parent, network=True)

    def test_two_explicit_profiles_control_capability_country_timezone_and_output(self):
        before = hashes(ROOT / "templates")
        item_a = gh_row()
        item_b = gh_row(id=222, absolute_url="https://job-boards.greenhouse.io/fixture-a/jobs/222", title="Python Data Engineer", location={"name": "Toronto, Canada"}, content="Python PostgreSQL data pipelines")
        path = self.work / "fixtures.json"
        scan.save(path, {"boards": [{"board": board(), "jobs": [item_a, item_b]}]})
        first = scan.scan(self.work.parent, fixtures=path)
        self.assertEqual([j["job_id"] for j in scan.load(first / "hits.json")], ["123456"])
        second_profile = synthetic_profile()
        second_profile.update(name="Second Synthetic Candidate", timezone="America/Toronto", eligible_countries=["CA", "Canada"], location_pattern="Canada|Toronto", tracks={"data": {"label": "Data", "title": "Data Engineer", "stack_all": ["Python", "PostgreSQL"]}}, limited_experience={}, matching_aliases=[], project_employment_pattern="")
        second_profile["search_brief"] = {"tracks": ["data"], "required_stack": ["python", "postgresql"], "requested_minimum": None}
        scan.save(self.work / "profile.json", second_profile)
        second = scan.scan(self.work.parent, fixtures=path)
        self.assertEqual([j["job_id"] for j in scan.load(second / "hits.json")], ["222"])
        jobs = {j["job_id"]: j for j in scan.load(second / "all_jobs.json")}
        self.assertEqual(jobs["222"]["location_scope"], "configured_geography")
        self.assertEqual(jobs["123456"]["location_scope"], "needs_location_check")
        self.assertEqual(scan.load(second / "meta.json")["timezone"], "America/Toronto")
        output = render.render(self.work.parent, second, fixture=True)
        self.assertTrue(output.is_relative_to(self.work))
        self.assertEqual(before, hashes(ROOT / "templates"))

    def test_private_paths_cannot_write_health_or_rendered_data_into_shared_tree(self):
        with self.assertRaisesRegex(ValueError, "inside .workhunt"):
            source_registry.record_source_checks(self.work.parent, {"source_health": "../leak.json"}, [], "2026-11-26T10:00:00Z")
        with self.assertRaisesRegex(ValueError, "inside .workhunt"):
            render.render(self.work.parent, output=self.work.parent / "leak.html")
        self.assertFalse((self.work.parent / "leak.json").exists())
        self.assertFalse((self.work.parent / "leak.html").exists())

    def test_sources_are_disabled_in_empty_shared_template(self):
        profile = json.loads((ROOT / "templates/profile.template.json").read_text())
        self.assertFalse(any(profile[k] for k in ("directory_enabled", "employer_registry_enabled", "techmap_enabled")))
        self.assertEqual(profile["extra_boards"], {})


class DegreePolicyTests(ReviewTests):
    def test_explicit_experience_alternative_policy_is_applied(self):
        review = copy.deepcopy(self.good)
        review["degree_status"] = "experience_equivalent"
        self.profile["degree_policy"]["accept_experience_alternative"] = False
        self.assertFalse(self.evaluate(review)["checks"]["education"])
        self.profile["degree_policy"]["accept_experience_alternative"] = True
        self.assertTrue(self.evaluate(review)["checks"]["education"])

    def test_completed_matching_degree_can_pass_but_unfinished_studies_cannot(self):
        review = copy.deepcopy(self.good)
        review.update(degree_status="mandatory_met", degree_qualification="fixture-degree", degree_evidence="Explicit qualifying degree requirement")
        self.profile["degree_policy"]["accepted_qualifications"] = ["fixture-degree"]
        self.profile["education"] = [{"id": "fixture-degree", "completed": False, "evidence_ids": ["cv-education"]}]
        self.assertFalse(self.evaluate(review)["checks"]["education"])
        self.profile["education"][0]["completed"] = True
        self.assertTrue(self.evaluate(review)["qualified"])
        self.profile["degree_policy"]["accepted_qualifications"] = ["different-degree"]
        self.assertFalse(self.evaluate(review)["checks"]["education"])


class ProfileMappingTests(unittest.TestCase):
    def test_synthetic_cv_mapping_preserves_provenance_overlap_studies_and_conflict(self):
        before = hashes(ROOT / "templates")
        with tempfile.TemporaryDirectory(prefix="workhunt-profile-synthetic-") as folder:
            workspace = Path(folder)
            # This CV-like text is a synthetic test input, not a released CV artifact.
            cv = workspace / "synthetic-source.txt"
            cv.write_text("Synthetic Example\nA: 2020-01-01 to 2022-01-01\nB: 2021-01-01 to 2023-01-01\nStudies: degree unfinished\nPython mentioned; duration unspecified\nC: start 2018 in one section, 2019 in another\n", encoding="utf-8")
            source = {"id": "synthetic-cv", "kind": "cv", "path": str(cv)}
            def fact(ident, line, target, value, **extra):
                return {"id": ident, "kind": "cv_fact", "source_id": source["id"], "locator": "line " + str(line), "target": target, "value": value, **extra}
            ledger = {"sources": [source], "facts": [
                fact("name", 1, "name", "Synthetic Example"),
                fact("job-a", 2, "experience", {"employer": "A", "start": "2020-01-01", "end": "2022-01-01", "date_precision": "day"}),
                fact("job-b", 3, "experience", {"employer": "B", "start": "2021-01-01", "end": "2023-01-01", "date_precision": "day"}),
                fact("education", 4, "education", {"qualification": "degree studies", "completed": False}),
                fact("skill", 5, "capabilities", {"name": "Python"}),
                fact("conflicting-job", 6, "experience", {"employer": "C", "start": "2018", "other_start": "2019"}, conflict_ids=["date-conflict"])],
                "conflicts": [{"id": "date-conflict", "fact_ids": ["conflicting-job"], "status": "unresolved", "claims": ["2018", "2019"], "locator": "line 6"}],
                "unknowns": [{"field": "capabilities.Python.duration_years", "reason": "not stated"}, {"field": "search preferences", "reason": "no user instruction"}], "decisions": []}
            setup.initialize(workspace)
            records.save(workspace / ".workhunt/data/jobs.json", {"opportunities": [{"id": "history-sentinel"}]})
            history_before = (workspace / ".workhunt/data/jobs.json").read_bytes()
            with patch.object(socket, "create_connection", side_effect=AssertionError("No network during setup")):
                root = setup.populate(workspace, ledger)
            self.assertEqual((root / "data/jobs.json").read_bytes(), history_before)
            profile = json.loads((root / "profile.json").read_text())
            evidence = json.loads((root / "profile-evidence.json").read_text())
            self.assertEqual(evidence["tenure_calculation"]["supported_non_overlapping_days"], 1096)
            self.assertEqual(len(profile["experience"]), 2)
            self.assertEqual(evidence["conflicts"], ledger["conflicts"])
            self.assertFalse(profile["education"][0]["completed"])
            self.assertIsNone(profile["capabilities"][0]["duration_years"])
            self.assertEqual(profile["capabilities"][0]["evidence_ids"], ["skill"])
            self.assertFalse(profile["configured"])
            self.assertEqual(profile["tracks"], {})
            self.assertEqual(profile["eligible_countries"], [])
            self.assertIsNone(profile["timezone"])
            self.assertIsNone(profile["preferences"]["availability"])
            self.assertTrue((root / "professional-summary.md").is_file())
            summary = (root / "professional-summary.md").read_text(encoding="utf-8")
            self.assertIn("Target role: Unknown; no explicit role preference supplied", summary)
            self.assertIn("1,096 days; overlapping intervals counted once", summary)
            self.assertIn("partial tenure total", summary)
            self.assertIn("degree studies; not completed", summary)
            self.assertIn("date-conflict", summary)
            self.assertIn(str(cv), summary)
            self.assertNotIn("{{", summary)
            saved = hashes(root)
            with self.assertRaisesRegex(ValueError, "reviewed update"):
                setup.populate(workspace, ledger)
            self.assertEqual(saved, hashes(root))
        self.assertEqual(before, hashes(ROOT / "templates"))

    def test_summary_uses_template_layout_without_turning_headline_into_desired_role(self):
        ledger = {"sources": [{"id": "cv"}], "facts": [
            {"id": "headline", "source_id": "cv", "locator": "line 1", "kind": "cv_fact", "target": "headline", "value": "Historical role, not a preference"}], "decisions": []}
        profile, evidence = setup.map_ledger(ledger)
        original = (setup.PACKAGE / "assets/professional-summary.template.md").read_bytes()
        with tempfile.TemporaryDirectory(prefix="workhunt-summary-template-") as folder:
            package = Path(folder)
            (package / "assets").mkdir()
            template = package / "assets/professional-summary.template.md"
            template.write_bytes(b"Template layout sentinel\n" + original)
            before = template.read_bytes()
            with patch.object(setup, "PACKAGE", package):
                summary = setup.render_summary(profile, evidence)
            self.assertTrue(summary.startswith("Template layout sentinel\n"))
            self.assertIn("Target role: Unknown; no explicit role preference supplied", summary)
            self.assertNotIn("Target role: Historical role", summary)
            self.assertEqual(template.read_bytes(), before)
        self.assertEqual((setup.PACKAGE / "assets/professional-summary.template.md").read_bytes(), original)

    def test_preferences_cannot_be_inferred_from_cv_facts(self):
        ledger = {"sources": [{"id": "cv"}], "facts": [{"id": "x", "source_id": "cv", "locator": "page 1", "kind": "cv_fact", "target": "eligible_countries", "value": ["CA"]}]}
        with self.assertRaisesRegex(ValueError, "cannot set search preferences"):
            setup.map_ledger(ledger)
        with self.assertRaisesRegex(ValueError, "Exact tenure"):
            setup.non_overlapping_days([("2020", "2021")])


class PlacementTests(unittest.TestCase):
    def test_export_rejects_private_legacy_fixture_and_generator_even_if_tracked(self):
        with tempfile.TemporaryDirectory(prefix="workhunt-export-guard-") as folder:
            for rel in ("skills/workhunt-search/tests/fixtures/legacy-collector-5f723c0.json",
                        ".agents/skills/workhunt-search/tests/fixtures/legacy-collector-5f723c0.json",
                        "tools/generate_legacy_brief_fixture.py"):
                with self.subTest(path=rel), patch.object(exporter.subprocess, "run") as command:
                    command.return_value.stdout = rel.encode("utf-8") + b"\0"
                    with self.assertRaisesRegex(ValueError, "Private or unsupported export entry"):
                        exporter.inventory(Path(folder))

    def test_refresh_ignores_private_state_and_keeps_empty_templates(self):
        with tempfile.TemporaryDirectory(prefix="workhunt-refresh-") as folder:
            clone = Path(folder) / "release"
            shutil.copytree(ROOT, clone, ignore=shutil.ignore_patterns(".git", "__pycache__", ".workhunt"))
            private = clone / ".workhunt"
            private.mkdir()
            (private / "profile.json").write_text(json.dumps({"configured": True, "name": "Private sentinel"}))
            (clone / "profile.json").write_text("Legacy private sentinel")
            before = hashes(private), hashes(clone / "templates")
            refresh.refresh(clone)
            refresh.refresh(clone, check=True)
            self.assertEqual(before, (hashes(private), hashes(clone / "templates")))
            self.assertFalse((clone / "data").exists())
            self.assertEqual(json.loads((clone / "skills/workhunt-search/assets/profile.example.json").read_text())["name"], "")
            expected, _, _ = installer.package(clone)
            for provider in refresh.PROVIDERS:
                for key, data in expected.items():
                    self.assertEqual(data, (clone / provider / "skills" / key).read_bytes())

    def test_explicit_isolated_install_preserves_unrelated_and_rejects_modified_files(self):
        with tempfile.TemporaryDirectory(prefix="workhunt-install-") as folder:
            home = Path(folder)
            for suffix in (".agents/skills", ".claude/skills", ".kiro/skills", ".gemini/config/skills"):
                root = home / suffix
                root.mkdir(parents=True)
                unrelated = root / "unrelated.txt"; unrelated.write_text("keep")
                result = installer.install(root)
                self.assertEqual(result["skills"], 17)
                installer.install(root, check=True)
                self.assertEqual(unrelated.read_text(), "keep")
                path = root / "workhunt-configure-profile/SKILL.md"
                path.write_text("Local modification")
                with self.assertRaisesRegex(ValueError, "locally modified"):
                    installer.install(root)
                self.assertEqual(path.read_text(), "Local modification")


if __name__ == "__main__":
    unittest.main()
