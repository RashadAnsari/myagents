import asyncio
import os

from fastembed import TextEmbedding

EMBEDDING_DIM = 384
_MODEL_ID = os.environ.get("AGENT_MEMORY_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
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


async def embed_one(text: str) -> list[float]:
    results = await embed([text])
    if not results:
        raise RuntimeError("Embedding returned empty result.")
    return results[0]
