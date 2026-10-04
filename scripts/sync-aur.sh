#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/mcmodding-mcp-aur-checkout" >&2
  exit 2
fi
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
aur_dir=$(realpath "$1")
if [[ ! -d "$aur_dir/.git" ]]; then
  echo "Not a Git checkout: $aur_dir" >&2
  exit 1
fi
remote=$(git -C "$aur_dir" config --get remote.origin.url)
case "$remote" in
  ssh://aur@aur.archlinux.org/mcmodding-mcp.git|aur@aur.archlinux.org:mcmodding-mcp.git) ;;
  *) echo "Unexpected AUR origin: $remote" >&2; exit 1 ;;
esac
if [[ $(git -C "$aur_dir" branch --show-current) != master ]]; then
  echo 'AUR checkout must be on master.' >&2
  exit 1
fi
if [[ -n $(git -C "$aur_dir" status --porcelain) ]]; then
  echo "AUR checkout has uncommitted changes: $aur_dir" >&2
  exit 1
fi
while IFS= read -r file; do
  case "$file" in
    PKGBUILD|.SRCINFO|xdg-cache.patch) ;;
    *) echo "Unexpected tracked AUR file: $file" >&2; exit 1 ;;
  esac
done < <(git -C "$aur_dir" ls-files)
python "$repo_root/scripts/validation.py" metadata
for file in PKGBUILD .SRCINFO xdg-cache.patch; do
  cp "$repo_root/$file" "$aur_dir/$file"
done
git -C "$aur_dir" add PKGBUILD .SRCINFO xdg-cache.patch
git -C "$aur_dir" status --short
