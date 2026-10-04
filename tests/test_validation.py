import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from helpers import recipe_fixture


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validation", REPO / "scripts/validation.py")
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        recipe_fixture(REPO, self.root)
        self.manifest = self.root / "manifest.json"
        self.commit = "a" * 40
        with patch.object(validation.subprocess, "check_output", side_effect=[(self.root / ".SRCINFO").read_bytes(), self.commit]):
            validation.create_manifest(self.root, self.manifest)

    def test_manifest_accepts_validated_files_and_rejects_modified_patch(self):
        validation.verify_manifest(self.root, self.manifest, self.commit)
        (self.root / "xdg-cache.patch").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "files differ"):
            validation.verify_manifest(self.root, self.manifest, self.commit)

    def test_manifest_rejects_different_commit_and_extra_files(self):
        with self.assertRaisesRegex(ValueError, "validated commit"):
            validation.verify_manifest(self.root, self.manifest, "b" * 40)
        data = json.loads(self.manifest.read_text())
        data["files"]["README.md"] = "bad"
        self.manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "files differ"):
            validation.verify_manifest(self.root, self.manifest, self.commit)

    def test_stale_metadata_is_rejected(self):
        (self.root / ".SRCINFO").write_text("stale\n")
        with self.assertRaisesRegex(ValueError, "Stale .SRCINFO"):
            validation.check_metadata(self.root)

    def test_package_version_preserves_epoch(self):
        info = self.root / ".SRCINFO"
        info.write_text(info.read_text().replace("\tpkgrel = 1", "\tpkgrel = 1\n\tepoch = 2"))
        self.assertEqual(validation.package_version(self.root), "2:0.5.0-1")

    def test_namcap_warnings_are_reported_but_errors_stop_publication(self):
        report = self.root / "namcap.log"
        report.write_text("mcmodding-mcp W: upstream warning\n")
        validation.check_namcap(report)
        report.write_text("mcmodding-mcp E: broken package\nPKGBUILD (mcmodding-mcp) E: broken recipe\n")
        with self.assertRaisesRegex(ValueError, "namcap errors"):
            validation.check_namcap(report)

    def test_rpc_transient_error_then_index_catches_up(self):
        stale = io.BytesIO(json.dumps({"results": [{"Name": "mcmodding-mcp", "Version": "0.4.0-1"}]}).encode())
        fresh = io.BytesIO(json.dumps({"results": [{"Name": "mcmodding-mcp", "Version": "0.5.0-1"}]}).encode())
        with patch.object(validation, "urlopen", side_effect=[OSError("network"), stale, fresh]), patch.object(validation.time, "sleep") as sleep:
            validation.poll_aur("0.5.0-1", attempts=3)
            self.assertEqual(sleep.call_count, 2)

    def test_rpc_delay_is_distinguished_from_git_publication_failure(self):
        with patch.object(validation, "urlopen", side_effect=OSError("offline")), patch.object(validation.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "Git commit and recipe files were verified"):
                validation.poll_aur("0.5.0-1", attempts=2)


if __name__ == "__main__":
    unittest.main()
