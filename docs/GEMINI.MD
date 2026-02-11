# Gemini AI Agent 开发记录

本文档记录了 Gemini AI 在构建此项目过程中的关键工程决策与问题解决过程。

## 🧠 关键决策记录

### 1. 为什么选择“分段处理” (Segmentation)?
针对用户提出的“6小时视频+4GB显存”极端需求，传统的“全提取-全放大-全合成”流程会造成 TB 级的磁盘占用和内存溢出。我们通过 `app/src/Media/segmenter.py` 实现了 5 分钟一段的循环处理：**提取 -> 放大 -> 合成小段 -> 删除帧**。这种“切香肠”模式保证了系统对任何长度的视频都有稳定的资源占用。

### 2. 为什么舍弃 python-dotenv 库？
在 Docker 环境下，我们改为使用 `python-dotenv` 解析 `.env`，由 `app/src/Config/settings.py` 统一加载配置，避免手写解析器带来的边界问题。

### 3. API 与 Worker 的“守护关系”
为了简化部署，我们将 `app/main.py` 设为父进程，由其统一启动 Worker 子进程并管理退出。前端仅调用 API，不再负责启动 Worker。

## 🛠️ 重要修复日志

- **[重构] Flask + Vue**: 前端与后端解耦，UI 使用 Vue，API 使用 Flask。
- **[修复] 任务卡死**: Worker 统一由 `app/main.py` 启动，避免分离启动导致的任务空转。
- **[修复] 404 模型下载**: 修正了官方 Real-ESRGAN 模型库中部分模型的下载链接。
- **[优化] 显存计算**: 调整了 Tile Size 阶梯，4GB 显存现在默认使用 128 Tile 以确保绝对安全。

## ⚠️ 维护者建议

1. **SQLite 并发**: 目前由于是单 Worker 模式，SQLite 不存在写入竞争。如果未来扩展为多 Worker，请将 `db.py` 升级为 PostgreSQL。
2. **磁盘空间**: 虽然分段处理节省了空间，但长视频合成后的最终文件依然很大。建议定期运行磁盘空间检查。
3. **模型扩展**: 新模型只需放入 `/workspace/app/models/video` 并在 `app/src/Media/upscaler.py` 中注册即可。
