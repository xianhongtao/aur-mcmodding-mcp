# mcmodding-mcp：Arch / AUR 打包交付

> 本文主体记录 2026-09-16 的构建与安装，非 2026-09-23 重测结果。当前仓库布局和 GitHub/AUR 工作流见 [README.md](README.md)，本次验证见 [docs/validation-2026-09-23.md](docs/validation-2026-09-23.md)。旧日志在 `local/logs/2026-09-16/`，旧报告在 `docs/history/2026-09-16/`。此前提及的 `../aur-submit` 在本次检查时不存在，需按首页重新克隆。

核对日期：2026-09-16。包名 `mcmodding-mcp`，版本 `0.5.0-1`，架构 `x86_64`。

## 提交文件

本目录根部的以下三个文件就是 AUR Git 仓库应提交的内容：

- `PKGBUILD`
- `.SRCINFO`（由实际的 `makepkg --printsrcinfo` 生成）
- `xdg-cache.patch`

PKGBUILD 第一行已填写本包维护者 `# Maintainer: xianhongtao <xianhongtao2022@outlook.com>`，不含占位符。没有冒用 codegraph-bin 的维护者信息。本说明、测试脚本、检查报告和二进制包都不需要上传 AUR。构建成品、提交文件压缩包和 SHA256SUMS 放在 `artifacts/`；可在该目录运行 `sha256sum -c SHA256SUMS` 校验。压缩包曾在维护者注释仍是占位符时生成，2026-09-16 已用最终三个文件重新打包并重算校验和；同一日期重新执行 `makepkg --verifysource`，五个 source 全部通过。`artifacts/` 里的成品是同一天 `extra-x86_64-build` 的干净 chroot 产物。

## 上游核实和命名

[npm 元数据](https://registry.npmjs.org/mcmodding-mcp/0.5.0)的 latest 为 0.5.0，入口是 `dist/index.js`。实际下载的 npm 压缩包包含编译后的 JavaScript 和 `postinstall`，不含 Node，也不包含完整的运行依赖树或锁文件。压缩包 SHA-256 为 `6c36e5668b251d216857342d750c3e192e850f1f47b02ac179afa2a213fee447`。

[GitHub v0.5.0 发布](https://github.com/OGMatrix/mcmodding-mcp/releases/tag/v0.5.0)的附件是数据库和清单，没有类似 codegraph 的自包含 Linux CLI。源码使用 TypeScript、pnpm 10.30.0 和提交到仓库的 `pnpm-lock.yaml`。

本配方选择从版本标签构建应用，所以用 **mcmodding-mcp**。这符合[固定版本源码包不加后缀、预编译应用加 -bin 的规则](https://wiki.archlinux.org/title/AUR_submission_guidelines)。如果以后改成直接重打包 npm 已编译应用，应重新考虑 `-bin`；“通过 npm 分发”本身不能决定后缀。

参照了实际获取的 [codegraph-bin 1.6.0-1 配方](https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=codegraph-bin)，保留 `/usr/lib/<应用名>` 配合 `/usr/bin` 启动脚本的布局。这里使用 Arch 的 Node，不照搬 codegraph 自带的 Node。

查询时 AUR RPC 中 `mcmodding-mcp` 和 `mcmodding-mcp-bin` 均无结果，本机同步的官方软件包数据库也未找到同名包；该名称随后由本包取得，见下文「AUR 提交」。

## 依赖和安装布局

| 项目 | 处理 |
| --- | --- |
| 运行依赖 | `nodejs>=22.15.0`、`glibc`、`libgcc`、`libstdc++.so`、`libvips`、`glib2`、`sh` |
| 构建依赖 | `node-gyp`、`python`、`pkgconf`；编译器、make、patch 等由 Arch 的 `base-devel` 提供 |
| pnpm | 固定 10.30.0，作为有 SHA-256 的 source 下载，在构建目录运行，不装入系统 |
| npm | 不调用 npm CLI，因此不另外声明 npm；不读写全局 prefix，不执行 `sudo npm install` |
| 架构 | 原生模块决定不能使用 `any`；本次仅验证并声明 x86_64 |
| 应用 | `/usr/lib/mcmodding-mcp/{dist,node_modules,package.json}` |
| 命令 | `/usr/bin/mcmodding-mcp`，权限 755，执行 `/usr/bin/node /usr/lib/mcmodding-mcp/dist/index.js "$@"` |
| 许可证 | 主程序 MIT 安装到 `/usr/share/licenses/mcmodding-mcp/LICENSE`；保留依赖自带许可证，并补齐 ONNX LICENSE、ThirdPartyNotices 和 sharp/libvips 许可说明 |
| 数据 | 上游使用 `$XDG_DATA_HOME/mcmodding-mcp`，默认 `~/.local/share/mcmodding-mcp`，可用 `MCMODDING_DATA_DIR` 覆盖 |
| 模型缓存 | 补丁设为 `$XDG_CACHE_HOME/mcmodding-mcp/transformers`，默认 `~/.cache/mcmodding-mcp/transformers` |

上游 package.json 声明 Node >=20，但运行路径使用原生 Zstandard 解压，故要求至少 22.15.0。本包不依赖外部 zstd 命令来运行服务。`glib2` 是编译后 sharp 直接链接的库，已显式声明。

prepare 阶段按锁文件获取依赖，并禁用所有生命周期脚本；build 阶段离线重建生产依赖树、编译 TypeScript、better-sqlite3 12.10.0 和旧版 sharp 0.32.6。旧版 sharp 链接系统 libvips。新版 sharp 0.34.5、其私有 libvips 和 ONNX 1.14.0 仍使用锁文件指定的上游预编译依赖；这里的“源码构建”指主应用及上述本地构建模块，并非所有第三方库全部源码重建。

全部直接 source 均固定版本并提供实算 SHA-256。传递依赖没有逐个写进 `source=()`：上游锁文件 7061 行、上千条记录，pnpm 的 `store add` 不接受本地 tarball，官方 Node.js 打包规范也只要求顶层包用 `source=()`。改用整图校验和钉死：锁文件随带 SHA-256 的源码包一起下发，配方另用 `_lockfile_sha256` 显式记录该文件自身的 SHA-256，并在 `prepare()` 和 `check()` 两处断言；两次安装都带 `--frozen-lockfile`，因此每个解析出的版本号和 integrity 都来自该文件，且该文件不允许被改写。`verify-store-integrity` 与 `strict-store-pkg-content-check` 在 pnpm 10.30.0 中默认开启（后者不匹配即抛 `UNEXPECTED_PKG_CONTENT_IN_STORE`），配方仍把前者显式写出。pnpm store/cache/state 在构建目录，不进入包。成品移除了其他平台原生文件、编译中间产物、内部 CLI 脚本和带构建路径的安装器元数据，并额外清掉 gyp 因 pnpm 的 `.pnpm` 路径拼错而留下的 `node-addon-api@*` 目录（里面只有 gyp 输出和空静态库 `nothing.a`，后者的 `ar` 时间戳会破坏可复现性）；复制时解除跨目录硬链接并保留运行所需的相对符号链接。

不提供 `.install`：pacman 安装时无需执行额外动作，更不应以 root 身份把数据库下载到某个用户目录。首次使用由用户运行 `mcmodding-mcp manage` 管理数据，首次语义搜索可能下载模型。主程序 MIT 不覆盖第三方组件；其各自许可证及声明保留在包内。

v0.5.0 标签里的 package.json 和 MCP serverInfo 仍写成 0.4.5，配方将这两处元数据修正为 0.5.0。

## 实际测试

本机为 Arch Linux x86_64，Node 26.8.2、node-gyp 13.0.2、GCC 16.2.1、Python 3.14.7、libvips 8.18.6。

- 实际运行 `makepkg --verifysource`：所有 source 校验通过。
- 实际完成 prepare → build → check → package；后续布局修正通过 `makepkg --repackage --force` 重新生成成品，没有重复编译未变化的代码。引入锁文件校验和与 gyp 残留清理后，又完整重跑了一次 prepare → build → check → package，`prepare()` 与 `check()` 均输出 `pnpm-lock.yaml: 成功`。
- 对比清理前后的成品：除 `builddate` 和被移除的 gyp 残留外逐字节相同，说明清理没有动到任何运行时文件。
- 清理后复查成品：9 个 x86_64 ELF、517 个符号链接（0 断链、0 指向树外）、0 个硬链接文件、无 `.a`/`.o`/`.mk` 残留。
- `check()` 验证 SQLite 内存查询、两版 sharp 的图像转换、transformers 导入、Zstandard API 和 XDG 模型缓存路径，均通过。
- 将包解压到独立目录执行真实 MCP `initialize` 和 `tools/list`：返回 0.5.0 和四个基础工具，测试通过；清理后在解包成品上复跑，并额外验证 better-sqlite3 内存查询与两版 sharp 的图像转换。
- 对最终成品再次执行 SQLite、两版 sharp、XDG 缓存测试，并用最小 ONNX Identity 模型实际运行 CPU 推理，全部通过。
- 检查成品符号链接、硬链接、构建路径残留、ELF 架构和动态库解析。无断链、无跨目录硬链接、无构建目录残留、无其他架构 ELF；所检查的原生模块没有缺失动态库。
- 用 namcap 3.6.0（已 `pacman -S namcap` 装到本机）对当前 PKGBUILD 与最终成品重跑，报告保存在 `namcap-report.txt`。
- 最终 namcap 结果为 0 个错误项、28 个警告项（19 条 ELF 加固/剥离/PIE、8 条上游冗余链接、1 条私有 libvips 被判为未安装依赖）；PKGBUILD 部分已无任何输出，早先的 `Missing Maintainer tag` 随维护者注释补全而消失。成品检查了 9 个 x86_64 ELF、517 个内部符号链接及 258 个许可证/声明文件。
- 用 `pacman -U` 将成品实际装到本机：`pacman -Qkk` 报告 `10687 全部文件，0 变化的文件`，所有文件属主为 root:root。
- 对系统安装的 `/usr/bin/mcmodding-mcp` 执行冒烟测试：`initialize` 返回 0.5.0，`tools/list` 返回四个基础工具，通过。
- 实际调用四个工具（`MCMODDING_DATA_DIR` 指向临时目录、跳过自动更新）：未下载数据库时返回结构良好的 MCP 错误（`isError: true`），服务不崩溃。其中 `get_minecraft_version` 把错误文本当正常内容返回且 `isError` 仍为 false，这是上游既有行为，不是打包引入的。
- 执行 `extra-x86_64-build` 干净 chroot 构建：成功（devtools 1:1.5.1-1）。逐文件比对显示**载荷 8600+ 个文件与宿主机构建逐字节一致**，只有 `.PKGINFO`、`.BUILDINFO`、`.MTREE` 三个元数据文件不同。
- 两者体积差异来自压缩配置：chroot 用 `zstd -c -T0 --ultra -20`（默认），本机 `/etc/makepkg.conf` 是 `zstd -c -T0 -`。`artifacts/` 发布 chroot 产物还有一个理由：它的 `.BUILDINFO` 只记录 214 个构建环境包，而本机构建的会写入本机全部 **1951** 个已装包（等于把本机软件清单写进成品）。
- 真实数据测试：启动时自动下载文档库（版本 0.1.1、解压后 720 MiB，走 `.zst` 流式解压，实测印证 `nodejs>=22.15.0` 这条依赖）。`get_minecraft_version` 返回文档库中最新的 **26.2**；`explain_fabric_concept` 返回 3875 字符真实内容；`search_fabric_docs` 返回 10 篇真实页面（如 `wiki.fabricmc.net/tutorial:blocks`）。
- 语义检索需要能访问 `huggingface.co`。本机该域名**直连超时**（只有 `https_proxy` 可达），而 Node 内置 fetch 默认不读代理变量，导致嵌入模型下载失败、检索退化为词法打分；设置 `NODE_USE_ENV_PROXY=1`（Node ≥24）后模型下载成功（`Xenova/all-MiniLM-L6-v2`，`model_quantized.onnx` 21.91 MiB），服务端日志出现 `Embedding model initialized successfully` 与 `Strategy 4 (embeddings): 11 results`。
- 上述模型落在 `~/.cache/mcmodding-mcp/transformers/`，正好在真实使用中验证了 `xdg-cache.patch` 的缓存路径。
- 已知小瑕疵：chroot 构建的 `.BUILDINFO` 中 `packager = Unknown Packager`（chroot 未继承本机 `PACKAGER`），只影响元数据显示。

namcap 的剩余警告包括上游预编译库缺少部分 ELF 加固、`!strip` 保留符号、共享扩展的 PIE 检查、上游冗余链接，以及私有 libvips 被视为“未安装依赖”。后者已用动态加载器解析和两版 sharp 实际调用确认：新版 sharp 经相对 RUNPATH 正确加载包内的 `libvips-cpp.so.8.17.3`，不是缺失系统依赖。没有把这些警告描述为“全零告警”。

测试复用了此前下载的 pnpm 内容缓存，仍由锁文件校验；干净 chroot 构建与系统安装均已通过。未做 ARM 测试，也未验证其他 MCP 客户端接入；文档库是 2026-09-16 下载的 0.1.1 版。系统 Node 的 ABI 升级后，应重建 better-sqlite3；不要把本次二进制包当作跨 Node 版本通用包。

## 本机构建、安装和使用

在解压后的 `mcmodding-mcp` 目录，以普通用户执行：

```sh
sudo pacman -S --needed base-devel nodejs node-gyp python pkgconf libvips
makepkg --verifysource
makepkg -s
sudo pacman -U ./mcmodding-mcp-0.5.0-1-x86_64.pkg.tar.zst
mcmodding-mcp manage
```

已存在成品而需要重建时使用 `makepkg -fs`。测试脚本在本目录根部，安装后可执行 `python ./smoke-test.py`。随附的已构建安装包位于 `artifacts/`，上面的安装命令针对在本目录重新构建的包。

CLI 只特判 `manage`，没有正常实现 `--help`、`--version` 或 `serve --mcp`，不要用这些参数判断安装成功。常见 MCP 客户端的 JSON 配置为：

```json
{
  "mcpServers": {
    "mcmodding": {
      "command": "/usr/bin/mcmodding-mcp",
      "args": []
    }
  }
}
```

绝对命令路径也能避免旧 npm 全局安装的同名命令抢占 PATH。首次使用时服务会自动下载文档库（当前版本解压后约 720 MiB）到 `$XDG_DATA_HOME/mcmodding-mcp`；首次语义检索还会下载嵌入模型，默认落在 `$XDG_CACHE_HOME/mcmodding-mcp/transformers`（约 22 MiB）。

若本机需要通过代理才能访问 `huggingface.co`，注意 Node 内置 fetch 默认**不读** `http_proxy`/`https_proxy`：Node ≥24 可设 `NODE_USE_ENV_PROXY=1`。否则嵌入模型下载会失败，`search_fabric_docs` 退化为词法打分，仍能返回结果但排序不含向量相似度。

## AUR 提交

维护者注释已填写。包名于 2026-09-16 确认未被占用后完成首次提交，现在归本包所有；上游也仍是 v0.5.0（npm latest 与 GitHub 最新标签一致）。`namcap` 与 `devtools` 已装到本机，namcap 已重跑，`extra-x86_64-build` 干净 chroot 构建也已通过。元数据若再有改动，需要重新生成 `.SRCINFO`：

```sh
makepkg --printsrcinfo > .SRCINFO
```

**首次导入已于 2026-09-16 完成并推送**：pkgbase `mcmodding-mcp`，commit `c019df8`（`Initial import: mcmodding-mcp 0.5.0`），maintainer `xianhongtao`，页面 <https://aur.archlinux.org/packages/mcmodding-mcp>。本地 AUR 检出在 `../aur-submit`；认证走 Bitwarden 的 SSH agent（agent 中标记为 `AUR` 的密钥，指纹 `SHA256:bvnu8sOz…`），所以该目录不需要存放私钥。当时执行的步骤：

```sh
git -c init.defaultBranch=master clone ssh://aur@aur.archlinux.org/mcmodding-mcp.git ../aur-submit
cp PKGBUILD .SRCINFO xdg-cache.patch ../aur-submit/
cd ../aur-submit
git add PKGBUILD .SRCINFO xdg-cache.patch
git commit -m 'Initial import: mcmodding-mcp 0.5.0'
git push origin master
```

推送后已核验：AUR 的 cgit 上三个文件与本地逐字节一致，包记录显示 maintainer `xianhongtao`。注意 AUR 的 RPC/search 索引有延迟：推送后包页面与 cgit 立即可见，但 `rpc/v5/info`（以及依赖它的 AUR helper 搜索）可能要过一段时间才会返回结果。后续发新版本时，改 `pkgver`/`pkgrel`（或校验和）→ 重新生成 `.SRCINFO` → 在 `../aur-submit` 里重复「拷贝 → `git add` → 提交 → 推送」。本机已用 `pacman -U` 安装同一份产物（载荷与 chroot 产物逐字节一致）。

参考规范：[Node.js 打包](https://wiki.archlinux.org/title/Node.js_package_guidelines)、[PKGBUILD](https://wiki.archlinux.org/title/PKGBUILD)、[AUR 提交](https://wiki.archlinux.org/title/AUR_submission_guidelines)。
