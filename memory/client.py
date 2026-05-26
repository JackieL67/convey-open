"""Memory client — public API for the cross-session memory system."""

import json
import logging
import math
import re
import time

import numpy as np

from data.memory_store.db import MemoryDAO
from data.memory_store.embedder import Embedder
from llm_bridge.config import LLMBridgeConfig
from llm_bridge.deepseek import DeepSeekClient
from memory.extractor import dedup_and_merge, extract_facts

logger = logging.getLogger(__name__)


class MemoryClient:
    def __init__(self, db_path: str = "data/memory_store/memory.db"):
        self.dao = MemoryDAO(db_path)
        self.embedder = Embedder.get()

    async def _extract_search_terms(self, query: str) -> list[str]:
        """Extract concise search terms from a raw user query for vector search."""
        prompt = (
            "Extract 1-3 key search terms from this user message.\n"
            "Focus on nouns, project names, technical terms, and topics.\n"
            "Output a JSON array of strings.\n"
            "If the message is short and clear, return it as-is.\n\n"
            "Examples:\n"
            "'昨天聊到那个项目帮我看看进度' → ['Convey 项目进度']\n"
            "'帮我推荐个吃的地方' → ['餐厅推荐']\n"
            "'Rust和Go哪个更好' → ['Rust', 'Go', '技术选型']\n"
            "'你好' → ['问候']\n\n"
            f"User message: {query}"
        )
        client = None
        try:
            client = DeepSeekClient(LLMBridgeConfig())
            response = await client.chat_completions_non_stream(
                [{"role": "user", "content": prompt}],
                max_tokens=256,
            )
            text = (
                (response.get("choices") or [{}])[0]
                .get("message", {})
                .get("content") or ""
            )
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                terms = json.loads(match.group())
                if terms:
                    return terms
            return [query]
        except Exception as e:
            logger.warning("_extract_search_terms failed (%s), falling back to raw query", e)
            return [query]
        finally:
            if client:
                await client.close()

    async def get(self, user_id: str, query: str, max_entries: int = 5) -> str:
        """Retrieve relevant memories, ranked by decay-adjusted similarity.

        Returns a formatted string like:
            [User memory]
            - fact 1
            - fact 2
        or empty string if no relevant memories exist.
        """
        try:
            entries = self.dao.get_active(user_id)
            if not entries:
                return ""

            # RAG step 1: query rewriting
            search_terms = await self._extract_search_terms(query)

            # RAG step 2: multi-term search, keep best score per entry
            now = time.time()
            scored_map: dict[int, tuple[float, dict]] = {}
            for term in search_terms:
                qv = self.embedder.embed(term)
                for entry in entries:
                    sim = float(np.dot(qv, entry["embedding"]))
                    if sim < 0.3:  # FIXME: 阈值待重新标定（原 MiniLM 384 维，迁移到 text-embedding-3-small 1536 维后需重新观察）
                        continue
                    eid = entry["id"]
                    if eid not in scored_map or sim > scored_map[eid][0]:
                        days_since = (
                            (now - entry["last_recalled_at"]) / 86400
                            if entry["last_recalled_at"]
                            else 99.0
                        )
                        score = (
                            entry["base_score"]
                            * (2 ** (-days_since / 99))
                            * (1 + 0.1 * math.log(entry["recall_count"] + 1))
                        )
                        scored_map[eid] = (score, {**entry, "_raw_sim": sim})

            # RAG step 3: rank and return top results
            scored = sorted(scored_map.values(), key=lambda x: x[0], reverse=True)
            top = scored[:max_entries]

            if not top:
                return ""

            for _, entry in top:
                self.dao.record_recall(entry["id"])

            lines = "\n".join(f"- {entry['content']}" for _, entry in top)
            return f"[User memory]\n{lines}"
        except Exception:
            logger.exception("get failed for user=%s", user_id)
            return ""

    async def update(self, user_id: str, messages: list[dict]) -> None:
        """Extract facts from conversation and store with dedup."""
        try:
            conversation_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in messages
            )
            facts = await extract_facts(conversation_text)
            if not facts:
                return
            existing = self.dao.get_active(user_id)
            msg_ids = [m["id"] for m in messages if m.get("id")]
            await dedup_and_merge(facts, existing, self.embedder, self.dao, user_id, message_ids=msg_ids)
        except Exception:
            logger.exception("update failed for user=%s", user_id)

    async def correct(self, user_id: str, old_id: int, new_fact: str) -> int:
        """Replace a memory entry by superseding it. Raises PermissionError if old_id doesn't belong to user_id."""
        entry = self.dao.get_by_id(old_id)
        if entry is None:
            raise ValueError(f"Memory entry {old_id} not found")
        if entry.get("user_id") != user_id:
            raise PermissionError(f"Memory entry {old_id} does not belong to {user_id}")

        cleaned_facts = await extract_facts(new_fact)
        fact_text = cleaned_facts[0] if cleaned_facts else new_fact
        vec = self.embedder.embed(fact_text)
        new_id = self.dao.insert(user_id, fact_text, vec, [])
        self.dao.supersede(old_id, new_id)
        return new_id
