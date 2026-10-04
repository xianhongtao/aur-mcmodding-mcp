# 自动更新与发布验证 · 2026-10-04

目标：`/home/xianhongtao/Repositories/aur-mcmodding-mcp`。

## 实现范围

- 新增每六小时调度、手动触发和相关文件推送触发的 GitHub Actions。
- 更新器读取稳定 Release 和源码包，计算源码及包内锁文件 SHA-256，检查元数据、pnpm、固定依赖路径与补丁；支持只读检查和写入失败回滚。
- 发布任务核对验证提交与三个文件的校验和，先更新 GitHub，再通过独立检出同步 AUR；拒绝降级并核验远程提交及内容，允许后续运行重试。
- 冒烟测试默认读取配方版本，支持显式版本参数，并允许新增工具。
- 未修改 PKGBUILD、.SRCINFO、xdg-cache.patch；版本保持 0.5.0-1。缓存、历史 chroot 产物和历史日志保留。

## 本地实测

- 首轮自动化测试：28 项通过，覆盖更新、只读检查、失败回滚、版本和依赖不兼容、发布提交竞态、白名单、AUR 降级保护、epoch 版本和发布失败重试。随后新增 GitHub 推送认证失败阻止 AUR 同步的回归测试。
- 在独立临时目录将维护配方设为模拟 0.8.0，再跑同一组 28 项测试：全部通过，确认测试夹具不会阻止后续自动升级；实际仓库版本没有改变。
- Bash 语法、actionlint 1.7.12、ShellCheck 0.11.0、工作流 YAML 与任务权限/密钥隔离检查通过；实际 makepkg --printsrcinfo 与 .SRCINFO 一致。
- 对真实 v0.5.0 执行一次 --check，并连续两次运行更新器：均返回无新稳定版，未更改三个配方文件。
- 真实源码 SHA-256：`e748b72ddbd1cd81faaf34a93a27abf1ad95d482de79cfb74af599e49d6f82d1`。
- 源码包内锁文件 SHA-256：`4b0356ea956fcd537a06c3cadd43544320ac78783af9e133e1bfc693fecceb98`；补丁 dry-run 通过。
- 使用修改后的冒烟脚本检查既有系统安装：mcmodding-mcp 0.5.0-1、Node 26.10.0-2，MCP initialize 返回 0.5.0，四个基础工具可用；数据目录隔离，未下载数据库或模型。这不是重新构建或重新安装测试。
- artifacts/SHA256SUMS 两个历史交付物均匹配；未重新构建这些交付物。
- 在独立 local/builds/2026-10-04/ 工作区完整执行 makepkg --verifysource -f 与 makepkg -f：五个 source 校验通过，prepare、build、check、package 全部完成；原有 src/、pkg/ 缓存未覆盖。
- 本次 check 验证锁文件未改写、SQLite 内存查询、两版 sharp PNG 转换、transformers 导入、Zstandard API 与 XDG 缓存路径，均通过。
- 本次宿主机构建成品 namcap：0 错误、28 警告，实际报告见 [namcap-2026-10-04.txt](namcap-2026-10-04.txt)。未把警告视为已解决。
- 对本次成品解包后执行离线 MCP 握手：initialize 返回 0.5.0，四个基础工具可用。成品与日志仅保存在 Git 忽略的 local/，未放入 artifacts/，未进行宿主机重新安装。

## CI 与发布

- 实现提交 `6f648aa83aafa33d8955d376ca1e8aebc1ae0c71` 已签名推送到 GitHub main；GitHub API 确认签名 verified=true、reason=valid。
- [首次推送触发运行 37206384061](https://github.com/xianhongtao/aur-mcmodding-mcp/actions/runs/37206384061)：validate 成功，28 项测试、五个 source 校验、完整 makepkg、原生模块 check、容器内 pacman 安装与离线 MCP 握手均通过。MCP 返回 0.5.0 和四个基础工具。namcap 为 0 错误、33 警告，实际报告见 [namcap-ci-2026-10-04.txt](namcap-ci-2026-10-04.txt)。
- 首次 publish 失败：root 读取 HEAD 时触发 Git 属主检查，echo 内的命令替换失败未阻止步骤，导致 source_commit 为空。已改为 chown 后由 builder 读取，独立赋值并与 GITHUB_SHA 核对；同时发布凭据改为仅发布步骤的进程环境，避免 checkout 的 root 凭据文件阻碍普通用户推送。
- 发布脚本对无改动配方也执行 GitHub 非强制 no-op push，核验写认证后才同步 AUR；不产生无意义提交。
- 修复后本地 29 项测试全部通过，actionlint、ShellCheck 与 git diff --check 通过。
- 用户已通过 Run workflow 触发 [手动运行 37206632521](https://github.com/xianhongtao/aur-mcmodding-mcp/actions/runs/37206632521)，它使用修复前提交；修复后的真实发布结果待补充。
- 独立检出 AUR 公共 Git：master 为 `c019df8bcd8e181dafad79050e55783a4c1a0b0c`，只含三个配方文件，逐字节与 GitHub 一致。官方 RPC 返回 0.5.0-1、维护者 xianhongtao。

未重跑干净 chroot、宿主机重新安装、真实数据库、嵌入模型或 ONNX 推理；历史报告不能视为本次结果。
