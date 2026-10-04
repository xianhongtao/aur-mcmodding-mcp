# mcmodding-mcp — Arch Linux / AUR package

This repository maintains the Arch Linux package recipe for
[OGMatrix/mcmodding-mcp](https://github.com/OGMatrix/mcmodding-mcp), the MCP server that serves
up-to-date Fabric and NeoForge modding documentation to AI assistants. It is a packaging repository,
not the application source.

The recipe builds the application from the pinned upstream source release with a frozen pnpm lock
file. A few third-party native dependencies use the upstream prebuilt artifacts. Only `x86_64` is
declared and tested.

| | |
| --- | --- |
| AUR | [`mcmodding-mcp`](https://aur.archlinux.org/packages/mcmodding-mcp) |
| Maintainer | `xianhongtao` |
| Upstream stable | `0.5.0` (npm and GitHub) |
| Packaged version | `0.5.0-1` |
| License | MIT for the application |

## Repository layout

| Path | Purpose |
| --- | --- |
| `PKGBUILD`, `.SRCINFO`, `xdg-cache.patch` | The three files submitted to AUR |
| `scripts/update-upstream.py` | Verify a newer stable release and update the recipe |
| `scripts/validation.py` | Provenance manifest, namcap gate, `.SRCINFO` check, AUR RPC poll |
| `scripts/publish-aur.sh`, `scripts/sync-aur.sh` | Publish to AUR / stage the three files in an AUR checkout |
| `.github/workflows/update-aur.yml` | Scheduled and manual validation and publication |
| `tests/`, `smoke-test.py` | Unit tests and an offline MCP handshake test |
| `artifacts/` | Kept locally, not tracked: the 2026-09-16 clean chroot build and `SHA256SUMS` |
| `src/`, `pkg/`, downloaded sources | makepkg work and cache directories; keep them, not tracked |

GitHub tracks the recipe, scripts, tests, and maintenance docs. AUR receives only `PKGBUILD`,
`.SRCINFO`, and `xdg-cache.patch`.

## Build locally

Install Arch's `base-devel` and the dependencies declared in `PKGBUILD`, then run as an ordinary
user from this directory:

```sh
makepkg --verifysource -f     # validate sources, skip the existing built package
makepkg --printsrcinfo > .SRCINFO
makepkg -f
```

`makepkg` is the only supported build path; do not run `npm install` or `pnpm install` at the
repository root. Dependencies are fetched in `prepare()`, and `build()` uses the offline production
tree. To test an installed or freshly built package:

```sh
sudo pacman -U ./mcmodding-mcp-0.5.0-1-x86_64.pkg.tar.zst
python smoke-test.py
```

The smoke test reads `pkgver` from `PKGBUILD` by default; pass `--expected-version VERSION` to
override it. It checks that the four base tools remain available and tolerates new ones.

Before publishing a binary, rebuild with `extra-x86_64-build` and never ship a host-built
`.BUILDINFO` as a clean chroot artifact — a host build records every installed package, while a
clean chroot build records only the build environment. The recipe pins the dependency graph through
the source archive's `pnpm-lock.yaml` and the `_lockfile_sha256` guard; keep `--frozen-lockfile`
and `--verify-store-integrity` in place.

## Automatic updates and publication

The [update workflow](.github/workflows/update-aur.yml) checks every six hours at 02:23, 08:23,
14:23 and 20:23 Asia/Shanghai; GitHub may delay scheduled runs. It also runs on manual dispatch
(**Actions → Update mcmodding-mcp AUR package → Run workflow**) and on a push to `main` that changes
the recipe, tests, or automation.

The updater follows GitHub stable releases only. For a newer version it downloads the same source
archive the recipe uses, computes the source SHA-256, reads the lock file from the archive for
`_lockfile_sha256`, resets `pkgrel=1`, and regenerates `.SRCINFO`. A changed checksum within the same
version is an error rather than a silent replacement, and an unchanged version produces no commit.
The frozen lock file and the `--frozen-lockfile` / `--verify-store-integrity` guards are kept as is;
when upstream changes the pnpm version, a pinned native dependency path, the patch, or the package
metadata, the workflow stops for review. The v0.5.0 metadata repair (upstream ships `0.4.5` strings)
is a known exception.

To check or update the recipe locally:

```sh
python scripts/update-upstream.py --check
python scripts/update-upstream.py
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

The validation job installs the Arch toolchain before checkout, then, as an unprivileged user, runs
the tests, verifies the source checksums, and runs a full `makepkg -f` build (without `-s`). It
installs the `x86_64` package, runs the offline MCP handshake and namcap, and rejects namcap errors.
Logs are kept as the `validation-logs` artifact for 14 days. These container checks are not a
substitute for a clean chroot, a host install, or a real database test.

The publication job receives only the three validated recipe files with their commit SHA and file
hashes. If GitHub `main` moved during validation, it stops and waits for revalidation. It commits the
validated recipe to GitHub as an unsigned `github-actions[bot]`, then publishes from a separate AUR
checkout, copying only the three files and refusing downgrades, unexpected files, and force pushes.
If the GitHub push succeeds but the AUR push fails, the next run retries.

To enable automatic publication, configure this repository:

1. Actions secret `AUR_SSH_PRIVATE_KEY`: an unencrypted Ed25519 key dedicated to this workflow; add
   its public key to your AUR account. Only the publication job reads it.
2. Actions variables `AUR_USERNAME` and `AUR_EMAIL`: the AUR commit identity.
3. `contents: write` for the publication job, and a branch rule that lets the robot update `main`.

Secrets: <https://github.com/xianhongtao/aur-mcmodding-mcp/settings/secrets/actions> ·
Variables: <https://github.com/xianhongtao/aur-mcmodding-mcp/settings/variables/actions>. Until these
are set, the publication job fails with an explicit message.

The workflow checks the [officially announced AUR Ed25519 host
fingerprint](https://archlinux.org/news/aur-migration-new-ssh-hostkeys/) and uses strict host
verification. After pushing it verifies the remote commit and the three files, then polls the AUR RPC
up to 30 times at 10 second intervals; if the index still lags, it reports a Git-verified but
index-delayed result and retries on the next run.

## Manual AUR synchronization

AUR keeps its own history, so use a separate checkout. Assuming this repository is the current
directory and `../aur-submit` does not exist:

```sh
git clone ssh://aur@aur.archlinux.org/mcmodding-mcp.git ../aur-submit
bash scripts/sync-aur.sh ../aur-submit
git -C ../aur-submit diff --check
git -C ../aur-submit diff --cached
git -C ../aur-submit commit -m 'Update mcmodding-mcp packaging'   # only if the recipe changed
git -C ../aur-submit push origin HEAD:master
```

If `../aur-submit` already exists, check its remote, branch, and working tree, fast-forward it, and
then stage the files. `artifacts/` is not refreshed by automatic updates; to publish a new binary,
rebuild with `extra-x86_64-build` and regenerate the submission archive, `SHA256SUMS`, and measured
results. The upstream MIT license is installed with the package; this repository's packaging scripts
carry no separate license.

## Sources

- [Upstream repository](https://github.com/OGMatrix/mcmodding-mcp)
- [Upstream releases](https://github.com/OGMatrix/mcmodding-mcp/releases)
- [Arch AUR submission guidelines](https://wiki.archlinux.org/title/AUR_submission_guidelines)
- [Arch Node.js package guidelines](https://wiki.archlinux.org/title/Node.js_package_guidelines)
