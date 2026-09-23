# mcmodding-mcp · Arch Linux / AUR

本仓库维护 [OGMatrix/mcmodding-mcp](https://github.com/OGMatrix/mcmodding-mcp) 的 Arch Linux 打包配方，不是应用源码仓库。

- AUR：[mcmodding-mcp](https://aur.archlinux.org/packages/mcmodding-mcp)，维护者 `xianhongtao`。
- 2026-09-23 核对：npm / GitHub 稳定版 `0.5.0`，AUR `0.5.0-1`；应用许可证 MIT。
- 从固定版本源码构建主程序，使用冻结的 pnpm 锁文件；部分第三方原生依赖使用上游预编译文件。仅声明并验证 `x86_64`。

## 文件分工

| 路径 | 用途 |
| --- | --- |
| `PKGBUILD`、`.SRCINFO`、`xdg-cache.patch` | AUR 提交白名单 |
| `README.md`、`README.zh-CN.md`、`AGENTS.md` | GitHub 首页、详细打包说明、维护约束 |
| `smoke-test.py` | 隔离数据目录的离线 MCP 握手测试 |
| `docs/validation-2026-09-23.md` | 本次实测结果 |
| `docs/history/2026-09-16/` | 原有验证记录，不能视为本次重测 |
| `artifacts/` | 原有干净 chroot 交付物与校验和；本地保留，Git 忽略 |
| `local/logs/`、`local/builds/` | 归档日志、宿主机构建包；Git 忽略 |
| `src/`、`pkg/`、下载的源码包 | makepkg 缓存；保留以便复用，Git 忽略 |

## 构建与验证

安装 `base-devel` 及 PKGBUILD 声明的依赖后，以普通用户在仓库根目录执行：

```sh
makepkg --verifysource -f
makepkg --printsrcinfo > .SRCINFO
makepkg -f
namcap PKGBUILD ./mcmodding-mcp-0.5.0-1-x86_64.pkg.tar.zst
python smoke-test.py /usr/bin/node "$PWD/pkg/mcmodding-mcp/usr/lib/mcmodding-mcp/dist/index.js"
```

`--verifysource -f` 用来绕过本目录已有成品的检查，仅校验源文件。构建只能通过 makepkg，不要在仓库根目录运行 npm/pnpm 安装命令。依赖下载发生于 prepare；build 使用离线生产依赖树。更改版本时，重新核对源码、锁文件校验和、补丁、原生模块版本路径和测试中的版本断言。

需要安装本机构建包时自行执行：

```sh
sudo pacman -U ./mcmodding-mcp-0.5.0-1-x86_64.pkg.tar.zst
python smoke-test.py
```

发布二进制前建议使用 `extra-x86_64-build` 重新构建；不要把宿主机生成的 `.BUILDINFO` 当作干净 chroot 产物发布。详细依赖、XDG 模型缓存和实际使用说明见 [README.zh-CN.md](README.zh-CN.md)。

## GitHub 与 AUR

本地 Git 仓库使用 `main`，尚未提交或推送。先在 GitHub 创建空仓库 `xianhongtao/aur-mcmodding-mcp`，再执行：

```sh
git add PKGBUILD .SRCINFO xdg-cache.patch .gitignore README.md README.zh-CN.md AGENTS.md smoke-test.py docs
git diff --cached --stat
git commit -m 'Organize mcmodding-mcp AUR packaging repository'
git remote add origin git@github.com:xianhongtao/aur-mcmodding-mcp.git
git push -u origin main
```

AUR 已有历史，使用独立检出保留其历史，只复制三个配方文件。不要将包含 GitHub 文档的 `main` 直接推到 AUR，也不要强制推送。以下命令假设当前位于本仓库且 `../aur-submit` 不存在：

```sh
git clone ssh://aur@aur.archlinux.org/mcmodding-mcp.git ../aur-submit
cp PKGBUILD .SRCINFO xdg-cache.patch ../aur-submit/
git -C ../aur-submit diff --check
git -C ../aur-submit diff
# 仅确有配方变更时提交；本次整理本身不需要发 AUR 新版本。
git -C ../aur-submit add PKGBUILD .SRCINFO xdg-cache.patch
git -C ../aur-submit commit -m 'Update mcmodding-mcp packaging'
git -C ../aur-submit push origin HEAD:master
```

若 `../aur-submit` 已存在，先检查其 remote、分支和未提交改动，确认干净后 `git pull --ff-only`，再复制文件。该独立检出的 `origin` 就是 AUR remote；GitHub 仓库的 `origin` 只指向 GitHub。

GitHub 可跟踪文档和测试，AUR 只包含配方。二进制、下载缓存及本地日志不提交 Git。上游 MIT 许可证随软件安装；本次整理未替维护者另行指定打包脚本的许可证。
