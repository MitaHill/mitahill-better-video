# CI/CD 与发布说明

本文说明本项目的远程仓库策略、GitHub Actions 工作流规则、镜像标签、发行版规则，以及使用时的注意事项和常见故障处理。

工作流文件：`.github/workflows/build-images.yml`

## 1. 远程仓库策略

- 唯一远程仓库是 GitHub：`https://github.com/MitaHill/mitahill-better-video`
- 原 Gitea 仓库已停用，不再推送。Gitea 上的 `.gitea/workflows` 已迁移为 `.github/workflows`，`gitea.ref` 已改为 `github.ref`。
- 原因：构建、测试和镜像上传都放到 GitHub 托管的 Runner 上执行，避免占用本地机器和网络。
- 分支：
  - `main`：稳定分支，推送后清空 Docker Hub 仓库旧镜像并发布 `latest`。
  - `dev`：开发分支，推送后只发布 `dev` 标签，不清空仓库，不动 `latest`（见第 4 节）。
  - 两个分支的历史已经分叉，`dev` 有 `main` 没有的功能提交。工作流、Dockerfile 等 CI 相关改动需要在两个分支上都保持一致，通常先提交到 `main`，再 `cherry-pick` 到 `dev`。
- 已知遗留：Gitea 上有 PR #1、#2 的引用，其提交（`df977a3`、`d3b90c8`）和讨论内容不会自动出现在 GitHub。删除 Gitea 仓库前需要确认是否保留。

## 2. 触发规则

工作流在以下事件发生时自动运行，每次变更只触发一次：

| 事件 | 条件 | 是否构建并测试 | 是否推送 Docker Hub | 是否创建发行版 |
| --- | --- | --- | --- | --- |
| push（含提交） | 目标为 `dev` 或 `main` | 是 | 是 | 否 |
| push 标签 | 标签匹配 `v*` | 是 | 是 | 是 |
| PR 开启（`opened`） | 目标分支为 `dev` 或 `main` | 是 | 否 | 否 |
| PR 关闭（`closed`） | 目标分支为 `dev` 或 `main`，且未合并 | 是 | 否 | 否 |
| PR 关闭（`closed`） | 已合并 | 跳过 | 跳过 | 跳过 |
| 手动触发 `workflow_dispatch` | 在 Actions 页面选择分支 | 是 | 是 | 否 |

要点：

- **已合并的 PR 关闭不再触发。** 合并会产生一次目标分支的 push 事件，由 push 负责构建，避免同一次变更构建两次。
- **PR 事件不登录、不推送 Docker Hub。** 未合并的代码不能覆盖 `latest` 或 `dev` 镜像，来自 fork 的 PR 也拿不到 Secrets。
- **“提交”指 push。** GitHub 只在 push 到远程时触发，本地 commit 不会触发。
- 提交信息包含 `[skip ci]` 时，push 不会触发工作流。用于仅改文档或 Secrets 尚未配置时的提交。

### 并发

并发组为 `docker-image-build-${{ github.ref }}`，`cancel-in-progress: false`：

- 不同分支的构建互不排队。
- 同一分支连续推送时，正在运行的构建不会被取消。后续运行会排队，且排队期间如果又有更新的运行进来，较早排队的会被替换。因此连续多次快速推送同一分支时，中间的提交可能不会单独构建，最终以最新一次为准。

## 3. 构建流程

`build` 任务在 `ubuntu-latest` 上按顺序执行：

1. 拉取源码
2. 根据触发引用确定镜像标签
3. 登录 Docker Hub（PR 事件跳过）
4. 构建基础镜像 `base_better_video:20260210-2330`（`deploy/docker/base/Dockerfile`）
5. 构建应用镜像（`deploy/docker/for-app/Dockerfile`）
6. 在镜像内运行单元测试：把 `tests/` 只读挂载到 `/workspace/tests`，对 `tests/test_*.py` 全部模块执行 `python3 -m unittest -v`
7. 清空 Docker Hub 仓库旧镜像（仅 `main` 和 `v*` 标签；PR 和 `dev` 跳过，见第 4 节）
8. 推送应用镜像；`main` 和 `v*` 标签额外打 `latest`（PR 事件跳过）
9. 清理构建残留（始终执行）

构建或测试失败时，第 7、8 步都不会执行，Docker Hub 上现有镜像保持不变。

### 镜像标签

镜像仓库：`kindmitaishere/mitahill-better-video`

`main` 和 `v*` 标签的推送会同时打上“触发引用对应的标签”和 `latest` 两个标签，指向同一个镜像。`dev` 只打 `dev` 标签。所以 `latest` 始终是**最近一次稳定发布（`main` 或版本标签）构建成功的镜像**，`dev` 上的实验性提交不会覆盖它。

| 触发引用 | 镜像标签 |
| --- | --- |
| `refs/heads/main` | `latest` |
| `refs/heads/dev` | `dev` |
| `refs/tags/v*` | 与标签名相同（如 `v0.0.4-alpha`）和 `latest` |
| PR | `pr-test`（仅本地构建，不推送） |
| 其他（手动触发在非上述引用上） | `manual` |

### 为什么测试放在镜像内

依赖包括 `torch==1.13.1+cu116`、`faster-whisper`、`basicsr` 等，要求 Python 3.10 和 Linux，本地 macOS 无法直接安装运行。测试在已构建好的镜像里执行，环境与线上一致，也不占用本地资源。本地直接运行 `python3 -m unittest` 会因缺少 `flask`、`yaml` 等依赖而在导入阶段失败，这不是代码问题。

## 4. Docker Hub 仓库清理策略

为了让拉取者始终拿到最新的稳定镜像，并控制仓库体积，`main` 分支和 `v*` 标签每次推送镜像前，会先删除 `kindmitaishere/mitahill-better-video` 仓库里的**全部标签**，再推送本次的标签和 `latest`。

| 触发 | 是否清空仓库 | 推送的标签 |
| --- | --- | --- |
| `main` push | 是 | `latest` |
| `v*` 标签 | 是 | 版本标签和 `latest` |
| `dev` push | 否 | `dev` |
| PR、其他分支手动触发 | 否 | 不推送或仅推送 `manual` |

实现方式：用 Docker Hub Token 通过 Docker Hub API 登录，逐页列出并删除所有标签，直到仓库为空，最多循环 20 轮；删除失败（如 Token 权限不足）时步骤报错退出，不会继续推送。

### 为什么 `dev` 不清空、不打 `latest`

如果 `dev` 也清空并打 `latest`，`dev` 上的实验性提交构建成功后，会把 `main` 的稳定镜像删掉，并让 `latest` 指向实验版本，拉取者拿到的就不是稳定版。所以 `dev` 只推送自己的 `dev` 标签。

### 位置：构建和测试通过之后，而不是最开始

清空步骤放在“构建应用镜像”和“运行单元测试”都通过之后、推送之前，而不是整个工作流的最开始。原因是：如果一开始就删，之后构建失败，仓库会一个镜像都不剩，别人无法拉取，而且要重新构建 6 到 7 分钟才能恢复。放在测试通过之后，最终状态相同，但失败的构建不会清空仓库。

### 必须知道的后果

- **`main` 或版本标签构建成功后，`dev` 标签也会被删除。** 清空是删除全部标签，包括 `dev`。之后需要下一次 `dev` 构建才会重新出现。
- **同一时间只保留最近一次稳定发布。** 仓库里没有“按版本保留”的概念。
- **历史版本标签会失效。** 形如 `kindmitaishere/mitahill-better-video:v0.0.4-alpha` 的标签，只在该次构建刚完成时存在，下一次 `main` 或版本标签的构建成功后就会被删除。因此发行版说明里统一使用 `latest`。
- **删除不可恢复。** Docker Hub 上删除的标签无法找回，只能重新构建。
- **短暂的空窗期。** 清空到推送完成之间约几分钟，此时仓库为空，拉取会失败。
- **`main` 与 `dev` 同时构建时互不排队。** 两个分支各有独立的并发组。`dev` 只推送 `dev` 标签，不会影响 `main` 的清空与发布；但 `main` 的清空可能恰好把 `dev` 刚推送的标签删掉，下一次 `dev` 构建会恢复。

### 仓库大小为什么远大于镜像大小

Docker Hub 页面上的“仓库大小”统计的是仓库占用的全部存储，不是当前标签的大小。2026-09-20 的实际情况：仓库里只有一个 `latest` 标签（约 3.49 GB），但页面显示仓库大小约 38.1 GiB（API 的 `storage_size` 约 40.9 GB）。

原因推断（尚未通过登录后的镜像清单完全确认）：

- 删除标签只是取消了标签指向，被删标签原来指向的镜像清单变成无标签映像，这些映像的层可能仍然计入仓库大小，直到 Docker Hub 回收。官方文档没有说明回收时机。
- 每次构建都会重新生成新的层，重复推送同一个标签（`latest`、`dev`）会不断产生新的、无标签的旧映像。调试期间这个仓库被推送了十多次，每次约 3.5 GB，累计量级与 38 GiB 吻合。
- 页面上的“标签数”“仓库大小”等统计可能不是实时更新。同一时间截图显示“3 个标签”，而 API 只返回 1 个。

处理办法：在 Docker Hub 仓库页面的“镜像管理”标签页，可以查看并批量删除无标签的映像；这一步没有写进工作流。如果确认这些映像长期不回收，可以再把“删除无标签映像”做成工作流的一步，需要先用登录后的接口确认删除接口和参数。

## 5. 发行版规则

推送 `v*` 标签且 `build` 任务成功后，`release` 任务自动创建或更新对应的 GitHub 发行版。

### 预览版判定

标签**以 `alpha` 或 `beta` 结尾**，一律标记为预览版（预发行版）：

| 标签 | 类型 | 发行版标题 |
| --- | --- | --- |
| `v0.0.4-alpha` | 预览版 | `v0.0.4-alpha 预览版` |
| `v0.1.0-beta` | 预览版 | `v0.1.0-beta 预览版` |
| `v1.0.0` | 正式版 | `v1.0.0` |

判断规则是标签结尾的字符串匹配，区分大小写。`v1.0.0-alpha.1`、`v1.0.0-rc1` 这类不以 `alpha` 或 `beta` 结尾的标签会被当作正式版，需要注意命名。

### 发行版说明

说明由两部分组成：

1. 一句类型说明（预览版提示不建议用于生产环境，或“正式版。”）
2. “Docker 镜像”段落：拉取命令和容器运行命令，内容摘自 `README.md`，并附一句说明“仓库只保留最近一次构建的镜像，因此统一使用 `latest` 标签”

### README 摘取约定

`README.md` 中 `<!-- release-docker:start -->` 与 `<!-- release-docker:end -->` 之间的内容会被原样摘取到发行版说明中，不做任何替换，镜像标签保持 README 里写的 `latest`。

- 修改 Docker 命令只需要改 README 这一处，不要改工作流。
- 不要删除或改名这两个标记。缺少标记时 `release` 任务会报错退出，不会创建空说明的发行版。
- 因为第 4 节的清理策略，版本标签的镜像会在下一次 `main` 或版本标签构建后被删除，所以发行版说明里不使用版本标签。

### 如何发布一个新版本

先确认 `main` 上最新提交的构建已通过，然后在 `main` 上打标签并推送：

```bash
git checkout main
git pull
git tag v0.1.0-beta
git push origin v0.1.0-beta
```

推送后会自动：构建并测试镜像、清空 Docker Hub 仓库旧镜像、推送 `kindmitaishere/mitahill-better-video:v0.1.0-beta` 和 `latest`、创建发行版。

注意：

- 标签一旦推送，对应的镜像标签和发行版就是公开内容，删除标签不会同步撤回 Docker Hub 上的镜像。发布前请确认版本号。
- 由于第 4 节的清理策略，版本标签的镜像会在下一次 `main` 或版本标签构建成功后被删除，发行版本身（源码、说明）不受影响，但不能再靠版本标签拉取旧镜像。
- 已存在同名发行版时，工作流会更新其标题、说明和预览标记，不会重复创建。
- 更早创建的 `v0.0.1-alpha` 到 `v0.0.4-alpha` 发行版不会自动补充说明。这些版本没有在 Docker Hub 上构建过对应标签的镜像，补充拉取命令会拉不到，因此没有回填。

## 6. Secrets 与权限

必须在 GitHub 仓库的 Settings → Secrets and variables → Actions 中配置：

| 名称 | 说明 |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub 用户名，即 `kindmitaishere` |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token，权限需要 Read, Write, Delete（清空仓库需要删除权限） |

- 工作流文件里只有对这两个 Secret 的引用，没有任何明文凭据。不要把 Token 写进工作流、README 或提交记录。
- Token 泄露或轮换后，在 Docker Hub 重新生成，再更新 GitHub Secret 即可，无需改代码。
- `release` 任务使用内置 `github.token`，仅声明了 `contents: write` 权限，不需要额外配置。
- 未配置 Secrets 时，push 触发的运行会在“登录 Docker Hub”步骤失败；PR 事件不受影响。

## 7. Runner 与资源

- 使用 GitHub 托管的 `ubuntu-latest`。公开仓库的标准 Runner 不计费。构建和上传都在云端完成，不占用本地网络。
- 磁盘空间有限（标准 Runner 约 14 GB 专用磁盘）。目前基础镜像加应用镜像构建和推送一次约 6 到 7 分钟，最终镜像约 3.5 GB，尚未出现磁盘不足。如果以后镜像明显变大，可以在构建前清理 Runner 预装软件（如 `/usr/share/dotnet`、`/usr/local/lib/android`）来腾出空间。升级到付费大型 Runner 仅限 Team 或 Enterprise Cloud 组织账号，GitHub Pro 不提供。
- 目前没有开启 Docker 层缓存，每次都会重新下载依赖和模型权重，速度取决于当次网络。

## 8. Dockerfile 中与 CI 相关的注意事项

### FFmpeg 下载

基础镜像下载 BtbN 的预构建 FFmpeg：

- 使用 `releases/download/latest/` 下的固定文件名 `ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz`，并从同一位置下载 `checksums.sha256` 做校验。
- **不要使用带日期的 `autobuild-YYYY-MM-DD-...` 固定链接。** BtbN 会清理旧的 autobuild 发行版，这类链接过一段时间会变成 404，构建会以 `wget` 退出码 8 失败。这正是 `dev` 分支曾经失败的原因。
- 代价：`latest` 是滚动版本，不同时间构建得到的 FFmpeg 小版本可能不同，构建不完全可复现。如果需要完全固定版本，需要自己托管 FFmpeg 压缩包。

### 下载重试

`wget`、`curl` 的下载都加了重试：

- `wget -q --tries=5 --waitretry=5 --retry-connrefused --timeout=60`
- `curl --retry 5 --retry-all-errors`

模型权重来自 GitHub Releases 和 Hugging Face，文件很大。没有重试时，一次网络抖动（`wget` 退出码 4）就会让整个构建失败。`main` 分支曾因此失败一次，加了重试之后 `main` 和 `dev` 都构建成功。

### 其他

- 构建命令带 `--network host`，在 GitHub 托管 Runner 上可以正常工作。
- 应用镜像只 `COPY app/`，`tests/` 不在镜像里，测试步骤通过挂载提供。

## 9. 常见故障处理

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 构建基础镜像失败，日志出现 `exit code: 8` | 下载地址返回 404 或服务器错误，常见于 FFmpeg 固定日期链接失效 | 确认使用 `latest` 链接；用 `curl -I` 检查链接 |
| 构建基础镜像失败，`exit code: 4` | 下载时网络故障 | 已加重试；仍失败则在 Actions 页面重新运行 |
| 登录 Docker Hub 失败 | Secrets 未配置、名称写错，或 Token 过期或权限不足 | 检查两个 Secret，必要时重新生成 Token |
| “清空 Docker Hub 仓库旧镜像”失败 | Token 没有 Delete 权限、Docker Hub API 变化，或登录失败 | 重新生成 Read, Write, Delete 权限的 Token；此时不会推送镜像，仓库保持原状 |
| “在镜像内运行单元测试”失败 | 测试或代码有问题 | 查看日志中 `FAIL`/`ERROR` 的用例；测试失败时不会推送镜像 |
| `release` 任务报缺少 `release-docker` 标记 | README 中标记被删除或改名 | 恢复 `<!-- release-docker:start -->` 与 `<!-- release-docker:end -->` |
| 推送后没有触发运行 | 提交信息含 `[skip ci]`，或分支不是 `dev`/`main` | 去掉 `[skip ci]` 重新提交，或手动触发 |
| 提交里改了 `.github/workflows` 后运行用的还是旧规则 | push 触发的运行使用该提交里的工作流版本 | 确认目标提交已包含最新工作流；两个分支都要同步 |
| 构建中途报磁盘空间不足 | Runner 磁盘约 14 GB | 见第 7 节清理预装软件 |

## 10. 已知问题与后续注意

- `actions/checkout@v4` 目前会收到 Node.js 20 弃用提示，运行时被强制使用 Node.js 24，现阶段不影响结果，后续可升级到新版本。
- `ubuntu-latest` 预计从 2026-10-19 起迁移到 Ubuntu 26。基础镜像和构建依赖较多，迁移后建议观察一次构建结果；如需保持稳定，可把 `runs-on` 固定为 `ubuntu-24.04`。
- 清空并重新推送整个仓库意味着每次都会完整上传约 3.5 GB 镜像，没有旧层可以复用。在 GitHub 托管 Runner 上这不占用本地网络，但会拉长每次构建的耗时。
- 仓库使用 Docker Hub 个人账号 `kindmitaishere` 存放镜像。Docker Hub 对拉取次数有限额，公开使用时需要留意。

## 11. 验证状态

已在真实 GitHub Actions 上验证：

- `dev` 与 `main` 的 push 触发：构建基础镜像、构建应用镜像、运行 21 个单元测试、推送镜像，全部成功，镜像大小约 3.49 GB。
- 手动触发 `workflow_dispatch`：可用。
- 各分支的 push 只触发一次运行，不同分支并行执行。
- **清空 Docker Hub 仓库并推送 `latest`**：`main` 分支的一次真实运行（2026-09-20）中，清空步骤通过 Docker Hub API 成功删除了 `latest`、`dev`、`20260115-1522` 三个标签，随后推送 `latest`，结果仓库里只剩 `latest`（约 3.49 GB）。说明当前 Token 具有 Delete 权限。
- FFmpeg 链接失效和 `wget` 网络故障两个问题的修复。

尚未在真实环境中验证（工作流语法和逻辑已在本地检查过）：

- **“仅 `main` 和版本标签清空并打 `latest`，`dev` 只推 `dev`”的分流条件**：分流逻辑在本地对 `main`、`dev`、版本标签、PR、其他分支五种引用逐一模拟过输出。真实运行中，清空和打 `latest` 只验证过 `main` 路径，版本标签路径（额外 `docker tag`）尚未真实执行。
- **PR 开启与关闭的触发**：包括“已合并的 PR 关闭会被跳过”这一条件。
- **`v*` 标签触发的 `release` 任务**：包括预览版标记、标题、说明中的 Docker 命令，以及 `--prerelease=false` 对正式版的处理。

这两项都会在 GitHub 上产生公开内容（PR、发行版与镜像标签），需要在确认后用一个测试 PR 和一个测试标签来验证。
