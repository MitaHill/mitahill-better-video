import threading
import time
from collections import OrderedDict

_LOCK = threading.Lock()
_CACHE = OrderedDict()
_MAX_TASKS = 16


def set_preview(task_id, kind, image_bytes, frame_number=None):
    if not task_id or not image_bytes or kind not in ("original", "upscaled"):
        return
    now = time.time()
    with _LOCK:
        entry = _CACHE.get(task_id)
        if entry is None:
            entry = {"original": None, "upscaled": None, "last": now}
        entry[kind] = {"bytes": image_bytes, "frame": frame_number, "ts": now}
        entry["last"] = now
        _CACHE[task_id] = entry
        _CACHE.move_to_end(task_id)
        while len(_CACHE) > _MAX_TASKS:
            _CACHE.popitem(last=False)


def set_preview_from_path(task_id, kind, src_path, frame_number=None):
    try:
        image_bytes = src_path.read_bytes()
    except Exception:
        return
    set_preview(task_id, kind, image_bytes, frame_number)


def get_preview(task_id, kind):
    if not task_id or kind not in ("original", "upscaled"):
        return None, None
    with _LOCK:
        entry = _CACHE.get(task_id)
        if not entry:
            return None, None
        data = entry.get(kind)
        if not data:
            return None, None
        return data.get("bytes"), data.get("frame")


def clear_task(task_id):
    if not task_id:
        return
    with _LOCK:
        _CACHE.pop(task_id, None)
