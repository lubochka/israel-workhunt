"""Offline boundary checks for installed setup, private manifests and artifact writes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_kit import OfflineCase, opportunity
from test_release import setup, installer, refresh, ROOT, hashes, module
import packets
import profile_config
import qualification
import records
import outcomes


class ManifestTests(OfflineCase):
    def test_measured_unknown_cv_and_custom_manifest_feed_selection_without_claiming_review(self):
        workspace = self.work / "new workspace with spaces"
        cv = self.work / "explicit synthetic CV.txt"
        cv.write_text("Historical software role. Qualification incomplete. Dates unresolved.", encoding="utf-8")
        before = hashes(ROOT / "templates")
        root = setup.initialize(workspace, shared=ROOT)
        ledger = {"sources": [{"id": "cv", "path": str(cv)}], "facts": [], "decisions": []}
        setup.populate(workspace, ledger, selected_cv=cv, shared=ROOT)
        profile = records.load(root / "profile.json")
        manifest = records.load(root / profile["cv_manifest"])
        first = manifest["versions"][0]
        self.assertEqual(first["sha256"], hashlib.sha256(cv.read_bytes()).hexdigest())
        self.assertEqual(first["path"], str(cv.resolve()))
        self.assertEqual(first["selection_status"], "unresolved")
        self.assertEqual(first["content_review"]["status"], "not_reviewed")
        self.assertFalse(profile["configured"])
        self.assertEqual(profile["tracks"], {})
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            packets.select_cv(workspace, "en", "development")
        # Confirmed role mapping is separate from an inferred desired search role.
        profile["cv_manifest"] = "cv/versions.json"
        records.save(root / "profile.json", profile)
        records.save(root / profile["cv_manifest"], manifest)
        version = setup.register_cv(workspace, cv, language="en", roles=["development"], selection_evidence="Synthetic explicit mapping")
        selected = packets.select_cv(workspace, "en", "development")
        self.assertEqual(selected["version_id"], version["version_id"])
        self.assertEqual(selected["file_status"], "hash_matches")
        self.assertFalse(selected["ready_to_attach"])
        self.assertFalse(selected["content_reviewed"])
        cv.write_text("Changed synthetic CV", encoding="utf-8")
        self.assertEqual(packets.select_cv(workspace, "en", "development")["file_status"], "changed_since_manifest")
        setup.register_cv(workspace, cv, language="en", roles=["development"], selection_evidence="Second explicit selection")
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            packets.select_cv(workspace, "en", "development")
        self.assertEqual(len(records.load(root / profile["cv_manifest"])["versions"]), 3)
        self.assertEqual(before, hashes(ROOT / "templates"))

    def test_manifest_collision_and_invalid_schema_preserve_every_input(self):
        cv = self.work / "cv.txt"; cv.write_text("Synthetic", encoding="utf-8")
        for pointer, value in [("data/jobs.json", {"opportunities": []}), ("reviews.json", []), ("profile-evidence.json", {}), ("custom.json", {"versions": {}})]:
            profile = {**self.profile, "cv_manifest": pointer}
            records.save(self.work / "profile.json", profile)
            records.save(self.work / pointer, value)
            before = hashes(self.work)
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                setup.register_cv(self.work, cv)
            self.assertEqual(before, hashes(self.work))

    def test_missing_cv_is_not_ready_and_review_requires_exact_content_evidence(self):
        cv = self.work / "cv.txt"; cv.write_text("Synthetic", encoding="utf-8")
        mapping = {"language": "en", "roles": ["development"], "selection_evidence": "Explicit fixture selection"}
        with self.assertRaisesRegex(ValueError, "exact measured"):
            setup.register_cv(self.work, cv, **mapping, content_review={"status": "reviewed", "evidence": "Claim", "sha256": "wrong"})
        setup.register_cv(self.work, cv, **mapping)
        cv.unlink()
        self.assertEqual(packets.select_cv(self.work, "en", "development")["file_status"], "unavailable")


class DeliveryBoundaryTests(OfflineCase):
    def test_outcome_outputs_preflight_both_paths_and_keep_legacy_inputs(self):
        records.save(self.work / "data/jobs.json", {"opportunities": [], "search_runs": []})
        records.save(self.work / "data/applied_jobs.json", {"records": []})
        output = self.work / "reports/new.md"
        legacy = self.work / "reviews.json"
        records.save(legacy, {"sentinel": True})
        before = legacy.read_bytes()
        with self.assertRaisesRegex(ValueError, "canonical"):
            outcomes.write_report(self.work, output, legacy)
        self.assertFalse(output.exists())
        self.assertEqual(legacy.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "inside .workhunt"):
            outcomes.write_report(self.work, self.work.parent / "outside.md")

    def test_saved_authorization_fields_do_not_authorize_actions(self):
        profile = {**self.profile, "authorized_methods": ["send"], "authorized_actions": ["apply"]}
        profile["search_brief"] = {**profile["search_brief"], "authorized_methods": ["send"], "authorized_actions": ["apply"]}
        import datetime as dt
        brief = qualification.search_brief(profile, dt.datetime.now(dt.timezone.utc))
        self.assertEqual(brief["authorized_methods"], [])
        self.assertEqual(brief["authorized_actions"], [])

    def test_packet_save_canonical_is_explicit_and_canonical_output_is_refused(self):
        cv = self.work / "cv.txt"; cv.write_text("Synthetic", encoding="utf-8")
        setup.register_cv(self.work, cv, language="en", roles=["development"], selection_evidence="Synthetic selection")
        job = opportunity()
        canonical = self.work / "data/jobs.json"
        records.save(canonical, {"opportunities": [job], "search_runs": []})
        request = self.work / "request.json"
        records.save(request, {"opportunity_id": job["id"], "language": "en", "role": "development"})
        command = [sys.executable, "-B", str(ROOT / "skills/workhunt-search/scripts/packets.py"), "prepare", str(self.work), "--input", str(request), "--save-canonical", "--output"]
        before = canonical.read_bytes()
        failed = subprocess.run(command + [str(canonical)], capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(canonical.read_bytes(), before)
        passed = subprocess.run(command + [str(self.work / "packets/draft.json")], capture_output=True)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        saved = records.load(canonical)["opportunities"][0]["application_packet"]
        self.assertEqual(saved["submission_state"], "not_sent")


class PortablePackagingTests(unittest.TestCase):
    def test_installed_setup_first_run_without_profile_and_unbound_distribution(self):
        files, _, sources = installer.package()
        self.assertEqual(len(sources), 17)
        for key, value in files.items():
            if key.endswith("workspace.json"):
                self.assertIsNone(json.loads(value)["workspace"])
        with tempfile.TemporaryDirectory(prefix="workhunt-installed-first-") as folder:
            home = Path(folder) / "home with spaces"
            dest = home / ".agents/skills"
            installer.install(dest)
            workspace = Path(folder) / "private workspace with spaces"
            script = dest / "workhunt-configure-profile/scripts/configure_profile.py"
            result = subprocess.run([sys.executable, "-B", str(script), str(workspace), "--shared-workspace", str(ROOT), "--initialize"], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(records.load(workspace / ".workhunt/profile.json")["configured"])
            self.assertEqual(records.load(workspace / ".workhunt/cv-manifest.json")["versions"], [])
            manifest = (dest / ".workhunt-install.json").read_text("utf-8")
            self.assertNotIn(str(ROOT), manifest)

    def test_whole_install_preflight_preserves_earlier_provider_when_later_conflicts(self):
        with tempfile.TemporaryDirectory(prefix="workhunt-preflight-") as folder:
            home = Path(folder)
            conflict = home / ".kiro/skills/workhunt-cv/SKILL.md"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("Unowned local file", encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/install_workhunt_skills.py"), "--home", str(home)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((home / ".agents").exists())
            self.assertEqual(conflict.read_text("utf-8"), "Unowned local file")


if __name__ == "__main__":
    unittest.main()
