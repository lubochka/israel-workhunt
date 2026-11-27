"""Real Git-inventory export checks for the reviewed public prompt boundary."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import export_release


class PublicPromptExportTests(unittest.TestCase):
    def test_project_diagnostics_and_filled_policy_are_private_but_empty_template_exports(self):
        path = self.stage("metadata.json", b"{}\n")
        for value in ({"project_scope": {"paid_client_work": True}}, {"nested": [{"stack_check": {"passed": True}}]},
                      {"search_brief": {"project_stack_policy": {"configured": True, "alternatives": [], "provenance": {"evidence": "Synthetic private adoption"}}}}):
            path.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, "Private observation diagnostics"):
                export_release.export(self.output, self.root)
            self.assertFalse(self.output.exists())
        empty = {"search_brief": {"project_stack_policy": {"configured": False, "alternatives": [], "provenance": {}}}}
        path.write_text(json.dumps(empty), encoding='utf-8')
        self.assertEqual(export_release.export(self.output, self.root), 1)

    def test_project_diagnostic_filename_is_rejected_even_without_json_payload(self):
        self.stage("angular-project-fixture.txt", b"Synthetic diagnostic only\n")
        with self.assertRaisesRegex(ValueError, "Private or unsupported export entry"):
            export_release.export(self.output, self.root)
        self.assertFalse(self.output.exists())
    def test_tracked_observation_diagnostic_artifacts_are_rejected_before_export(self):
        self.stage("observation-binding-fixture.json", b"{}\n")
        with self.assertRaisesRegex(ValueError, "Private or unsupported export entry"):
            export_release.export(self.output, self.root)
        self.assertFalse(self.output.exists())

    def test_renamed_nested_runtime_diagnostics_are_rejected_but_public_metadata_exports(self):
        path = self.stage("metadata.json", b"{}\n")
        for key in ("binding", "ignored_observation", "ignored_attempts", "other_observations"):
            value = {"nested": [{"payload": {key: {"synthetic_private_value": "fixture-only"}}}]}
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Private observation diagnostics"):
                export_release.export(self.output, self.root)
            self.assertFalse(self.output.exists())
        public = {"schema_version": 1, "versions": [], "public_route": "https://fixture.invalid/jobs"}
        path.write_text(json.dumps(public), encoding="utf-8")
        self.assertEqual(export_release.export(self.output, self.root), 1)
        self.assertEqual(json.loads((self.output / "metadata.json").read_text('utf-8')), public)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="workhunt-public-prompt-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        assert self.base.is_relative_to(Path(tempfile.gettempdir()).resolve())
        self.root = self.base / "repository"
        self.root.mkdir()
        subprocess.run(["git", "init", "-b", "fixture"], cwd=self.root, check=True, capture_output=True)
        self.output = self.base / "export"
        self.public = (ROOT / "workhunt_prompt.md").read_bytes()

    def stage(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        subprocess.run(["git", "add", "--", relative], cwd=self.root, check=True, capture_output=True)
        return path

    def test_reviewed_public_root_prompt_exports_exact_bytes_without_history(self):
        self.stage("workhunt_prompt.md", self.public)
        self.assertEqual(export_release.export(self.output, self.root), 1)
        self.assertEqual((self.output / "workhunt_prompt.md").read_bytes(), self.public)
        self.assertFalse((self.output / ".git").exists())

    def test_same_heading_and_marker_do_not_allow_personalized_or_unreviewed_root_content(self):
        changed = self.public + b"\nPrivate candidate override: Synthetic Person; use the completed personal preferences.\n"
        path = self.stage("workhunt_prompt.md", changed)
        with self.assertRaisesRegex(ValueError, "reviewed public variant"):
            export_release.export(self.output, self.root)
        self.assertFalse(self.output.exists())
        self.assertEqual(path.read_bytes(), changed)
        path.write_bytes(b"# Reusable Workhunt manual-search prompt\n\nCompleted private request.\n")
        with self.assertRaisesRegex(ValueError, "reviewed public variant"):
            export_release.export(self.output, self.root)
        self.assertFalse(self.output.exists())

    def test_nested_prompt_copy_is_rejected_even_when_public_bytes_are_identical(self):
        self.stage("nested/workhunt_prompt.md", self.public)
        with self.assertRaisesRegex(ValueError, "Private or unsupported export entry"):
            export_release.export(self.output, self.root)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
