"""
Convey Engine Client · Portal ↔ Engine 适配层

Portal 通过此模块调用 Engine。当前 Engine 已实现 Python 模块，
直接 import ConversationEngine 即可。Engine 未就绪时回退到 JSON 文件。

V2 架构:
  - Portal (FastAPI :3000) 是唯一对外 Web 服务
  - Engine 是内部微服务，不对外暴露端口
  - Portal ↔ Engine: Python 直接 import (本地 RPC)
  - Engine 定义接口，Portal 适配

接口权威方: Engine (ConversationEngine)
"""

import json
import uuid
import time
import asyncio
import os
from pathlib import Path
from typing import AsyncIterator, Optional

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RPC Engine Client — 对接真实 Engine 模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RpcEngineClient:
    """
    通过 Python RPC 调用 Engine 的实现。

    Engine 和 Portal 中心化部署在同一台机器，
    RPC 方式为 Python 直接 import（本地调用，无网络开销）。

    接口完全匹配 engine.ConversationEngine 的方法签名。
    """

    def __init__(self):
        import sys
        convey_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if convey_root not in sys.path:
            sys.path.insert(0, convey_root)
        from engine.engine import ConversationEngine
        self._engine = ConversationEngine()
        self._ready = True

    # ── 认证 ──

    def auth(self, email: str, device_id: str) -> dict:
        """匹配 engine.auth(email, device_id) → dict"""
        return self._engine.auth(email, device_id)

    def get_user(self, email: str) -> Optional[dict]:
        """匹配 engine.get_user(email) → Optional[dict]"""
        return self._engine.get_user(email)

    # ── Session ──

    def create_session(self, email: str) -> str:
        """匹配 engine.create_session(email) → str (session_id)"""
        return self._engine.create_session(email)

    def switch_session(self, email: str, session_id: str) -> bool:
        """匹配 engine.switch_session(email, session_id) → bool"""
        return self._engine.switch_session(email, session_id)

    def list_sessions(self, email: str) -> list[dict]:
        """匹配 engine.list_sessions(email) → list[dict]"""
        return self._engine.list_sessions(email)

    def delete_session(self, email: str, session_id: str) -> dict:
        """匹配 engine.delete_session(email, session_id) → dict"""
        return self._engine.delete_session(email, session_id)

    # ── 消息 ──

    def get_history(
        self,
        email: str,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        """匹配 engine.get_history(email, session_id, limit, offset) → list[dict]"""
        return self._engine.get_history(email, session_id, limit=limit, offset=offset)

    async def chat_stream(
        self,
        email: str,
        session_id: str,
        message: str,
        options: dict = None,
        attachments: list = None,
    ) -> AsyncIterator[str]:
        """匹配 engine.chat_stream(email, session_id, message, options, attachments) → AsyncIterator[str]"""
        async for event in self._engine.chat_stream(email, session_id, message, options=options, attachments=attachments):
            yield event

    # ── 系统 ──

    async def get_agent_status(self) -> dict:
        return await self._engine.get_agent_status()

    async def get_tools(self) -> dict:
        return await self._engine.get_tools()

    def get_pending_messages(self, session_id: str = None) -> list:
        """匹配 engine.get_pending_messages(session_id) → list"""
        return self._engine.get_pending_messages(session_id)

    async def get_context_preview(self, email: str, session_id: str, message: str) -> dict:
        """匹配 engine.get_context_preview(email, session_id, message) → dict"""
        return await self._engine.get_context_preview(email, session_id, message)

    def close(self):
        if hasattr(self._engine, 'close'):
            self._engine.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JSON 文件后端（Engine 未就绪时的回退方案）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class JsonFileEngineClient:
    """
    JSON 文件 Engine 实现（回退方案）。

    接口签名与 RpcEngineClient 完全一致（匹配 Engine 定义）。
    数据目录:
      data/users.json                      — 用户记录
      data/conversations/{email}/{sid}.json — 对话历史
    """

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._users_db = data_dir / "users.json"
        self._conversations_dir = data_dir / "conversations"
        self._ready = False

        data_dir.mkdir(parents=True, exist_ok=True)
        self._conversations_dir.mkdir(parents=True, exist_ok=True)

    # ── 用户存储 ──

    def _load_users(self) -> dict:
        if not self._users_db.exists():
            return {}
        data = json.loads(self._users_db.read_text())
        for v in data.values():
            if "session_id" in v and "current_session_id" not in v:
                v["current_session_id"] = v.pop("session_id")
            if "session_ids" not in v:
                v["session_ids"] = (
                    [v.get("current_session_id", "")]
                    if v.get("current_session_id")
                    else []
                )
        return data

    def _save_users(self, users: dict) -> None:
        self._users_db.write_text(json.dumps(users, indent=2, ensure_ascii=False))

    def _get_conv_path(self, email: str, session_id: str) -> Path:
        safe = email.replace("@", "_at_").replace(".", "_")
        d = self._conversations_dir / safe
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{session_id}.json"

    def _load_conv(self, email: str, session_id: str) -> list:
        p = self._get_conv_path(email, session_id)
        return json.loads(p.read_text()) if p.exists() else []

    def _save_conv(self, email: str, session_id: str, history: list) -> None:
        self._get_conv_path(email, session_id).write_text(
            json.dumps(history, ensure_ascii=False, indent=2)
        )

    # ── 接口 (匹配 Engine 定义) ──

    def auth(self, email: str, device_id: str) -> dict:
        users = self._load_users()

        if email in users:
            u = users[email]
            if device_id not in u["device_ids"]:
                u["device_ids"].append(device_id)
            u["last_active"] = time.time()
            if not u.get("current_session_id"):
                sid = f"conv_{uuid.uuid4().hex[:12]}"
                u["current_session_id"] = sid
                u["session_ids"] = [sid]
            self._save_users(users)
            return {
                "email": u["email"],
                "session_id": u["current_session_id"],
                "display_name": u.get("display_name", ""),
                "is_new": False,
            }

        sid = f"conv_{uuid.uuid4().hex[:12]}"
        u = {
            "email": email,
            "device_ids": [device_id],
            "current_session_id": sid,
            "session_ids": [sid],
            "created_at": time.time(),
            "last_active": time.time(),
            "display_name": "",
        }
        users[email] = u
        self._save_users(users)
        return {
            "email": email,
            "session_id": sid,
            "display_name": "",
            "is_new": True,
        }

    def get_user(self, email: str) -> Optional[dict]:
        users = self._load_users()
        if email not in users:
            return None
        u = users[email]
        return {
            "email": u["email"],
            "session_id": u["current_session_id"],
            "display_name": u.get("display_name", ""),
            "last_active": u.get("last_active", 0),
        }

    def create_session(self, email: str) -> str:
        users = self._load_users()
        if email not in users:
            raise KeyError(f"用户不存在: {email}")
        u = users[email]
        sid = f"conv_{uuid.uuid4().hex[:12]}"
        u.setdefault("session_ids", []).append(sid)
        u["current_session_id"] = sid
        u["last_active"] = time.time()
        self._save_users(users)
        return sid

    def switch_session(self, email: str, session_id: str) -> bool:
        users = self._load_users()
        if email not in users:
            return False
        u = users[email]
        if session_id not in u.get("session_ids", []):
            return False
        u["current_session_id"] = session_id
        u["last_active"] = time.time()
        self._save_users(users)
        return True

    def list_sessions(self, email: str) -> list[dict]:
        users = self._load_users()
        if email not in users:
            return []
        u = users[email]
        sessions = []
        for sid in u.get("session_ids", []):
            history = self._load_conv(email, sid)
            preview = ""
            for msg in history:
                if msg["role"] == "user":
                    c = msg["content"]
                    preview = c[:50] + ("..." if len(c) > 50 else "")
                    break
            sessions.append({
                "session_id": sid,
                "is_current": sid == u["current_session_id"],
                "message_count": len(history),
                "preview": preview or "新对话",
                "last_message_time": history[-1]["timestamp"] if history else 0,
            })
        sessions.sort(key=lambda s: s["last_message_time"], reverse=True)
        return sessions

    def get_history(
        self,
        email: str,
        session_id: str,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        history = self._load_conv(email, session_id)
        return history[offset:offset + limit]

    async def chat_stream(
        self,
        email: str,
        session_id: str,
        message: str,
        options: dict = None,
        attachments: list = None,
    ) -> AsyncIterator[str]:
        """
        Mock 流式回复（回退方案）。
        Engine 就绪后无需此实现。
        """
        # 保存用户消息
        self.save_message(email, session_id, "user", message)

        reply = f"收到你的消息：「{message}」。Agent Bridge 对接后这里会是真正的 AI 回复。"
        for char in reply:
            yield f"data: {json.dumps({'choices': [{'delta': {'content': char}}]})}\n\n"
            await asyncio.sleep(0.02)

        self.save_message(email, session_id, "assistant", reply)
        yield "data: [DONE]\n\n"

    # ── 内部方法 ──

    def save_message(self, email: str, session_id: str, role: str, content: str) -> None:
        """保存消息（仅 JSON 回退方案需要）。"""
        history = self._load_conv(email, session_id)
        history.append({"role": role, "content": content, "timestamp": time.time()})
        self._save_conv(email, session_id, history)

    async def get_context_preview(self, email: str, session_id: str, message: str) -> dict:
        """获取上下文预览（JSON 回退方案）。"""
        history = self._load_conv(email, session_id)
        # 简单实现：返回历史预览 + 当前消息
        history_preview = []
        for msg in history[-10:]:  # 最多显示最后 10 条消息
            content = msg["content"]
            preview = content[:100] + ("..." if len(content) > 100 else "")
            history_preview.append({
                "role": msg["role"],
                "content": preview,
                "full_length": len(content),
            })
        
        system_prompt = "你是一个有帮助的助手。"
        history_tokens = sum(len(h["content"]) // 4 for h in history_preview)
        system_tokens = len(system_prompt) // 4
        current_tokens = len(message) // 4
        
        return {
            "system_prompt": system_prompt,
            "history": history_preview,
            "current_message": message,
            "history_count": len(history),
            "history_token_estimate": history_tokens,
            "system_token_estimate": system_tokens,
            "current_token_estimate": current_tokens,
            "total_token_estimate": system_tokens + history_tokens + current_tokens,
        }

    def close(self):
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 工厂函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def create_engine_client(data_dir: Path) -> RpcEngineClient | JsonFileEngineClient:
    """
    创建 Engine 客户端。

    默认使用 RpcEngineClient（真实 Engine），初始化失败时 fail fast。
    仅当显式设置 CONVEY_ENGINE_BACKEND=json 时才使用 JSON 文件回退。

    环境变量:
      CONVEY_ENGINE_BACKEND=rpc  (默认) — 生产模式，Engine 必须可用
      CONVEY_ENGINE_BACKEND=json       — 开发模式，使用 JSON 文件存储
    """
    backend = os.environ.get("CONVEY_ENGINE_BACKEND", "rpc").lower()

    if backend == "json":
        print("[engine_client] ⚠️  CONVEY_ENGINE_BACKEND=json，使用 JSON 文件方案（开发模式）")
        return JsonFileEngineClient(data_dir)

    # 生产模式：Engine 必须可用，否则 fail fast
    client = RpcEngineClient()
    print("[engine_client] ✅ 使用 RPC Engine (ConversationEngine)")
    return client
