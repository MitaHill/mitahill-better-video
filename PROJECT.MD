# Real-ESRGAN Web App 项目企划与架构文档

## 1. 项目概述 (Project Overview)

> 本项目是一个基于 Web 的 Real-ESRGAN 图像与视频超分辨率增强工具。

* **核心目标**: 提供一个简单易用的 Web 界面，利用 Real-ESRGAN 算法对图像和视频进行高质量的超分辨率处理（Upscaling）。
* **主要功能**:
    * 支持上传图片（单张或批量）和视频文件。
    * 提供多种 Real-ESRGAN 模型选择 (`x4plus`, `anime`, `general-x4v3` 等)。
    * 支持视频处理，保留原始音频，并提供 CRF 质量控制。
    * 支持 GPU 加速 (NVIDIA CUDA) 推理。
    * 提供 Tiling (分块) 处理以优化显存使用。
* **目标用户**: 需要对老旧照片、低分辨率动漫或视频进行画质修复和增强的用户。

## 1.5 对AI开发助手的说明 (Instructions for AI Assistant)

**重要提示**：当你阅读此文档协助开发时，请务必遵守以下原则：

1. **质量至上**: 本项目的代码质量要求极高。请严格遵守本文档中的各项设计模式、命名规范和架构要求。
2. **文档驱动**: 请完整、准确地理解本文档。在生成代码时，若遇到不确定的架构决策，**必须**回溯本文档或询问用户，严禁擅自通过“猜测”来决定核心架构。
3. **逐步引导**: 不要一次性生成过于庞大的代码块。应采用逐步引导、分模块实现的方式，确保每一步都可验证。
4. **交互限制**: **AI助手不应尝试执行需要用户实时输入的交互式脚本**（如需输入的Shell脚本）。应当生成脚本并指示用户手动执行，根据反馈继续下一步。
5. **语言要求**: 请始终使用 **简体中文** 与用户进行技术沟通，确保术语准确、信息传达一致。

## 2. 技术栈 (Tech Stack)

* **编程语言**: Python 3.10
* **前端/图形框架**: Streamlit
* **后端/核心逻辑**:
    * PyTorch (Deep Learning Framework)
    * Real-ESRGAN (Super-Resolution Architecture)
    * FFmpeg (Video Processing)
* **数据存储**: SQLite3
* **依赖管理**: pip (requirements.txt / Dockerfile embedded)
* **打包/部署工具**: Docker, Docker Compose (NVIDIA Runtime)
* **版本控制**: Git

## 3. Git 工作流与规范 (Git Workflow & Standards)

本项目采用严格的分支管理规范，以确保代码库的整洁性、稳定性和可追溯性。

### 3.1 分支管理策略

* **主分支 (`main` / `master`)**: 仅存放经过完整测试、随时可发布的稳定版本代码。严禁直接 Push。
* **开发分支 (`develop`)**: 日常开发的主干分支，汇集所有已完成并通过测试的功能。
* **功能/修复分支 (`feat/xxx`, `fix/xxx`)**: 所有的开发工作**必须**在独立分支上进行。
* **规则**: 任何功能开发或 Bug 修复都需从 `develop` 检出新分支。

### 3.2 Commit 提交规范

**格式**: `<Type>: <Subject>`

* `feat`: 新功能 (Feature)
* `fix`: 修复 Bug
* `docs`: 文档修改
* `style`: 代码格式修改 (空格、缩进等)
* `refactor`: 代码重构
* `chore`: 构建过程或辅助工具的变动

## 4. 开发与部署 (Development & Deployment)

**所有运行、部署、调试均采用 Docker Compose 方式。**

### 4.1 环境要求
* NVIDIA Driver installed on host.
* NVIDIA Container Toolkit installed.
* Docker & Docker Compose.

### 4.2 运行命令
```bash
# 构建并启动服务 (Detached mode)
docker-compose up --build -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 5. 目录结构 (Directory Structure)

```text
/root/real-esrgan-web-app/
├── Dockerfile                  # Docker 构建文件
├── PROJECT.MD                  # 项目文档 (本文件)
├── README.md                   # 项目说明
├── Real-ESRGAN/                # [Submodule] Real-ESRGAN 核心代码库
│   ├── assets/                 # 静态资源
│   ├── experiments/            # 模型与实验数据
│   ├── inference_realesrgan.py # 推理脚本
│   ├── realesrgan/             # 模型定义包
│   ├── requirements.txt        # 核心依赖
│   └── ...
├── demo.gif                    # 演示动图
├── docker-compose.yml          # Docker Compose 编排文件
├── streamlit_app.py            # Streamlit 主程序入口
└── .streamlit/                 # Streamlit 配置
    └── config.toml             # 配置文件 (如上传限制)
```

## 6. 模块设计与命名规范 (Module Design & Naming)

### 6.1 职责单一化与细分
* **UI 层**: `streamlit_app.py` 负责界面渲染、状态管理 (`st.session_state`) 和用户交互。
* **逻辑层**: 调用 `Real-ESRGAN` 提供的 `RealESRGANer` 类进行推理；调用 `ffmpeg` 进行视频流处理。

### 6.2 命名规范
* **文件/模块名**: `snake_case` (e.g., `streamlit_app.py`)
* **类名**: `UpperCamelCase`
* **变量/函数名**: `snake_case`

## 7. 配置、数据与入口规范

### 7.1 程序入口
* `streamlit_app.py`: 通过 `streamlit run` 启动。

### 7.2 数据存储
* **SQLite3**: 用于存储任务元数据、用户配置或历史记录（如需）。
* **文件系统**: 临时文件和处理结果存储在 `/workspace/output` (Docker 卷)。

## 8. 日志与异常处理规范

* **日志**: 使用 Python 标准 `logging` 模块，或通过 `st.error`/`st.warning` 直接反馈给用户。
* **异常**: 捕获 `RuntimeError` (如 ffmpeg 失败, CUDA OOM) 并优雅提示用户，避免应用崩溃。

## 9. 测试与质量保证 (Testing & QA)

* **功能测试**: 确保视频/图片上传、处理、下载全流程通畅。
* **性能测试**: 监控显存使用 (VRAM)，确保 Tile Size 设置合理，避免 OOM。

## 10. 项目变更日志 (Change Logs)

| 日期 | 修改人 | 修改类型 | 变更描述 |
| --- | --- | --- | --- |
| 2026-01-07 | Gemini | docs | 初始化 PROJECT.MD，完善项目技术栈与架构描述 |
