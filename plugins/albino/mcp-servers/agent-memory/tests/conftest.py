import os
from pathlib import Path

import pytest

from agent_memory.db import AgentMemoryStore
from agent_memory.memory_service import ProjectMemoryService, UserMemoryService
from agent_memory.server import create_server


def pytest_configure(config):
    config.addinivalue_line("markers", "vec: mark test as requiring the sqlite-vec extension")


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def store(tmp_path: Path) -> AgentMemoryStore:
    s = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    if not s._vec_available:
        s.close()
        if os.environ.get("REQUIRE_VEC"):
            pytest.fail(
                "sqlite-vec extension failed to load but REQUIRE_VEC=1 is set. "
                "Use uv-managed Python or Homebrew Python on macOS."
            )
        pytest.skip(
            "sqlite-vec extension failed to load. Vector search tests require a Python build that supports "
            "dynamic extension loading. Use uv-managed Python or Homebrew Python on macOS."
        )
    yield s
    s.close()


@pytest.fixture
def service(store: AgentMemoryStore) -> ProjectMemoryService:
    return ProjectMemoryService(store)


@pytest.fixture
def user_service(store: AgentMemoryStore) -> UserMemoryService:
    return UserMemoryService(store)


@pytest.fixture
def mcp_server(service: ProjectMemoryService, user_service: UserMemoryService):
    return create_server(service, user_service)
