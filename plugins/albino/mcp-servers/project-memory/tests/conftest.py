from pathlib import Path

import pytest

from project_memory.db import ProjectMemoryStore
from project_memory.memory_service import ProjectMemoryService, UserMemoryService
from project_memory.server import create_server


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def store(tmp_path: Path) -> ProjectMemoryStore:
    s = ProjectMemoryStore(str(tmp_path / "memory.sqlite"))
    if not s._vec_available:
        s.close()
        pytest.skip(
            "sqlite-vec extension failed to load. Vector search tests require a Python build that supports "
            "dynamic extension loading. Use uv-managed Python or Homebrew Python on macOS."
        )
    yield s
    s.close()


@pytest.fixture
def service(store: ProjectMemoryStore) -> ProjectMemoryService:
    return ProjectMemoryService(store)


@pytest.fixture
def user_service(store: ProjectMemoryStore) -> UserMemoryService:
    return UserMemoryService(store)


@pytest.fixture
def mcp_server(service: ProjectMemoryService, user_service: UserMemoryService):
    return create_server(service, user_service)
