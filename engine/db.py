"""Engine DB — thin wrapper, delegates to ConversationDB."""

import json as _json
import logging

from conversation.db import ConversationDB

logger = logging.getLogger(__name__)


class EngineDB(ConversationDB):
    """Backward-compatible wrapper. All logic lives in ConversationDB."""

    def get_session_bridge_node(self, session_id: str) -> str:
        """获取 session 对应的 Bridge 节点。"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT bridge_node FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return row["bridge_node"] if row else "local"

    def get_orphaned_user_messages(self) -> list[dict]:
        """
        获取没有对应 AI 回复的用户消息（用于恢复）。

        查找最后一条用户消息后没有 assistant 消息的会话。
        """
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT m.* FROM messages m
                INNER JOIN (
                    SELECT session_id, MAX(created_at) as max_time
                    FROM messages
                    GROUP BY session_id
                ) latest ON m.session_id = latest.session_id AND m.created_at = latest.max_time
                WHERE m.role = 'user'
                ORDER BY m.created_at DESC
            """).fetchall()

            orphans = []
            for r in rows:
                d = dict(r)
                try:
                    meta = _json.loads(d["metadata"]) if d["metadata"] else {}
                except (ValueError, TypeError):
                    meta = {}
                if meta.get("status") in ("pending", "processing"):
                    d["metadata"] = meta
                    orphans.append(d)
            return orphans

    def mark_stale_processing_as_pending(self) -> int:
        """
        启动时将所有 processing 状态的消息标记为 pending（待重试）。

        Returns:
            被标记的消息数量
        """
        count = 0
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, metadata FROM messages WHERE role = 'user'"
            ).fetchall()
            for r in rows:
                try:
                    meta = _json.loads(r["metadata"]) if r["metadata"] else {}
                except (ValueError, TypeError):
                    continue
                if meta.get("status") == "processing":
                    meta["status"] = "pending"
                    conn.execute(
                        "UPDATE messages SET metadata = ? WHERE id = ?",
                        (_json.dumps(meta, ensure_ascii=False), r["id"]),
                    )
                    count += 1
        return count
