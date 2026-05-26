"""LLM Bridge — 主循环入口

与现有 chat_handler.chat_stream() 的 yield 格式兼容。
替换 router.stream_events_with_history() 调用链路。

Bridge 不直接访问 DB，所有数据通过参数传入。
"""

import json
from typing import AsyncIterator

from .config import LLMBridgeConfig
from .deepseek import DeepSeekClient
from .messages import Attachment, build_messages
from . import stream as stream_parser


async def chat_stream(
    *,
    # ── 会话上下文 ──
    email: str,
    session_id: str,

    # ── 用户输入 ──
    message: str,
    attachments: list[Attachment] | None = None,

    # ── 历史消息 ──
    history: list[dict] | None = None,

    # ── 系统提示 ──
    system_prompt: str | None = None,
    system_parts: dict | None = None,

    # ── 对话选项 ──
    options: dict | None = None,

    # ── 配置 ──
    config: LLMBridgeConfig | None = None,
) -> AsyncIterator[str]:
    """DeepSeek 流式对话主循环（无工具版本）。

    调用方（chat_handler）职责:
      1. 从 data/session/db 获取 history
      2. 传入 email / session_id / message / attachments
      3. 遍历本生成器，将 SSE 事件写到 HTTP 响应
      4. 可选地边流式边持久化
    """
    if config is None:
        config = LLMBridgeConfig()

    reasoning_effort: str = "high"
    model_override: str | None = None
    if options:
        reasoning_effort = options.get("reasoning_effort", "high")
        model_override = options.get("model") or None
    if reasoning_effort not in ("high", "max"):
        reasoning_effort = "high"

    messages = build_messages(
        history or [],
        message,
        attachments=attachments,
        system_prompt=system_prompt,
        system_parts=system_parts,
    )

    client = DeepSeekClient(config)
    full_content = ""
    full_reasoning = ""
    usage: dict | None = None

    try:
        async for chunk in client.chat_completions(
            messages,
            model=model_override,
            reasoning_effort=reasoning_effort,
            stream=True,
        ):
            events = stream_parser.parse_chunk(chunk)
            for event in events:
                if event.type == "reasoning":
                    content = event.data.get("content", "")
                    if not content:           # DS 首个 reasoning delta 常为空
                        continue
                    full_reasoning += content
                    yield (
                        f"event: reasoning\n"
                        f"data: {json.dumps({'type': 'reasoning', 'content': content})}\n\n"
                    )
                elif event.type == "text":
                    token = event.data.get("token", "")
                    full_content += token
                    yield (
                        f"data: {json.dumps({'choices': [{'delta': {'content': token}}]})}\n\n"
                    )
                elif event.type == "done":
                    if event.data.get("usage"):
                        usage = event.data["usage"]

    except Exception as exc:
        yield (
            f"event: error\n"
            f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        )

    finally:
        await client.close()

    yield (
        f"event: done\n"
        f"data: {json.dumps({'type': 'done', 'response': full_content, 'reasoning': full_reasoning, 'usage': usage})}\n\n"
    )
    yield "data: [DONE]\n\n"


# ════════════════════════════════════════════════════════════════
# Tool-enabled stream — 原生支持工具调用
# ════════════════════════════════════════════════════════════════

async def chat_stream_with_tools(
    *,
    email: str,
    session_id: str,
    message: str,
    attachments: list | None = None,
    history: list | None = None,
    system_prompt: str | None = None,
    system_parts: dict | None = None,
    options: dict | None = None,
    tools: list | None = None,
    config: LLMBridgeConfig | None = None,
) -> AsyncIterator[str]:
    """带工具定义的 DeepSeek 流式对话。

    与 chat_stream 的区别：
    1. 传入 tools 参数 → DeepSeek 可输出 tool_calls
    2. done 事件携带 finish_reason + tool_calls（供上游 chat_handler 循环）
    3. 本身不执行工具，只负责「调 LLM + 报告结果」

    done 事件扩展格式:
      {
        "type": "done",
        "finish_reason": "stop" | "tool_calls",
        "tool_calls": [                      # finish_reason=tool_calls 时存在
          {"id": "...", "type": "function",
           "function": {"name": "...", "arguments": "{...}"}}
        ],
        "response": "...",
        "reasoning": "...",
        "usage": {...}
      }
    """
    if config is None:
        config = LLMBridgeConfig()

    reasoning_effort: str = "high"
    model_override: str | None = None
    if options:
        reasoning_effort = options.get("reasoning_effort", "high")
        model_override = options.get("model") or None
    if reasoning_effort not in ("high", "max"):
        reasoning_effort = "high"

    messages = build_messages(
        history or [],
        message,
        attachments=attachments,
        system_prompt=system_prompt,
        system_parts=system_parts,
    )

    client = DeepSeekClient(config)
    full_content = ""
    full_reasoning = ""
    reasoning_content_chunks: list[str] = []  # 原始 reasoning_content 片段（DS V4 要求回传）
    usage: dict | None = None

    # 累积 tool_calls（DS 流式分散在多个 chunk）
    tc_deltas: dict[int, dict] = {}  # index → {id, name, arguments}

    try:
        async for chunk in client.chat_completions(
            messages,
            model=model_override,
            reasoning_effort=reasoning_effort,
            stream=True,
            tools=tools,
        ):
            events = stream_parser.parse_chunk(chunk)
            for event in events:
                if event.type == "reasoning":
                    content = event.data.get("content", "")
                    if not content:           # DS 首个 reasoning delta 常为空
                        continue
                    full_reasoning += content
                    reasoning_content_chunks.append(content)
                    yield (
                        f"event: reasoning\n"
                        f"data: {json.dumps({'type': 'reasoning', 'content': content})}\n\n"
                    )
                elif event.type == "text":
                    token = event.data.get("token", "")
                    full_content += token
                    yield (
                        f"data: {json.dumps({'choices': [{'delta': {'content': token}}]})}\n\n"
                    )
                elif event.type == "tool_call_delta":
                    idx = event.data.get("index", 0)
                    if idx not in tc_deltas:
                        tc_deltas[idx] = {"id": "", "name": "", "arguments": ""}
                    if event.data.get("id"):
                        tc_deltas[idx]["id"] = event.data["id"]
                    if event.data.get("function_name"):
                        tc_deltas[idx]["name"] = event.data["function_name"]
                    tc_deltas[idx]["arguments"] += (event.data.get("function_arguments") or "")
                elif event.type == "done":
                    if event.data.get("usage"):
                        usage = event.data["usage"]

    except Exception as exc:
        yield (
            f"event: error\n"
            f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        )

    finally:
        await client.close()

    # 构建 done 事件（含 tool_calls + reasoning_content）
    done_data = {
        "type": "done",
        "finish_reason": "stop",
        "response": full_content,
        "reasoning": full_reasoning,
        "reasoning_content": "".join(reasoning_content_chunks),  # DS V4 要求后续轮次回传
        "usage": usage,
    }

    if tc_deltas:
        full_tool_calls = []
        for idx in sorted(tc_deltas.keys()):
            tc = tc_deltas[idx]
            if tc["name"]:
                full_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })
        if full_tool_calls:
            done_data["finish_reason"] = "tool_calls"
            done_data["tool_calls"] = full_tool_calls

    yield (
        f"event: done\n"
        f"data: {json.dumps(done_data)}\n\n"
    )
    yield "data: [DONE]\n\n"
