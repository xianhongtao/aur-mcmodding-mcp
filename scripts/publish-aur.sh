#!/usr/bin/env bash
set -euo pipefail

: "${AUR_SSH_PRIVATE_KEY:?Set the AUR_SSH_PRIVATE_KEY repository secret}"
: "${AUR_USERNAME:?Set the AUR_USERNAME repository variable}"
: "${AUR_EMAIL:?Set the AUR_EMAIL repository variable}"
: "${VALIDATED_COMMIT:?Set VALIDATED_COMMIT to the source commit from the validation job}"

if [[ $(id -u) -eq 0 ]]; then
  echo 'Run publication as an unprivileged user; makepkg refuses root.' >&2
  exit 1
fi
cd "$(dirname "$0")/.."
if [[ ! -d .git ]]; then
  echo 'Not a Git checkout; install git before actions/checkout.' >&2
  exit 1
fi
if [[ $(git branch --show-current) != main ]]; then
  echo 'Publication requires the main branch.' >&2
  exit 1
fi
if [[ $(git rev-parse HEAD) != "$VALIDATED_COMMIT" ]]; then
  echo 'Checkout differs from the commit that was validated; retry validation.' >&2
  exit 1
fi
python scripts/validation.py verify-manifest validation-manifest.json --commit "$VALIDATED_COMMIT"
# Only the three validated recipe files may have changed in this job.
python - <<'PY'
import subprocess
allowed = {'PKGBUILD', '.SRCINFO', 'xdg-cache.patch'}
for row in subprocess.check_output(['git', 'status', '--porcelain', '-z']).split(b'\0'):
    if row and (row[:2] not in (b' M', b'M ', b'??', b'AM', b'A ') or row[3:].decode() not in allowed):
        raise SystemExit('Unexpected workspace change before publication: ' + row.decode())
PY
git fetch origin main
if [[ $(git rev-parse origin/main) != "$VALIDATED_COMMIT" ]]; then
  echo 'GitHub main moved since validation; retry on the next run.' >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
install -m 700 -d "$work/ssh"
printf '%s\n' "$AUR_SSH_PRIVATE_KEY" > "$work/ssh/aur_key"
chmod 600 "$work/ssh/aur_key"
ssh-keyscan -T 10 -t ed25519 aur.archlinux.org 2>/dev/null > "$work/ssh/known_hosts"
test -s "$work/ssh/known_hosts"
fingerprint=$(ssh-keygen -lf "$work/ssh/known_hosts" -E sha256 | awk '{print $2}')
if [[ $fingerprint != 'SHA256:RFzBCUItH9LZS0cKB5UE6ceAYhBD5C8GeOBip8Z11+4' ]]; then
  echo "Unexpected AUR SSH host fingerprint: $fingerprint" >&2
  exit 1
fi
export GIT_SSH_COMMAND="ssh -i $work/ssh/aur_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$work/ssh/known_hosts"

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git config commit.gpgsign false
git add PKGBUILD .SRCINFO xdg-cache.patch
repo_version=$(python scripts/validation.py version)
if ! git diff --cached --quiet; then
  git commit -m "Update mcmodding-mcp to $repo_version"
  git push origin HEAD:main
fi

git clone --branch master ssh://aur@aur.archlinux.org/mcmodding-mcp.git "$work/aur"
aur_version=$(awk '$1 == "epoch" && $2 == "=" {e=$3} $1 == "pkgver" && $2 == "=" {v=$3} $1 == "pkgrel" && $2 == "=" {r=$3} END {print (e == "" ? "" : e ":") v "-" r}' "$work/aur/.SRCINFO")
if [[ ! $aur_version =~ ^([0-9]+:)?[0-9]+(\.[0-9]+)+-[0-9]+(\.[0-9]+)?$ ]]; then
  echo "Unexpected AUR package version: $aur_version" >&2
  exit 1
fi
if [[ $(vercmp "$aur_version" "$repo_version") -gt 0 ]]; then
  echo "AUR already has newer version $aur_version; refusing to overwrite it with $repo_version" >&2
  exit 1
fi
bash scripts/sync-aur.sh "$work/aur"
if ! git -C "$work/aur" diff --cached --quiet; then
  git -C "$work/aur" config user.name "$AUR_USERNAME"
  git -C "$work/aur" config user.email "$AUR_EMAIL"
  git -C "$work/aur" -c commit.gpgsign=false commit -m "Update mcmodding-mcp to $repo_version"
  git -C "$work/aur" push origin HEAD:master
fi
local_head=$(git -C "$work/aur" rev-parse HEAD)
remote_head=$(git -C "$work/aur" ls-remote origin refs/heads/master | cut -f1)
if [[ $local_head != "$remote_head" ]]; then
  echo 'AUR remote HEAD does not match the published commit.' >&2
  exit 1
fi
# Fetch the public remote again and compare committed bytes, not just the local files.
git -C "$work/aur" fetch origin master
for file in PKGBUILD .SRCINFO xdg-cache.patch; do
  git -C "$work/aur" show "origin/master:$file" > "$work/remote-file"
  cmp "$file" "$work/remote-file"
done
echo "AUR Git commit and three recipe files verified: $remote_head"
python scripts/validation.py poll-aur "$repo_version"
