"""Mock embedding implementation.

Uses simple hash-based vectors. Implements EmbeddingPort.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

DEFAULT_DIMENSION = 128


class HashEmbeddingService:
    """Deterministic hash-based embedding. Easy to swap for a real model."""

    def __init__(self, dimension: int = DEFAULT_DIMENSION):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def generate(self, text: str) -> np.ndarray:
        tokens = re.findall(r"[a-zA-Z_]\w*", text.lower())
        vec = np.zeros(self._dimension, dtype=np.float32)
        for token in tokens:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self._dimension
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def generate_batch(self, texts: list[str]) -> np.ndarray:
        return np.array([self.generate(t) for t in texts], dtype=np.float32)
