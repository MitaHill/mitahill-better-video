# MitaHill Better Video

基于 Real-ESRGAN 的高性能视频/图像超分辨率增强 Web 应用。

## 1. 项目目标
- **稳定性优先**：Fail-Fast 原则，任何核心错误必须抛出并终止。
- **前后端分离**：Flask 提供 API，Vue 负责 UI 与交互。
- **可维护性**：清晰目录结构 + 可扩展模块设计。
- **长视频可用性**：分段处理，稳定资源占用。
- **配置一致性**：通过 `python-dotenv` 统一加载 `.env`。

## 2. 核心架构
- **后端**：Flask API + Worker 子进程
- **前端**：Vue 3 + Vite（静态资源由 Flask 提供）
- **任务处理**：SQLite 任务队列 + Worker 轮询处理
- **模型运行**：Real-ESRGAN (CUDA)
- **日志与审计**：stdout + `logs/` 文件归档

## 3. 程序入口规范
- **主入口**：`app/main.py`
  - 初始化配置与数据库
  - 启动 Worker 子进程
  - 启动 Flask API
- **Worker 入口**：`app/src/Worker/entrypoint.py`
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
- **模块约束**：页面文件仅负责装配，业务逻辑下沉到 `composables/`，大块 UI 下沉到 `components/`
- **参考拆分**：`TaskCreatePanel -> EnhanceTaskForm + ConvertTaskForm + WatermarkTimelineEditor`
- **状态拆分**：`TaskStatusPanel -> StatusQueryHeader + StatusProgressSummary + StatusPreviewGrid + StatusParamTable`
- **深入拆分**：`EnhanceTaskForm/ConvertTaskForm` 再按参数区拆分到 `enhance/*`、`convert/*`
- **逻辑拆分**：`useWorkbenchController` 仅编排，具体职责拆分到 `composables/workbench/*`

## 7. 目录结构
```
mitahill-better-video/
  app/
    main.py                # 主入口
    models/                # 模型目录 (video/audio)
    src/                  # Python source modules
    WebUI/                # Vue UI
      src/
        pages/            # 页面壳层（仅装配）
        components/       # 可复用界面组件
          workbench/      # 工作台组件
            enhance/      # 增强参数原子组件
            convert/      # 转换参数原子组件
            status/       # 状态展示原子组件
        composables/      # 页面逻辑编排
          workbench/      # 工作台逻辑原子模块
        constants/        # 前端常量
        styles/           # 拆分样式模块
    vendor/               # 上游依赖
    src/Api/              # Flask API
    src/Audio/            # 音频增强/降噪
    src/Config/           # 统一配置
    src/Data/             # 模型校验数据
    src/Database/         # SQLite 操作
    src/Media/            # 视频/图像处理
    src/Notifications/    # 事件推送
    src/Services/         # 进程服务
    src/Utils/            # 通用工具
    src/Worker/           # 任务处理
  config/
    .env                 # 环境变量
  deploy/
    docker/              # Dockerfiles
    compose/             # Compose 文件
  docs/                  # 设计、规范、迁移文档
  storage/
    output/              # 结果与临时文件
    upload/              # 上传原始文件
    data/                # SQLite 数据库
    logs/                # 运行日志与 ffmpeg stderr
  app/vendor/Real-ESRGAN/    # 上游模型代码
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
