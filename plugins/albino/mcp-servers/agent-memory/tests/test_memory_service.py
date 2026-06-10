import pytest

from agent_memory.memory_service import MemoryQualityError, ProjectMemoryService, UserMemoryService
from agent_memory.paths import (
    _normalize_git_remote,
    default_database_path,
    fingerprint_remote,
    normalize_project_root,
)


async def test_remember_rejects_non_git_directory(service: ProjectMemoryService, tmp_dir, monkeypatch):
    import agent_memory.paths as paths_module

    monkeypatch.setattr(paths_module, "get_git_root", lambda _: None)
    with pytest.raises(ValueError, match="not a git repository"):
        await service.remember(
            project_root=str(tmp_dir),
            content="This memory should be rejected because the directory has no git repository initialized.",
        )


async def test_subdirectory_path_shares_project_with_git_root(service: ProjectMemoryService, tmp_dir):
    subdir = tmp_dir / "src" / "module"
    subdir.mkdir(parents=True)

    mem_root = await service.remember(
        project_root=str(tmp_dir),
        content="All public functions must have a corresponding unit test in the tests directory at the repo root.",
    )
    mem_sub = await service.remember(
        project_root=str(subdir),
        content="The module layer owns all business logic and must never import directly from the API handlers layer.",
    )

    assert mem_root.project_id == mem_sub.project_id

    results_from_root = await service.search(project_root=str(tmp_dir), query="unit test convention module decision")
    results_from_sub = await service.search(project_root=str(subdir), query="unit test convention module decision")

    root_ids = {m.id for m in results_from_root}
    sub_ids = {m.id for m in results_from_sub}
    assert mem_root.id in root_ids
    assert mem_sub.id in root_ids
    assert root_ids == sub_ids


async def test_stores_and_searches_durable_memory(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="Use the agent-memory MCP server for durable project decisions and verify memories against repo files before acting.",
        source="test",
    )
    results = await service.search(project_root=str(tmp_dir), query="durable project decisions", k=5)

    assert memory.id > 0
    assert memory.source == "test"
    assert len(results) == 1
    assert results[0].id == memory.id
    assert "durable project decisions" in results[0].content


async def test_rejects_vague_memory(service: ProjectMemoryService, tmp_dir):
    with pytest.raises(MemoryQualityError, match="too vague"):
        await service.remember(
            project_root=str(tmp_dir),
            content="fixed the issue and all done with the work that needed to be completed for this task.",
        )


async def test_rejects_too_short_memory(service: ProjectMemoryService, tmp_dir):
    with pytest.raises(MemoryQualityError, match="too short"):
        await service.remember(
            project_root=str(tmp_dir),
            content="Use PostgreSQL.",
        )


async def test_rejects_duplicate_memory(service: ProjectMemoryService, tmp_dir):
    content = "Use the agent-memory MCP server for durable project decisions and verify memories against repo files before acting."
    await service.remember(project_root=str(tmp_dir), content=content)
    with pytest.raises(MemoryQualityError, match="duplicates"):
        await service.remember(project_root=str(tmp_dir), content=content)


async def test_archive_and_hard_delete(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="Running tests in parallel caused intermittent failures due to shared test database state not being cleaned up.",
    )
    result = service.forget(str(tmp_dir), memory.id)
    assert result["archived"] is True

    memory2 = await service.remember(
        project_root=str(tmp_dir),
        content="A second gotcha about running tests in sequence instead of parallel to avoid flaky test results here.",
    )
    result2 = service.forget(str(tmp_dir), memory2.id, hard_delete=True)
    assert result2["deleted"] is True


async def test_update_memory_content(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="All service methods must return typed result objects instead of throwing exceptions for expected error cases.",
    )
    updated = await service.update(
        project_root=str(tmp_dir),
        memory_id=memory.id,
        content="All service methods must return typed result objects instead of throwing exceptions; callers must check the result.",
    )
    assert "callers must check" in updated.content


async def test_default_database_path_uses_home():
    import os

    if "AGENT_MEMORY_DIR" in os.environ:
        pytest.skip("AGENT_MEMORY_DIR is set; default path check is not applicable.")
    path = default_database_path()
    assert "myagents" in path
    assert path.endswith("memory.sqlite")


async def test_normalize_project_root_is_absolute(tmp_dir):
    root = normalize_project_root(str(tmp_dir))
    assert root == str(tmp_dir.resolve())


def test_normalize_git_remote_strips_https_credentials():
    assert _normalize_git_remote("https://user:pass@github.com/org/repo") == "https://github.com/org/repo"


def test_normalize_git_remote_converts_ssh_to_https():
    assert _normalize_git_remote("git@github.com:org/repo.git") == "https://github.com/org/repo"


def test_normalize_git_remote_strips_dot_git_suffix():
    assert _normalize_git_remote("https://github.com/org/repo.git") == "https://github.com/org/repo"


def test_normalize_git_remote_lowercases():
    assert _normalize_git_remote("https://GitHub.com/Org/Repo") == "https://github.com/org/repo"


def test_fingerprint_remote_returns_none_for_none():
    assert fingerprint_remote(None) is None


def test_fingerprint_remote_returns_hex_string():
    result = fingerprint_remote("https://github.com/org/repo")
    assert result is not None
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_fingerprint_remote_is_deterministic():
    remote = "https://github.com/org/repo"
    assert fingerprint_remote(remote) == fingerprint_remote(remote)


async def test_user_remember_and_search(user_service: UserMemoryService):
    memory = await user_service.remember(
        content="User strongly prefers concise function names that accurately describe what the function does without abbreviation.",
        source="test",
    )
    results = await user_service.search(query="naming functions concise")
    assert memory.id > 0
    assert len(results) >= 1


async def test_user_rejects_duplicate(user_service: UserMemoryService):
    content = "User strongly prefers concise function names that accurately describe what the function does without abbreviation."
    await user_service.remember(content=content)
    with pytest.raises(MemoryQualityError, match="duplicates"):
        await user_service.remember(content=content)


async def test_user_forget_archives(user_service: UserMemoryService):
    memory = await user_service.remember(
        content="User previously used Yarn for package management but has since migrated all projects to pnpm for better performance.",
    )
    result = user_service.forget(memory.id)
    assert result["archived"] is True


async def test_archive_excludes_from_search(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="SQLite journal mode must be set to WAL before enabling foreign keys to avoid lock contention issues.",
    )
    service.forget(str(tmp_dir), memory.id)

    results = await service.search(project_root=str(tmp_dir), query="SQLite WAL journal mode foreign keys")
    assert all(r.id != memory.id for r in results)

    results_with_archived = await service.search(
        project_root=str(tmp_dir), query="SQLite WAL journal mode foreign keys", include_archived=True
    )
    assert any(r.id == memory.id for r in results_with_archived)


async def test_remember_defaults(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="All database queries must use parameterized statements to prevent SQL injection vulnerabilities in production.",
    )
    assert memory.source is None
    assert memory.source_ref is None


async def test_end_to_end_workflow(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="All Python functions must have type annotations for parameters and return values without exception.",
    )

    results = await service.search(project_root=str(tmp_dir), query="type annotations Python functions")
    assert len(results) == 1
    assert results[0].id == memory.id

    updated = await service.update(
        project_root=str(tmp_dir),
        memory_id=memory.id,
        content="All Python functions must have type annotations; mypy strict mode is enforced in CI.",
    )
    assert "mypy strict" in updated.content

    service.forget(str(tmp_dir), memory.id)
    results_after = await service.search(project_root=str(tmp_dir), query="type annotations Python")
    assert all(r.id != memory.id for r in results_after)

    with_archived = await service.search(
        project_root=str(tmp_dir), query="type annotations Python", include_archived=True
    )
    assert any(r.id == memory.id for r in with_archived)


async def test_hard_delete_removes_from_search(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="Embedding the model must be initialized lazily to avoid loading large model weights at import time.",
    )
    service.forget(str(tmp_dir), memory.id, hard_delete=True)

    results = await service.search(
        project_root=str(tmp_dir), query="embedding model lazy initialization startup", include_archived=True
    )
    assert all(r.id != memory.id for r in results)
