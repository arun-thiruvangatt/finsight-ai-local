"""Embeddings. A local hashing embedder keeps RAG functional with zero external dependencies;
configure EMBEDDING_PROVIDER=openai for semantic quality."""
import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import AIProviderError


class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Feature-hashing bag of uni/bi-grams, L2 normalised. Deterministic, lexical (not semantic)."""

    def __init__(self, dim: int):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        feats = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        v = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.sha1(f.encode()).digest()[:8], "big")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0:
            v[0], norm = 1.0, 1.0  # never return a zero vector (undefined cosine distance)
        return [x / norm for x in v]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str, base_url: str, dim: int):
        self.api_key, self.model, self.base_url, self.dim = api_key, model, base_url.rstrip("/"), dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            batch = texts[i:i + 64]
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(f"{self.base_url}/embeddings",
                                          headers={"Authorization": f"Bearer {self.api_key}"},
                                          json={"model": self.model, "input": batch, "dimensions": self.dim})
                r.raise_for_status()
                rows = sorted(r.json()["data"], key=lambda d: d["index"])
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                raise AIProviderError("Embedding provider request failed.") from exc
            out.extend(row["embedding"] for row in rows)
        if out and len(out[0]) != self.dim:
            raise AIProviderError(f"Embedding dimension {len(out[0])} != EMBEDDING_DIM {self.dim}.")
        return out


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.EMBEDDING_PROVIDER.lower() == "openai" and s.EMBEDDING_API_KEY and s.EMBEDDING_MODEL:
        return OpenAIEmbedder(s.EMBEDDING_API_KEY, s.EMBEDDING_MODEL,
                              s.EMBEDDING_BASE_URL or "https://api.openai.com/v1", s.EMBEDDING_DIM)
    return HashingEmbedder(s.EMBEDDING_DIM)
