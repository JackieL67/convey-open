"""Embedder — OpenAI-compatible embedding via zenmux (singleton, eager-init).

Replaces the old local sentence-transformers model (~470MB) with a lightweight
API client that uses text-embedding-3-small via zenmux proxy (1536-dim vectors).
Initialised eagerly on first get() so connectivity is verified early, not on the
first user message.
"""

import logging
import os

import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL_NAME = "openai/text-embedding-3-small"
VECTOR_DIM = 1536
ZENMUX_BASE_URL = "https://zenmux.ai/api/v1"


class Embedder:
    """OpenAI-compatible embedding via zenmux. Singleton, initialised eagerly."""

    _instance: "Embedder | None" = None

    def __init__(self):
        api_key = os.environ.get("ZENMUX_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ZENMUX_API_KEY environment variable is required for embeddings"
            )
        self._client: OpenAI = OpenAI(api_key=api_key, base_url=ZENMUX_BASE_URL)
        self._dim: int = VECTOR_DIM

        # Eager warmup — verify connectivity on init, not on first chat
        try:
            self._client.embeddings.create(model=MODEL_NAME, input="warmup")
            logger.info(
                "Embedding client ready: %s (%d-dim) via %s",
                MODEL_NAME,
                VECTOR_DIM,
                ZENMUX_BASE_URL,
            )
        except Exception as e:
            logger.warning("Embedding warmup failed (non-fatal): %s", e)

    @classmethod
    def get(cls) -> "Embedder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text. Returns (1536,) float32 unit-norm vector."""
        resp = self._client.embeddings.create(model=MODEL_NAME, input=text)
        return np.asarray(resp.data[0].embedding, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts. Returns (N, 1536) float32 matrix."""
        resp = self._client.embeddings.create(model=MODEL_NAME, input=texts)
        vecs = [np.asarray(d.embedding, dtype=np.float32) for d in resp.data]
        return np.stack(vecs, axis=0)
