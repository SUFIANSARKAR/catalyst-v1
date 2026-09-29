from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

@dataclass(frozen=True)
class LocalModelConfig:
    """OpenAI-compatible local inference endpoint (Ollama/llama.cpp/vLLM/etc.)."""
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = ""
    api_key: str = "local"
    timeout: float = 180.0
    max_tokens: int = 8192

class LocalModelProvider:
    """Small, optional local brain. No model is downloaded by Catalyst itself.

    The provider speaks the OpenAI-compatible chat API so the local runtime can be
    swapped independently of Catalyst. It is intentionally lazy: if no local
    server is running, Catalyst can fall back to cloud providers.
    """
    kind = "local"
    role = "local"

    def __init__(self, config: LocalModelConfig):
        self.config = config

    @property
    def configured(self) -> bool:
        return bool(self.config.model and self.config.base_url)

    def _payload(self, messages, tools=None, temperature=.2):
        p = {"model": self.config.model, "messages": messages,
             "temperature": temperature, "max_tokens": self.config.max_tokens}
        if tools:
            p["tools"] = tools
        return p

    def chat(self, messages, tools=None, temperature=.2):
        if not self.configured:
            raise RuntimeError("Local model is not configured. Set a local model name first.")
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        with httpx.Client(timeout=self.config.timeout) as client:
            r = client.post(url, json=self._payload(messages, tools, temperature), headers=headers)
            r.raise_for_status()
            data = r.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or [], "raw": data}

    def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "reachable": False, "model": self.config.model, "base_url": self.config.base_url}
        try:
            url = self.config.base_url.rstrip("/") + "/models"
            with httpx.Client(timeout=min(self.config.timeout, 10)) as client:
                r = client.get(url)
                r.raise_for_status()
            return {"configured": True, "reachable": True, "model": self.config.model, "base_url": self.config.base_url}
        except Exception as exc:
            return {"configured": True, "reachable": False, "model": self.config.model, "base_url": self.config.base_url, "error": str(exc)}
