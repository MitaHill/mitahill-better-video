import copy
import json
from typing import Any, Dict, List, Optional, Tuple

from app.src.Database import admin as db_admin
from app.src.Data.transcription_languages import (
    TRANSCRIPTION_LANGUAGE_CODES,
    TRANSCRIPTION_TARGET_LANGUAGE_CODES,
)

_SETTINGS_FORM_CONSTRAINTS = "admin_form_constraints_v1"
_VALID_LOCKS = {"free", "fixed", "range"}
_VALID_GLOBAL_LOCKS = {"free", "fixed"}
_VALID_KINDS = {"number", "enum", "boolean", "string"}


def _default_constraints() -> Dict[str, Any]:
    return {
        "version": 1,
        "categories": {
            "enhance": {
                "label": "视频增强",
                "global_lock": "free",
                "fields": {
                    "input_type": {
                        "label": "输入类型",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "Video",
                        "fixed_value": "Video",
                        "allowed_values": ["Video", "Image"],
                    },
                    "model_name": {
                        "label": "模型",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "realesrgan-x4plus",
                        "fixed_value": "realesrgan-x4plus",
                        "allowed_values": [
                            "realesrgan-x4plus",
                            "realesrnet-x4plus",
                            "realesrgan-x4plus-anime",
                            "realesr-animevideov3",
                            "realesr-general-x4v3",
                        ],
                    },
                    "upscale": {
                        "label": "放大倍率",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 3,
                        "fixed_value": 3,
                        "min_value": 2,
                        "max_value": 4,
                        "step": 1,
                    },
                    "tile": {
                        "label": "切片大小",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 256,
                        "fixed_value": 256,
                        "min_value": 64,
                        "max_value": 512,
                        "step": 64,
                    },
                    "denoise_strength": {
                        "label": "降噪强度",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.5,
                        "fixed_value": 0.5,
                        "min_value": 0.0,
                        "max_value": 1.0,
                        "step": 0.05,
                    },
                    "keep_audio": {
                        "label": "保留音轨",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": True,
                        "fixed_value": True,
                    },
                    "audio_enhance": {
                        "label": "音频增强",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "pre_denoise_mode": {
                        "label": "前置降噪",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "off",
                        "fixed_value": "off",
                        "allowed_values": ["off", "speech_enhance", "vhs_hiss"],
                    },
                    "haas_enabled": {
                        "label": "哈斯效应",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "haas_delay_ms": {
                        "label": "哈斯延迟(ms)",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 3000,
                        "step": 1,
                    },
                    "haas_lead": {
                        "label": "哈斯声道先行",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "left",
                        "fixed_value": "left",
                        "allowed_values": ["left", "right"],
                    },
                    "crf": {
                        "label": "CRF",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 18,
                        "fixed_value": 18,
                        "min_value": 10,
                        "max_value": 35,
                        "step": 1,
                    },
                    "output_codec": {
                        "label": "输出编码",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "h264",
                        "fixed_value": "h264",
                        "allowed_values": ["h264", "h265"],
                    },
                    "deinterlace": {
                        "label": "反交错",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "tile_pad": {
                        "label": "切片填充",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 10,
                        "fixed_value": 10,
                        "min_value": 0,
                        "max_value": 128,
                        "step": 1,
                    },
                    "fp16": {
                        "label": "FP16",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": True,
                        "fixed_value": True,
                    },
                },
            },
            "convert": {
                "label": "视频转换",
                "global_lock": "free",
                "fields": {
                    "convert_mode": {
                        "label": "转换类型",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "transcode",
                        "fixed_value": "transcode",
                        "allowed_values": ["transcode", "export_frames", "demux_streams"],
                    },
                    "output_format": {
                        "label": "输出格式",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "mp4",
                        "fixed_value": "mp4",
                        "allowed_values": ["mp4", "mkv", "mov", "avi"],
                    },
                    "video_codec": {
                        "label": "视频编码",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "h264",
                        "fixed_value": "h264",
                        "allowed_values": ["h264", "h265"],
                    },
                    "frame_rate": {
                        "label": "帧率",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 120,
                        "step": 1,
                    },
                    "audio_source_mode": {
                        "label": "音频来源",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "keep_original",
                        "fixed_value": "keep_original",
                        "allowed_values": ["keep_original", "replace_uploaded", "mix_uploaded"],
                    },
                    "audio_channels_mode": {
                        "label": "声道模式",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "keep",
                        "fixed_value": "keep",
                        "allowed_values": ["keep", "mono", "stereo"],
                    },
                    "haas_enabled": {
                        "label": "哈斯效应",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "haas_delay_ms": {
                        "label": "哈斯延迟",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 3000,
                        "step": 1,
                    },
                    "haas_lead": {
                        "label": "哈斯先行声道",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "left",
                        "fixed_value": "left",
                        "allowed_values": ["left", "right"],
                    },
                    "aspect_ratio": {
                        "label": "宽高比",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                        "allowed_values": ["", "16/9", "4/3", "1/1", "9/16"],
                    },
                    "second_pass_reencode": {
                        "label": "二次编码",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "deinterlace": {
                        "label": "反交错",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "flip_horizontal": {
                        "label": "左右翻转",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "flip_vertical": {
                        "label": "上下翻转",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "video_fade_in_sec": {
                        "label": "视频淡入(秒)",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.0,
                        "fixed_value": 0.0,
                        "min_value": 0.0,
                        "max_value": 30.0,
                        "step": 0.1,
                    },
                    "video_fade_out_sec": {
                        "label": "视频淡出(秒)",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.0,
                        "fixed_value": 0.0,
                        "min_value": 0.0,
                        "max_value": 30.0,
                        "step": 0.1,
                    },
                    "crf": {
                        "label": "CRF",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 18,
                        "fixed_value": 18,
                        "min_value": 10,
                        "max_value": 35,
                        "step": 1,
                    },
                    "video_bitrate_k": {
                        "label": "视频码率(kbps)",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 200000,
                        "step": 1,
                    },
                    "target_size_mb": {
                        "label": "目标大小(MB)",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.0,
                        "fixed_value": 0.0,
                        "min_value": 0.0,
                        "max_value": 102400.0,
                        "step": 0.1,
                    },
                    "target_width": {
                        "label": "目标宽度",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 16384,
                        "step": 1,
                    },
                    "target_height": {
                        "label": "目标高度",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 16384,
                        "step": 1,
                    },
                    "audio_sample_rate": {
                        "label": "采样率",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 192000,
                        "step": 1,
                    },
                    "audio_bitrate_k": {
                        "label": "音频码率(kbps)",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 192,
                        "fixed_value": 192,
                        "min_value": 32,
                        "max_value": 1024,
                        "step": 1,
                    },
                    "mute_audio": {
                        "label": "静音",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "audio_fade_in_sec": {
                        "label": "音频淡入(秒)",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.0,
                        "fixed_value": 0.0,
                        "min_value": 0.0,
                        "max_value": 30.0,
                        "step": 0.1,
                    },
                    "audio_fade_out_sec": {
                        "label": "音频淡出(秒)",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.0,
                        "fixed_value": 0.0,
                        "min_value": 0.0,
                        "max_value": 30.0,
                        "step": 0.1,
                    },
                    "audio_echo": {
                        "label": "音频回声",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "audio_echo_delay_ms": {
                        "label": "回声延迟(ms)",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 200,
                        "fixed_value": 200,
                        "min_value": 1,
                        "max_value": 3000,
                        "step": 1,
                    },
                    "audio_echo_decay": {
                        "label": "回声衰减",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.4,
                        "fixed_value": 0.4,
                        "min_value": 0.0,
                        "max_value": 1.0,
                        "step": 0.05,
                    },
                    "audio_denoise": {
                        "label": "音频降噪",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "audio_reverse": {
                        "label": "音频反向",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "audio_volume": {
                        "label": "音量倍率",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 1.0,
                        "fixed_value": 1.0,
                        "min_value": 0.0,
                        "max_value": 5.0,
                        "step": 0.1,
                    },
                    "meta_title": {
                        "label": "元数据标题",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                    },
                    "meta_author": {
                        "label": "元数据作者",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                    },
                    "meta_comment": {
                        "label": "元数据注释",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                    },
                    "watermark_enable_text": {
                        "label": "启用文字水印",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "watermark_enable_image": {
                        "label": "启用图片水印",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "watermark_default_text": {
                        "label": "默认文字水印",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                    },
                    "watermark_alpha": {
                        "label": "水印透明度",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.45,
                        "fixed_value": 0.45,
                        "min_value": 0.05,
                        "max_value": 1.0,
                        "step": 0.05,
                    },
                    "frame_export_fps": {
                        "label": "导出帧率",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 0,
                        "fixed_value": 0,
                        "min_value": 0,
                        "max_value": 120,
                        "step": 1,
                    },
                    "frame_export_fps_mode": {
                        "label": "导出帧率模式",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "manual",
                        "fixed_value": "manual",
                        "allowed_values": ["manual", "auto"],
                    },
                    "frame_export_format": {
                        "label": "导出帧格式",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "jpg",
                        "fixed_value": "jpg",
                        "allowed_values": ["jpg", "jpeg", "png", "gif", "pdf"],
                    },
                },
            },
            "transcribe": {
                "label": "视频转录",
                "global_lock": "free",
                "fields": {
                    "transcribe_mode": {
                        "label": "转录类型",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "subtitle_zip",
                        "fixed_value": "subtitle_zip",
                        "allowed_values": ["subtitle_zip", "subtitled_video", "subtitle_and_video_zip"],
                    },
                    "subtitle_format": {
                        "label": "字幕格式",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "srt",
                        "fixed_value": "srt",
                        "allowed_values": ["srt", "vtt"],
                    },
                    "whisper_model": {
                        "label": "Whisper模型",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "medium",
                        "fixed_value": "medium",
                        "allowed_values": [
                            "tiny",
                            "tiny.en",
                            "base",
                            "base.en",
                            "small",
                            "small.en",
                            "medium",
                            "medium.en",
                            "large",
                            "large-v1",
                            "large-v2",
                            "large-v3",
                            "turbo",
                            "distil-large-v2",
                            "distil-large-v3",
                        ],
                    },
                    "language": {
                        "label": "输入语言",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "auto",
                        "fixed_value": "auto",
                        "allowed_values": TRANSCRIPTION_LANGUAGE_CODES,
                    },
                    "translate_to": {
                        "label": "翻译目标语言",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                        "allowed_values": TRANSCRIPTION_TARGET_LANGUAGE_CODES,
                    },
                    "translator_provider": {
                        "label": "翻译提供器",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "none",
                        "fixed_value": "none",
                        "allowed_values": ["none", "ollama", "openai_compatible"],
                    },
                    "translator_base_url": {
                        "label": "翻译服务地址",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                    },
                    "translator_model": {
                        "label": "翻译模型",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                    },
                    "translator_api_key": {
                        "label": "翻译API Key",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                        "sensitive": True,
                    },
                    "translator_prompt": {
                        "label": "翻译提示词",
                        "kind": "string",
                        "lock": "free",
                        "default_value": "",
                        "fixed_value": "",
                    },
                    "translator_timeout_sec": {
                        "label": "翻译超时",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 120.0,
                        "fixed_value": 120.0,
                        "min_value": 1.0,
                        "max_value": 1200.0,
                        "step": 1,
                    },
                    "generate_bilingual": {
                        "label": "双语字幕",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": True,
                        "fixed_value": True,
                    },
                    "export_json": {
                        "label": "导出JSON",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "prepend_timestamps": {
                        "label": "文本附带时间戳",
                        "kind": "boolean",
                        "lock": "free",
                        "default_value": False,
                        "fixed_value": False,
                    },
                    "max_line_chars": {
                        "label": "最大行宽",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 42,
                        "fixed_value": 42,
                        "min_value": 0,
                        "max_value": 200,
                        "step": 1,
                    },
                    "temperature": {
                        "label": "温度",
                        "kind": "number",
                        "number_type": "float",
                        "lock": "range",
                        "default_value": 0.0,
                        "fixed_value": 0.0,
                        "min_value": 0.0,
                        "max_value": 1.0,
                        "step": 0.1,
                    },
                    "beam_size": {
                        "label": "Beam Size",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 5,
                        "fixed_value": 5,
                        "min_value": 1,
                        "max_value": 20,
                        "step": 1,
                    },
                    "best_of": {
                        "label": "Best Of",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 5,
                        "fixed_value": 5,
                        "min_value": 1,
                        "max_value": 20,
                        "step": 1,
                    },
                    "output_video_codec": {
                        "label": "输出视频编码",
                        "kind": "enum",
                        "lock": "free",
                        "default_value": "h264",
                        "fixed_value": "h264",
                        "allowed_values": ["h264", "h265"],
                    },
                    "output_audio_bitrate_k": {
                        "label": "输出音频码率(kbps)",
                        "kind": "number",
                        "number_type": "int",
                        "lock": "range",
                        "default_value": 192,
                        "fixed_value": 192,
                        "min_value": 32,
                        "max_value": 1024,
                        "step": 1,
                    },
                },
            },
        },
    }


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_number(value: Any, number_type: str = "float", fallback: Any = 0):
    if number_type == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return int(float(fallback)) if fallback is not None else 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback) if fallback is not None else 0.0


def _to_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _case_insensitive_pick(value: str, allowed_values: List[str]) -> Optional[str]:
    source = str(value or "").strip()
    if not source:
        return None
    for item in allowed_values:
        if source.lower() == str(item).strip().lower():
            return item
    return None


def _normalize_allowed_values(kind: str, values: Any) -> List[Any]:
    if not isinstance(values, list):
        return []
    out = []
    seen = set()
    for item in values:
        if kind == "boolean":
            normalized = bool(item)
            key = f"bool:{int(normalized)}"
        elif kind == "number":
            try:
                normalized = float(item)
                key = f"num:{normalized}"
            except (TypeError, ValueError):
                continue
        else:
            normalized = str(item)
            key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _normalize_field(field_template: Dict[str, Any], field_input: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(field_template)
    out.update({k: v for k, v in (field_input or {}).items() if k in field_template})

    kind = out.get("kind", "string")
    if kind not in _VALID_KINDS:
        kind = field_template.get("kind", "string")
        out["kind"] = kind

    lock = str(out.get("lock", "free") or "free").strip().lower()
    if lock not in _VALID_LOCKS:
        lock = "free"
    if kind != "number" and lock == "range":
        lock = "free"
    out["lock"] = lock

    if kind == "number":
        number_type = str(out.get("number_type", "float") or "float").strip().lower()
        if number_type not in {"int", "float"}:
            number_type = "float"
        out["number_type"] = number_type
        out["default_value"] = _to_number(out.get("default_value"), number_type, field_template.get("default_value"))
        out["fixed_value"] = _to_number(out.get("fixed_value"), number_type, out["default_value"])

        min_val = out.get("min_value")
        max_val = out.get("max_value")
        if min_val is not None:
            min_val = _to_number(min_val, number_type, field_template.get("min_value") or 0)
        if max_val is not None:
            max_val = _to_number(max_val, number_type, field_template.get("max_value") or 0)
        if min_val is not None and max_val is not None and min_val > max_val:
            min_val, max_val = max_val, min_val
        out["min_value"] = min_val
        out["max_value"] = max_val
        if "step" in out and out.get("step") is not None:
            out["step"] = _to_number(out.get("step"), number_type, field_template.get("step") or 1)

    elif kind == "boolean":
        out["default_value"] = _to_bool(out.get("default_value"), _to_bool(field_template.get("default_value"), False))
        out["fixed_value"] = _to_bool(out.get("fixed_value"), out["default_value"])

    else:
        out["default_value"] = _to_string(out.get("default_value"), _to_string(field_template.get("default_value"), ""))
        out["fixed_value"] = _to_string(out.get("fixed_value"), out["default_value"])

    if kind in {"enum", "string"}:
        allowed = _normalize_allowed_values("string", out.get("allowed_values"))
        out["allowed_values"] = allowed
        if allowed:
            picked_default = _case_insensitive_pick(out.get("default_value", ""), allowed)
            out["default_value"] = picked_default if picked_default is not None else allowed[0]
            picked_fixed = _case_insensitive_pick(out.get("fixed_value", ""), allowed)
            out["fixed_value"] = picked_fixed if picked_fixed is not None else out["default_value"]
    elif kind == "number":
        out["allowed_values"] = _normalize_allowed_values("number", out.get("allowed_values"))
    elif kind == "boolean":
        out["allowed_values"] = _normalize_allowed_values("boolean", out.get("allowed_values"))

    out["sensitive"] = _to_bool(out.get("sensitive"), _to_bool(field_template.get("sensitive"), False))
    return out


def normalize_form_constraints(payload: Dict[str, Any]) -> Dict[str, Any]:
    template = _default_constraints()
    raw = payload if isinstance(payload, dict) else {}

    out = {
        "version": int(raw.get("version") or template["version"]),
        "categories": {},
    }

    raw_categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
    for category, category_template in template["categories"].items():
        source = raw_categories.get(category) if isinstance(raw_categories.get(category), dict) else {}
        category_out = {
            "label": str(source.get("label") or category_template.get("label") or category),
            "global_lock": str(source.get("global_lock") or category_template.get("global_lock") or "free").strip().lower(),
            "fields": {},
        }
        if category_out["global_lock"] not in _VALID_GLOBAL_LOCKS:
            category_out["global_lock"] = "free"

        source_fields = source.get("fields") if isinstance(source.get("fields"), dict) else {}
        for field_key, field_template in category_template.get("fields", {}).items():
            field_source = source_fields.get(field_key) if isinstance(source_fields.get(field_key), dict) else {}
            category_out["fields"][field_key] = _normalize_field(field_template, field_source)

        out["categories"][category] = category_out
    return out


def _deep_merge_dict(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def ensure_form_constraints_config():
    raw = db_admin.get_setting(_SETTINGS_FORM_CONSTRAINTS)
    if raw is not None:
        return
    defaults = normalize_form_constraints(_default_constraints())
    db_admin.set_setting(_SETTINGS_FORM_CONSTRAINTS, json.dumps(defaults, ensure_ascii=False))


def get_form_constraints_config() -> Dict[str, Any]:
    raw = db_admin.get_setting(_SETTINGS_FORM_CONSTRAINTS)
    if not raw:
        return normalize_form_constraints(_default_constraints())
    try:
        payload = json.loads(raw)
    except Exception:
        return normalize_form_constraints(_default_constraints())
    return normalize_form_constraints(payload)


def get_public_form_constraints_config() -> Dict[str, Any]:
    config = get_form_constraints_config()
    public_config = copy.deepcopy(config)
    for category in public_config.get("categories", {}).values():
        for field in category.get("fields", {}).values():
            if field.get("sensitive"):
                field["default_value"] = ""
                field["fixed_value"] = ""
    return public_config


def update_form_constraints_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    current = get_form_constraints_config()
    merged = _deep_merge_dict(current, patch if isinstance(patch, dict) else {})
    normalized = normalize_form_constraints(merged)
    db_admin.set_setting(_SETTINGS_FORM_CONSTRAINTS, json.dumps(normalized, ensure_ascii=False))
    return normalized


def _sanitize_one_value(raw_value: Any, field: Dict[str, Any], effective_lock: str):
    kind = field.get("kind", "string")

    if effective_lock == "fixed":
        return copy.deepcopy(field.get("fixed_value"))

    if kind == "boolean":
        value = _to_bool(raw_value, _to_bool(field.get("default_value"), False))
        allowed = field.get("allowed_values") or []
        if allowed:
            if value not in allowed:
                return _to_bool(field.get("default_value"), False)
        return value

    if kind == "number":
        number_type = field.get("number_type", "float")
        default = field.get("default_value")
        value = _to_number(raw_value, number_type, default)

        if effective_lock == "range":
            min_val = field.get("min_value")
            max_val = field.get("max_value")
            if min_val is not None:
                value = max(min_val, value)
            if max_val is not None:
                value = min(max_val, value)

        allowed = field.get("allowed_values") or []
        if allowed and value not in allowed:
            value = _to_number(default, number_type, 0)
        return int(value) if number_type == "int" else float(value)

    text = _to_string(raw_value, _to_string(field.get("default_value"), ""))
    allowed = field.get("allowed_values") or []
    if allowed:
        picked = _case_insensitive_pick(text, allowed)
        if picked is None:
            if effective_lock == "range":
                picked = _case_insensitive_pick(field.get("default_value"), allowed)
            if picked is None:
                picked = allowed[0]
        text = picked
    return text


def apply_constraints_to_params(category: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    config = get_form_constraints_config()
    categories = config.get("categories") or {}
    category_config = categories.get(category) if isinstance(categories.get(category), dict) else None
    if not category_config:
        return params, None

    out = dict(params or {})
    global_lock = str(category_config.get("global_lock") or "free").strip().lower()
    if global_lock not in _VALID_GLOBAL_LOCKS:
        global_lock = "free"

    fields = category_config.get("fields") if isinstance(category_config.get("fields"), dict) else {}
    for field_key, field in fields.items():
        if not isinstance(field, dict):
            continue
        field_lock = str(field.get("lock") or "free").strip().lower()
        if field_lock not in _VALID_LOCKS:
            field_lock = "free"
        effective_lock = "fixed" if global_lock == "fixed" else field_lock

        raw_value = out.get(field_key, field.get("default_value"))
        out[field_key] = _sanitize_one_value(raw_value, field, effective_lock)

    return out, None
