通过本[项目（点击前往Github）](https://github.com/MitaHill/mitahill-better-video)，你可以在一个页面即可完成：
**视频超分辨率**、**从视频中转录字幕文件**、**将外语翻译为目标语言**、**从Youtube等网站下载视频**

**通过Docker运行**，**支持nvidia GPU加速**。*能够运行什么模型，根据显卡本身能力决定。*

<!--more-->


# MitaHill Better Video - 自部署视频增强、转换与转录平台

![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
![GPU](https://img.shields.io/badge/NVIDIA-GPU-green.svg)
![Python](https://img.shields.io/badge/python-3.10-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3-black.svg)
![Vue](https://img.shields.io/badge/Vue-3-42b883.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-CUDA-orange.svg)
![GitHub last commit](https://img.shields.io/github/last-commit/MitaHill/mitahill-better-video)
![GitHub repo size](https://img.shields.io/github/repo-size/MitaHill/mitahill-better-video)

本项目，旨在帮助**转录视频**、**超分辨率增强**、**转换视频格式**、**下载视频**，且均支持批量处理；
通过容器化，可以快速部署项目，并消除系统环境不一致造成的依赖冲突等运行异常问题。


---------------

## 核心特性

- **增强** - 基于 Real-ESRGAN 进行超分辨率增强
- **转换** - 提供常用视频封装、编码和水印能力
- **转录** - 使用 Whisper 进行语音识别，生成字幕
- **翻译** - 支持 OpenAI 兼容格式的翻译服务
- **容器化** - 默认使用 Docker

---------------

## 功能概览

### 1. 增强任务

- 图片 / 视频上传处理
- Real-ESRGAN 超分增强
- 通过分段，来处理长视频
- 支持动态 GPU 编码器检测

### 2. 转换任务

- 视频格式转换
- 视频水印
- 输出编码选择

### 3. 转录任务

- Whisper 模型本地识别
- 可选择已安装模型
- 支持原文字幕、译文字幕和双语字幕
- 生成带软字幕的视频文件

### 4. 管理功能

- 任务状态总览
- GPU 使用率监控
- 容器运行日志
- 转录模型下载
- 转录模型和翻译源测试
- 管理员密码与维护模式

---------------

## 系统要求

### 硬件要求

- **CPU**: 1 核及以上
- **内存**: 8GB RAM 起步，推荐 16GB+
- **显卡**: **仅**支持 CUDA 的 NVIDIA GPU
- **显存**:
  - 4GB 显存可以运行较小 Whisper 模型和基础增强任务（运行Whisper Small模型无压力，但Medium模型会超过4G显存触发OOM）
  - 8GB 及以上体验更稳定 （推荐）
  - 大模型、长视频、高分辨率增强会增加显存压力
- **存储**: 推荐 32GB 以上可用空间，长视频处理需要更多临时空间

### 软件依赖

- Docker
- NVIDIA Driver
- NVIDIA Container Toolkit
- 可在宿主机运行 `nvidia-smi`

验证 GPU 容器环境：

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

如果使用 WSL2 部署，请先阅读 [WSL2 部署提示](docs/WSL2.md)。

---------------

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/MitaHill/mitahill-better-video.git
cd mitahill-better-video
```

### 2. 构建镜像

```bash
docker compose -f deploy/compose/docker-compose.build.yml build base_image
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

如果只是应用层代码变化，通常只需要重建应用镜像：

```bash
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

### 3. 启动服务

```bash
cd pre-run
docker compose up -d
```

### 4. 访问页面

服务默认使用 host 网络模式，访问：

```text
http://服务器地址:8501
```

本机部署时：

```text
http://127.0.0.1:8501
```

---------------

## 运行目录说明

标准运行入口是 `pre-run/`。

```text
pre-run/
├── docker-compose.yaml       # 运行用 Compose 文件
├── .env                      # 运行配置，挂载到容器 /workspace/config/.env
└── storage/                  # 持久化数据
    ├── upload/               # 上传文件
    ├── output/               # 输出结果和任务临时目录
    ├── data/                 # SQLite 数据库
    ├── logs/                 # 运行日志
    └── models/               # 转录模型缓存
```

---------------

## 模型说明

### 增强模型

项目内置 Real-ESRGAN 相关加载逻辑，常用模型包括：

- `realesrgan-x4plus`
- `realesrnet-x4plus`
- `realesr-general-x4v3`

### 转录模型

> 下载模型的地址是 OpenAI 提供。若在中国大陆连通性不佳，请使用代理软件手动进行下载，并存放在特定目录中。
> 但最推荐，运行本项目的服务器，本身可以自由访问国际互联网。见[稳定运行的软路由方案](https://www.mitahill.com/archives/1/)

转录使用Whisper，模型文件放在：

```text
pre-run/storage/models/transcription/whisper/
```

管理页面提供模型下载入口，若网络连接正常，可直接下载。


经过测试：

- GTX 960 4GB 使用 `small`，使用更大模型则OOM

---------------

## 翻译服务

翻译器仅有 **OpenAI 格式**

你可以使用：

- OpenAI 兼容云服务
- vLLM
- Ollama 的 OpenAI 兼容接口
- 其它兼容 `/v1/chat/completions` 的服务

如果本地部署模型，建议使用 vLLM 暴露 OpenAI 兼容接口。

---------------

## 使用流程

### 视频增强

1. 打开 Web 页面
2. 选择“增强”
3. 上传视频或图片
4. 选择模型、倍率、输出编码
5. 提交任务
6. 在任务状态中查看进度并下载结果

### 视频转录

1. 进入管理页面下载 Whisper 模型
2. 在转录任务中选择已安装模型
3. 选择是否翻译到目标语言
4. 提交任务
5. 下载字幕、文本或带字幕视频

当选择带字幕视频且启用翻译时，结果视频会包含三条**软**字幕轨：

- 原文
- 译文
- 双语

如果不翻译，则只嵌入原文字幕。

### 视频转换

1. 选择“转换”
2. 上传视频
3. 选择转换类型和输出编码
4. 如需水印，配置水印内容和位置
5. 提交任务并等待结果

---------------

## 常用命令

### 查看容器状态

```bash
cd pre-run
docker compose ps
```

### 查看日志

```bash
cd pre-run
docker compose logs -f better_video
```

### 重启服务

```bash
cd pre-run
docker compose up -d --force-recreate better_video
```

### 检查 Compose 配置

```bash
cd pre-run
docker compose config
```

### 手动构建应用镜像

```bash
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

---------------

## 故障排除

### 1. 容器内无法使用 GPU

先在宿主机确认：

```bash
nvidia-smi
```

再确认 Docker GPU：

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

如果宿主机 `nvidia-smi` 报错，优先处理显卡驱动。不要先改项目代码。

### 2. 没有可用 GPU 编码器

项目会根据 FFmpeg 和当前 NVIDIA 驱动能力检测编码器。旧显卡或旧驱动可能只支持：

```text
h264
h265
```

AV1 编码需要较新的显卡和驱动，不是所有 NVIDIA GPU 都支持。

### 3. Whisper medium OOM

小显存不能装下模型。如果 GPU OOM，直接换更小模型。

### 4. 任务文件需要清理

管理页面任务状态总览提供删除按钮。删除会移除任务数据库记录和相关实体文件。

---------------

## 项目结构

```text
mitahill-better-video/
├── app/
│   ├── main.py              # 服务入口
│   ├── src/                 # 后端 API、Worker、媒体处理逻辑
│   └── WebUI/               # Vue 前端
├── deploy/
│   ├── compose/             # 构建、开发、测试 Compose 文件
│   └── docker/              # 基础镜像和应用镜像 Dockerfile
├── docs/                    # 架构、API、运维文档
├── pre-run/                 # 标准运行目录
├── pyproject.toml           # uv 依赖定义
└── uv.lock                  # uv 锁定文件
```

---------------

## 开发规范

本项目的代码修改原则是：

> 易实现、稳健、最小改动、简单。

具体要求：

- 不为假想需求增加复杂抽象
- 不保留多套 fallback 逻辑
- 优先复用已有 API、数据库、Worker 和工具模块
- 模型加载失败要清晰报错，不要静默降级
- 任务结束后及时释放 GPU 模型和临时文件
- 前端只暴露确实有用、后端真实生效的配置项

Git 分支约定：

- `dev`: 日常开发分支，新功能和修复从这里开始
- `main`: 稳定分支，只合并已测试版本

每个 `dev` 提交都应完成必要验证后再提交。

推荐检查：

```bash
python3 -m compileall -q app/src
cd app/WebUI && npm run build
cd ../../pre-run && docker compose config
```

---------------

## 文档资源

- [项目文档索引](docs/README.md)
- [架构说明](docs/ARCHITECTURE.md)
- [API 说明](docs/API.md)
- [运行 SOP](docs/SOP.md)
- [真实 IP 部署](docs/DEPLOY_REAL_IP.md)
- [Compose 工作流](deploy/compose/README.md)

---------------

## 致谢

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [FFmpeg](https://ffmpeg.org/)
- [PyTorch](https://pytorch.org/)
- [Vue](https://vuejs.org/)
- [Flask](https://flask.palletsprojects.com/)
