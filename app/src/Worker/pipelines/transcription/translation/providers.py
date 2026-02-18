import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests


_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z]+)?\s*([\s\S]*?)```", re.MULTILINE)
_THINK_TAG_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_LANGUAGE_NAME_MAP = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ru": "Russian",
    "ar": "Arabic",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "cs": "Czech",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "el": "Greek",
    "he": "Hebrew",
    "hi": "Hindi",
    "id": "Indonesian",
    "ms": "Malay",
    "vi": "Vietnamese",
    "th": "Thai",
}


def _line_to_text(line) -> str:
    if line is None:
        return ""
    if isinstance(line, bytes):
        try:
            return line.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""
    return str(line).strip()


class BaseTranslator:
    label = "base"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        prompt: str,
        timeout_sec: float,
        fallback_mode: str = "source_text",
        runtime_mode: str = "parallel",
        translation_mode: str = "window_batch",
        context_window_size: int = 6,
        batch_window_size: int = 10,
        batch_max_chars: int = 2500,
    ):
        self.base_url = (base_url or "").strip()
        self.model = (model or "").strip()
        self.api_key = (api_key or "").strip()
        self.prompt = (prompt or "").strip()
        self.timeout_sec = float(timeout_sec or 120.0)
        mode = str(fallback_mode or "source_text").strip().lower()
        self.fallback_mode = mode if mode in {"model_full_text", "source_text"} else "source_text"
        safe_runtime_mode = str(runtime_mode or "parallel").strip().lower()
        self.runtime_mode = safe_runtime_mode if safe_runtime_mode in {"parallel", "memory_saving"} else "parallel"
        safe_translation_mode = str(translation_mode or "window_batch").strip().lower()
        self.translation_mode = safe_translation_mode if safe_translation_mode in {"window_batch", "single_sentence"} else "window_batch"
        self.context_window_size = max(1, min(int(context_window_size or 6), 50))
        self.batch_window_size = max(1, min(int(batch_window_size or 10), 50))
        self.batch_max_chars = max(500, min(int(batch_max_chars or 2500), 20000))
        # List[Tuple[user_content, assistant_content]]
        self._dialogue_rounds: List[Tuple[str, str]] = []

    def translate_text(self, text: str, target_language: str, stream_callback=None) -> str:
        raise NotImplementedError

    def translate_batch(self, batch_items: List[Dict[str, Any]], target_language: str, stream_callback=None) -> List[str]:
        raise NotImplementedError

    @staticmethod
    def _sanitize_model_text(raw_text: str) -> str:
        full_text = str(raw_text or "").strip()
        if not full_text:
            return ""
        cleaned = _THINK_TAG_RE.sub("", full_text).strip()
        return cleaned or full_text

    @staticmethod
    def _extract_code_blocks(raw_text: str) -> List[str]:
        cleaned = BaseTranslator._sanitize_model_text(raw_text)
        if not cleaned:
            return []
        out = []
        for item in _CODE_BLOCK_RE.findall(cleaned):
            candidate = str(item or "").strip()
            if candidate:
                out.append(candidate)
        return out

    def _resolve_fallback_text(self, *, model_raw_text: str, source_text: str) -> str:
        if self.fallback_mode == "source_text":
            return str(source_text or "")
        sanitized = self._sanitize_model_text(model_raw_text)
        if sanitized:
            return sanitized
        return str(source_text or "")

    def fallback_text(self, source_text: str, model_raw_text: str = "") -> str:
        return self._resolve_fallback_text(model_raw_text=model_raw_text, source_text=source_text)

    def prepare_for_task(self):
        return None

    def on_task_end(self):
        return None

    @staticmethod
    def _resolve_target_language(target_language: str):
        code = str(target_language or "").strip().lower()
        name = _LANGUAGE_NAME_MAP.get(code, code or "target-language")
        display = f"{name} ({code})" if code else name
        return code, name, display

    @staticmethod
    def _render_custom_prompt(prompt_text: str, target_language: str) -> str:
        raw = str(prompt_text or "").strip()
        if not raw:
            return ""
        code, name, display = BaseTranslator._resolve_target_language(target_language)
        rendered = (
            raw.replace("{{target_language_code}}", code)
            .replace("{{target_language_name}}", name)
            .replace("{{target_language}}", display)
        )
        return rendered

    @classmethod
    def _system_prompt(cls, target_language: str, custom_prompt: str = "") -> str:
        code, name, display = cls._resolve_target_language(target_language)
        resolved_custom = cls._render_custom_prompt(custom_prompt, target_language)
        target_line = f"Target language: {display}" if code else f"Target language: {name}"
        strict_rules = (
            "You are a professional translation engine for transcription segments.\n"
            f"{target_line}\n"
            "Never output reasoning, explanations, comments, markdown, or code fences.\n"
            "Return translated text only.\n"
            "Preserve original line breaks and text structure.\n"
            "Keep numbers, punctuation, URLs, emails, and IDs unchanged unless translation is required.\n"
            "Do not translate placeholders or markup, such as {name}, [MASK], <tag>, %s, ${VAR}.\n"
            "If the source text is empty, return an empty string."
        )
        if resolved_custom:
            return f"{resolved_custom}\n\n{strict_rules}"
        return strict_rules

    def _build_context_messages(self) -> List[Dict[str, str]]:
        rounds = list(self._dialogue_rounds or [])
        if not rounds:
            return []
        limit = max(1, int(self.context_window_size or 1))
        if len(rounds) > limit:
            # Preserve first round, clip from second round onward.
            rounds = [rounds[0], *rounds[-(limit - 1):]] if limit > 1 else [rounds[0]]
        messages: List[Dict[str, str]] = []
        for user_text, assistant_text in rounds:
            if str(user_text or "").strip():
                messages.append({"role": "user", "content": str(user_text)})
            if str(assistant_text or "").strip():
                messages.append({"role": "assistant", "content": str(assistant_text)})
        return messages

    def _remember_round(self, user_text: str, assistant_text: str):
        safe_user = str(user_text or "").strip()
        safe_assistant = self._sanitize_model_text(assistant_text)
        if not safe_user and not safe_assistant:
            return
        self._dialogue_rounds.append((safe_user, safe_assistant))

    def _build_translate_batch_user_prompt(self, batch_items: List[Dict[str, Any]], target_language: str) -> str:
        payload = [
            {
                "id": str(item.get("id") or ""),
                "text": str(item.get("text") or ""),
            }
            for item in (batch_items or [])
        ]
        payload_json = json.dumps(payload, ensure_ascii=False)
        _code, _name, display = self._resolve_target_language(target_language)
        return (
            f"Translate all segments into {display}.\n"
            "Output must be valid JSON array only with exact schema: [{\"id\":\"SEG_1\",\"text\":\"...\"}].\n"
            "Rules:\n"
            "1) Keep all ids unchanged.\n"
            "2) Output one item for each input id.\n"
            "3) Do not add or remove ids.\n"
            "4) Do not add extra fields/comments.\n"
            "5) Do not output markdown/code fences/thinking text/explanations.\n"
            "Input JSON:\n"
            f"```json\n{payload_json}\n```"
        )

    @staticmethod
    def _extract_translation_rows(obj: Any) -> Optional[List[Dict[str, Any]]]:
        if isinstance(obj, list):
            return obj
        if not isinstance(obj, dict):
            return None
        for key in ("segments", "translations", "items", "data", "result"):
            value = obj.get(key)
            if isinstance(value, list):
                return value
        return None

    def _parse_batch_result(self, raw_text: str, expected_ids: List[str]) -> Dict[str, str]:
        sanitized = self._sanitize_model_text(raw_text)
        if not sanitized:
            raise ValueError("empty translation response")

        candidates = [*self._extract_code_blocks(sanitized), sanitized]
        seen = set()
        expected = [str(item or "").strip() for item in (expected_ids or []) if str(item or "").strip()]
        expected_set = set(expected)

        for candidate in candidates:
            safe = str(candidate or "").strip()
            if not safe or safe in seen:
                continue
            seen.add(safe)
            try:
                decoded = json.loads(safe)
            except Exception:
                decoded = None
            rows = self._extract_translation_rows(decoded)
            if not rows:
                continue
            if not isinstance(rows, list):
                continue
            mapped: Dict[str, str] = {}
            invalid_rows = 0
            unknown_ids = 0
            duplicate_ids = 0
            for row in rows:
                if not isinstance(row, dict):
                    invalid_rows += 1
                    continue
                row_id = str(row.get("id") or "").strip()
                if not row_id:
                    invalid_rows += 1
                    continue
                if row_id not in expected_set:
                    unknown_ids += 1
                    continue
                if row_id in mapped:
                    duplicate_ids += 1
                    continue
                value = row.get("text")
                if value is None:
                    value = ""
                if isinstance(value, (dict, list)):
                    invalid_rows += 1
                    continue
                mapped[row_id] = str(value).strip()
            if invalid_rows or unknown_ids or duplicate_ids:
                continue
            if set(mapped.keys()) == expected_set and len(mapped) == len(expected):
                return mapped

        raise ValueError("failed to parse batch translation response")


class OllamaTranslator(BaseTranslator):
    label = "ollama"

    def _keep_alive_value(self):
        if self.runtime_mode == "parallel":
            return -1
        # Aggressive memory-saving mode: unload model after each request.
        return 0

    def prepare_for_task(self):
        if self.runtime_mode == "memory_saving":
            # Skip warmup in memory-saving mode to avoid preloading model into VRAM.
            return None
        if not self.base_url or not self.model:
            return None
        try:
            endpoint = f"{self.base_url.rstrip('/')}/api/generate"
            requests.post(
                endpoint,
                json={
                    "model": self.model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": self._keep_alive_value(),
                },
                timeout=min(self.timeout_sec, 10.0),
            )
        except Exception:
            return None
        return None

    def on_task_end(self):
        if self.runtime_mode != "memory_saving":
            return None
        if not self.base_url or not self.model:
            return None
        try:
            endpoint = f"{self.base_url.rstrip('/')}/api/generate"
            requests.post(
                endpoint,
                json={"model": self.model, "prompt": "", "stream": False, "keep_alive": 0},
                timeout=min(self.timeout_sec, 10.0),
            )
        except Exception:
            return None
        return None

    def _resolve_translated(self, source_text: str, model_raw_text: str) -> str:
        code_blocks = self._extract_code_blocks(model_raw_text)
        if code_blocks:
            return code_blocks[0]
        return self._resolve_fallback_text(model_raw_text=model_raw_text, source_text=source_text)

    def _translate_streaming(self, endpoint: str, payload: dict, stream_callback) -> str:
        raw_parts = []
        with requests.post(endpoint, json=payload, timeout=self.timeout_sec, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                safe_line = _line_to_text(line)
                if not safe_line:
                    continue
                try:
                    packet = json.loads(safe_line)
                except Exception:
                    continue
                delta = str(((packet.get("message") or {}).get("content") or ""))
                if delta:
                    raw_parts.append(delta)
                    if stream_callback:
                        stream_callback(delta)
                if packet.get("done") is True:
                    break
        if not raw_parts:
            raise RuntimeError("ollama stream returned no content")
        return "".join(raw_parts).strip()

    def _translate_non_stream(self, endpoint: str, payload: dict, stream_callback=None) -> str:
        payload = dict(payload or {})
        payload["stream"] = False
        response = requests.post(endpoint, json=payload, timeout=self.timeout_sec)
        response.raise_for_status()
        data = response.json()
        content = ((data.get("message") or {}).get("content") or "").strip()
        if stream_callback and content:
            stream_callback(content)
        return content

    def _chat(self, messages: List[Dict[str, str]], stream_callback=None) -> str:
        if not self.base_url or not self.model:
            raise ValueError("Ollama translator requires translator_base_url and translator_model.")
        endpoint = f"{self.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "stream": bool(stream_callback),
            "messages": messages,
            "options": {"temperature": 0.2, "top_p": 0.9},
            "keep_alive": self._keep_alive_value(),
        }
        if stream_callback:
            try:
                return self._translate_streaming(endpoint, payload, stream_callback)
            except Exception:
                return self._translate_non_stream(endpoint, payload, stream_callback=stream_callback)
        return self._translate_non_stream(endpoint, payload)

    def translate_text(self, text: str, target_language: str, stream_callback=None) -> str:
        source_text = str(text or "")
        user_prompt = source_text
        messages = [
            {"role": "system", "content": self._system_prompt(target_language, self.prompt)},
            *self._build_context_messages(),
            {"role": "user", "content": user_prompt},
        ]
        content = self._chat(messages, stream_callback=stream_callback)
        translated = " ".join(str(self._resolve_translated(source_text, content) or "").split())
        self._remember_round(f"TEXT SOURCE:\n{source_text}", f"TEXT TARGET:\n{translated}")
        return translated

    def translate_batch(self, batch_items: List[Dict[str, Any]], target_language: str, stream_callback=None) -> List[str]:
        safe_items = []
        for item in batch_items or []:
            seg_idx = int(item.get("segment_index") or 0)
            text = str(item.get("text") or "")
            if seg_idx <= 0:
                continue
            safe_items.append({"id": f"SEG_{seg_idx}", "text": text, "segment_index": seg_idx})
        if not safe_items:
            return []

        user_prompt = self._build_translate_batch_user_prompt(safe_items, target_language)
        messages = [
            {"role": "system", "content": self._system_prompt(target_language, self.prompt)},
            *self._build_context_messages(),
            {"role": "user", "content": user_prompt},
        ]
        content = self._chat(messages, stream_callback=stream_callback)
        expected_ids = [str(item.get("id") or "") for item in safe_items]
        parsed = self._parse_batch_result(content, expected_ids)

        out = []
        memory_source_lines = []
        memory_target_lines = []
        for item in safe_items:
            seg_id = str(item.get("id") or "")
            translated = " ".join(str(parsed.get(seg_id) or "").split())
            out.append(translated)
            memory_source_lines.append(f"{seg_id}: {item.get('text', '')}")
            memory_target_lines.append(f"{seg_id}: {translated}")

        self._remember_round(
            "BATCH SOURCE:\n" + "\n".join(memory_source_lines),
            "BATCH TARGET:\n" + "\n".join(memory_target_lines),
        )
        return out


class OpenAICompatibleTranslator(BaseTranslator):
    label = "openai_compatible"

    def _endpoint(self) -> str:
        raw = self.base_url.rstrip("/")
        if raw.endswith("/chat/completions"):
            return raw
        return f"{raw}/chat/completions"

    def _resolve_translated(self, source_text: str, model_raw_text: str) -> str:
        code_blocks = self._extract_code_blocks(model_raw_text)
        if code_blocks:
            return code_blocks[0]
        return self._resolve_fallback_text(model_raw_text=model_raw_text, source_text=source_text)

    def _translate_streaming(self, endpoint: str, headers: dict, payload: dict, stream_callback) -> str:
        raw_parts = []
        with requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout_sec, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                safe_line = _line_to_text(line)
                if not safe_line.startswith("data:"):
                    continue
                data_text = safe_line[5:].strip()
                if not data_text or data_text == "[DONE]":
                    continue
                try:
                    packet = json.loads(data_text)
                except Exception:
                    continue
                choices = packet.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = str(delta.get("content") or "")
                if piece:
                    raw_parts.append(piece)
                    if stream_callback:
                        stream_callback(piece)
        if not raw_parts:
            raise RuntimeError("openai stream returned no content")
        return "".join(raw_parts).strip()

    def _translate_non_stream(self, endpoint: str, headers: dict, payload: dict, stream_callback=None) -> str:
        payload = dict(payload or {})
        payload["stream"] = False
        response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout_sec)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if stream_callback and content:
            stream_callback(content)
        return content

    def _chat(self, messages: List[Dict[str, str]], stream_callback=None) -> str:
        if not self.base_url or not self.model:
            raise ValueError("OpenAI-compatible translator requires translator_base_url and translator_model.")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": bool(stream_callback),
        }
        endpoint = self._endpoint()
        if stream_callback:
            try:
                return self._translate_streaming(endpoint, headers, payload, stream_callback)
            except Exception:
                return self._translate_non_stream(endpoint, headers, payload, stream_callback=stream_callback)
        return self._translate_non_stream(endpoint, headers, payload)

    def translate_text(self, text: str, target_language: str, stream_callback=None) -> str:
        source_text = str(text or "")
        user_prompt = source_text
        messages = [
            {"role": "system", "content": self._system_prompt(target_language, self.prompt)},
            *self._build_context_messages(),
            {"role": "user", "content": user_prompt},
        ]
        content = self._chat(messages, stream_callback=stream_callback)
        translated = " ".join(str(self._resolve_translated(source_text, content) or "").split())
        self._remember_round(f"TEXT SOURCE:\n{source_text}", f"TEXT TARGET:\n{translated}")
        return translated

    def translate_batch(self, batch_items: List[Dict[str, Any]], target_language: str, stream_callback=None) -> List[str]:
        safe_items = []
        for item in batch_items or []:
            seg_idx = int(item.get("segment_index") or 0)
            text = str(item.get("text") or "")
            if seg_idx <= 0:
                continue
            safe_items.append({"id": f"SEG_{seg_idx}", "text": text, "segment_index": seg_idx})
        if not safe_items:
            return []

        user_prompt = self._build_translate_batch_user_prompt(safe_items, target_language)
        messages = [
            {"role": "system", "content": self._system_prompt(target_language, self.prompt)},
            *self._build_context_messages(),
            {"role": "user", "content": user_prompt},
        ]
        content = self._chat(messages, stream_callback=stream_callback)
        expected_ids = [str(item.get("id") or "") for item in safe_items]
        parsed = self._parse_batch_result(content, expected_ids)

        out = []
        memory_source_lines = []
        memory_target_lines = []
        for item in safe_items:
            seg_id = str(item.get("id") or "")
            translated = " ".join(str(parsed.get(seg_id) or "").split())
            out.append(translated)
            memory_source_lines.append(f"{seg_id}: {item.get('text', '')}")
            memory_target_lines.append(f"{seg_id}: {translated}")

        self._remember_round(
            "BATCH SOURCE:\n" + "\n".join(memory_source_lines),
            "BATCH TARGET:\n" + "\n".join(memory_target_lines),
        )
        return out


def create_translator(options) -> Optional[BaseTranslator]:
    provider = (options.get("translator_provider") or "none").strip().lower()
    if provider == "none" or not (options.get("translate_to") or "").strip():
        return None

    kwargs = {
        "base_url": options.get("translator_base_url", ""),
        "model": options.get("translator_model", ""),
        "api_key": options.get("translator_api_key", ""),
        "prompt": options.get("translator_prompt", ""),
        "fallback_mode": options.get("translator_fallback_mode", "source_text"),
        "timeout_sec": options.get("translator_timeout_sec", 120.0),
        "runtime_mode": options.get("transcribe_runtime_mode", "parallel"),
        "translation_mode": options.get("translator_mode", "window_batch"),
        "context_window_size": options.get("translator_context_window_size", 6),
        "batch_window_size": options.get("translator_batch_window_size", 10),
        "batch_max_chars": options.get("translator_batch_max_chars", 2500),
    }
    if provider == "ollama":
        return OllamaTranslator(**kwargs)
    if provider == "openai_compatible":
        return OpenAICompatibleTranslator(**kwargs)

    raise ValueError(f"Unsupported translator provider: {provider}")
