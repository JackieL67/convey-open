"""DeepSeek HTTP 调用层

OpenAI SDK 调用 api.deepseek.com/chat/completions。
支持流式/非流式，不涉及消息构建或事件处理。

DeepSeek API: https://api-docs.deepseek.com
"""

import asyncio
from typing import AsyncIterator

import openai
from openai import AsyncOpenAI

from .config import LLMBridgeConfig


class DeepSeekClient:
    """DeepSeek API 客户端（via OpenAI SDK）"""

    def __init__(self, config: LLMBridgeConfig):
        self.config = config
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=0,
        )

    async def chat_completions(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        tools: list[dict] | None = None,
        stream: bool = True,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[dict]:
        """Stream chat completions, yield raw dict chunks."""
        kwargs: dict = {
            "model": model or self.config.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": max_tokens or self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                stream_resp = await self._client.chat.completions.create(**kwargs)
                async for chunk in stream_resp:
                    yield chunk.model_dump()
                return
            except (PermissionError, ValueError):
                raise
            except openai.AuthenticationError:
                raise PermissionError("API Key 无效")
            except openai.APIStatusError as e:
                if e.status_code == 402:
                    raise PermissionError("余额不足")
                if e.status_code in (400, 422):
                    raise ValueError(str(e.message))
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ValueError(f"HTTP {e.status_code} after {max_retries} retries")
            except openai.APIError:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

    async def chat_completions_non_stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> dict:
        """Non-streaming variant. Returns the full response dict."""
        kwargs: dict = {
            "model": model or self.config.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        try:
            response = await self._client.chat.completions.create(**kwargs)
            return response.model_dump()
        except openai.AuthenticationError:
            raise PermissionError("API Key 无效")
        except openai.APIStatusError as e:
            if e.status_code == 402:
                raise PermissionError("余额不足")
            if e.status_code in (400, 422):
                raise ValueError(str(e.message))
            raise

    async def close(self):
        await self._client.close()
