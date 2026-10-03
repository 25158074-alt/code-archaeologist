from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Literal

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from code_archaeologist.core.config import get_settings


class ModelTier(str, Enum):
    ULTRA = "ultra"
    SUPER = "super"
    NANO = "nano"


@dataclass(slots=True)
class ModelConfig:
    name: str
    temperature: float
    max_tokens: int
    tier: ModelTier


@dataclass(slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(slots=True)
class CompletionResponse:
    content: str
    model: str
    usage: dict[str, int]
    latency_ms: float
    tier: ModelTier


class NebiusClient:
    def __init__(
        self,
        nebius_settings=None,
        model_settings=None,
    ):
        settings = get_settings()
        self._nebius = nebius_settings or settings.nebius
        self._models = model_settings or settings.models
        self._client: httpx.AsyncClient | None = None
        self._model_configs = self._build_model_configs()

    def _build_model_configs(self) -> dict[ModelTier, ModelConfig]:
        return {
            ModelTier.ULTRA: ModelConfig(
                name=self._models.ultra_model,
                temperature=self._models.ultra_temperature,
                max_tokens=self._models.max_tokens_ultra,
                tier=ModelTier.ULTRA,
            ),
            ModelTier.SUPER: ModelConfig(
                name=self._models.super_model,
                temperature=self._models.super_temperature,
                max_tokens=self._models.max_tokens_super,
                tier=ModelTier.SUPER,
            ),
            ModelTier.NANO: ModelConfig(
                name=self._models.nano_model,
                temperature=self._models.nano_temperature,
                max_tokens=self._models.max_tokens_nano,
                tier=ModelTier.NANO,
            ),
        }

    async def __aenter__(self) -> NebiusClient:
        self._client = httpx.AsyncClient(
            base_url=self._nebius.base_url,
            headers={
                "Authorization": f"Bearer {self._nebius.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self._nebius.timeout),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    def _get_config(self, tier: ModelTier) -> ModelConfig:
        return self._model_configs[tier]

    def _normalize_messages(self, messages: list) -> list[dict[str, str]]:
        normalized = []
        for m in messages:
            if isinstance(m, dict):
                normalized.append({"role": m["role"], "content": m["content"]})
            else:
                normalized.append({"role": m.role, "content": m.content})
        return normalized

    @retry(
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def complete(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        tier: ModelTier = ModelTier.SUPER,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResponse:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        config = self._get_config(tier)
        model_name = model or config.name
        temp = temperature if temperature is not None else config.temperature
        max_tok = max_tokens if max_tokens is not None else config.max_tokens

        payload = {
            "model": model_name,
            "messages": self._normalize_messages(messages),
            "temperature": temp,
            "max_tokens": max_tok,
            "stream": False,
        }

        if response_format:
            payload["response_format"] = response_format

        start = time.perf_counter()
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        latency_ms = (time.perf_counter() - start) * 1000

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return CompletionResponse(
            content=choice["message"]["content"],
            model=model_name,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            latency_ms=latency_ms,
            tier=tier,
        )

    async def complete_stream(
        self,
        messages: list[ChatMessage],
        tier: ModelTier = ModelTier.SUPER,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        config = self._get_config(tier)
        model_name = model or config.name
        temp = temperature if temperature is not None else config.temperature
        max_tok = max_tokens if max_tokens is not None else config.max_tokens

        payload = {
            "model": model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temp,
            "max_tokens": max_tok,
            "stream": True,
        }

        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue

    def select_tier(self, task_complexity: Literal["simple", "moderate", "complex"]) -> ModelTier:
        mapping = {
            "simple": ModelTier.NANO,
            "moderate": ModelTier.SUPER,
            "complex": ModelTier.ULTRA,
        }
        return mapping[task_complexity]

    async def estimate_tokens(self, text: str) -> int:
        return len(text) // 4