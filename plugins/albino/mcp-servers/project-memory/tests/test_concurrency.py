"""
Concurrency tests verifying that simultaneous asyncio coroutines sharing one
SQLite connection do not corrupt data.  embed() is mocked so tests run without
a model download and focus on the DB access pattern.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from project_memory.db import ProjectMemoryStore
from project_memory.embedding import EMBEDDING_DIM
from project_memory.memory_service import ProjectMemoryService, UserMemoryService

_VECTOR = [0.1] * EMBEDDING_DIM


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


def _make_contents(n: int) -> list[tuple[str, str]]:
    """Return n distinct (content, why) pairs that pass quality checks."""
    contents = [
        (
            "Use postgres for all persistent storage to keep infrastructure unified and avoid cache invalidation bugs.",
            "Agents need this to avoid adding Redis or Mongo unnecessarily to the technology stack.",
        ),
        (
            "All service layer methods must return typed result objects instead of raising exceptions for expected errors.",
            "Future agents should use result types rather than exception catching when implementing new service methods.",
        ),
        (
            "Database migrations must be reversible and include both up and down steps for every schema change made.",
            "Agents need this to safely roll back failed deployments without manual SQL intervention in production.",
        ),
        (
            "Use environment variables for all configuration values and never hardcode credentials in source files.",
            "Agents must read configuration from the environment to keep secrets out of version control permanently.",
        ),
        (
            "All API endpoints must validate request bodies with Pydantic schemas before processing any business logic.",
            "Future agents need this to prevent malformed data from reaching the service layer and causing silent bugs.",
        ),
        (
            "Write integration tests that hit a real database instead of mocking the DB layer for all service tests.",
            "Agents need real DB tests because mocked DB tests missed a schema migration bug in the previous quarter.",
        ),
        (
            "Use structured logging with JSON output in production to enable log aggregation and alerting by severity.",
            "Agents need structured logs to query for errors and set up alerts without parsing unstructured log strings.",
        ),
        (
            "Pin all direct dependencies to exact versions in requirements files to ensure reproducible builds everywhere.",
            "Agents need pinned deps to prevent surprise breakages from upstream package releases in CI and production.",
        ),
    ]
    return contents[:n]


async def test_concurrent_remember_creates_all_memories(svc, bare_store, tmp_path):
    pairs = _make_contents(5)
    with patch("project_memory.memory_service.embed", new=AsyncMock(return_value=[_VECTOR])):
        memories = await asyncio.gather(
            *[
                svc.remember(
                    project_root=str(tmp_path),
                    kind="decision",
                    content=content,
                    why_useful_later=why,
                )
                for content, why in pairs
            ]
        )

    assert len(memories) == 5
    assert len({m.id for m in memories}) == 5  # all unique IDs

    project = bare_store.get_or_create_project(str(tmp_path))
    active = bare_store.list_active_memories(project.id)
    assert len(active) == 5


async def test_concurrent_remember_no_id_collisions(svc, tmp_path):
    pairs = _make_contents(8)
    with patch("project_memory.memory_service.embed", new=AsyncMock(return_value=[_VECTOR])):
        memories = await asyncio.gather(
            *[
                svc.remember(
                    project_root=str(tmp_path),
                    kind="convention",
                    content=content,
                    why_useful_later=why,
                )
                for content, why in pairs
            ]
        )

    ids = [m.id for m in memories]
    assert len(ids) == len(set(ids)), "Duplicate IDs detected under concurrent inserts"


async def test_concurrent_user_remember_creates_all(user_svc, bare_store):
    pairs = _make_contents(5)
    with patch("project_memory.memory_service.embed", new=AsyncMock(return_value=[_VECTOR])):
        memories = await asyncio.gather(
            *[
                user_svc.remember(
                    kind="preference",
                    content=content,
                    why_useful_later=why,
                )
                for content, why in pairs
            ]
        )

    assert len(memories) == 5
    assert len({m.id for m in memories}) == 5

    active = bare_store.list_active_user_memories()
    assert len(active) == 5


async def test_concurrent_remember_and_search(svc, tmp_path):
    first_content, first_why = _make_contents(1)[0]
    with patch("project_memory.memory_service.embed", new=AsyncMock(return_value=[_VECTOR])):
        await svc.remember(
            project_root=str(tmp_path),
            kind="decision",
            content=first_content,
            why_useful_later=first_why,
        )

    pairs = _make_contents(8)[1:]  # skip the already-stored first one
    with patch("project_memory.memory_service.embed", new=AsyncMock(return_value=[_VECTOR])):
        results = await asyncio.gather(
            svc.search(project_root=str(tmp_path), query="postgres storage"),
            *[
                svc.remember(
                    project_root=str(tmp_path),
                    kind="decision",
                    content=content,
                    why_useful_later=why,
                )
                for content, why in pairs
            ],
        )

    search_results = results[0]
    assert isinstance(search_results, list)
