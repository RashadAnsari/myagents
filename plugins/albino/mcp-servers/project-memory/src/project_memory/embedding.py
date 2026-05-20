import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

EMBEDDING_DIM = 384
_MODEL_ID = "BAAI/bge-small-en-v1.5"

_model: "TextEmbedding | None" = None


def _get_model() -> "TextEmbedding":
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(_MODEL_ID)
    return _model


def embed_sync(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    return [emb.tolist() for emb in model.embed(texts)]


async def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(embed_sync, texts)


def memory_embed_text(content: str, summary: str | None, tags: list[str]) -> str:
    parts = [content]
    if summary:
        parts.append(summary)
    if tags:
        parts.append(" ".join(tags))
    return " ".join(parts)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    denom = mag_a * mag_b
    return dot / denom if denom != 0 else 0.0
