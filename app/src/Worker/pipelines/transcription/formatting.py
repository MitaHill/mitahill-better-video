import textwrap


def format_srt_time(seconds):
    total_ms = max(0, int(round(float(seconds or 0.0) * 1000)))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    sec = total_sec % 60
    total_min = total_sec // 60
    minute = total_min % 60
    hour = total_min // 60
    return f"{hour:02d}:{minute:02d}:{sec:02d},{ms:03d}"


def format_vtt_time(seconds):
    return format_srt_time(seconds).replace(",", ".")


def format_segment_text(text, max_line_chars):
    payload = " ".join(str(text or "").split())
    if max_line_chars <= 0:
        return payload
    lines = textwrap.wrap(payload, width=max_line_chars)
    return "\n".join(lines) if lines else payload


def segments_to_srt(segments, max_line_chars=42):
    lines = []
    for idx, segment in enumerate(segments or [], start=1):
        start = format_srt_time(segment.get("start", 0))
        end = format_srt_time(segment.get("end", 0))
        text = format_segment_text(segment.get("text", ""), max_line_chars)
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def segments_to_vtt(segments, max_line_chars=42):
    lines = ["WEBVTT", ""]
    for idx, segment in enumerate(segments or [], start=1):
        start = format_vtt_time(segment.get("start", 0))
        end = format_vtt_time(segment.get("end", 0))
        text = format_segment_text(segment.get("text", ""), max_line_chars)
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def segments_to_text(segments, prepend_timestamps=False):
    lines = []
    for segment in segments or []:
        text = " ".join(str(segment.get("text", "")).split())
        if not text:
            continue
        if prepend_timestamps:
            lines.append(f"[{format_srt_time(segment.get('start', 0))}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines).strip() + ("\n" if lines else "")
