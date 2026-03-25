import unicodedata


_BIDI_CONTROL_CODES = {
    0x061C,
    0x200E,
    0x200F,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
}

_ZERO_WIDTH_CODES = {
    0x00AD,
    0x034F,
    0x180E,
    0x200B,
    0x200C,
    0x200D,
    0x2060,
    0xFE0E,
    0xFE0F,
    0xFEFF,
}

_FILENAME_FORBIDDEN_CHARS = set('<>:"|?*')
_FILENAME_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}


def describe_codepoint(ch: str) -> str:
    code = ord(ch)
    name = unicodedata.name(ch, "UNKNOWN")
    return f"U+{code:04X} ({name})"


def find_unsafe_text_char(value: str):
    if not isinstance(value, str):
        return None
    for ch in value:
        code = ord(ch)
        if ch in {"\n", "\r", "\t"}:
            continue
        if code < 32 or code == 127:
            return ch
        if code in _BIDI_CONTROL_CODES or code in _ZERO_WIDTH_CODES:
            return ch
        if unicodedata.category(ch) == "Cf":
            return ch
    return None


def validate_filename_text(name: str, max_len: int = 180):
    text = str(name or "")
    if not text or len(text) > max_len:
        return "文件名为空或过长。"
    bad = find_unsafe_text_char(text)
    if bad is not None:
        return f"文件名包含不安全字符 {describe_codepoint(bad)}。"
    if "/" in text or "\\" in text:
        return "文件名不能包含路径分隔符。"
    if any(ch in _FILENAME_FORBIDDEN_CHARS for ch in text):
        return "文件名包含系统保留特殊字符。"
    if text.endswith(" ") or text.endswith("."):
        return "文件名不能以空格或句点结尾。"
    if ".." in text:
        return "文件名不能包含连续句点。"
    stem = text.rsplit(".", 1)[0].strip().lower()
    if stem in _FILENAME_RESERVED_NAMES:
        return "文件名使用了系统保留名称。"
    return None


def validate_nested_text_payload(payload, path=""):
    if isinstance(payload, str):
        bad = find_unsafe_text_char(payload)
        if bad is not None:
            field_name = path or "输入内容"
            return f"{field_name} 包含不安全字符 {describe_codepoint(bad)}。"
        return None
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}" if path else str(key)
            err = validate_nested_text_payload(value, next_path)
            if err:
                return err
        return None
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            err = validate_nested_text_payload(item, next_path)
            if err:
                return err
        return None
    return None
