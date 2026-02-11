import json
import logging
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.src.Utils.ffmpeg import run_ffmpeg

from .common import (
    VALID_WATERMARK_ANIMATIONS,
    VALID_WATERMARK_POSITIONS,
    to_bool,
    to_float,
    to_int,
)

logger = logging.getLogger("CONVERTER")


def _load_font(size):
    size = to_int(size, 26, min_value=10, max_value=144)
    for font_path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ):
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render_text_overlay_image(text, out_path, font_size, font_color):
    text = (text or "").strip()
    if not text:
        return None
    font = _load_font(font_size)
    dummy = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    drawer = ImageDraw.Draw(dummy)
    bbox = drawer.textbbox((0, 0), text, font=font)
    w = max(8, bbox[2] - bbox[0] + 24)
    h = max(8, bbox[3] - bbox[1] + 20)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, h), fill=(0, 0, 0, 90))
    draw.text((12, 10), text, font=font, fill=font_color or "white")
    img.save(out_path)
    return out_path


def _parse_lua_like_segments(script):
    script = (script or "").strip()
    if not script:
        return []
    cleaned = []
    for line in script.splitlines():
        stripped = line.split("--", 1)[0].strip()
        if stripped:
            cleaned.append(stripped)
    payload = " ".join(cleaned)
    if "return" in payload:
        payload = payload.split("return", 1)[1].strip()
    start = payload.find("{")
    end = payload.rfind("}")
    if start < 0 or end <= start:
        return []
    table = payload[start : end + 1]
    table = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", r'"\1":', table)
    table = table.replace("'", '"').replace("nil", "null")
    try:
        parsed = json.loads(table)
    except Exception:
        logger.warning("Failed to parse watermark_lua_script; fallback to timeline.")
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    out = []
    for item in parsed:
        if isinstance(item, dict):
            out.append(item)
    return out


def _resolve_position_expr(position, x_expr, y_expr):
    if position not in VALID_WATERMARK_POSITIONS:
        position = "bottom_right"
    if position == "top_left":
        return "24", "24"
    if position == "top_right":
        return "W-w-24", "24"
    if position == "bottom_left":
        return "24", "H-h-24"
    if position == "center":
        return "(W-w)/2", "(H-h)/2"
    if position == "custom":
        return (x_expr or "W-w-24"), (y_expr or "H-h-24")
    return "W-w-24", "H-h-24"


def _resolve_animation_expr(animation, base_x, base_y, x_expr, y_expr):
    animation = (animation or "none").lower()
    if animation not in VALID_WATERMARK_ANIMATIONS:
        animation = "none"
    if animation == "swing":
        return f"({base_x})+18*sin(2*PI*t)", f"({base_y})+6*sin(3*PI*t)"
    if animation == "dvd_bounce":
        x = "abs(mod((t*120),(2*(W-w)))-(W-w))"
        y = "abs(mod((t*90),(2*(H-h)))-(H-h))"
        return x, y
    if x_expr and y_expr:
        return x_expr, y_expr
    return base_x, base_y


def _build_watermark_segments(options, run_dir, duration_seconds):
    segments = options.get("watermark_timeline") or []
    script_segments = _parse_lua_like_segments(options.get("watermark_lua_script"))
    if script_segments:
        segments = script_segments

    enable_text = to_bool(options.get("watermark_enable_text"), False)
    enable_image = to_bool(options.get("watermark_enable_image"), False)
    default_text = (options.get("watermark_default_text") or "").strip()
    alpha_default = to_float(options.get("watermark_alpha"), 0.45, min_value=0.05, max_value=1.0)

    if not segments:
        if enable_text and default_text:
            segments = [
                {
                    "label": "A",
                    "enabled": True,
                    "source_type": "text",
                    "text": default_text,
                    "start_sec": 0,
                    "end_sec": duration_seconds,
                    "position": "bottom_right",
                    "alpha": alpha_default,
                    "rotation_deg": 0,
                    "animation": "none",
                    "font_size": 26,
                    "font_color": "white",
                }
            ]
        elif enable_image and options.get("watermark_images"):
            segments = [
                {
                    "label": "A",
                    "enabled": True,
                    "source_type": "image",
                    "image_index": 0,
                    "start_sec": 0,
                    "end_sec": duration_seconds,
                    "position": "bottom_right",
                    "alpha": alpha_default,
                    "rotation_deg": 0,
                    "animation": "none",
                }
            ]

    built = []
    watermark_images = options.get("watermark_images") or []
    compat_one = options.get("watermark_image_path")
    if compat_one and compat_one not in watermark_images:
        watermark_images = [compat_one, *watermark_images]

    text_dir = run_dir / "watermark_text"
    text_dir.mkdir(parents=True, exist_ok=True)

    for idx, raw in enumerate(segments, start=1):
        if not isinstance(raw, dict):
            continue
        if not to_bool(raw.get("enabled"), True):
            continue

        source_type = str(raw.get("source_type", "text")).lower()
        start_sec = to_float(raw.get("start_sec"), 0.0, min_value=0.0)
        end_sec = to_float(raw.get("end_sec"), duration_seconds, min_value=0.0)
        if end_sec <= start_sec:
            end_sec = max(start_sec + 0.1, duration_seconds)
        if start_sec > duration_seconds:
            continue

        alpha = to_float(raw.get("alpha"), alpha_default, min_value=0.05, max_value=1.0)
        position = str(raw.get("position", "bottom_right")).lower()
        x_expr = (raw.get("x_expr") or "").strip()
        y_expr = (raw.get("y_expr") or "").strip()
        base_x, base_y = _resolve_position_expr(position, x_expr, y_expr)
        anim = str(raw.get("animation", "none")).lower()
        x_final, y_final = _resolve_animation_expr(anim, base_x, base_y, x_expr, y_expr)
        rotation = to_float(raw.get("rotation_deg"), 0.0, min_value=-180.0, max_value=180.0)

        if source_type == "image":
            image_index = to_int(raw.get("image_index"), 0, min_value=0)
            if image_index >= len(watermark_images):
                continue
            image_path = Path(watermark_images[image_index])
            if not image_path.exists():
                continue
            built.append(
                {
                    "source_path": image_path,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "x_expr": x_final,
                    "y_expr": y_final,
                    "alpha": alpha,
                    "rotation": rotation,
                }
            )
            continue

        text = str(raw.get("text", default_text)).strip()
        if not text:
            continue
        text_png = text_dir / f"segment_{idx:03d}.png"
        font_size = to_int(raw.get("font_size"), 26, min_value=12, max_value=144)
        font_color = str(raw.get("font_color", "white") or "white")
        rendered = _render_text_overlay_image(text, text_png, font_size, font_color)
        if rendered is None:
            continue
        built.append(
            {
                "source_path": rendered,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "x_expr": x_final,
                "y_expr": y_final,
                "alpha": alpha,
                "rotation": rotation,
            }
        )

    return built


def apply_watermark_and_metadata(source_path, final_path, options, duration_seconds, run_dir):
    metadata_args = []
    for key in ("title", "author", "comment"):
        val = (options.get(f"meta_{key}") or "").strip()
        if val:
            tag = "artist" if key == "author" else key
            metadata_args += ["-metadata", f"{tag}={val}"]

    segments = _build_watermark_segments(options, run_dir, duration_seconds)
    if not segments and not metadata_args:
        if source_path != final_path:
            shutil.move(source_path, final_path)
        return

    if not segments and metadata_args:
        cmd = ["ffmpeg", "-y", "-i", str(source_path), "-c", "copy", *metadata_args, str(final_path)]
        run_ffmpeg(cmd)
        return

    cmd = ["ffmpeg", "-y", "-i", str(source_path)]
    for seg in segments:
        cmd += ["-i", str(seg["source_path"])]

    filter_parts = []
    current_label = "[0:v]"
    for idx, seg in enumerate(segments, start=1):
        wm_in = f"[{idx}:v]"
        wm_label = f"[wm{idx}]"
        next_label = f"[v{idx}]"
        alpha = to_float(seg.get("alpha"), 0.45, min_value=0.05, max_value=1.0)
        rotation = to_float(seg.get("rotation"), 0.0, min_value=-180.0, max_value=180.0)

        wm_filter = f"{wm_in}format=rgba,colorchannelmixer=aa={alpha:.3f}"
        if abs(rotation) > 1e-4:
            wm_filter += f",rotate={rotation:.6f}*PI/180:ow=rotw(iw):oh=roth(ih):c=none"
        wm_filter += wm_label
        filter_parts.append(wm_filter)

        start_sec = to_float(seg.get("start_sec"), 0.0, min_value=0.0)
        end_sec = to_float(seg.get("end_sec"), duration_seconds, min_value=0.0)
        if end_sec <= start_sec:
            end_sec = start_sec + 0.1
        enable_expr = f"between(t,{start_sec:.3f},{end_sec:.3f})"
        x_expr = seg.get("x_expr") or "W-w-24"
        y_expr = seg.get("y_expr") or "H-h-24"
        overlay = (
            f"{current_label}{wm_label}"
            f"overlay=x={x_expr}:y={y_expr}:enable='{enable_expr}'"
            f"{next_label}"
        )
        filter_parts.append(overlay)
        current_label = next_label

    cmd += ["-filter_complex", ";".join(filter_parts)]
    cmd += ["-map", current_label, "-map", "0:a?"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy"]
    cmd += metadata_args
    cmd += [str(final_path)]
    run_ffmpeg(cmd)
