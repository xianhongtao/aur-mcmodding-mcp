# mcmodding-mcp 整理与验证 · 2026-09-23

目标：`/home/xianhongtao/Repositories/mcmodding-mcp/`。

## 改动

- 新增 README.md，包含 GitHub 首页、目录说明、构建验证和独立 AUR 检出工作流。
- 更新 .gitignore，允许跟踪文档、AGENTS.md、测试和 docs；忽略缓存及产物。
- 更新 README.zh-CN.md，标注历史结果、修正警告分类数量、提示旧 AUR 检出已不在原路径。
- 更新 AGENTS.md，补充目录布局及维护规则。
- 重新生成 .SRCINFO，内容与原文件完全一致；PKGBUILD 和 xdg-cache.patch 未改动，无须增加 pkgrel。
- 两份旧报告移至 docs/history/2026-09-16/；根目录日志移至 local/logs/2026-09-16/；宿主机构建包移至 local/builds/。
- 保留 src/、pkg/、下载缓存及 artifacts/；整理前文档备份在 local/backup-before-organization-2026-09-23/。
- 初始化 Git main 分支，未提交、未配置 remote、未创建 GitHub 远程仓库或推送。

## 上游核实

直接读取 npm registry / GitHub API / AUR RPC：npm 0.5.0（MIT），GitHub v0.5.0（2026-08-28），AUR mcmodding-mcp 0.5.0-1，维护者 xianhongtao。

- https://registry.npmjs.org/mcmodding-mcp/latest
- https://github.com/OGMatrix/mcmodding-mcp/releases/tag/v0.5.0
- https://aur.archlinux.org/packages/mcmodding-mcp

## 本次实测

- makepkg --printsrcinfo：成功，与原文件无差异；bash -n PKGBUILD 通过。
- 首次 makepkg --verifysource 被已有成品检查阻止；使用 --verifysource -f 后，5 个 source 的 SHA-256 全部通过，没有重新打包。
- artifacts/SHA256SUMS 两个交付物全部匹配。
- AUR 提交压缩包中三个配方文件与当前文件逐字节一致。
- namcap：PKGBUILD 无输出，既有 artifacts 成品 0 个错误、28 个警告，完整输出在 docs/namcap-2026-09-23.txt。
- 解包既有 artifacts 成品后运行 smoke-test.py，initialize 返回 0.5.0，tools/list 返回预期四个工具；数据目录隔离，跳过自动更新。
- 对同一解包成品执行 SQLite 内存查询、sharp 0.34.5 / 0.32.6 的 PNG 转换，均通过。

28 条警告由 19 条 ELF 加固/剥离/PIE、8 条冗余链接、1 条私有 libvips 被判为未安装依赖组成。两版 sharp 均已成功加载并转换图像；其余二进制警告保留，未宣称全部解决。

本次未更改构建逻辑，未重跑完整 makepkg 构建、干净 chroot 构建、系统安装、真实数据或 ONNX 推理测试。历史报告不能视为本次重测结果。

## GitHub / AUR

在 GitHub 创建空仓库后，于目标目录执行：

```sh
git remote add origin git@github.com:xianhongtao/aur-mcmodding-mcp.git
```

完整提交及推送步骤见 README.md。AUR 已有历史，应使用独立检出：

```sh
git clone ssh://aur@aur.archlinux.org/mcmodding-mcp.git ../aur-submit
```

其 origin 指向 AUR；只复制 PKGBUILD、.SRCINFO、xdg-cache.patch，在该检出中提交并 git push origin HEAD:master。本次配方未变，无须重复提交 AUR。
