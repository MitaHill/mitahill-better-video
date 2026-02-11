import json


def bool_from_form(form, key, default=False):
    value = form.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def int_from_form(form, key, default=0):
    value = form.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def float_from_form(form, key, default=0.0):
    value = form.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_watermark_timeline(raw):
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    out = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "label": str(item.get("label", "")).strip(),
                "enabled": bool(item.get("enabled", True)),
                "source_type": str(item.get("source_type", "text")).strip().lower(),
                "text": str(item.get("text", "")),
                "image_index": int(item.get("image_index", 0) or 0),
                "start_sec": float(item.get("start_sec", 0.0) or 0.0),
                "end_sec": float(item.get("end_sec", 0.0) or 0.0),
                "position": str(item.get("position", "bottom_right")).strip().lower(),
                "x_expr": str(item.get("x_expr", "")).strip(),
                "y_expr": str(item.get("y_expr", "")).strip(),
                "rotation_deg": float(item.get("rotation_deg", 0.0) or 0.0),
                "alpha": float(item.get("alpha", 0.45) or 0.45),
                "animation": str(item.get("animation", "none")).strip().lower(),
                "font_size": int(item.get("font_size", 26) or 26),
                "font_color": str(item.get("font_color", "white")).strip(),
            }
        )
    return out


def merge_unparsed_form_fields(form, parsed):
    """Keep unknown form fields so task params stay extensible without parser rewrites."""
    for key in form.keys():
        if key in parsed:
            continue
        values = form.getlist(key)
        parsed[key] = values if len(values) > 1 else form.get(key)
    return parsed


def get_list_field(form, key):
    if hasattr(form, "getlist"):
        return form.getlist(key)
    raw = form.get(key, [])
    if isinstance(raw, list):
        return raw
    if raw is None:
        return []
    return [raw]
