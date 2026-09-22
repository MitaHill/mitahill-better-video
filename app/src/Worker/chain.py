"""任务链推进。

链上的每一步都是一条普通任务记录，靠 `chain_next_task_id` 单向串起来，还没轮到
的步骤停在 `WAITING`，不会被 `get_next_task_atomic()` 取走。Worker 在一步结束后
调用 `advance_chain()`：成功就把产物交给下一步并放行，失败就把下游整条标记失败，
不让 WAITING 步骤挂死。

推进逻辑放在 Worker 而不是任务进程里：任务进程只负责自己那一步，排队和衔接是
Worker 的职责。
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.src.Database import core as db
from app.src.Notifications.events import send_event
from app.src.Utils.media_items import (
    AUDIO_SUFFIXES,
    IMAGE_SUFFIXES,
    VIDEO_SUFFIXES,
    apply_media_input,
)

logger = logging.getLogger("WORKER")

# 每一步能接受的输入类型。转录产出的是字幕，任何一步都接不了，所以建链时就
# 要求转录只能放在最后。
ACCEPTED_SUFFIXES = {
    "enhance": VIDEO_SUFFIXES | IMAGE_SUFFIXES,
    "convert": VIDEO_SUFFIXES,
    "transcribe": VIDEO_SUFFIXES | AUDIO_SUFFIXES,
}

# 防御环状的 chain_next_task_id，正常链远短于这个数
_MAX_CHAIN_WALK = 32


def _emit(task_id, category, status, progress, message, stage):
    send_event(
        {
            "task_id": task_id,
            "task_category": category,
            "status": status,
            "progress": progress,
            "message": message,
            "stage": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def _resolve_source(prev_task, next_task):
    """校验上一步的产物能不能直接喂给下一步。不合法就明确失败，不做兜底转换。"""
    raw = str(prev_task.get("result_path") or "").strip()
    if not raw:
        return None, "上一步没有产出结果文件"

    path = Path(raw)
    if not path.is_file():
        return None, f"上一步的结果文件不存在：{raw}"

    suffix = path.suffix.lower()
    if suffix == ".zip":
        return None, "上一步产出的是压缩包，链式任务要求每一步只产出单个媒体文件"

    category = str(next_task.get("task_category") or "enhance").lower()
    accepted = ACCEPTED_SUFFIXES.get(category, VIDEO_SUFFIXES)
    if suffix not in accepted:
        return None, f"上一步产出的 {suffix or '无扩展名'} 文件不能作为{category}步骤的输入"
    return path, None


def _fail_step(task, message):
    task_id = task["task_id"]
    db.update_task_status(task_id, "FAILED", progress=task.get("progress") or 0, message=message)
    _emit(task_id, task.get("task_category"), "FAILED", task.get("progress") or 0, message, "failed")


def _fail_downstream(task, reason):
    """上游失败后，把后面还在等待的步骤一次性终止。"""
    current = task
    for _ in range(_MAX_CHAIN_WALK):
        next_id = str(current.get("chain_next_task_id") or "").strip()
        if not next_id:
            return
        nxt = db.get_task(next_id)
        if not nxt or str(nxt.get("status") or "").upper() != "WAITING":
            return
        _fail_step(nxt, reason)
        current = nxt
    logger.warning("Chain walk from task %s exceeded %s steps, stopping.", task["task_id"], _MAX_CHAIN_WALK)


def _promote_next(task):
    next_id = str(task.get("chain_next_task_id") or "").strip()
    if not next_id:
        return
    nxt = db.get_task(next_id)
    if not nxt:
        logger.warning("Chain step %s points at missing task %s.", task["task_id"], next_id)
        return
    if str(nxt.get("status") or "").upper() != "WAITING":
        # 已经推进过（或已被取消），推进保持幂等
        return

    source, err = _resolve_source(task, nxt)
    if err:
        logger.error("Chain step %s cannot start: %s", next_id, err)
        _fail_step(nxt, err)
        _fail_downstream(nxt, f"上游步骤失败：{err}")
        return

    params = json.loads(nxt.get("task_params") or "{}")
    params, video_info = apply_media_input(str(nxt.get("task_category") or "enhance").lower(), params, source)
    db.update_task_params(next_id, params)
    db.update_task_video_info(next_id, video_info)
    # 走 update_task_status 是有意的：链被取消时它会把状态直接写成 FAILED，
    # 等于自动拦下推进，不需要再判断一次取消标记。
    db.update_task_status(next_id, "PENDING", 0, "Waiting to start")
    logger.info("Chain step %s released with input %s", next_id, source)


def advance_chain(task_id):
    """一步结束后推进整条链。非链任务直接返回，对现有流程零影响。"""
    task = db.get_task(task_id)
    if not task or task.get("chain_step") is None:
        return
    status = str(task.get("status") or "").upper()
    step_no = int(task.get("chain_step") or 0) + 1
    if status == "COMPLETED":
        _promote_next(task)
    elif status == "FAILED":
        _fail_downstream(task, f"上游第 {step_no} 步失败，已跳过")


def recover_chains():
    """启动时补一次推进，防止上一步刚写完 COMPLETED 就断电留下挂死的 WAITING。"""
    try:
        pending = db.list_chain_tasks_to_advance()
    except Exception as exc:
        logger.error("Failed to scan chains during startup: %s", exc)
        return
    for task in pending:
        advance_chain(task["task_id"])
