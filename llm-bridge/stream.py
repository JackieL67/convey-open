"""流式事件解析

将 DeepSeek API 返回的 streaming chunk 解析为结构化事件。
纯函数转换，不涉及 DB 写入或 SSE 格式化。

DeepSeek streaming chunk 格式:
  {"choices": [{"delta": {"content": "...", "reasoning_content": "..."}, "finish_reason": null}]}
  {"choices": [{"delta": {"tool_calls": [...]}, "finish_reason": "tool_calls"}]}  # 会发出 tool_call_delta 事件
  {"usage": {...}}  (final chunk)
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class StreamEvent:
    """解析后的流式事件"""
    type: Literal["reasoning", "text", "done", "error", "tool_call_delta"]
    data: dict = field(default_factory=dict)


def parse_chunk(chunk: dict) -> list[StreamEvent]:
    """将 DeepSeek API chunk dict 解析为 StreamEvent 列表。"""
    events: list[StreamEvent] = []
    choices = chunk.get("choices", [])
    usage = chunk.get("usage")

    # Usage-only chunk (include_usage=true sends a final chunk with empty choices)
    if not choices and usage:
        events.append(StreamEvent(type="done", data={"finish_reason": "stop", "usage": usage}))
        return events

    for choice in choices:
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        reasoning = delta.get("reasoning_content")
        content = delta.get("content")
        role = delta.get("role")

        # Skip role-declaration chunk (has role but no content)
        if role and reasoning is None and content is None:
            continue

        if reasoning is not None:
            events.append(StreamEvent(type="reasoning", data={"content": reasoning}))

        if content is not None:
            events.append(StreamEvent(type="text", data={"token": content}))

        # tool_calls delta（DS V4 流式返回，多个 chunk 累积）
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                events.append(StreamEvent(
                    type="tool_call_delta",
                    data={
                        "index": tc.get("index", 0),
                        "id": tc.get("id"),
                        "function_name": (tc.get("function", {}) or {}).get("name"),
                        "function_arguments": (tc.get("function", {}) or {}).get("arguments", ""),
                    },
                ))

        if finish_reason is not None:
            events.append(StreamEvent(
                type="done",
                data={"finish_reason": finish_reason, "usage": usage},
            ))

    return events


def parse_final_usage(chunk: dict) -> dict | None:
    """从结束 chunk 中提取 usage 信息。"""
    return chunk.get("usage")
