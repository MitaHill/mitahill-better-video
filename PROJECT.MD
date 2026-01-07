# Real-ESRGAN Web App 项目企划与架构文档

## 1. 项目概述 (Project Overview)

> 本项目是一个基于 Web 的 Real-ESRGAN 图像与视频超分辨率增强工具。

* **核心目标**: 提供一个简单易用的 Web 界面，利用 Real-ESRGAN 算法对图像和视频进行高质量的超分辨率处理（Upscaling）。
* **主要功能**:
    * **异步任务系统**: 支持后台处理，网页关闭后任务继续运行。
    * **任务状态查询**: 通过 Task ID 实时查询进度、详情及预览图。
    * **多种模型支持**: `x4plus`, `anime`, `general-x4v3` 等。
    * **GPU 加速**: 强制使用 NVIDIA CUDA 加速推理。
    * **数据库持久化**: 使用 SQLite3 记录所有任务元数据及参数。

## 2. 技术栈 (Tech Stack)

* **编程语言**: Python 3.10
* **前端框架**: Streamlit
* **任务处理**: Python Worker 独立进程
* **深度学习**: PyTorch + Real-ESRGAN
* **多媒体处理**: FFmpeg
* **数据存储**: SQLite3 (JSON 格式存储动态参数)
* **部署工具**: Docker, Docker Compose (NVIDIA Runtime)

## 3. Git 工作流与规范

* **主分支 (main)**: 稳定发布版本。
* **开发分支 (develop)**: 日常功能汇总。
* **功能/修复分支**: `feat/xxx`, `fix/xxx`, `docs/xxx`。

## 4. 模块设计

* `streamlit_app.py`: Web UI，负责任务提交与状态展示。
* `worker.py`: 核心处理引擎，独立运行，更新数据库进度。
* `db.py`: 数据库交互层。
* `/workspace/output/run_{task_id}/`: 任务专属工作目录，存储临时帧及预览图。

## 5. 开发与部署

```bash
# 构建并启动
docker-compose up --build -d

# 查看日志
docker-compose logs -f
```

## 9. 测试与质量保证 (Testing & QA)

### 9.1 测试标准作业程序 (Testing SOP)

本项目严格执行以下测试流程，确保代码质量与环境兼容性：

1.  **修改代码**: 开发者在独立的功能或修复分支上进行代码编写。
2.  **构建**: 执行 `docker-compose build` 重新构建镜像，确保依赖和补丁正确打包。
3.  **运行**: 执行 `docker-compose up -d` 启动容器环境。
4.  **查看日志**: 执行 `docker-compose logs -f` 实时监控容器输出。
5.  **结果判定**:
    *   **若无错误**: 验证功能正常后，通知用户并准备合并代码。
    *   **若有错误**:
        *   分析日志，判断是 **代码问题** 还是 **环境问题** (如驱动缺失、显存不足等)。
        *   如果是代码问题：回退至步骤 1，修复代码。
        *   如果是环境问题：记录报错信息，尝试优化 Docker 配置或通知系统管理员调整宿主机环境。

### 9.2 核心功能测试
*   **上传测试**: 验证图片和视频上传并保存到正确目录。
*   **异步测试**: 提交任务后关闭浏览器，等待一段时间后重新输入 Task ID 查看结果。
*   **预览图测试**: 验证第一帧预览图是否正常生成并在查询页显示。

## 10. 项目变更日志 (Change Logs)

| 日期 | 修改人 | 修改类型 | 变更描述 |
| --- | --- | --- | --- |
| 2026-01-07 | Gemini | docs | 重新初始化 PROJECT.MD，并添加测试 SOP |
