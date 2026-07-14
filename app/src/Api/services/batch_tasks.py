import datetime
import json
import tempfile
import zipfile
from pathlib import Path

from app.src.Database import core as db

from .enhance_tasks import find_result_file


def create_batch(batch_category):
    return db.create_batch(batch_category)


def add_batch_item(batch_id, task_id, task_category, item_label=""):
    db.add_batch_item(batch_id, task_id, task_category, item_label)


def _normalize_utc_timestamp(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(" ", "T", 1) if "T" not in text and " " in text else text
    if normalized.endswith("Z") or "+" in normalized[-6:] or "-" in normalized[-6:]:
        return normalized
    return f"{normalized}+00:00"


def _batch_status(children):
    statuses = [str(item.get("status") or "").upper() for item in children]
    if not statuses:
        return "PENDING"
    if all(status == "COMPLETED" for status in statuses):
        return "COMPLETED"
    if any(status in {"PENDING", "PROCESSING"} for status in statuses):
        return "PROCESSING"
    if any(status == "FAILED" for status in statuses):
        return "FAILED"
    return "PROCESSING"


def get_batch_status(batch_id):
    batch = db.get_batch(batch_id)
    if not batch:
        return None

    # 批次状态不入队，由子任务实时聚合出来
    children = db.list_batch_items(batch_id)
    progress_values = []
    child_payload = []
    for item in children:
        progress = int(item.get("progress") or 0)
        progress_values.append(max(0, min(100, progress)))
        child_payload.append(
            {
                "task_id": item.get("task_id"),
                "task_category": item.get("task_category"),
                "item_label": item.get("item_label") or "",
                "status": item.get("status") or "PENDING",
                "progress": progress,
                "message": item.get("message") or "",
                "updated_at": _normalize_utc_timestamp(item.get("updated_at")),
            }
        )

    status = _batch_status(child_payload)
    progress = round(sum(progress_values) / len(progress_values)) if progress_values else 0
    message = f"{len([c for c in child_payload if c['status'] == 'COMPLETED'])}/{len(child_payload)} 个子任务已完成"
    if status == "FAILED":
        message = "批次中存在失败任务"
    elif status == "COMPLETED":
        message = "批次任务已完成"

    return {
        "is_batch": True,
        "batch_id": batch_id,
        "task_id": batch_id,
        "task_category": batch.get("batch_category") or "batch",
        "status": status,
        "progress": progress,
        "message": message,
        "created_at": _normalize_utc_timestamp(batch.get("created_at")),
        "updated_at": _normalize_utc_timestamp(batch.get("updated_at")),
        "children": child_payload,
    }


def make_batch_result_zip(batch_id, output_root):
    batch = get_batch_status(batch_id)
    if not batch:
        return None, "批次不存在"
    if batch["status"] != "COMPLETED":
        unfinished = [
            f"{item['task_id']}({item['status']})"
            for item in batch["children"]
            if item["status"] != "COMPLETED"
        ]
        detail = "、".join(unfinished) if unfinished else "存在未完成任务"
        return None, f"批次尚未全部完成：{detail}"

    files = []
    missing = []
    for child in batch["children"]:
        task = db.get_task(child["task_id"])
        if not task:
            missing.append(child["task_id"])
            continue
        path = find_result_file(task, output_root)
        if not path:
            missing.append(child["task_id"])
            continue
        files.append((child, path))
    if missing:
        return None, f"子任务结果文件缺失：{', '.join(missing)}"

    tmp = tempfile.NamedTemporaryFile(prefix=f"batch_{batch_id}_", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    used_names = set()
    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for child, path in files:
            task_id = child["task_id"]
            label = Path(child.get("item_label") or path.name).stem or task_id
            arcname = f"{task_id}_{label}{path.suffix}"
            # 文件名来自用户上传内容，重复时保留任务 ID 兜底
            if arcname in used_names:
                arcname = f"{task_id}_{path.name}"
            used_names.add(arcname)
            zf.write(path, arcname)
        manifest = {
            "batch_id": batch_id,
            "created_at": datetime.datetime.now().isoformat(),
            "children": batch["children"],
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return tmp_path, None
