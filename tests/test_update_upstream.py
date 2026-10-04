import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from helpers import recipe_fixture


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("updater", REPO / "scripts/update-upstream.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
EMBEDDINGS = """/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */

import { pipeline, env } from '@xenova/transformers';
import type { DocumentChunk } from './chunker.js';

// Configure transformers.js for local execution
env.allowLocalModels = true;
env.allowRemoteModels = true;

"""


def archive_bytes(version="0.6.0", omit=None, overrides=None, extra=None):
    files = {
        "package.json": json.dumps({"name": "mcmodding-mcp", "version": version, "packageManager": "pnpm@10.30.0"}),
        "pnpm-lock.yaml": "lockfileVersion: '9.0'\npackages:\n" + "".join(f"  '{key}':\n    resolution: {{integrity: test}}\n" for key in updater.PINNED_PACKAGES),
        "src/index.ts": f"const server = new Server({{name: 'mcmodding-mcp', version: '{version}'}}, {{}});\n",
        "src/indexer/embeddings.ts": EMBEDDINGS,
        "LICENSE": "MIT",
        "tsconfig.json": "{}",
    }
    files.update(overrides or {})
    if omit:
        del files[omit]
    with io.BytesIO() as stream:
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for name, content in files.items():
                value = content.encode()
                member = tarfile.TarInfo(f"mcmodding-mcp-{version}/{name}")
                member.size = len(value)
                archive.addfile(member, io.BytesIO(value))
            if extra:
                member = tarfile.TarInfo(extra)
                member.size = 1
                archive.addfile(member, io.BytesIO(b"x"))
        return stream.getvalue()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        recipe_fixture(REPO, self.root)
        self.original = (self.root / "PKGBUILD").read_bytes()
        self.info = (self.root / ".SRCINFO").read_bytes()

    def unchanged(self):
        self.assertEqual((self.root / "PKGBUILD").read_bytes(), self.original)
        self.assertEqual((self.root / ".SRCINFO").read_bytes(), self.info)

    def downloaded_update(self, payload, check=False):
        def download(url, destination):
            self.assertEqual(url, updater.SOURCE.format("0.6.0"))
            destination.write_bytes(payload)
        with patch.object(updater, "release", return_value="0.6.0"), patch.object(updater, "download", side_effect=download):
            return updater.update(self.root, check=check)

    def test_new_release_updates_only_version_and_source_pins(self):
        payload = archive_bytes()
        self.assertTrue(self.downloaded_update(payload))
        candidate = (self.root / "PKGBUILD").read_text()
        self.assertEqual(updater.field(candidate, "pkgver"), "0.6.0")
        self.assertEqual(updater.field(candidate, "pkgrel"), "1")
        self.assertEqual(updater.source_checksum(candidate), hashlib.sha256(payload).hexdigest())
        self.assertNotEqual(updater.field(candidate, "_lockfile_sha256"), updater.field(self.original.decode(), "_lockfile_sha256"))
        # Ancillary sources, pnpm pin, and all three integrity checks survive the update.
        old_hashes = self.original.decode().split("sha256sums=(", 1)[1].split(")", 1)[0].splitlines()[1:]
        new_hashes = candidate.split("sha256sums=(", 1)[1].split(")", 1)[0].splitlines()[1:]
        self.assertEqual(old_hashes, new_hashes)
        generated = subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=self.root)
        self.assertEqual((self.root / ".SRCINFO").read_bytes(), generated)

    def test_check_mode_generates_metadata_without_writing(self):
        self.assertTrue(self.downloaded_update(archive_bytes(), check=True))
        self.unchanged()

    def test_same_or_older_release_preserves_pkgrel_and_rechecks_pins(self):
        recipe = self.original.decode().replace("pkgrel=1\n", "pkgrel=3\n")
        (self.root / "PKGBUILD").write_text(recipe)
        self.original = recipe.encode()
        pins = updater.source_checksum(recipe), updater.field(recipe, "_lockfile_sha256")
        for latest in ("0.5.0", "0.4.0"):
            with self.subTest(latest=latest), patch.object(updater, "release", side_effect=[latest, "0.5.0"]), patch.object(updater, "verify_source", return_value=pins) as verify:
                self.assertFalse(updater.update(self.root))
                verify.assert_called_once_with("0.5.0", recipe, self.root)
                self.unchanged()

    def test_same_version_changed_source_or_lock_is_rejected(self):
        recipe = self.original.decode()
        pins = updater.source_checksum(recipe), updater.field(recipe, "_lockfile_sha256")
        for changed in (("0" * 64, pins[1]), (pins[0], "0" * 64)):
            with self.subTest(changed=changed), patch.object(updater, "release", return_value="0.5.0"), patch.object(updater, "verify_source", return_value=changed):
                with self.assertRaisesRegex(ValueError, "Same-version"):
                    updater.update(self.root)
                self.unchanged()

    def test_download_failure_preserves_both_files(self):
        with patch.object(updater, "release", return_value="0.6.0"), patch.object(updater, "download", side_effect=OSError("network unavailable")):
            with self.assertRaises(OSError):
                updater.update(self.root)
        self.unchanged()

    def test_incompatible_source_preserves_both_files(self):
        cases = [
            (archive_bytes(omit="pnpm-lock.yaml"), "pnpm-lock"),
            (archive_bytes(overrides={"package.json": json.dumps({"name": "mcmodding-mcp", "version": "0.6.0", "packageManager": "pnpm@11.0.0"})}), "pnpm version"),
            (archive_bytes(overrides={"src/index.ts": "name: 'mcmodding-mcp', version: '0.4.5'"}), "server version"),
            (archive_bytes(overrides={"pnpm-lock.yaml": "lockfileVersion: '9.0'\npackages:\n"}), "dependency path"),
            (archive_bytes(extra="../outside"), "archive path"),
        ]
        for payload, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.downloaded_update(payload)
            self.unchanged()

    def test_patch_failure_preserves_both_files(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.downloaded_update(archive_bytes(overrides={"src/indexer/embeddings.ts": "incompatible upstream\n"}))
        self.unchanged()

    def test_metadata_failure_preserves_both_files(self):
        with patch.object(updater, "metadata", side_effect=subprocess.CalledProcessError(1, "makepkg")):
            with self.assertRaises(subprocess.CalledProcessError):
                self.downloaded_update(archive_bytes())
        self.unchanged()

    def test_second_file_write_failure_restores_both_files(self):
        real_write = Path.write_bytes
        failed = False
        def write(path, data):
            nonlocal failed
            if path == self.root / ".SRCINFO" and not failed:
                failed = True
                raise OSError("disk full")
            return real_write(path, data)
        with patch.object(Path, "write_bytes", new=write):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.downloaded_update(archive_bytes())
        self.unchanged()

    def test_releases_reject_prereleases_drafts_and_unexpected_tags(self):
        for value in ({"tag_name": "v0.6.0", "prerelease": True}, {"tag_name": "v0.6.0", "draft": True}, {"tag_name": "v0.6.0-rc1"}, {"tag_name": "../bad"}):
            with self.subTest(value=value), patch.object(updater, "urlopen", return_value=io.BytesIO(json.dumps(value).encode())):
                with self.assertRaises(ValueError):
                    updater.release()


if __name__ == "__main__":
    unittest.main()
