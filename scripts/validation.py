#!/usr/bin/env python3
"""Record validated recipe provenance, check namcap, and poll the AUR index."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
FILES = ("PKGBUILD", ".SRCINFO", "xdg-cache.patch")
RPC = "https://aur.archlinux.org/rpc/v5/info?arg[]=mcmodding-mcp"


def hashes(root):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in FILES}


def package_version(root):
    info = (root / ".SRCINFO").read_text()
    values = {}
    for key in ("pkgbase", "pkgver", "pkgrel"):
        matches = re.findall(rf"(?m)^\s*{key} = (\S+)$", info)
        if len(matches) != 1:
            raise ValueError(f"Expected one {key} in .SRCINFO")
        values[key] = matches[0]
    if values["pkgbase"] != "mcmodding-mcp":
        raise ValueError("Unexpected pkgbase in .SRCINFO")
    epochs = re.findall(r"(?m)^\s*epoch = (\d+)$", info)
    if len(epochs) > 1:
        raise ValueError("Expected at most one epoch in .SRCINFO")
    prefix = epochs[0] + ":" if epochs else ""
    return prefix + values["pkgver"] + "-" + values["pkgrel"]


def check_metadata(root):
    generated = subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=root)
    if generated != (root / ".SRCINFO").read_bytes():
        raise ValueError("Stale .SRCINFO; regenerate it with makepkg --printsrcinfo")
    return package_version(root)


def create_manifest(root, destination):
    version = check_metadata(root)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    data = {"schema": 1, "source_commit": commit, "package_version": version, "files": hashes(root)}
    destination.write_text(json.dumps(data, indent=2) + "\n")


def verify_manifest(root, path, commit):
    data = json.loads(path.read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Expected a complete validated Git commit SHA")
    if data.get("schema") != 1 or data.get("source_commit") != commit:
        raise ValueError("Validation manifest does not match the validated commit")
    if data.get("files") != hashes(root):
        raise ValueError("Recipe files differ from the validated artifact")
    version = check_metadata(root)
    if data.get("package_version") != version:
        raise ValueError("Manifest package version does not match .SRCINFO")
    print(f"Verified validation artifact: {commit}, mcmodding-mcp {version}")


def check_namcap(path):
    report = path.read_text()
    errors = re.findall(r"(?m)^.+ E:.*$", report)
    warnings = re.findall(r"(?m)^.+ W:.*$", report)
    print(f"namcap: {len(errors)} errors, {len(warnings)} warnings")
    if errors:
        raise ValueError("namcap errors prevent publication:\n" + "\n".join(errors))


def poll_aur(expected, attempts=30, delay=10):
    reported = "unavailable"
    for attempt in range(1, attempts + 1):
        try:
            request = Request(RPC, headers={"User-Agent": "mcmodding-mcp-aur-publisher"})
            with urlopen(request, timeout=20) as response:
                data = json.load(response)
            rows = data.get("results", [])
            reported = rows[0]["Version"] if len(rows) == 1 and rows[0].get("Name") == "mcmodding-mcp" else "unavailable"
        except Exception as error:
            reported = f"error: {error}"
        print(f"AUR metadata check {attempt}/{attempts}: {reported}", flush=True)
        if reported == expected:
            return
        if attempt < attempts:
            time.sleep(delay)
    raise RuntimeError(
        f"AUR Git commit and recipe files were verified, but the RPC index still reports "
        f"{reported} instead of {expected} after {attempts} checks. "
        "The index may be delayed; retry verification on the next run."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-manifest")
    create.add_argument("path", type=Path)
    verify = commands.add_parser("verify-manifest")
    verify.add_argument("path", type=Path)
    verify.add_argument("--commit", required=True)
    namcap = commands.add_parser("namcap")
    namcap.add_argument("path", type=Path)
    commands.add_parser("metadata")
    commands.add_parser("version")
    rpc = commands.add_parser("poll-aur")
    rpc.add_argument("version")
    args = parser.parse_args()
    if args.command == "create-manifest":
        create_manifest(ROOT, args.path)
    elif args.command == "verify-manifest":
        verify_manifest(ROOT, args.path, args.commit)
    elif args.command == "namcap":
        check_namcap(args.path)
    elif args.command == "metadata":
        print(check_metadata(ROOT))
    elif args.command == "version":
        print(package_version(ROOT))
    elif args.command == "poll-aur":
        poll_aur(args.version)


if __name__ == "__main__":
    main()
