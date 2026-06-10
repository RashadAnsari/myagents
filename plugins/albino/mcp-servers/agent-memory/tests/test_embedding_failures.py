import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from agent_memory.db import AgentMemoryStore
from agent_memory.memory_service import ProjectMemoryService, UserMemoryService


@pytest.fixture
def bare_store(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=False)
    s = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    yield s
    s.close()


@pytest.fixture
def svc(bare_store):
    return ProjectMemoryService(bare_store)


@pytest.fixture
def user_svc(bare_store):
    return UserMemoryService(bare_store)


_CONTENT = "Embedding failure test memory with enough words and characters to pass quality checks."
_USER_CONTENT = "User embedding failure test preference with sufficient length to pass quality validation checks."


async def test_project_remember_leaves_db_clean_on_embed_error(svc, bare_store, tmp_path):
    with patch("agent_memory.memory_service.embed_one", new=AsyncMock(side_effect=RuntimeError("model down"))):
        with pytest.raises(RuntimeError, match="model down"):
            await svc.remember(project_root=str(tmp_path), content=_CONTENT)

    active = bare_store.list_active_project_memories(bare_store.get_or_create_project(str(tmp_path)).id)
    assert len(active) == 0


async def test_project_remember_raises_on_empty_embed(svc, tmp_path):
    with patch(
        "agent_memory.memory_service.embed_one",
        new=AsyncMock(side_effect=RuntimeError("Embedding returned empty result.")),
    ):
        with pytest.raises(RuntimeError, match="empty result"):
            await svc.remember(project_root=str(tmp_path), content=_CONTENT)


async def test_user_remember_leaves_db_clean_on_embed_error(user_svc, bare_store):
    with patch("agent_memory.memory_service.embed_one", new=AsyncMock(side_effect=RuntimeError("model down"))):
        with pytest.raises(RuntimeError, match="model down"):
            await user_svc.remember(content=_USER_CONTENT)

    active = bare_store.list_active_user_memories()
    assert len(active) == 0


async def test_user_remember_raises_on_empty_embed(user_svc):
    with patch(
        "agent_memory.memory_service.embed_one",
        new=AsyncMock(side_effect=RuntimeError("Embedding returned empty result.")),
    ):
        with pytest.raises(RuntimeError, match="empty result"):
            await user_svc.remember(content=_USER_CONTENT)
