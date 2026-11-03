from abc import ABC, abstractmethod
from typing import List


class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class CompletionResponse:
    def __init__(self, content: str):
        self.content = content


class ProviderError(Exception):
    """Raised for timeouts, HTTP failures and malformed provider responses. Never contains secrets."""


class LLMProvider(ABC):
    name = "base"

    @property
    def is_configured(self) -> bool:
        return True

    @abstractmethod
    async def complete(self, messages: List[Message], **kwargs) -> CompletionResponse:
        pass
