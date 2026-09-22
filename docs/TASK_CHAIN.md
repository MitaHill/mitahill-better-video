# 任务链（Task Chain）设计

状态：**设计稿，尚未实现**。本文描述在现有三条处理管线之上，增加「一次提交、多步串联」能力的方案，以及实施时必须同步修改的既有代码点。

## 1. 背景

现状下，把一个视频先转码、再超分、再转录，用户要做三次：提交 → 等待 → 下载 → 再上传。三条管线之间没有任何衔接。

需求方向来自 ComfyUI 那类「可拖拽工作流」。检阅 `Comfy-Org/ComfyUI` 后的结论是：**不照搬它的节点图模型**，只取「多步串联」这一层价值。理由：

- ComfyUI 的执行内核（`execution.py` 1446 行 + `comfy_execution/graph.py` 387 行 + `caching.py` 620 行，约 2450 行）中，最大的部分是**结果缓存**（按「节点输入 + 全部祖先签名」算 key 的 `CacheKeySetInputSignature`，配 `HierarchicalCache` / `LRUCache` / `RAMPressureCache`）。它的前提是「一张图在同一个进程、同一个 CUDA 上下文里跑完，中间结果留在内存和显存里」。本项目的架构约束正好相反：一任务一进程，进程退出即释放显存，禁止跨任务模型缓存。缓存层在本项目落不了地，删掉之后剩下的只是一个拓扑排序。
- ComfyUI 的节点粒度是「一次 CLIP 编码」「一次采样」，共几十上百个原子节点；本项目只有三条粗粒度管线。在只有三个节点的图上做 DAG 引擎，是为假想需求提前引入抽象。
- 画布本身也不能直接复用：`Comfy-Org/litegraph.js` 已于 2025-08-05 归档并入 `ComfyUI_frontend`，不再是可独立安装的包；`ComfyUI_frontend` 有 72 个运行时依赖。本项目前端目前只有 4 个运行时依赖。

值得借鉴的只有三点，且都很便宜：步骤用声明式元数据自描述、用类型字符串校验衔接合法性、**编辑用的 JSON 与执行用的 JSON 分离**。本方案采用后两点。

## 2. 范围

做：

- 一条**线性**的步骤序列：上传 → 步骤 1 → 步骤 2 → … → 结果。
- 步骤可在前端拖拽排序、增删，每步仍用现有的三套参数表单。
- 上一步的产物自动成为下一步的输入。

不做：

- 不做分叉、汇合、条件分支、循环。
- 不做并行执行。Worker 仍是单进程串行，链只是把串行排得更长。
- 不做结果缓存和部分重跑。改一个参数就整条链重跑。
- 不做自定义节点或插件机制。
- 前端不引入画布库。拖拽只用于**步骤排序**，用原生 HTML5 drag & drop，不新增依赖。

术语上对外统一叫「任务链」，不叫「工作流编辑器」，避免用户按 ComfyUI 的预期要求并行、部分重跑和自定义节点。

## 3. 方案成立的前提

这三条是从现有代码中确认的事实，方案建立在其上：

| 事实 | 位置 |
| --- | --- |
| 三条管线的输入**都是从 params 里读本地路径**：enhance 读 `params["upload_path"]`，convert 读 `params["video_files"][].upload_path`，transcribe 读 `params["media_files"][].upload_path` | `Worker/pipelines/enhancement/pipeline.py:53`、`conversion/pipeline.py:23`、`transcription/pipeline.py:104` |
| 批次容器已存在，自身不入队，状态由子任务聚合；子任务有进度时 `/api/events` 会额外向 `batch_id` 房间推一份聚合状态 | `Database/core.py:143`（`task_batch_items`）、`Api/services/batch_tasks.py`、`Api/routes/events.py:37` |
| 三个参数解析器只用 `form.get`，没有用到 `getlist`，普通 dict 可以直接传入 | `Api/task_parsers/*.py`；`get_list_field` 仅定义与导出，无调用者 |

第一条意味着：**把上一步的 `result_path` 写进下一步的 params，三条管线内部一行都不用改。**

第二条意味着：如果让「链」就是一个批次（`chain_id` 即 `batch_id`），那么实时推送、状态聚合、`GET /api/batches/<id>`、结果打包下载、管理端批次取消，全部零改动复用。

## 4. 数据模型

不新建链表，复用批次：

- `task_batches` 增加一条记录，`batch_category = "chain"`。
- 每个步骤是一个普通的 `task_queue` 行，通过 `task_batch_items` 挂到该批次。
- `task_queue` 新增两列，走现有的 `_ensure_columns()` 加列机制（`Database/core.py:560`）：
  - `chain_step INTEGER`：步骤序号，从 0 开始；非链任务为 `NULL`。
  - `chain_next_task_id TEXT`：下一步的 task_id；末步为 `NULL`。

`chain_next_task_id` 是冗余的（按 `chain_step` 排序也能推出下一步），但它让推进逻辑是一次主键查询，不需要读整个批次再排序。`list_batch_items` 现在按 `created_at, task_id` 排序（`core.py:255`），同秒创建的步骤顺序不稳，链的展示顺序一律以 `chain_step` 为准。

### 新状态 WAITING

现有终态只有 `COMPLETED` / `FAILED`，没有 `CANCELLED`（取消是写 `task_control.cancel_requested` 再把状态强制成 `FAILED`，见 `core.py:281` 的 `update_task_status`）。本方案只增加一个非终态：

- `WAITING`：链的后续步骤，输入尚未就绪。`get_next_task_atomic()` 只取 `status='PENDING'`（`core.py:432`），所以 `WAITING` 不会被 Worker 提前拾取——这是选这个方案的关键，不需要改调度器。

### 建链时一次性写全部步骤

`create_conversion_task` / `create_transcription_task` 都强耦合 Flask `request` 来取上传文件（`Api/services/conversion_tasks.py:40`、`transcription_tasks.py:54`），而链的后续步骤没有上传文件，只有一个本地路径。为了不被迫重构这两个 service，**建链时就把所有步骤的任务行一次性插好**：

- 第 0 步：走现有上传流程（`uploads.py:save_upload_to_disk`），`status = PENDING`。
- 第 1..n 步：用 `db.create_task()` 直接插行，params 里的输入路径字段留空，`status` 随后改为 `WAITING`。
- 推进时只做两件事：把上一步的 `result_path` 填进下一步 params 的输入路径字段（必要时补 `db.update_task_video_info`），然后 `PENDING`。

这样推进逻辑不需要建任务，也不碰上传层。副作用是前端在链开始前就能看到完整的步骤列表和各自的 task_id。

## 5. 执行流程

推进逻辑放在 **Worker**，不放在任务进程里——任务进程只负责自己那一步，Worker 负责排队和监督，这是现有的进程职责划分（`docs/ARCHITECTURE.md` 的 Process Model）。

落点：`worker_loop()` 中 `_run_task_process(task_id)` 返回之后调用一次 `advance_chain(task_id)`（新文件 `app/src/Worker/chain.py`）。放在返回之后而不是 `_run_task_process` 内部的 COMPLETED 分支，是为了让进程异常退出、被标记 FAILED 的路径也走一次推进检查。

`advance_chain(task_id)` 的行为：

1. 读该任务，`chain_step` 为 `NULL` 就直接返回（非链任务，零影响）。
2. 终态是 `COMPLETED`：读 `result_path`，校验（见下），写进 `chain_next_task_id` 那一步的 params，把它从 `WAITING` 改成 `PENDING`。没有下一步就结束。
3. 终态是 `FAILED`：沿 `chain_next_task_id` 把后面所有 `WAITING` 的步骤标成 `FAILED`，message 写明「上游步骤 N 失败，已跳过」。

`WAITING → PENDING` 这一步走 `db.update_task_status()`：它在 `cancel_requested` 时会把状态强制写成 `FAILED`（`core.py:293`），正好等于「链已被取消就不再推进」，不需要额外判断。

### 输入校验

`result_path` 不保证是单个媒体文件——转换多文件时会打成 zip（`conversion/pipeline.py:43`）。推进前必须校验：

- 文件存在，且不是 `.zip`；
- 扩展名对下一步的类别合法（例如转录的产物是字幕文件，不能接给超分）。

不合法就把下一步标 `FAILED` 并写清原因，**不做静默降级**，不尝试解包 zip。相应地，链的每一步限定**单输入单输出**，前端在构建时就要挡住会产出多文件的配置（多文件转换、导出帧序列）。

## 6. 取消、失败与重启恢复

| 场景 | 处理 |
| --- | --- |
| 取消整条链 | 复用 `POST /api/admin/batches/<batch_id>/cancel`。**需要改**：`Database/admin.py:354` 目前只对 `PENDING` / `PROCESSING` 的子任务取消，要把 `WAITING` 加进集合。`cancel_task` 本身（`admin.py:321`）只排除 `COMPLETED` / `FAILED`，对 `WAITING` 已经适用，不用改。 |
| 某步失败 | 见上，后续 `WAITING` 步骤标 `FAILED`。链的聚合状态经 `_batch_status()` 变成 `FAILED`。 |
| 容器重启 | **这是最容易出事的地方。** `get_unfinished_tasks()` 取 `status NOT IN ('COMPLETED','FAILED')`（`core.py:576`），`recover_tasks()` 会把返回的任务全部重置成 `PENDING`；而 `WAITING` 步骤的输入文件此时还不存在，会走进 `db.delete_task(task_id)` 被直接删掉（`Worker/loop.py:51`）。必须同时改这两处：恢复查询排除 `WAITING`，或在恢复分支里对 `chain_step` 非空的任务单独处理。 |
| 中间产物清理 | 现有 TTL 按任务清理。链跑完前，上游步骤的 `result_path` 不能被清掉——清理逻辑要把「属于未完成链的任务」排除在外。 |

## 7. API

只新增一个端点，其余复用批次接口。

### POST /api/chains

`multipart/form-data`：

| 字段 | 说明 |
| --- | --- |
| `file` | 第 0 步的输入文件 |
| `steps` | JSON 数组，每项 `{"category": "enhance｜convert｜transcribe", "params": {...}}` |

服务端对每项的 `params` 调用对应的现有解析器（`parse_enhance_task_params` 等）。解析器只用 `form.get`，传普通 dict 即可，不要复制一份解析逻辑。

响应 `201`：

```json
{ "chain_id": "<batch_id>", "task_ids": ["<step0>", "<step1>"] }
```

校验：步骤数上限（建议 5）、相邻步骤的类别衔接合法、单输入单输出约束。不合法返回 `400` 并说明是哪一步。

### 复用

- `GET /api/batches/<chain_id>`：链状态。需要小改 `batch_tasks.py`：`_batch_status()` 的「进行中」判断要把 `WAITING` 算进去；进度不再取子任务平均，改成按步加权（已完成步数 + 当前步进度）/ 总步数。
- `GET /api/batches/<chain_id>/result`：结果打包。
- Socket.IO：`join` 传 `chain_id` 即可，`events.py:37` 的批次转发已经覆盖。

## 8. 前端

落点遵守既有的模块化规则（页面只做组装，逻辑进 composables，视图分区进 components）：

- `constants/workbench.js`：`CATEGORY_PATH` / `CATEGORY_TABS` 增加 `chain: "/chain"`，标签「链式」。
- `components/workbench/chain/ChainStepList.vue`：可拖拽排序的步骤条，原生 `draggable` 属性 + `dragstart` / `dragover` / `drop`，不引入依赖。
- `components/workbench/chain/ChainStepCard.vue`：单步卡片，内部按类别复用现有的 `EnhanceTaskForm` / `ConvertTaskForm` / `TranscribeTaskForm`。**表单组件不得为链再复制一份。**
- `composables/workbench/useTaskChain.js`：步骤增删改排序、衔接合法性校验、提交。
- `composables/workbench/submission/submitChainTask.js`，在 `submission/index.js` 的 `submitterMap` 注册。

状态展示复用 `TaskStatusPanel`，按 `chain_step` 排序显示每步进度。

## 9. 需要改动的既有代码

| 文件 | 改动 |
| --- | --- |
| `Database/core.py` | `_ensure_columns()` 加两列；`get_unfinished_tasks()` 排除 `WAITING` |
| `Database/admin.py:354` | `cancel_batch` 的状态集合加 `WAITING` |
| `Worker/loop.py` | `worker_loop` 中调用 `advance_chain()`；`recover_tasks()` 对链步骤单独处理 |
| `Worker/chain.py` | 新建，推进逻辑 |
| `Api/services/chain_tasks.py` | 新建，建链 |
| `Api/routes/chains.py` | 新建，`POST /api/chains` |
| `Api/services/batch_tasks.py` | `_batch_status()` 认 `WAITING`；进度改按步加权 |
| 清理逻辑 | 未完成链的中间产物不清 |
| `docs/ARCHITECTURE.md`、`docs/API.md` | 实现时同步更新 |

管线代码（`Worker/pipelines/**`）和上传服务不改。

## 10. 验证清单

除 `docs/SOP.md` 的常规项外，本功能必须实测：

1. 三步链（转换 → 增强 → 转录）跑通，每步产物正确衔接。
2. 中间步骤失败：后续步骤标 `FAILED`，链状态 `FAILED`，不留 `WAITING` 僵尸行。
3. 链运行中取消：当前步进程被杀，`WAITING` 步骤一并终止。
4. **链运行中重启容器**：`WAITING` 步骤没有被误删、也没有被提前拾取。
5. 单任务（非链）提交不受影响——`chain_step` 为 `NULL` 的路径要回归一遍。
6. 上一步产出 zip 时，下一步给出明确报错而不是静默失败。

## 11. 已知限制

- 串行。四步链的耗时是四步之和，UI 上要说清楚。
- 整条链重跑，没有部分重跑。
- 每步单输入单输出，多文件批量与链不能同时用。
- 中间产物占磁盘，链越长占得越多。

## 12. 后续演进

如果实际出现「同一个源要同时转码和转录」这类分叉需求，再把前端的步骤条换成画布（候选 `@vue-flow/core`，MIT，解包约 1.28 MB，依赖 d3-drag / d3-zoom / d3-selection / d3-interpolate 和 `@vueuse/core`），后端把线性推进换成串行拓扑推进。线性链是 DAG 的退化情形，届时 API 契约和数据模型可以保留，不用重来。

在这个需求真实出现之前不要提前做。
