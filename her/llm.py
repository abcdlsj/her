"""LLM abstraction layer - supports multiple providers."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class Provider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class LLMConfig:
    provider: Provider = Provider.OPENAI
    model: str = "gpt-4o"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 10240


class LLM(ABC):
    """Abstract LLM interface."""

    @abstractmethod
    def chat(self, messages: list[dict], system: str | None = None) -> str:
        """Send messages and get response."""
        pass


class AnthropicLLM(LLM):
    """Anthropic Claude implementation."""

    def __init__(self, config: LLMConfig):
        from anthropic import Anthropic

        self.client = Anthropic(
            api_key=config.api_key or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=config.base_url or os.environ.get("ANTHROPIC_BASE_URL"),
        )
        self.model = config.model
        self.max_tokens = config.max_tokens

    def chat(self, messages: list[dict], system: str | None = None) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text


class OpenAILLM(LLM):
    """OpenAI implementation."""

    def __init__(self, config: LLMConfig):
        from openai import OpenAI

        self.client = OpenAI(
            api_key=config.api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=config.base_url or os.environ.get("OPENAI_BASE_URL"),
        )
        self.model = config.model
        self.max_tokens = config.max_tokens

    def chat(self, messages: list[dict], system: str | None = None) -> str:
        if system:
            messages = [{"role": "system", "content": system}] + messages

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content


def create_llm(config: LLMConfig | None = None) -> LLM:
    """Factory function to create LLM instance."""
    if config is None:
        config = LLMConfig()

    if config.provider == Provider.ANTHROPIC:
        return AnthropicLLM(config)
    elif config.provider == Provider.OPENAI:
        return OpenAILLM(config)
    else:
        raise ValueError(f"Unknown provider: {config.provider}")
