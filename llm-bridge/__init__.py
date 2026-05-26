"""LLM Bridge — DeepSeek 推理 + 多轮对话 + 工具调用通信层

与 Engine 平级，由 Portal 调用。
负责:
  - 消息构建（历史 + 当前消息 + 附件注入）
  - DeepSeek API 通信（流式/非流式）
  - 流式事件解析（reasoning / text / tool_calls）
  - 工具调用循环 [预留]
"""

from .client import chat_stream
from .config import LLMBridgeConfig

__all__ = ["chat_stream", "LLMBridgeConfig"]
