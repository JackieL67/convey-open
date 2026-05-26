"""
Conversation Engine · 对话引擎

内部微服务模块，提供 Python RPC 接口供 User Portal 调用。
不对外暴露 HTTP 端口。

核心职责:
  - Session + 消息持久化 (SQLite)
  - 唯一 Session 权威源
  - Session 路由到 Bridge

使用方式（Portal 直接 import）:
    from engine import engine

    # 认证
    result = engine.auth("user@example.com", "device_abc")

    # 创建会话
    session_id = engine.create_session("user@example.com")

    # 发送消息（SSE 流式）
    async for event in engine.chat("user@example.com", session_id, "你好"):
        print(event)
"""

from engine.engine import ConversationEngine
from engine.config import EngineConfig

# 全局单例 — Portal import 后直接使用
_default_config = EngineConfig()
engine = ConversationEngine(_default_config)

__all__ = ["ConversationEngine", "EngineConfig", "engine"]
