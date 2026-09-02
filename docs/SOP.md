# 运行与开发 SOP

## 运行规则

- 标准运行目录是 `pre-run/`。
- 持久化数据必须放在 `pre-run/storage/`。
- 不用项目根目录下的临时 `docker run` 验证正式部署，避免挂载或生成错误的存储路径。
- 服务端口是 `8501`。重启前先确认端口没有冲突。
- Compose 项目名固定为 `mitahill-better-video`，容器名保留 `better_video`。
- 标准运行容器时区使用 GMT+8（`TZ=Asia/Shanghai`）。

## 工程原则

本项目优先级固定为：

> 易实现、稳健、最小改动、简单。

- 优先复用已有 API、服务、数据库工具和 Worker 模块。
- 不为未来可能性提前增加抽象、状态机、调度器或多套路径。
- 启动、恢复、清理、模型加载必须短链路、可解释、失败清晰。
- 一个方案如果更聪明但更难维护，默认不采用。
- 前端只保留后端真实生效、用户确实需要的配置项。

## 进程模型

- `app/main.py` 是正常运行时唯一进程管理入口。
- Flask 提供 API 和静态前端。
- Worker 由主进程管理为独立子进程。
- 前端不能启动 Worker。
- 收到 SIGTERM / SIGINT 时，主进程必须干净结束 Worker。

## 初始化规则

避免在模块 import 阶段做重活。

GPU 探测、模型必要文件检查、`nvidia-smi`、模型加载等操作必须放在明确的运行初始化流程里，不写在顶层 import 中。

## 启动自检

- 启动自检默认开启，并保持最小。
- 第一件事是执行 `nvidia-smi`。失败时输出命令结果并终止进程。
- 自检可以通过已有服务/Worker 跑一个很小的 GPU 任务。
- 自检结束后必须删除任务记录和临时文件。
- 自检不能下载模型，也不能做大范围模块验证。
- 更深的验证放到管理页测试工具或人工 smoke test。

## 性能与清理

- 生产日志默认 `INFO`，避免帧级、tile 级调试日志；管理面板保存 INFO+ 日志与 Python warnings。
- 系统日志文件和数据库日志固定保留 14 天，启动时清理过期记录。
- 重模型任务必须走轻量 GPU 模型协调器。
- 加载模型前释放其它已注册模型；显存不足时清晰失败，不继续硬加载。
- 任务结束后立即释放 GPU 模型，再执行 Python / CUDA 内存清理。
- Worker 空闲时只检查自身的 PyTorch 显存。清理后仍超过 128 MiB 时，Worker 原地重启以释放异常 CUDA 上下文，不影响 Flask 和任务队列。
- 转录视频默认使用软字幕流，复制原视频和音频流。
- 翻译任务输出原文、译文、双语三种字幕；不翻译时只输出原文字幕。
- 字幕封装使用 `/workspace/storage/tmp/subtitles/` 下的安全临时文件，ffmpeg 结束后立即删除。
- 基础镜像固定使用 FFmpeg 8.1 GPL 静态构建，不使用持续变化的 master 构建，并校验下载文件 SHA256。
- 转录固定使用 Faster-Whisper 的 `large-v3` FP16 成品模型。CUDA 必需，不增加 CPU fallback。
- 模型从 Hugging Face 下载 CTranslate2 文件，不在本地转换；检查 `model.bin`、`config.json`、`tokenizer.json`、`vocabulary.json`，随后用短音频热身。`preprocessor_config.json` 不参与检查。
- 显存不足时清晰失败，不尝试降级到 CPU 或其它精度。
- 字幕与文本转录可以启用低数据传输：前端用同源托管的 ffmpeg.wasm 提取 m4a 音频后再提交，后端仍走普通转录任务路径。
- 自动过期删除任务当前禁用。任务文件和数据库记录由管理员在任务总览里显式删除；批量任务按批次 ID 折叠显示，展开后可查看子任务归属；批次状态页通过 WebSocket 接收聚合状态。

## 构建与部署

快速启动脚本是 `scripts/quick-start.sh`，用于检测环境并拉取项目。检测通过后，会自动运行 `quick-deploy`。

```bash
curl -fsSL https://raw.githubusercontent.com/MitaHill/mitahill-better-video/main/scripts/quick-start.sh | bash
```

部署脚本是 `scripts/quick-deploy.sh`，必须在项目仓库内运行，只负责构建镜像和启动容器。

```bash
bash scripts/quick-deploy.sh
```

`quick-deploy` 会检查 Debian 系统、NVIDIA GPU、Docker、DockerHub、GitHub、Docker GPU 调用能力，再执行标准构建和 `pre-run` 启动流程。
脚本会根据系统时区显示中文或英文，并自动区分 WSL2 与标准 Linux。

只检查环境：

```bash
bash scripts/quick-deploy.sh --check-only
```

允许脚本安装缺失依赖：

```bash
curl -fsSL https://raw.githubusercontent.com/MitaHill/mitahill-better-video/main/scripts/quick-start.sh | bash -s -- --install-deps
```

如果 NVIDIA GPU 和互联网正常，但 Docker 或 NVIDIA Container Toolkit 缺失，脚本会询问是否允许自动安装。

脚本模块放在 `scripts/quick-deploy-src/`。WSL2 会自动附加 `docker-compose.wsl2.yaml`，不直接修改 `pre-run/docker-compose.yaml`。

从仓库根目录构建应用镜像：

```bash
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

从 `pre-run/` 部署：

```bash
cd pre-run
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=200 better_video
```

模型打包规则：

- 小型、稳定、重复使用的模型可以随项目或镜像持久化。
- 大型模型权重放基础镜像层或显式模型卷，不提交进源码仓库。
- 默认镜像不包含 VoiceFixer、DeepFilterNet 等音频增强模型。
- FFmpeg 默认使用 Ubuntu 软件源版本，优先兼容旧 NVIDIA 驱动。
- 前端只展示当前容器和 GPU 实测可用的编码器。

## 验证清单

1. 容器运行且没有反复重启。
2. `/api/health` 返回正常。
3. 日志没有启动 traceback。
4. 前端可以通过 `8501` 打开。
5. 小任务可以提交、完成，并能在管理页删除。

常用检查：

```bash
python3 -m compileall -q app/src
cd app/WebUI && npm run build
cd ../../pre-run && docker compose config
```

行为改动需要额外跑一个小任务，确认状态、输出和日志。

## Git 工作流

- `dev`：开发分支，新功能、修复、文档改动从这里开始。
- `main`：稳定分支，只放已测试、可发布版本。
- 不直接在 `main` 开发。
- 合入 `main` 前必须先同步远程 `main`，避免覆盖别人提交。
- 不用强制推送把 `dev` 压到 `main`。
- 如果远程 `main` 有新提交，只把本次需要发布的提交合入 `main`。
- 每个 `dev` 提交都要先测试，再提交。
- 每次代码行为变化后，同步更新相关项目文档；没有文档影响时，在提交前确认无需更新。

提交信息保持短而清楚，可以使用：

- `feat:` 功能或行为变化
- `fix:` 问题修复
- `docs:` 文档
- `perf:` 性能
- `chore:` 维护

推送前检查：

```bash
git status -sb
git log --oneline --decorate -5
```

推送当前分支：

```bash
git push -u origin "$(git branch --show-current)"
```

## 版本规则

- 版本号写在 `VERSION`。
- 带 `alpha` 或 `beta` 后缀的版本都是预览版。
- 没有后缀的纯版本号才是正式发行版。
- Git 标签使用 `v` 前缀，例如 `v0.0.2-alpha`、`v0.1.0`。
- `alpha` / `beta` 标签创建 GitHub Release 时必须勾选预览版。
- 纯版本号标签创建 GitHub Release 时作为正式发行版。

示例：

| 版本号 | 标签 | Release 类型 |
| --- | --- | --- |
| `0.0.2-alpha` | `v0.0.2-alpha` | 预览版 |
| `0.1.0-beta` | `v0.1.0-beta` | 预览版 |
| `0.1.0` | `v0.1.0` | 正式发行版 |
