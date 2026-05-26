"""
Conversation Engine · 主入口

Python RPC 接口，供 User Portal 直接调用。
不对外暴露 HTTP 端口。

使用方式:
    from engine import engine

    # 认证
    result = engine.auth("user@example.com", "device_abc")

    # 创建会话
    session_id = engine.create_session("user@example.com")

    # 发送消息（SSE 流式）
    async for event in engine.chat("user@example.com", session_id, "你好"):
        print(event)
"""

import logging
import sys
from typing import Optional, AsyncIterator

from engine.config import EngineConfig
from engine.db import EngineDB
from engine.chat_handler import ChatHandler

logger = logging.getLogger(__name__)


# 导入 MemoryClient 和 llm-bridge
try:
    from memory.client import MemoryClient
    from llm_bridge.client import chat_stream as llm_chat_stream
except ImportError as e:
    logger.warning("Failed to import memory or llm-bridge: %s", e)
    MemoryClient = None
    llm_chat_stream = None

# 导入 DeepSeekClient（工具循环直接调用，绕过 llm-bridge 的消息构建层）
try:
    from llm_bridge.deepseek import DeepSeekClient
    from llm_bridge.config import LLMBridgeConfig
except ImportError as e:
    logger.warning("Failed to import DeepSeekClient: %s", e)
    DeepSeekClient = None
    LLMBridgeConfig = None
try:
    import sys as _sys
    from util.tools.executor import ToolExecutor, get_registry
    from util.tools.web_search import handler as _ws_handler
    from util.tools.read_file import handler as _rf_handler
    from util.tools.describe_image import handler as _di_handler
    _TOOLS_AVAILABLE = True
except ImportError as e:
    logger.warning("Failed to import tool modules: %s", e)
    ToolExecutor = None
    get_registry = None
    _TOOLS_AVAILABLE = False


class ConversationEngine:
    """
    Conversation Engine — 对话引擎 RPC 接口。

    这是 Portal 调用的唯一入口。
    所有方法都是同步或异步的 Python 方法调用，不涉及 HTTP。
    """

    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        self.db = EngineDB(self.config.db_path)

        # 初始化 MemoryClient 和 llm-bridge
        self.memory_client = None
        if MemoryClient:
            try:
                self.memory_client = MemoryClient()
            except Exception as e:
                logger.warning("Failed to initialize MemoryClient: %s", e)

        # 初始化工具执行器并绑定三个内置工具的 handler
        self.tool_executor = None
        if _TOOLS_AVAILABLE and ToolExecutor and get_registry:
            try:
                self.tool_executor = ToolExecutor()
                registry = get_registry()
                # 绑定三个内置工具的真实 handler（延迟注入模式）
                registry.set_handler("web_search", _ws_handler)
                registry.set_handler("read_file", _rf_handler)
                registry.set_handler("describe_image", _di_handler)
                logger.info("ToolExecutor initialized with 3 handlers: web_search, read_file, describe_image")
            except Exception as e:
                logger.warning("Failed to initialize ToolExecutor: %s", e)
                self.tool_executor = None

        # 创建 ChatHandler（传入 memory_client、llm_chat_stream、tool_executor）
        self.chat_handler = ChatHandler(
            self.db,
            self.config,
            memory_client=self.memory_client,
            llm_chat_stream=llm_chat_stream,
            tool_executor=self.tool_executor,
        )

        # 启动恢复：将 stale processing 状态标记为 pending
        recovered = self.db.mark_stale_processing_as_pending()
        if recovered > 0:
            logger.info("Engine recovery: %d stale 'processing' messages marked as 'pending'", recovered)

        # 检查孤儿消息
        orphans = self.db.get_orphaned_user_messages()
        if orphans:
            logger.info("Engine recovery: %d orphaned user messages found (pending retry)", len(orphans))

        logger.info("Conversation Engine initialized (db=%s)", self.config.db_path)

    # ═══════════════════════════════════════════
    #  认证
    # ═══════════════════════════════════════════

    def auth(self, email: str, device_id: str) -> dict:
        """
        邮箱认证（首次或新设备）。

        Args:
            email: 用户邮箱
            device_id: 设备标识

        Returns:
            {
                "email": str,
                "session_id": str,      # 当前活跃 session
                "display_name": str,
                "is_new": bool,
            }

        Raises:
            ValueError: 邮箱格式无效
        """
        if not email or "@" not in email:
            raise ValueError("请输入有效的邮箱地址")

        return self.db.get_or_create_user(email, device_id)

    def get_user(self, email: str) -> Optional[dict]:
        """
        查询用户信息。

        Returns:
            {"email", "session_id", "display_name", "last_active"} or None
        """
        return self.db.get_user(email)

    # ═══════════════════════════════════════════
    #  Session 管理
    # ═══════════════════════════════════════════

    def create_session(self, email: str, title: str = "") -> str:
        """
        创建新会话。

        Args:
            email: 用户邮箱
            title: 会话标题（可选）

        Returns:
            session_id
        """
        return self.db.create_session(email, title)

    def switch_session(self, email: str, session_id: str) -> bool:
        """
        切换到指定会话。

        Args:
            email: 用户邮箱
            session_id: 目标会话 ID

        Returns:
            True 成功，False 会话不存在
        """
        return self.db.switch_session(email, session_id)

    def list_sessions(self, email: str) -> list[dict]:
        """
        列出用户的所有会话。

        Returns:
            [{
                "session_id": str,
                "is_current": bool,
                "message_count": int,
                "preview": str,
                "last_message_time": float,
            }]
        """
        return self.db.list_sessions(email)

    def delete_session(self, email: str, session_id: str) -> dict:
        """
        删除指定会话。

        Returns:
            {"ok": True, "new_session_id": str} 或 404
        """
        ok = self.db.delete_session(email, session_id)
        if not ok:
            return {"ok": False, "error": "会话不存在"}
        # 获取新当前 session
        user = self.db.get_user(email)
        return {"ok": True, "new_session_id": user["session_id"]}

    # ═══════════════════════════════════════════
    #  消息 & 对话
    # ═══════════════════════════════════════════

    def get_history(
        self,
        email: str,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        """
        获取会话的消息历史。

        Args:
            email: 用户邮箱（用于权限校验）
            session_id: 会话 ID
            limit: 最大返回条数
            offset: 偏移量

        Returns:
            [{"id", "session_id", "role", "content", "metadata", "created_at"}]

        Raises:
            PermissionError: session 不存在或不属于该用户
        """
        # 先校验 session 存在且属于该用户（无论是否有消息）
        self._verify_session(email, session_id)
        return self.db.get_messages(session_id, limit=limit, offset=offset)

    async def chat(
        self,
        email: str,
        session_id: str,
        message: str,
    ) -> dict:
        """
        发送消息并获取回复（同步）。

        Args:
            email: 用户邮箱
            session_id: 会话 ID
            message: 用户消息

        Returns:
            {"reply": str, "user_message_id": int, "assistant_message_id": int}
        """
        self._verify_session(email, session_id)
        return await self.chat_handler.chat(email, session_id, message)

    async def chat_stream(
        self,
        email: str,
        session_id: str,
        message: str,
        options: dict = None,
        attachments: list = None,
    ) -> AsyncIterator[str]:
        """
        发送消息并获取 SSE 流式回复。

        Args:
            email: 用户邮箱
            session_id: 会话 ID
            message: 用户原始消息文本
            options: ChatOptions (reasoning_level, reply_style, model)
            attachments: 附件列表 [{file_id, filename, content_type, url}]
        """
        self._verify_session(email, session_id)
        async for event in self.chat_handler.chat_stream(email, session_id, message, options=options, attachments=attachments):
            yield event

    # ═══════════════════════════════════════════
    #  系统状态
    # ═══════════════════════════════════════════

    async def get_agent_status(self) -> dict:
        """获取 Agent 状态。"""
        return await self.chat_handler.get_agent_status()

    async def get_tools(self) -> dict:
        """获取可用工具列表。"""
        return await self.chat_handler.get_tools()

    def get_token_stats(self, session_id: str = None) -> dict:
        """获取 Token 使用统计。"""
        return self.chat_handler.get_token_stats(session_id)

    async def get_context_preview(self, email: str, session_id: str, message: str) -> dict:
        """
        获取当前会话即将发给 LLM 的完整上下文预览。

        Args:
            email: 用户邮箱
            session_id: 会话 ID
            message: 用户要发送的新消息

        Returns:
            {
                "system_prompt": str,        # 完整 system_prompt
                "history": list,             # 历史消息列表
                "current_message": str,      # 当前用户消息
                "history_count": int,        # 历史消息条数
                "history_token_estimate": int,  # 历史 token 估算
                "total_token_estimate": int,    # 全部 token 估算
            }

        Raises:
            PermissionError: session 不存在或不属于该用户
        """
        self._verify_session(email, session_id)
        return await self.chat_handler.get_context_preview(email, session_id, message)

    # ═══════════════════════════════════════════
    #  容错与恢复
    # ═══════════════════════════════════════════

    def get_pending_messages(self, session_id: str = None) -> list[dict]:
        """
        获取待重试的用户消息。

        Args:
            session_id: 指定会话（可选，不传则查所有）

        Returns:
            [{id, session_id, content, metadata, created_at}] — status 为 pending 的消息
        """
        orphans = self.db.get_orphaned_user_messages()
        if session_id:
            orphans = [m for m in orphans if m["session_id"] == session_id]
        return orphans

    # ═══════════════════════════════════════════
    #  内部方法
    # ═══════════════════════════════════════════

    def _verify_session(self, email: str, session_id: str):
        """校验 session 属于该用户。"""
        self.db.assert_session_owner(email, session_id)

    def close(self):
        """关闭引擎，释放资源。"""
        logger.info("Conversation Engine closed")
