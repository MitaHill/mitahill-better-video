# Real-ESRGAN Web App 核心架构与运维 SOP

## 🚨 核心禁令：禁止在模块顶层执行重量级初始化 [CRITICAL]

**曾发故障**：Worker 进程陷入无限重启循环（Infinite Restart Loop）。
**故障分析**：在 Python 中，`import config` 会导致模块级代码在子进程中被立即执行。若在顶层执行 `nvidia-smi`、模型 SHA256 校验等操作，会导致资源竞争、IO 堵塞，最终触发子进程静默崩溃。

### ✅ 正确操作规范：
1. **延迟加载**：所有硬件审计、模型校验、GPU 信息获取必须封装在 `config.initialize_context()` 中。
2. **显式调用**：UI 主进程和 Worker 子进程必须在完成所有 `import` 后，显式调用一次 `config.initialize_context()`。
3. **防止重入**：初始化函数内必须有状态位判断，确保只执行一次。

---

## 🛡️ 进程管理与守护策略 (Flask + Worker)

**故障现象**：Worker 未启动或被重复启动导致任务停滞。
**原因分析**：主进程未统一管理子进程生命周期，导致 Worker 丢失或僵尸进程残留。

### ✅ 解决方案：
- **唯一启动点**：只能由 `app/main.py` 启动 Worker。
- **显式退出**：主进程收到 SIGTERM/SIGINT 时，必须终止 Worker。
- **禁止 UI 拉起 Worker**：前端仅调用 API，禁止在 UI 侧创建后台进程。

---

## 🚀 IO 与性能优化规范

**1. 日志级别管理**：
- **生产环境**：默认级别必须为 `logging.INFO`。
- **原因**：视频处理涉及海量分片（Tiles）运算，`DEBUG` 日志会产生百万量级的磁盘 IO 写入，极度拖慢处理速度。

**2. 内存与显存回收**：
- 每完成一个任务，必须显式调用 `gc.collect()` 和 `torch.cuda.empty_cache()`。

---

## 🛠️ 构建与部署 SOP

1. **优先使用缓存构建**：除非排查缓存污染问题，否则使用缓存加速构建。
2. **集成审计测试（拆分流程）**：
   - **构建镜像**（完成后进入 pre-run 阶段）
   - **先修改 `pre-run/.env` 与 `pre-run/docker-compose.yaml`**（按本次构建标签与配置更新）
     - 镜像标签格式：`mitahill-better-video:YYYYMMDD-HHMM`
     - 若无特殊配置，`pre-run/.env` 保持默认（空或注释即可）
   - **在 `pre-run/` 中启动容器**（使用对应 compose）
   - **禁止直接使用项目根目录的 `docker run` 作为常规验证手段**，避免挂载到错误的 `storage/` 路径
   - **持久化目录固定在 `pre-run/storage/`**（输出、上传、数据库、日志）
   - **等待 3 秒**并检查容器运行状态
   - **查看容器日志**，确认无异常
   - **若以上均正常**，提醒用户开始测试
3. **镜像标签规范**：
   - 生产镜像统一推送到 `kindmitaishere/mitahill-better-video`
   - 标签格式：`YYMMDD-HHMM`（UTC+8）
4. **端口冲突解决**：
   - 若 8501 端口被占用，使用 `lsof -ti:8501 | xargs kill -9` 强力清理，严禁在端口冲突状态下强行重启。

---

## 🌳 Git 工作流与版本控制规范

**1. 分支策略**：
- **develop**：主开发分支。所有实验性修复、UI 调整必须在 develop 进行。
- **main**：稳定发布分支。仅在 develop 验证无误且通过“构建时审计”后方可合并。

**2. 提交准则 (Commit Message)**：
- 必须使用语义化前缀：
  - `fix:` 修复功能性 Bug（如 `ImportError`、进程死锁）。
  - `feat:` 增加新特性或优化逻辑。
  - `perf:` 性能相关变更（如 IO 优化、显存回收）。
  - `docs:` 仅文档变更（如更新 SOP）。

**3. 源码与镜像同步 [CRITICAL]**：
- **操作顺序**：修改代码 -> 构建新镜像并打标 -> **更新 `deploy/compose/docker-compose.local.yml` 中的镜像标签** -> 提交 Git。
- **严禁**：在 `deploy/compose/docker-compose.local.yml` 指向旧镜像或标签不匹配的状态下提交代码。
- **标签规范**：推荐使用日期时间戳，如 `20260107-1530`。

**4. 紧急回滚流程**：
- 若部署后出现不可预知错误，应立即执行：
  1. `git reset --hard HEAD@{1}` (或指定哈希) 还原源码。
  2. 手动将 `deploy/compose/docker-compose.local.yml` 中的镜像标签改为上一个稳定版本的 Tag。
  3. `docker-compose -f deploy/compose/docker-compose.local.yml up -d --force-recreate` 确保旧逻辑物理生效。

**5. 远端同步策略（本地为主） [CRITICAL]**：
- 本项目以**本地仓库**为主（Source of Truth），远程仓库为从。
- 任何本地新增/更新的提交与分支，都必须同步到远程，确保“本地状态 = 远程状态”。
- 每次阶段性开发完成后，至少执行以下命令（以 `github` 远程为准）：
  1. `git fetch github --prune`
  2. `git push github --all`
  3. `git push github --tags`
- 若存在多个远程，请以项目主远程（当前为 `github`）为强制同步目标；其他远程按权限与需要另行处理。

---
*Last Updated: 2026-02-11*
