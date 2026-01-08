# Real-ESRGAN Web App 核心架构与运维 SOP

## 🚨 核心禁令：禁止在模块顶层执行重量级初始化 [CRITICAL]

**曾发故障**：Worker 进程陷入无限重启循环（Infinite Restart Loop）。
**故障分析**：在 Python 中，`import config` 会导致模块级代码在子进程中被立即执行。若在顶层执行 `nvidia-smi`、模型 SHA256 校验等操作，会导致资源竞争、IO 堵塞，最终触发子进程静默崩溃。

### ✅ 正确操作规范：
1. **延迟加载**：所有硬件审计、模型校验、GPU 信息获取必须封装在 `config.initialize_context()` 中。
2. **显式调用**：UI 主进程和 Worker 子进程必须在完成所有 `import` 后，显式调用一次 `config.initialize_context()`。
3. **防止重入**：初始化函数内必须有状态位判断，确保只执行一次。

---

## 🛡️ 进程管理与单例模式 (Streamlit 特有)

**故障现象**：容器内出现大量 `<defunct>` (僵尸) 进程，Worker 逻辑虽然正确但被重复启动。
**原因分析**：Streamlit 每次页面刷新都会重跑主脚本。如果在脚本中直接实例化管理类（如 `mgr = WorkerManager()`），会导致每次刷新都创建一个失去旧进程句柄的新实例。

### ✅ 解决方案：
- **必须**使用 `@st.cache_resource` 装饰一个 getter 函数来获取实例。
- **示例**：
  ```python
  @st.cache_resource
  def get_manager():
      return WorkerManager()
  
  mgr = get_manager() # 跨刷新保持唯一实例
  mgr.ensure_worker_running()
  ```

---

## 🚀 IO 与性能优化规范

**1. 日志级别管理**：
- **生产环境**：默认级别必须为 `logging.INFO`。
- **原因**：视频处理涉及海量分片（Tiles）运算，`DEBUG` 日志会产生百万量级的磁盘 IO 写入，极度拖慢处理速度。

**2. 内存与显存回收**：
- 每完成一个任务，必须显式调用 `gc.collect()` 和 `torch.cuda.empty_cache()`。

---

## 🛠️ 构建与部署 SOP

1. **无缓存构建**：进行逻辑变更后，优先使用 `docker build --no-cache` 以排除层干扰。
2. **集成审计测试**：
   - 构建镜像后，必须先运行临时容器执行审计脚本：
     `docker run --rm --gpus all <image_tag> python3 config.py`
   - 只有输出 `[SUCCESS]` 后，方可推送到镜像仓库或部署生产环境。
3. **端口冲突解决**：
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
- **操作顺序**：修改代码 -> 构建新镜像并打标 -> **更新 `r/docker-compose.yml` 中的镜像标签** -> 提交 Git。
- **严禁**：在 `docker-compose.yml` 指向旧镜像或标签不匹配的状态下提交代码。
- **标签规范**：推荐使用日期时间戳，如 `20260107-1530`。

**4. 紧急回滚流程**：
- 若部署后出现不可预知错误，应立即执行：
  1. `git reset --hard HEAD@{1}` (或指定哈希) 还原源码。
  2. 手动将 `docker-compose.yml` 中的镜像标签改为上一个稳定版本的 Tag。
  3. `docker-compose up -d --force-recreate` 确保旧逻辑物理生效。

---
*Last Updated: 2026-01-07*
