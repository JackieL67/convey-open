"""MemoryDAO — SQLite persistence for memory_entries."""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np


class MemoryDAO:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    message_ids TEXT DEFAULT '[]',
                    pending_review INTEGER DEFAULT 0,
                    base_score REAL DEFAULT 1.0,
                    created_at REAL NOT NULL,
                    last_recalled_at REAL DEFAULT 0,
                    recall_count INTEGER DEFAULT 0,
                    superseded_by INTEGER DEFAULT NULL,
                    FOREIGN KEY (superseded_by) REFERENCES memory_entries(id)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_user
                    ON memory_entries(user_id);
                CREATE INDEX IF NOT EXISTS idx_memory_active
                    ON memory_entries(user_id, superseded_by);
            """)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_active(self, user_id: str) -> list[dict]:
        """Return non-superseded entries for user, with embeddings as np.ndarray."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memory_entries WHERE user_id = ? AND superseded_by IS NULL",
                (user_id,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["embedding"] = np.frombuffer(d["embedding"], dtype=np.float32)
            try:
                d["message_ids"] = json.loads(d["message_ids"] or "[]")
            except (ValueError, TypeError):
                d["message_ids"] = []
            result.append(d)
        return result

    def record_recall(self, entry_id: int) -> None:
        """Bump recall_count and last_recalled_at for an entry."""
        with self._conn() as conn:
            conn.execute(
                """UPDATE memory_entries
                   SET recall_count = recall_count + 1,
                       last_recalled_at = ?
                   WHERE id = ?""",
                (time.time(), entry_id),
            )

    def insert(
        self,
        user_id: str,
        content: str,
        embedding: np.ndarray,
        message_ids: list[int],
        pending_review: bool = False,
    ) -> int:
        """Insert a new memory entry. Returns the new row id."""
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO memory_entries
                   (user_id, content, embedding, message_ids, pending_review, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    content,
                    sqlite3.Binary(embedding.tobytes()),
                    json.dumps(message_ids),
                    1 if pending_review else 0,
                    time.time(),
                ),
            )
            return cursor.lastrowid

    def supersede(self, old_id: int, new_id: int) -> None:
        """Mark old entry as superseded by new entry."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE memory_entries SET superseded_by = ? WHERE id = ?",
                (new_id, old_id),
            )

    def get_by_id(self, entry_id: int) -> dict | None:
        """Get a single entry by id. Returns None if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memory_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["embedding"] = np.frombuffer(d["embedding"], dtype=np.float32)
        try:
            d["message_ids"] = json.loads(d["message_ids"] or "[]")
        except (ValueError, TypeError):
            d["message_ids"] = []
        return d

    def delete(self, entry_id: int) -> None:
        """Hard delete an entry."""
        with self._conn() as conn:
            conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))

    def get_pending_review(self, user_id: str) -> list[dict]:
        """Get entries flagged for LLM review (pending_review=1, not superseded)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM memory_entries
                   WHERE user_id = ? AND pending_review = 1 AND superseded_by IS NULL""",
                (user_id,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["embedding"] = np.frombuffer(d["embedding"], dtype=np.float32)
            try:
                d["message_ids"] = json.loads(d["message_ids"] or "[]")
            except (ValueError, TypeError):
                d["message_ids"] = []
            result.append(d)
        return result

    def update_content(
        self,
        entry_id: int,
        content: str,
        embedding: np.ndarray,
        message_ids: list[int],
    ) -> None:
        """Update content and embedding of an existing entry (merge path)."""
        with self._conn() as conn:
            conn.execute(
                """UPDATE memory_entries
                   SET content = ?, embedding = ?, message_ids = ?
                   WHERE id = ?""",
                (
                    content,
                    sqlite3.Binary(embedding.tobytes()),
                    json.dumps(message_ids),
                    entry_id,
                ),
            )
