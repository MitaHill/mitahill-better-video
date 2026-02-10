import re
from typing import Optional

import requests


_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z]+)?\\s*([\\s\\S]*?)```", re.MULTILINE)
_THINK_TAG_RE = re.compile(r"<think>[\\s\\S]*?</think>", re.IGNORECASE)


class BaseTranslator:
    label = "base"

    def __init__(self, *, base_url: str, model: str, api_key: str, prompt: str, timeout_sec: float):
        self.base_url = (base_url or "").strip()
        self.model = (model or "").strip()
        self.api_key = (api_key or "").strip()
        self.prompt = (prompt or "").strip()
        self.timeout_sec = float(timeout_sec or 120.0)

    def translate_text(self, text: str, target_language: str) -> str:
        raise NotImplementedError

    @staticmethod
    def _extract_content(raw_text: str) -> str:
        cleaned = _THINK_TAG_RE.sub("", str(raw_text or "")).strip()
        matches = _CODE_BLOCK_RE.findall(cleaned)
        if matches:
            return matches[0].strip()
        return cleaned

    @staticmethod
    def _message_prompt(target_language: str) -> str:
        lang = (target_language or "").strip()
        return f"Translate the input text into {lang}. Output translated text only."


class OllamaTranslator(BaseTranslator):
    label = "ollama"

    def translate_text(self, text: str, target_language: str) -> str:
        if not self.base_url or not self.model:
            raise ValueError("Ollama translator requires translator_base_url and translator_model.")
        endpoint = f"{self.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": self.prompt or self._message_prompt(target_language)},
                {"role": "user", "content": str(text or "")},
            ],
            "options": {"temperature": 0.2, "top_p": 0.9},
        }
        response = requests.post(endpoint, json=payload, timeout=self.timeout_sec)
        response.raise_for_status()
        data = response.json()
        content = ((data.get("message") or {}).get("content") or "").strip()
        parsed = self._extract_content(content)
        return parsed or str(text or "")


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
                {"role": "system", "content": self.prompt or self._message_prompt(target_language)},
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
            return str(text or "")
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        parsed = self._extract_content(content)
        return parsed or str(text or "")


def create_translator(options) -> Optional[BaseTranslator]:
    provider = (options.get("translator_provider") or "none").strip().lower()
    if provider == "none" or not (options.get("translate_to") or "").strip():
        return None

    kwargs = {
        "base_url": options.get("translator_base_url", ""),
        "model": options.get("translator_model", ""),
        "api_key": options.get("translator_api_key", ""),
        "prompt": options.get("translator_prompt", ""),
        "timeout_sec": options.get("translator_timeout_sec", 120.0),
    }
    if provider == "ollama":
        return OllamaTranslator(**kwargs)
    if provider == "openai_compatible":
        return OpenAICompatibleTranslator(**kwargs)

    raise ValueError(f"Unsupported translator provider: {provider}")
