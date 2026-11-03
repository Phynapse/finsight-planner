import logging
from typing import List

import httpx

from .base import LLMProvider, Message, CompletionResponse, ProviderError
from ...core.config import settings

logger = logging.getLogger("finsight.llm")
PLACEHOLDER_KEYS = {"", "your_api_key_here", "changeme"}
MAX_ATTEMPTS = 2  # one bounded retry for timeouts / 5xx / 429


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None, transport=None):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key.strip() not in PLACEHOLDER_KEYS

    async def complete(self, messages: List[Message], **kwargs) -> CompletionResponse:
        if not self.is_configured:
            raise ProviderError("LLM provider not configured")
        payload = {"model": self.model, "messages": [{"role": m.role, "content": m.content} for m in messages],
                   "temperature": kwargs.get("temperature", 0), "max_tokens": kwargs.get("max_tokens", 800)}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last = "unknown error"
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    r = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                except httpx.TimeoutException:
                    last = "timeout"
                    logger.warning("LLM request timed out (attempt %d)", attempt)
                    continue
                except httpx.HTTPError as e:
                    raise ProviderError(f"LLM transport error: {type(e).__name__}")
                if r.status_code >= 500 or r.status_code == 429:
                    last = f"HTTP {r.status_code}"
                    logger.warning("LLM provider returned %s (attempt %d)", r.status_code, attempt)
                    continue
                if r.status_code >= 400:
                    raise ProviderError(f"LLM provider rejected request: HTTP {r.status_code}")
                try:
                    content = r.json()["choices"][0]["message"]["content"]
                except (ValueError, KeyError, IndexError, TypeError):
                    raise ProviderError("Malformed LLM provider response")
                if not isinstance(content, str) or not content.strip():
                    raise ProviderError("Empty LLM provider response")
                return CompletionResponse(content)
        raise ProviderError(f"LLM provider unavailable: {last}")


def get_provider() -> LLMProvider:
    return OpenAICompatibleProvider()
