#!/usr/bin/env python3
"""Verify stable source releases and update the AUR recipe without relaxing its pins."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com/repos/OGMatrix/mcmodding-mcp/releases"
SOURCE = "https://codeload.github.com/OGMatrix/mcmodding-mcp/tar.gz/refs/tags/v{}"
PINNED_PACKAGES = (
    "better-sqlite3@12.10.0", "sharp@0.32.6", "onnxruntime-node@1.14.0",
    "@img/sharp-libvips-linux-x64@1.2.4", "protobufjs@6.11.4",
)


def field(contents, name):
    matches = re.findall(rf"(?m)^{re.escape(name)}=([^\n]+)$", contents)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {name} in PKGBUILD")
    return matches[0].strip().strip("'\"")


def replace(contents, name, value):
    updated, count = re.subn(
        rf"(?m)^{re.escape(name)}=[^\n]+$", lambda _: f"{name}={value}", contents
    )
    if count != 1:
        raise ValueError(f"Expected exactly one {name} in PKGBUILD")
    return updated


def release(suffix="/latest"):
    request = Request(API + suffix, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "mcmodding-mcp-aur-updater",
    })
    with urlopen(request, timeout=30) as response:
        data = json.load(response)
    tag = data.get("tag_name", "")
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("Upstream release is not stable")
    if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+)+", tag):
        raise ValueError(f"Unexpected upstream tag: {tag!r}")
    return tag[1:]


def download(url, destination):
    request = Request(url, headers={"User-Agent": "mcmodding-mcp-aur-updater"})
    with urlopen(request, timeout=90) as response, destination.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)


def source_checksum(contents):
    matches = re.findall(r"(?m)^sha256sums=\('([0-9a-f]{64})'", contents)
    if len(matches) != 1:
        raise ValueError("Expected the source archive as the first SHA-256 entry")
    return matches[0]


def inspect_source(archive_path, version, recipe, patch):
    prefix = f"mcmodding-mcp-{version}/"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != prefix[:-1]:
                raise ValueError(f"Unexpected archive path: {member.name!r}")

        def read(name):
            matches = [m for m in members if m.name == prefix + name]
            if len(matches) != 1 or not matches[0].isfile():
                raise ValueError(f"Expected one regular {name} in source archive")
            return archive.extractfile(matches[0]).read()

        package = json.loads(read("package.json"))
        lock = read("pnpm-lock.yaml")
        index = read("src/index.ts").decode()
        embeddings = read("src/indexer/embeddings.ts")
        read("LICENSE")
        read("tsconfig.json")
    if package.get("name") != "mcmodding-mcp":
        raise ValueError("Unexpected source package name")
    if package.get("packageManager") != "pnpm@" + field(recipe, "_pnpmver"):
        raise ValueError("Upstream pnpm version changed; review the recipe before publishing")
    versions = re.findall(
        r"name:\s*['\"]mcmodding-mcp['\"]\s*,\s*version:\s*['\"]([^'\"]+)['\"]", index
    )
    allowed = {version}
    if version == "0.5.0":
        allowed.add("0.4.5")  # The existing recipe repairs this known upstream metadata bug.
    if package.get("version") not in allowed or len(versions) != 1 or versions[0] not in allowed:
        raise ValueError("Upstream package/server version does not match the stable tag")
    lock_text = lock.decode()
    if not re.search(r"(?m)^lockfileVersion: ['\"]?9\.0['\"]?$", lock_text):
        raise ValueError("Unsupported pnpm lockfile format; review the recipe")
    for package_key in PINNED_PACKAGES:
        if not re.search(rf"(?m)^  ['\"]?{re.escape(package_key)}['\"]?:\s*$", lock_text):
            raise ValueError(f"Pinned dependency path changed: {package_key}; review the recipe")
    with tempfile.TemporaryDirectory(prefix="mcmodding-patch-check-") as temporary:
        directory = Path(temporary)
        target = directory / "src/indexer/embeddings.ts"
        target.parent.mkdir(parents=True)
        target.write_bytes(embeddings)
        subprocess.run([
            "patch", "--dry-run", "--batch", "--forward", "--fuzz=0", "-Np1",
            "-d", str(directory), "-i", str(patch.resolve()),
        ], check=True)
    return hashlib.sha256(lock).hexdigest()


def verify_source(version, recipe, root):
    expected_source = '${pkgname}-${pkgver}.tar.gz::' + SOURCE.format('${pkgver}')
    if expected_source not in recipe:
        raise ValueError("Source URL changed; review the updater before publishing")
    for required in ("--frozen-lockfile", "--verify-store-integrity", "_lockfile_sha256"):
        if required not in recipe:
            raise ValueError(f"Missing recipe integrity guard: {required}")
    with tempfile.TemporaryDirectory(prefix="mcmodding-upstream-") as temporary:
        path = Path(temporary) / f"mcmodding-mcp-{version}.tar.gz"
        download(SOURCE.format(version), path)
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        lock_checksum = inspect_source(path, version, recipe, root / "xdg-cache.patch")
    print(f"Verified v{version}: source={checksum}, lockfile={lock_checksum}")
    return checksum, lock_checksum


def metadata(recipe, root):
    # Generate metadata before touching either deliverable in the maintenance checkout.
    with tempfile.TemporaryDirectory(prefix="mcmodding-srcinfo-") as temporary:
        directory = Path(temporary)
        (directory / "PKGBUILD").write_text(recipe)
        (directory / "xdg-cache.patch").write_bytes((root / "xdg-cache.patch").read_bytes())
        return subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=directory)


def update(root=ROOT, check=False):
    recipe_path, info_path = root / "PKGBUILD", root / ".SRCINFO"
    original_bytes, original_info = recipe_path.read_bytes(), info_path.read_bytes()
    original = original_bytes.decode()
    current = field(original, "pkgver")
    latest = release()
    comparison = int(subprocess.check_output(["vercmp", latest, current], text=True).strip())
    version = latest if comparison > 0 else current
    if comparison < 0 and release(f"/tags/v{current}") != current:
        raise ValueError("Current version's stable release is missing")
    checksum, lock_checksum = verify_source(version, original, root)
    if comparison <= 0:
        if checksum != source_checksum(original) or lock_checksum != field(original, "_lockfile_sha256"):
            raise ValueError("Same-version source or lockfile changed; refusing to replace pinned checksums")
        print(f"No newer stable release: current {current}, upstream {latest}")
        return False
    updated = replace(original, "pkgver", version)
    updated = replace(updated, "pkgrel", "1")
    updated = replace(updated, "_lockfile_sha256", f"'{lock_checksum}'")
    updated, count = re.subn(
        r"(?m)^(sha256sums=\(')[0-9a-f]{64}(')",
        lambda match: match[1] + checksum + match[2], updated,
    )
    if count != 1:
        raise ValueError("Expected exactly one source checksum")
    updated = re.sub(
        r"(?m)^# The dependency graph is pinned by checksum: this is upstream v[^\n]+$",
        f"# The dependency graph is pinned by checksum: this is upstream v{version}'s", updated,
    )
    generated = metadata(updated, root)
    if check:
        print("".join(difflib.unified_diff(
            original.splitlines(keepends=True), updated.splitlines(keepends=True),
            fromfile="PKGBUILD", tofile="PKGBUILD (candidate)",
        )), end="")
        print(f"Check only: would update mcmodding-mcp to {version}-1")
        return True
    try:
        recipe_path.write_text(updated)
        info_path.write_bytes(generated)
    except BaseException:
        recipe_path.write_bytes(original_bytes)
        info_path.write_bytes(original_info)
        raise
    print(f"Updated mcmodding-mcp to {version}-1")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify and show candidate changes without writing files")
    update(check=parser.parse_args().check)
