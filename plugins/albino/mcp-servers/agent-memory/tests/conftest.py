import os
import subprocess
from pathlib import Path

import pytest

from agent_memory.db import AgentMemoryStore
from agent_memory.memory_service import ProjectMemoryService, UserMemoryService
from agent_memory.server import create_server


def pytest_configure(config):
    config.addinivalue_line("markers", "vec: mark test as requiring the sqlite-vec extension")


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=False)
    return tmp_path


@pytest.fixture
def agent_store(tmp_path: Path) -> AgentMemoryStore:
    try:
        s = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    except Exception as exc:
        if os.environ.get("REQUIRE_VEC"):
            pytest.fail(
                f"sqlite-vec extension failed to load but REQUIRE_VEC=1 is set: {exc}. "
                "Use uv-managed Python or Homebrew Python on macOS."
            )
        pytest.skip(
            f"sqlite-vec extension failed to load ({exc}). Tests require a Python build that supports "
            "dynamic extension loading. Use uv-managed Python or Homebrew Python on macOS."
        )
    yield s
    s.close()


@pytest.fixture
def service(agent_store: AgentMemoryStore) -> ProjectMemoryService:
    return ProjectMemoryService(agent_store)


@pytest.fixture
def user_service(agent_store: AgentMemoryStore) -> UserMemoryService:
    return UserMemoryService(agent_store)


@pytest.fixture
def mcp_server(service: ProjectMemoryService, user_service: UserMemoryService):
    return create_server(service, user_service)
