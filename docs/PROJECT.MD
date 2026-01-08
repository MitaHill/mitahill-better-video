# MitaHill Better Video

基于 Real-ESRGAN 的高性能视频/图像超分辨率增强 Web 应用。

## 1. 项目目标
- **稳定性优先**：Fail-Fast 原则，任何核心错误必须抛出并终止。
- **前后端分离**：Flask 提供 API，Vue 负责 UI 与交互。
- **可维护性**：清晰目录结构 + 可扩展模块设计。
- **长视频可用性**：分段处理，稳定资源占用。

## 2. 核心架构
- **后端**：Flask API + Worker 子进程
- **前端**：Vue 3 + Vite（静态资源由 Flask 提供）
- **任务处理**：SQLite 任务队列 + Worker 轮询处理
- **模型运行**：Real-ESRGAN (CUDA)

## 3. 程序入口规范
- **主入口**：`app/backend/main.py`
  - 初始化配置与数据库
  - 启动 Worker 子进程
  - 启动 Flask API
- **Worker 入口**：`app/worker.py`
  - 轮询 SQLite 队列
  - 处理视频/图像并写入输出
  - 持续更新任务状态

## 4. SQLite 性能优化
**策略与约束**：
- WAL 模式：`PRAGMA journal_mode=WAL`
- 异步写入：`PRAGMA synchronous=NORMAL`
- 内存临时表：`PRAGMA temp_store=MEMORY`
- 超时：`PRAGMA busy_timeout=30000`
- 索引：`status`、`created_at`

**禁忌**：
- 禁止在 UI/接口层做长时间占用的事务
- 禁止将任务队列拆到多文件（避免锁竞争加剧）

## 5. API 约定 (Flask)
- `POST /api/tasks`：上传任务
- `GET /api/tasks/<task_id>`：查询任务状态
- `GET /api/tasks/<task_id>/preview/original`：原图预览
- `GET /api/tasks/<task_id>/preview/upscaled`：放大预览
- `GET /api/tasks/<task_id>/result`：下载结果
- `GET /api/health`：健康检查

## 6. 前端规范 (Vue)
- **样式目标**：极简、清晰、高级质感
- **视觉策略**：渐变背景 + 玻璃面板 + 有节奏动画
- **交互体验**：实时轮询 + 任务 ID 一键复制 + 下载按钮

## 7. 目录结构
```
mitahill-better-video/
  app/
    backend/             # Flask API
    frontend/            # Vue UI
    src_worker/          # Worker 核心逻辑
    worker.py            # Worker 入口
    config.py            # 统一配置
    db.py                # SQLite 操作
  config/
    .env                 # 环境变量
  deploy/
    docker/              # Dockerfiles
    compose/             # Compose 文件
  docs/                  # 设计、规范、迁移文档
  output/                # 结果与临时文件
  vendor/Real-ESRGAN/    # 上游模型代码
```

## 8. SOP 标准流程
任何改动必须遵循：
1. 计划 → 2. 修改 → 3. Git 提交 → 4. 构建审计 → 5. 推送申请 → 6. 生产同步

## 9. Roadmap
- [ ] Flask + Vue 重构完成
- [ ] SQLite 优化验证与压力测试
- [ ] 引入 API 权限与上传配额
- [ ] 前端状态可视化增强

## 10. Git 工作流与提交规范
**分支策略**：
- `develop`：主开发分支
- `main`：稳定发布分支
- 功能分支：`feat/*`、`fix/*`、`refactor/*`

**提交格式**：`<type>: <subject>`
- `feat` / `fix` / `docs` / `refactor` / `perf` / `chore`
- 主题 50 字以内，聚焦本次改动
