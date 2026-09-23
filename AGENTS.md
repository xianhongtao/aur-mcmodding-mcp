# mcmodding-mcp — AUR 打包仓库

本仓库不是应用源码仓库，只是把上游 [OGMatrix/mcmodding-mcp](https://github.com/OGMatrix/mcmodding-mcp) 打成 AUR 包的配方。
当前目录布局、构建与双仓库发布流程见 `README.md`；技术细节与历史记录见 `README.zh-CN.md`；此处只列 agent 容易踩错的约束。

## 禁止在仓库根目录跑包管理器

- 构建只能走 `makepkg`：`makepkg --verifysource`、`makepkg -f`。不要加 `-s`（会触发 sudo 安装依赖）。
- 不要执行 `npm install` / `pnpm install` / `npm run build`。根目录下的 `src/`、`pkg/`、`*.log`、`mcmodding-mcp-*.tar.gz`、`pnpm-*.tgz` 都是 makepkg 的工作区与缓存；包管理器只允许由 `PKGBUILD` 在 `$srcdir` 内调用，否则会造出未受冻结锁文件约束的依赖树，破坏配方刻意钉死的依赖图。

## 本机环境的三个坑

- **文件属主/权限必须在沙箱外判断。** 沙箱终端把宿主机的 root 文件显示为 `uid 65534(nobody)`，因此 `pacman -Qkk` 会报出成千上万条 UID/GID 不匹配的假警。遇到这类告警先做对照（`/etc/passwd`、`/usr/bin/pacman` 这类必然是 root 的文件在沙箱里同样显示 65534），再用沙箱外视角复核。
- **没有免密 sudo。** `sudo -n` 直接失败。需要 root 的命令（`pacman -U`、`extra-x86_64-build`）交给用户在终端自行输入密码，不要换参数反复重试，也不要通过其他工具索要密码。
- **工作区外的路径在沙箱内不可见。** AUR 检出 `../aur-submit`、chroot 目录 `/var/lib/archbuild/extra-x86_64` 都需要在沙箱外访问。

## 改动配方必须同步刷新交付物

改动 `PKGBUILD` 后：

```sh
makepkg --printsrcinfo > .SRCINFO                       # 元数据变化时必须重新生成
namcap PKGBUILD ./mcmodding-mcp-<版本>-1-x86_64.pkg.tar.zst > namcap-report.txt
(cd artifacts && sha256sum -c SHA256SUMS)               # 成品/提交包变了要重算
```

- 报告里**只写实测结果**：不要把「重跑后应该是 N 条」这类推断写成结论；未验证的项目继续保持「未测试」标注。
- 重新构建成品后，`namcap-report.txt`、`validation-report.txt`、`artifacts/`（含提交包与 `SHA256SUMS`）、README 里的数字与结论都可能过期，需一并核对，否则交付物会静默退回到旧版本。

## 不可简化的发布约束

- `_lockfile_sha256`、`--frozen-lockfile`、`--verify-store-integrity` 是刻意的校验链（依据见 README）。不要删除或放宽；仅在上游 `pkgver` 更新时，从**源码包内的 `pnpm-lock.yaml`** 重算该值。
- `artifacts/` 放 `extra-x86_64-build` 的干净 chroot 产物，不要放本机构建结果：本机构建的 `.BUILDINFO` 会把本机全部已装包清单写进成品（实测 1951 条，chroot 为 214 条）。
- AUR 只提交 `PKGBUILD`、`.SRCINFO`、`xdg-cache.patch` 三个文件。推送后 cgit 与包页面立即可见，但 `rpc/v5/info` 索引有延迟，不要据此判断推送失败。

## GitHub 仓库整理（2026-09-23）

- GitHub 跟踪文档、smoke-test.py 和 docs/；AUR 仍仅提交三个配方文件。使用独立 AUR 检出，不把 GitHub main 分支直接推到 AUR。
- local/ 存放历史日志、宿主机成品和整理前文档备份；artifacts/ 保留原有 chroot 交付物。两者均不进 Git。
- src/、pkg/ 和下载缓存原位保留；不要因为整理目录而破坏已存在的构建缓存。
- 原 namcap-report.txt 和 validation-report.txt 已归档到 docs/history/2026-09-16/；当前结果见 docs/validation-2026-09-23.md。重新验证要写明日期与实际范围，不能沿用旧报告当作本次结果。
