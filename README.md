# mcmodding-mcp · Arch Linux / AUR

本仓库维护 [OGMatrix/mcmodding-mcp](https://github.com/OGMatrix/mcmodding-mcp) 的 Arch Linux 打包配方，不是应用源码仓库。

- AUR：[mcmodding-mcp](https://aur.archlinux.org/packages/mcmodding-mcp)，维护者 `xianhongtao`。
- 2026-10-04 核对：npm / GitHub 稳定版 `0.5.0`，AUR `0.5.0-1`；应用许可证 MIT。
- 从固定版本源码构建主程序，使用冻结的 pnpm 锁文件；部分第三方原生依赖使用上游预编译文件。仅声明并验证 `x86_64`。

## 文件分工

| 路径 | 用途 |
| --- | --- |
| `PKGBUILD`、`.SRCINFO`、`xdg-cache.patch` | AUR 提交白名单 |
| `README.md`、`README.zh-CN.md`、`AGENTS.md` | GitHub 首页、详细打包说明、维护约束 |
| `smoke-test.py` | 隔离数据目录的离线 MCP 握手测试 |
| `scripts/`、`tests/` | 上游更新、验证、AUR 发布及自动化测试 |
| `.github/workflows/update-aur.yml` | 六小时调度、手动触发及配方推送验证 |
| `docs/validation-2026-10-04.md` | 自动化实现与本次实测范围 |
| `docs/validation-2026-09-23.md` | 上次仓库整理的验证记录 |
| `docs/history/2026-09-16/` | 原有验证记录，不能视为本次重测 |
| `artifacts/` | 2026-09-16 的历史干净 chroot 交付物与校验和；本地保留，Git 忽略 |
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

`--verifysource -f` 用来绕过本目录已有成品的检查，仅校验源文件。构建只能通过 makepkg，不要在仓库根目录运行 npm/pnpm 安装命令。依赖下载发生于 prepare；build 使用离线生产依赖树。更改版本时，重新核对源码、锁文件校验和、补丁和原生模块版本路径。冒烟测试默认读取配方的 `pkgver`，也可使用 `--expected-version VERSION` 指定期望版本；验证四个基础工具仍可用，允许新增工具。

需要安装本机构建包时自行执行：

```sh
sudo pacman -U ./mcmodding-mcp-0.5.0-1-x86_64.pkg.tar.zst
python smoke-test.py
```

发布二进制前建议使用 `extra-x86_64-build` 重新构建；不要把宿主机生成的 `.BUILDINFO` 当作干净 chroot 产物发布。详细依赖、XDG 模型缓存和实际使用说明见 [README.zh-CN.md](README.zh-CN.md)。

## 自动更新与发布

GitHub 仓库为 [xianhongtao/aur-mcmodding-mcp](https://github.com/xianhongtao/aur-mcmodding-mcp)，维护分支为 `main`。工作流参照本机 `aur-opencodex-bin`，每六小时检查一次：北京时间 02:23、08:23、14:23、20:23。GitHub 的定时运行可能延迟。可在 **Actions → Update mcmodding-mcp AUR package → Run workflow** 手动运行；向 `main` 推送配方、测试或自动化脚本的改动也会触发验证。

更新器只跟随 GitHub 稳定 Release，不跟随开发分支、预发行版或数据库附件变化。它下载与配方相同 URL 的源码包，计算源码 SHA-256，并从包内读取锁文件计算 `_lockfile_sha256`。新版重置 `pkgrel=1`，保留 pnpm 和其他 source 的校验和，重新生成 `.SRCINFO`。同版本校验和变化会报错，不会静默替换校验和。版本未变时不改配方、不产生提交。

可在普通用户终端只读检查，或手动更新配方：

```sh
python scripts/update-upstream.py --check
python scripts/update-upstream.py
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

自动更新保留 `--frozen-lockfile` 和 `--verify-store-integrity`。上游 pnpm 版本、固定原生依赖路径、补丁或包/MCP 元数据不兼容时，工作流停止，维护者需要审查并调整配方与更新器。v0.5.0 的 0.4.5 元数据修补是已知例外；后续标签的元数据必须与版本一致。

验证任务在 Arch 容器内先安装 git 及构建依赖，再 checkout；以普通用户运行测试、源码校验和完整 `makepkg -f` 构建，不使用 `-s`。随后在容器内安装 x86_64 包，运行离线 MCP 握手和 namcap。namcap 错误阻止发布，警告写入实际日志；日志作为 Actions 的 `validation-logs` 保留 14 天。CI 不下载文档数据库或模型，也不把二进制上传到本地 `artifacts/`。这些容器检查不能替代干净 chroot、宿主机安装或真实数据库测试。

发布任务只接收通过验证的三个配方文件及其提交 SHA、文件校验和。若 GitHub `main` 在验证期间前移，任务停止并等待重新验证。自动提交使用未签名的 `github-actions[bot]`；先更新 GitHub，再在独立 AUR 检出中发布。只复制 `PKGBUILD`、`.SRCINFO`、`xdg-cache.patch`，拒绝降级、意外文件和强制推送。若 GitHub 已更新而 AUR 发布失败，下一次运行继续同步。

启用发布需要在**本仓库**配置：

1. Actions Secret `AUR_SSH_PRIVATE_KEY`：专用于 Actions、无口令的 AUR SSH 私钥；对应公钥需已登记到 AUR 账户。私钥仅交给发布任务。
2. Actions Variables `AUR_USERNAME`、`AUR_EMAIL`：AUR 提交作者身份。
3. 工作流发布任务的 `contents: write` 权限，以及允许机器人更新 `main` 的分支规则。

配置入口：[Secrets](https://github.com/xianhongtao/aur-mcmodding-mcp/settings/secrets/actions)、[Variables](https://github.com/xianhongtao/aur-mcmodding-mcp/settings/variables/actions)。参考仓库的 Secret 不会自动共享给本仓库；缺少配置时发布任务给出明确提示。

SSH 连接核对 [AUR 官方 Ed25519 主机指纹](https://archlinux.org/news/aur-migration-new-ssh-hostkeys/)，启用严格主机验证。推送后核对远程提交和三个配方文件的内容，再轮询 AUR RPC 最多 30 次、间隔 10 秒。RPC 仍落后时，日志明确区分“Git 已核验”和“索引延迟”，本轮验证失败并在下次运行重试。

## 手动同步 AUR

AUR 已有历史，使用独立检出保留其历史。以下命令假设当前位于本仓库且 `../aur-submit` 不存在：

```sh
git clone ssh://aur@aur.archlinux.org/mcmodding-mcp.git ../aur-submit
bash scripts/sync-aur.sh ../aur-submit
git -C ../aur-submit diff --check
git -C ../aur-submit diff --cached
# 仅确有配方变更时提交。
git -C ../aur-submit commit -m 'Update mcmodding-mcp packaging'
git -C ../aur-submit push origin HEAD:master
```

若 `../aur-submit` 已存在，先检查其 remote、分支和未提交改动，确认干净后 `git pull --ff-only`，再复制文件。该独立检出的 `origin` 就是 AUR remote；GitHub 仓库的 `origin` 只指向 GitHub。

GitHub 跟踪文档和测试，AUR 只包含三个配方文件。二进制、下载缓存及本地日志不提交 Git。`artifacts/` 的历史成品与提交包不随自动更新刷新；需要发布新二进制时，另行执行 `extra-x86_64-build` 并重新生成提交包、校验和和实际验证记录。上游 MIT 许可证随软件安装；本仓库未另行指定打包脚本的许可证。
