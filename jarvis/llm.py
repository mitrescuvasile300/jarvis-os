"""LLM Client abstraction — supports OpenAI, Anthropic, and Ollama.

Provides a unified interface for chat completions with tool use support.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("jarvis.llm")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a chat completion request.

        Returns:
            dict with keys: text (str), tool_calls (list[dict] | None)
        """
        ...


class OpenAIClient(BaseLLMClient):
    """OpenAI API client (GPT-4o, GPT-5, o1, o3, etc.)."""

    # Models that require max_completion_tokens instead of max_tokens
    NEW_PARAM_MODELS = {
        "o1", "o1-mini", "o1-preview",
        "o3", "o3-mini", "o3-pro",
        "o4-mini",
        "gpt-5", "gpt-5-mini", "gpt-5.1", "gpt-5.2",
    }

    # Reasoning models that don't support temperature
    REASONING_MODELS = {
        "o1", "o1-mini", "o1-preview",
        "o3", "o3-mini", "o3-pro",
        "o4-mini",
    }

    def __init__(self, config: dict):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        api_key = config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = config.get("model", "gpt-4o")

    def _uses_new_token_param(self) -> bool:
        """Check if the model uses max_completion_tokens instead of max_tokens."""
        model = self.model.lower()
        return any(model.startswith(m) for m in self.NEW_PARAM_MODELS)

    def _is_reasoning_model(self) -> bool:
        """Check if this is a reasoning model (o1/o3/o4 series)."""
        model = self.model.lower()
        return any(model.startswith(m) for m in self.REASONING_MODELS)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        # Use correct token parameter based on model
        if self._uses_new_token_param():
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        # Reasoning models (o1/o3/o4) don't support temperature
        if not self._is_reasoning_model():
            kwargs["temperature"] = temperature

        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        result: dict[str, Any] = {"text": message.content or ""}

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in message.tool_calls
            ]

        return result


class AnthropicClient(BaseLLMClient):
    """Anthropic API client (Claude)."""

    def __init__(self, config: dict):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

        api_key = config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = config.get("model", "claude-sonnet-4-20250514")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        # Anthropic uses system as a top-level param
        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        chat_msgs = [m for m in messages if m["role"] != "system"]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": chat_msgs,
            "system": "\n\n".join(system_msgs) if system_msgs else "",
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {}),
                }
                for t in tools
            ]

        response = await self.client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "arguments": block.input,
                })

        result: dict[str, Any] = {"text": "\n".join(text_parts)}
        if tool_calls:
            result["tool_calls"] = tool_calls

        return result


class OllamaClient(BaseLLMClient):
    """Ollama client for local LLMs (Llama 3, Mistral, etc.)."""

    def __init__(self, config: dict):
        try:
            import httpx
        except ImportError:
            raise ImportError("Install httpx: pip install httpx")

        self.host = config.get("ollama_host") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = config.get("model", "llama3")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.host}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        return {"text": data.get("message", {}).get("content", "")}


def create_llm_client(config: dict) -> BaseLLMClient:
    """Factory function to create the appropriate LLM client."""
    provider = config.get("provider", "openai").lower()

    if provider == "openai":
        return OpenAIClient(config)
    elif provider == "anthropic":
        return AnthropicClient(config)
    elif provider == "ollama":
        return OllamaClient(config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use: openai, anthropic, ollama")
