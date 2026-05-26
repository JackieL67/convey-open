"""LLM-based fact extraction and semantic deduplication for memory module."""

import json
import logging
import re
import sys

import numpy as np

logger = logging.getLogger(__name__)

# llm-bridge uses a hyphenated directory name — add to path for direct import
# Bridge path resolved via package imports
if _LLM_BRIDGE_PATH not in sys.path:
    sys.path.insert(0, _LLM_BRIDGE_PATH)

EXTRACTION_PROMPT = """\
You are a memory assistant. Extract specific, verifiable facts about the user \
from the conversation below. Facts must be concrete and attributable to the user \
(not the AI). Skip vague statements, opinions, or anything unverifiable.

Output a JSON array of strings. Each string is one fact. Example:
["User lives in Beijing.", "User is a software engineer.", "User prefers Python."]

If no clear facts exist, output: []

Conversation:
{conversation_text}
"""


async def extract_facts(conversation_text: str) -> list[str]:
    """Call DeepSeek non-streaming to extract user facts from conversation text."""
    import sys
    from llm_bridge.deepseek import DeepSeekClient  # noqa: PLC0415
    from llm_bridge.config import LLMBridgeConfig   # noqa: PLC0415

    client = DeepSeekClient(LLMBridgeConfig())
    try:
        messages = [
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(conversation_text=conversation_text),
            }
        ]
        response = await client.chat_completions_non_stream(messages, max_tokens=2048)
        text = (
            (response.get("choices") or [{}])[0]
            .get("message", {})
            .get("content") or ""
        )
        # Greedy match: capture from first '[' to last ']'
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
    except Exception:
        logger.exception("extract_facts failed")
        return []
    finally:
        await client.close()


async def dedup_and_merge(
    new_facts: list[str],
    existing_entries: list[dict],
    embedder,
    dao,
    user_id: str,
    message_ids: list[int] | None = None,
) -> list[int]:
    """Deduplicate new facts against existing memory entries.

    Similarity thresholds:
      > 0.88  → merge into existing entry (update content + timestamp)
      0.65–0.88 → flag as pending_review (insert but mark for LLM review)
      < 0.65  → insert as new entry

    # FIXME: 以下阈值基于 384 维 MiniLM (paraphrase-multilingual-MiniLM-L12-v2) 标定。
    # 已迁移至 text-embedding-3-small (1536 维, via zenmux proxy)，余弦相似度分布不同，
    # 需在真实数据上观察后重新调优三个阈值（0.88 合并 / 0.65 待审 / 0.3 召回截止）。
    """
    created_ids: list[int] = []

    for fact in new_facts:
        try:
            vec = embedder.embed(fact)

            best_sim = 0.0
            best_entry = None
            for entry in existing_entries:
                sim = float(np.dot(vec, entry["embedding"]))
                if sim > best_sim:
                    best_sim = sim
                    best_entry = entry

            if best_sim > 0.88 and best_entry is not None:  # FIXME: 阈值待重新标定（原 MiniLM 384 维）
                merged_ids = list(set(best_entry["message_ids"] + (message_ids or [])))
                dao.update_content(best_entry["id"], fact, vec, merged_ids)
                created_ids.append(best_entry["id"])
            elif best_sim >= 0.65 and best_entry is not None:  # FIXME: 阈值待重新标定（原 MiniLM 384 维）
                entry_id = dao.insert(user_id, fact, vec, message_ids or [], pending_review=True)
                created_ids.append(entry_id)
            else:
                entry_id = dao.insert(user_id, fact, vec, message_ids or [])
                created_ids.append(entry_id)
        except Exception:
            logger.exception("dedup_and_merge failed for fact: %r", fact)

    return created_ids
