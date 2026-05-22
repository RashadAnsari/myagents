from unittest.mock import AsyncMock, patch

import pytest

from project_memory.db import ProjectMemoryStore
from project_memory.memory_service import ProjectMemoryService, UserMemoryService


@pytest.fixture
def bare_store(tmp_path):
    s = ProjectMemoryStore(str(tmp_path / "memory.sqlite"))
    yield s
    s.close()


@pytest.fixture
def svc(bare_store):
    return ProjectMemoryService(bare_store)


@pytest.fixture
def user_svc(bare_store):
    return UserMemoryService(bare_store)


_CONTENT = "Embedding failure test memory with enough words and characters to pass quality checks."
_WHY = "Future agents need this to verify rollback behavior when embedding generation fails unexpectedly."
_USER_CONTENT = "User embedding failure test preference with sufficient length to pass quality validation checks."
_USER_WHY = "Agents need this to verify user memory rollback when the embedding model raises an exception."


async def test_project_remember_rolls_back_on_embed_error(svc, bare_store, tmp_path):
    with patch("project_memory.memory_service.embed", new=AsyncMock(side_effect=RuntimeError("model down"))):
        with pytest.raises(RuntimeError, match="model down"):
            await svc.remember(
                project_root=str(tmp_path),
                kind="decision",
                content=_CONTENT,
                why_useful_later=_WHY,
            )

    active = bare_store.list_active_memories(bare_store.get_or_create_project(str(tmp_path)).id)
    assert len(active) == 0


async def test_project_remember_raises_on_empty_embed(svc, tmp_path):
    with patch("project_memory.memory_service.embed", new=AsyncMock(return_value=[])):
        with pytest.raises(RuntimeError, match="empty result"):
            await svc.remember(
                project_root=str(tmp_path),
                kind="decision",
                content=_CONTENT,
                why_useful_later=_WHY,
            )


async def test_project_remember_reraises_when_cleanup_also_fails(svc, tmp_path):
    with patch("project_memory.memory_service.embed", new=AsyncMock(side_effect=RuntimeError("model down"))):
        with patch.object(svc._store, "hard_delete_memory", side_effect=RuntimeError("db locked")):
            with pytest.raises(RuntimeError, match="model down"):
                await svc.remember(
                    project_root=str(tmp_path),
                    kind="decision",
                    content=_CONTENT,
                    why_useful_later=_WHY,
                )


async def test_user_remember_rolls_back_on_embed_error(user_svc, bare_store):
    with patch("project_memory.memory_service.embed", new=AsyncMock(side_effect=RuntimeError("model down"))):
        with pytest.raises(RuntimeError, match="model down"):
            await user_svc.remember(
                kind="preference",
                content=_USER_CONTENT,
                why_useful_later=_USER_WHY,
            )

    active = bare_store.list_active_user_memories()
    assert len(active) == 0


async def test_user_remember_raises_on_empty_embed(user_svc):
    with patch("project_memory.memory_service.embed", new=AsyncMock(return_value=[])):
        with pytest.raises(RuntimeError, match="empty result"):
            await user_svc.remember(
                kind="preference",
                content=_USER_CONTENT,
                why_useful_later=_USER_WHY,
            )


async def test_user_remember_reraises_when_cleanup_also_fails(user_svc):
    with patch("project_memory.memory_service.embed", new=AsyncMock(side_effect=RuntimeError("model down"))):
        with patch.object(user_svc._store, "hard_delete_user_memory", side_effect=RuntimeError("db locked")):
            with pytest.raises(RuntimeError, match="model down"):
                await user_svc.remember(
                    kind="preference",
                    content=_USER_CONTENT,
                    why_useful_later=_USER_WHY,
                )
