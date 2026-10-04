"""Exercise real Git publication against disposable local GitHub and AUR remotes."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from helpers import recipe_fixture


REPO = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
PYTHON = shutil.which("python")
AUR_URL = "ssh://aur@aur.archlinux.org/mcmodding-mcp.git"
spec = importlib.util.spec_from_file_location("validation", REPO / "scripts/validation.py")
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


@unittest.skipIf(os.geteuid() == 0, "publication must run as an ordinary user")
class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.github = self.base / "github.git"
        self.aur = self.base / "aur.git"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        AUR_SSH_PRIVATE_KEY="test-only-key", AUR_USERNAME="tester",
                        AUR_EMAIL="tester@example.com", GIT_CONFIG_COUNT="1",
                        GIT_CONFIG_KEY_0=f"url.{self.aur}.insteadOf", GIT_CONFIG_VALUE_0=AUR_URL)
        recipe_fixture(REPO, self.root)
        shutil.copytree(REPO / "scripts", self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / ".gitignore").write_text("/validation-manifest.json\n")
        self.git(self.base, "init", "--bare", "-q", str(self.github))
        self.git(self.base, "init", "--bare", "-q", "--initial-branch=master", str(self.aur))
        self.init_repo(self.root, "main")
        self.git(self.root, "remote", "add", "origin", str(self.github))
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "initial")
        self.git(self.root, "push", "-q", "origin", "main")
        seed = self.base / "aur-seed"
        seed.mkdir()
        for name in validation.FILES:
            shutil.copy(self.root / name, seed / name)
        self.init_repo(seed, "master")
        self.git(seed, "add", ".")
        self.git(seed, "commit", "-qm", "initial")
        self.git(seed, "remote", "add", "origin", str(self.aur))
        self.git(seed, "push", "-q", "origin", "master")
        self.wrapper("ssh-keyscan", "#!/bin/sh\nprintf 'aur.archlinux.org ssh-ed25519 test-only-host-key\\n'\n")
        self.wrapper("ssh-keygen", "#!/bin/sh\nprintf '256 SHA256:RFzBCUItH9LZS0cKB5UE6ceAYhBD5C8GeOBip8Z11+4 test (ED25519)\\n'\n")
        self.wrapper("python", f'''#!/bin/sh
if [ "$1" = scripts/validation.py ] && [ "$2" = poll-aur ]; then
  echo "TEST RPC: $3"
  exit 0
fi
exec {PYTHON} "$@"
''')
        self.wrapper("git", f'''#!/bin/sh
if [ "$1" = -C ] && [ "$3" = push ] && [ "$TEST_FAIL_AUR_PUSH" = 1 ]; then
  echo "TEST AUR PUSH FAILURE" >&2
  exit 1
fi
exec {GIT} "$@"
''')
        self.env["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        self.manifest()

    def git(self, cwd, *args):
        result = subprocess.run([GIT, *args], cwd=cwd, env=self.env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout.strip()

    def init_repo(self, directory, branch):
        self.git(directory, "init", "-q", "-b", branch)
        self.git(directory, "config", "user.name", "Test")
        self.git(directory, "config", "user.email", "test@example.com")
        self.git(directory, "config", "commit.gpgsign", "false")

    def wrapper(self, name, contents):
        path = self.bin / name
        path.write_text(contents)
        path.chmod(0o755)

    def manifest(self):
        validation.create_manifest(self.root, self.root / "validation-manifest.json")
        self.env["VALIDATED_COMMIT"] = self.git(self.root, "rev-parse", "HEAD")

    def candidate(self):
        recipe = (self.root / "PKGBUILD").read_text().replace("pkgver=0.5.0\n", "pkgver=0.6.0\n")
        (self.root / "PKGBUILD").write_text(recipe)
        info = subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=self.root)
        (self.root / ".SRCINFO").write_bytes(info)
        self.manifest()

    def publish(self, **overrides):
        return subprocess.run(["bash", "scripts/publish-aur.sh"], cwd=self.root,
                              env=dict(self.env, **overrides), text=True, capture_output=True)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unchanged_recipe_produces_no_github_or_aur_commit(self):
        github_head = self.git(self.github, "rev-parse", "main")
        aur_head = self.git(self.aur, "rev-parse", "master")
        self.assert_ok(self.publish())
        self.assertEqual(self.git(self.github, "rev-parse", "main"), github_head)
        self.assertEqual(self.git(self.aur, "rev-parse", "master"), aur_head)

    def test_new_candidate_publishes_only_three_aur_files(self):
        self.candidate()
        self.assert_ok(self.publish())
        self.assertEqual(set(self.git(self.aur, "ls-tree", "--name-only", "master").splitlines()), set(validation.FILES))
        for name in validation.FILES:
            self.assertEqual(self.git(self.aur, "show", "master:" + name), (self.root / name).read_text().strip())

    def test_github_success_aur_failure_is_retried_without_second_github_commit(self):
        self.candidate()
        result = self.publish(TEST_FAIL_AUR_PUSH="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TEST AUR PUSH FAILURE", result.stderr)
        github_head = self.git(self.github, "rev-parse", "main")
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), github_head)
        self.manifest()  # Next validation runs against the now-current GitHub commit.
        self.assert_ok(self.publish())
        self.assertEqual(self.git(self.github, "rev-parse", "main"), github_head)
        self.assertIn("pkgver = 0.6.0", self.git(self.aur, "show", "master:.SRCINFO"))

    def test_remote_main_moving_after_validation_blocks_publication(self):
        other = self.base / "other"
        self.git(self.base, "clone", "-q", "--branch", "main", str(self.github), str(other))
        self.git(other, "config", "user.name", "Test")
        self.git(other, "config", "user.email", "test@example.com")
        self.git(other, "config", "commit.gpgsign", "false")
        self.git(other, "commit", "-qm", "concurrent update", "--allow-empty")
        self.git(other, "push", "-q", "origin", "main")
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("main moved since validation", result.stderr)

    def test_aur_newer_version_is_not_overwritten(self):
        seed = self.base / "aur-seed"
        recipe = (seed / "PKGBUILD").read_text().replace("pkgver=0.5.0\n", "pkgver=0.9.0\n")
        (seed / "PKGBUILD").write_text(recipe)
        (seed / ".SRCINFO").write_bytes(subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=seed))
        self.git(seed, "add", ".")
        self.git(seed, "commit", "-qm", "newer version")
        self.git(seed, "push", "-q", "origin", "master")
        expected = self.git(self.aur, "rev-parse", "master")
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AUR already has newer version", result.stderr)
        self.assertEqual(self.git(self.aur, "rev-parse", "master"), expected)

    def test_missing_settings_are_explained(self):
        for name in ("AUR_SSH_PRIVATE_KEY", "AUR_USERNAME", "AUR_EMAIL", "VALIDATED_COMMIT"):
            with self.subTest(name=name):
                result = self.publish(**{name: ""})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr)

    def test_modified_artifact_and_stale_metadata_are_rejected(self):
        (self.root / "xdg-cache.patch").write_text("tampered\n")
        result = self.publish()
        self.assertIn("files differ", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        shutil.copy(REPO / "xdg-cache.patch", self.root / "xdg-cache.patch")
        (self.root / ".SRCINFO").write_text("stale\n")
        result = subprocess.run([PYTHON, str(self.root / "scripts/validation.py"), "metadata"], cwd=self.root, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Stale .SRCINFO", result.stderr)

    def test_sync_rejects_wrong_remote_and_dirty_checkout(self):
        seed = self.base / "aur-seed"
        result = subprocess.run(["bash", str(self.root / "scripts/sync-aur.sh"), str(seed)], env=self.env, text=True, capture_output=True)
        self.assertIn("Unexpected AUR origin", result.stderr)
        self.git(seed, "remote", "set-url", "origin", AUR_URL)
        (seed / "untracked").write_text("keep me")
        result = subprocess.run(["bash", str(self.root / "scripts/sync-aur.sh"), str(seed)], env=self.env, text=True, capture_output=True)
        self.assertIn("uncommitted changes", result.stderr)
        self.assertEqual((seed / "untracked").read_text(), "keep me")


if __name__ == "__main__":
    unittest.main()
