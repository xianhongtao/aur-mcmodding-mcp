"""Recipe fixtures stay at their own baseline when the real package is upgraded."""
from pathlib import Path
import re
import shutil
import subprocess


def recipe_fixture(source, destination):
    destination = Path(destination)
    text = (source / "PKGBUILD").read_text()
    text = re.sub(r"(?m)^pkgver=.*$", "pkgver=0.5.0", text)
    text = re.sub(r"(?m)^pkgrel=.*$", "pkgrel=1", text)
    (destination / "PKGBUILD").write_text(text)
    shutil.copy(source / "xdg-cache.patch", destination / "xdg-cache.patch")
    (destination / ".SRCINFO").write_bytes(
        subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=destination)
    )
