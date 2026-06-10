"""
Concurrency tests verifying that simultaneous asyncio coroutines sharing one
SQLite connection do not corrupt data. embed_one() is mocked so tests run without
a model download and focus on the DB access pattern.
"""

import asyncio
import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from agent_memory.db import AgentMemoryStore
from agent_memory.embedding import EMBEDDING_DIM
from agent_memory.memory_service import ProjectMemoryService, UserMemoryService

_VECTOR = [0.1] * EMBEDDING_DIM


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


_CONTENTS = [
    "Use postgres for all persistent storage to keep infrastructure unified and avoid cache invalidation bugs.",
    "All service layer methods must return typed result objects instead of raising exceptions for expected errors.",
    "Database migrations must be reversible and include both up and down steps for every schema change made.",
    "Use environment variables for all configuration values and never hardcode credentials in source files.",
    "All API endpoints must validate request bodies with Pydantic schemas before processing any business logic.",
    "Write integration tests that hit a real database instead of mocking the DB layer for all service tests.",
    "Use structured logging with JSON output in production to enable log aggregation and alerting by severity.",
    "Pin all direct dependencies to exact versions in requirements files to ensure reproducible builds everywhere.",
]


async def test_concurrent_remember_creates_all_memories(svc, bare_store, tmp_path):
    with patch("agent_memory.memory_service.embed_one", new=AsyncMock(return_value=_VECTOR)):
        memories = await asyncio.gather(
            *[svc.remember(project_root=str(tmp_path), content=content) for content in _CONTENTS[:5]]
        )

    assert len(memories) == 5
    assert len({m.id for m in memories}) == 5

    project = bare_store.get_or_create_project(str(tmp_path))
    active = bare_store.list_active_project_memories(project.id)
    assert len(active) == 5


async def test_concurrent_remember_no_id_collisions(svc, tmp_path):
    with patch("agent_memory.memory_service.embed_one", new=AsyncMock(return_value=_VECTOR)):
        memories = await asyncio.gather(
            *[svc.remember(project_root=str(tmp_path), content=content) for content in _CONTENTS]
        )

    ids = [m.id for m in memories]
    assert len(ids) == len(set(ids)), "Duplicate IDs detected under concurrent inserts"


async def test_concurrent_user_remember_creates_all(user_svc, bare_store):
    with patch("agent_memory.memory_service.embed_one", new=AsyncMock(return_value=_VECTOR)):
        memories = await asyncio.gather(*[user_svc.remember(content=content) for content in _CONTENTS[:5]])

    assert len(memories) == 5
    assert len({m.id for m in memories}) == 5

    active = bare_store.list_active_user_memories()
    assert len(active) == 5


async def test_concurrent_remember_and_search(svc, tmp_path):
    with patch("agent_memory.memory_service.embed_one", new=AsyncMock(return_value=_VECTOR)):
        await svc.remember(project_root=str(tmp_path), content=_CONTENTS[0])

    with patch("agent_memory.memory_service.embed_one", new=AsyncMock(return_value=_VECTOR)):
        results = await asyncio.gather(
            svc.search(project_root=str(tmp_path), query="postgres storage"),
            *[svc.remember(project_root=str(tmp_path), content=content) for content in _CONTENTS[1:]],
        )

    search_results = results[0]
    assert isinstance(search_results, list)
