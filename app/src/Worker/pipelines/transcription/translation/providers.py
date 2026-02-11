import re
from typing import Optional

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
        fallback_mode: str = "model_full_text",
        runtime_mode: str = "parallel",
    ):
        self.base_url = (base_url or "").strip()
        self.model = (model or "").strip()
        self.api_key = (api_key or "").strip()
        self.prompt = (prompt or "").strip()
        self.timeout_sec = float(timeout_sec or 120.0)
        mode = str(fallback_mode or "model_full_text").strip().lower()
        self.fallback_mode = mode if mode in {"model_full_text", "source_text"} else "model_full_text"
        safe_runtime_mode = str(runtime_mode or "parallel").strip().lower()
        self.runtime_mode = safe_runtime_mode if safe_runtime_mode in {"parallel", "memory_saving"} else "parallel"

    def translate_text(self, text: str, target_language: str) -> str:
        raise NotImplementedError

    @staticmethod
    def _sanitize_model_text(raw_text: str) -> str:
        full_text = str(raw_text or "").strip()
        if not full_text:
            return ""
        cleaned = _THINK_TAG_RE.sub("", full_text).strip()
        return cleaned or full_text

    @staticmethod
    def _extract_code_block_content(raw_text: str) -> str:
        cleaned = BaseTranslator._sanitize_model_text(raw_text)
        if not cleaned:
            return ""
        matches = _CODE_BLOCK_RE.findall(cleaned)
        for item in matches:
            candidate = str(item or "").strip()
            if candidate:
                return candidate
        return ""

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
            "Return translated text only, with no explanations.\n"
            "Preserve original line breaks and text structure.\n"
            "Keep numbers, punctuation, URLs, emails, and IDs unchanged unless translation is required.\n"
            "Do not translate placeholders or markup, such as {name}, [MASK], <tag>, %s, ${VAR}.\n"
            "If the source text is empty, return an empty string."
        )
        if resolved_custom:
            return f"{resolved_custom}\n\n{strict_rules}"
        return strict_rules


class OllamaTranslator(BaseTranslator):
    label = "ollama"

    def _keep_alive_value(self):
        if self.runtime_mode == "parallel":
            return -1
        return "2m"

    def prepare_for_task(self):
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
            # warmup failure should not fail task creation
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

    def translate_text(self, text: str, target_language: str) -> str:
        if not self.base_url or not self.model:
            raise ValueError("Ollama translator requires translator_base_url and translator_model.")
        endpoint = f"{self.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": self._system_prompt(target_language, self.prompt)},
                {"role": "user", "content": str(text or "")},
            ],
            "options": {"temperature": 0.2, "top_p": 0.9},
            "keep_alive": self._keep_alive_value(),
        }
        response = requests.post(endpoint, json=payload, timeout=self.timeout_sec)
        response.raise_for_status()
        data = response.json()
        content = ((data.get("message") or {}).get("content") or "").strip()
        parsed = self._extract_code_block_content(content)
        if parsed:
            return parsed
        return self._resolve_fallback_text(model_raw_text=content, source_text=text)


class OpenAICompatibleTranslator(BaseTranslator):
    label = "openai_compatible"

    def _endpoint(self) -> str:
        raw = self.base_url.rstrip("/")
        if raw.endswith("/chat/completions"):
            return raw
        return f"{raw}/chat/completions"

    def translate_text(self, text: str, target_language: str) -> str:
        if not self.base_url or not self.model:
            raise ValueError("OpenAI-compatible translator requires translator_base_url and translator_model.")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt(target_language, self.prompt)},
                {"role": "user", "content": str(text or "")},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        response = requests.post(self._endpoint(), headers=headers, json=payload, timeout=self.timeout_sec)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return self._resolve_fallback_text(model_raw_text="", source_text=text)
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        parsed = self._extract_code_block_content(content)
        if parsed:
            return parsed
        return self._resolve_fallback_text(model_raw_text=content, source_text=text)


def create_translator(options) -> Optional[BaseTranslator]:
    provider = (options.get("translator_provider") or "none").strip().lower()
    if provider == "none" or not (options.get("translate_to") or "").strip():
        return None

    kwargs = {
        "base_url": options.get("translator_base_url", ""),
        "model": options.get("translator_model", ""),
        "api_key": options.get("translator_api_key", ""),
        "prompt": options.get("translator_prompt", ""),
        "fallback_mode": options.get("translator_fallback_mode", "model_full_text"),
        "timeout_sec": options.get("translator_timeout_sec", 120.0),
        "runtime_mode": options.get("transcribe_runtime_mode", "parallel"),
    }
    if provider == "ollama":
        return OllamaTranslator(**kwargs)
    if provider == "openai_compatible":
        return OpenAICompatibleTranslator(**kwargs)

    raise ValueError(f"Unsupported translator provider: {provider}")
