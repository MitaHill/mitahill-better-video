"""任务链创建。

一条链就是一个 `batch_category = "chain"` 的批次，每一步是一条普通任务记录。
建链时把所有步骤一次性插好：第一步是 PENDING，后面的停在 WAITING，输入字段
留空，等 Worker 把上一步的产物填进来。这样推进逻辑不需要再建任务，也不用碰
上传层。
"""

import json

from app.src.Database import core as db
from app.src.Utils.media_items import apply_media_input

from ..task_parsers import (
    parse_conversion_task_params,
    parse_enhance_task_params,
    parse_transcription_task_params,
)
from .batch_tasks import add_batch_item, create_batch
from .uploads import new_task_dirs, save_uploaded_files

CHAIN_MAX_STEPS = 5

_PARSERS = {
    "enhance": parse_enhance_task_params,
    "convert": parse_conversion_task_params,
    "transcribe": parse_transcription_task_params,
}

_ALLOWED_ENHANCE_CODECS = {"h264", "hevc", "h265", "mpeg2video"}


def _as_form(params):
    """参数解析器是按表单写的，取到的值都是字符串。

    链的步骤参数走 JSON 传进来，复合值会是数组或对象（例如水印时间轴），直接
    交给解析器会在 `json.loads` 上炸掉，所以先还原成表单里的字符串形态。
    """
    form = {}
    for key, value in (params or {}).items():
        if isinstance(value, bool) or value is None:
            form[key] = value
        elif isinstance(value, (dict, list)):
            form[key] = json.dumps(value, ensure_ascii=False)
        else:
            form[key] = value
    return form


def _validate_steps(steps):
    if not isinstance(steps, list) or not steps:
        return "steps 不能为空"
    if len(steps) > CHAIN_MAX_STEPS:
        return f"一条链最多 {CHAIN_MAX_STEPS} 步"

    last_index = len(steps) - 1
    for index, step in enumerate(steps):
        position = index + 1
        if not isinstance(step, dict):
            return f"第 {position} 步格式不正确"
        category = str(step.get("category") or "").strip().lower()
        if category not in _PARSERS:
            return f"第 {position} 步的类别 {category or '(空)'} 不支持"
        params = step.get("params")
        if params is not None and not isinstance(params, dict):
            return f"第 {position} 步的 params 必须是对象"
        if index == last_index:
            continue
        # 中间步骤的产物要能直接喂给下一步，所以只允许单输入单输出的形态
        if category == "transcribe":
            return "转录产出的是字幕，只能放在链的最后一步"
        if category == "convert":
            mode = str((params or {}).get("convert_mode") or "transcode").strip().lower()
            if mode != "transcode":
                return f"第 {position} 步的转换模式 {mode} 会产出多个文件，只能放在最后一步"
    return None


def create_chain(upload, steps, client_ip, output_root, upload_root, logger):
    err = _validate_steps(steps)
    if err:
        return None, None, err

    parsed_steps = []
    for step in steps:
        category = str(step.get("category")).strip().lower()
        parsed_steps.append((category, _PARSERS[category](_as_form(step.get("params")))))

    # 目录先占位再建记录：task_id 的可用性同时看数据库和 run 目录，全部分配完才
    # 能把 chain_next_task_id 串起来。
    allocated = []
    for _ in parsed_steps:
        allocated.append(new_task_dirs(output_root, upload_root))

    first_task_id, _first_run_dir, first_upload_dir = allocated[0]
    media_dir = first_upload_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    saved, err = save_uploaded_files([upload], media_dir)
    if err:
        return None, None, err
    if not saved:
        return None, None, "没有可用的输入文件"

    first_category, first_params = parsed_steps[0]
    first_params, first_video_info = apply_media_input(
        first_category, first_params, saved[0]["upload_path"]
    )
    if first_category == "enhance" and first_params.get("input_type") == "Video":
        codec = str(first_video_info.get("video_codec") or "").lower()
        if codec not in _ALLOWED_ENHANCE_CODECS:
            return None, None, "仅支持 H.264/H.265/MPEG2 视频编码。"

    task_ids = [item[0] for item in allocated]
    chain_id = create_batch("chain")
    for index, (category, params) in enumerate(parsed_steps):
        task_id = task_ids[index]
        next_task_id = task_ids[index + 1] if index + 1 < len(task_ids) else None
        if index == 0:
            params, video_info = first_params, first_video_info
            status = "PENDING"
        else:
            video_info = {}
            status = "WAITING"
        db.create_task(
            task_id,
            client_ip,
            params,
            video_info,
            task_category=category,
            status=status,
            chain_step=index,
            chain_next_task_id=next_task_id,
        )
        add_batch_item(chain_id, task_id, category, item_label=f"{index + 1}.{category}")

    logger.info("Chain %s created with steps %s", chain_id, task_ids)
    return chain_id, task_ids, None
