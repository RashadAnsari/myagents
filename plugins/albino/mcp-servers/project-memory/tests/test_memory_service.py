import pytest

from project_memory.memory_service import MemoryQualityError, ProjectMemoryService, UserMemoryService
from project_memory.paths import default_database_path, normalize_project_root


async def test_stores_and_searches_durable_memory(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        kind="decision",
        content="Use the project-memory MCP server for durable project decisions and verify memories against repo files before acting.",
        why_useful_later="Future agents need this to retrieve useful project context without trusting stale notes blindly.",
        tags=["mcp", "memory"],
        confidence="high",
        source="test",
    )
    results = await service.search(project_root=str(tmp_dir), query="durable project decisions", k=5)

    assert memory.id > 0
    assert len(results) == 1
    assert "durable project decisions" in results[0].content


async def test_filters_search_results_by_kind_and_tag(service: ProjectMemoryService, tmp_dir):
    await service.remember(
        project_root=str(tmp_dir),
        kind="decision",
        content="Memory search should support decision filtering for architecture discussions about durable context retrieval.",
        why_useful_later="Future agents need filtered retrieval when many memory kinds exist in the same project.",
        tags=["architecture", "retrieval"],
        confidence="high",
    )
    await service.remember(
        project_root=str(tmp_dir),
        kind="gotcha",
        content="Memory search should also store gotchas about retrieval behavior without mixing them into decision results.",
        why_useful_later="Future agents need gotcha filtering separately from durable architecture decisions.",
        tags=["retrieval"],
        confidence="medium",
    )
    results = await service.search(
        project_root=str(tmp_dir),
        query="retrieval",
        kinds=["decision"],
        tags=["architecture"],
    )
    assert len(results) == 1
    assert results[0].kind == "decision"
    assert "architecture" in results[0].tags


async def test_rejects_vague_memory(service: ProjectMemoryService, tmp_dir):
    with pytest.raises(MemoryQualityError, match="too vague"):
        await service.remember(
            project_root=str(tmp_dir),
            kind="handoff",
            content="fixed the issue and all done with the work that needed to be completed for this task.",
            why_useful_later="Future agents need to know what was done so they can continue the work effectively.",
        )


async def test_rejects_too_short_memory(service: ProjectMemoryService, tmp_dir):
    with pytest.raises(MemoryQualityError, match="too short"):
        await service.remember(
            project_root=str(tmp_dir),
            kind="decision",
            content="Use PostgreSQL.",
            why_useful_later="Agents need to know the database.",
        )


async def test_rejects_duplicate_memory(service: ProjectMemoryService, tmp_dir):
    content = "Use the project-memory MCP server for durable project decisions and verify memories against repo files before acting."
    why = "Future agents need this to retrieve useful project context without trusting stale notes blindly."
    await service.remember(project_root=str(tmp_dir), kind="decision", content=content, why_useful_later=why)
    with pytest.raises(MemoryQualityError, match="duplicates"):
        await service.remember(project_root=str(tmp_dir), kind="decision", content=content, why_useful_later=why)


async def test_archive_and_hard_delete(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        kind="gotcha",
        content="Running tests in parallel caused intermittent failures due to shared test database state not being cleaned up.",
        why_useful_later="Future agents need isolated databases to avoid non-deterministic failures in parallel test runs.",
    )
    result = service.forget(str(tmp_dir), memory.id, reason="Resolved.")
    assert result["archived"] is True

    # Hard delete
    memory2 = await service.remember(
        project_root=str(tmp_dir),
        kind="gotcha",
        content="A second gotcha about running tests in sequence instead of parallel to avoid flaky test results here.",
        why_useful_later="Future agents need to know this to prevent flaky tests caused by parallel test execution issues.",
    )
    result2 = service.forget(str(tmp_dir), memory2.id, hard_delete=True, reason="Cleaned up.")
    assert result2["deleted"] is True


async def test_update_memory(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        kind="convention",
        content="All service methods must return typed result objects instead of throwing exceptions for expected error cases.",
        why_useful_later="Future agents should use result types rather than exceptions when implementing service methods.",
        confidence="medium",
    )
    updated = await service.update(
        project_root=str(tmp_dir),
        memory_id=memory.id,
        confidence="high",
        reason="Confirmed across all service files.",
    )
    assert updated.confidence == "high"


async def test_project_brief_groups_by_kind(service: ProjectMemoryService, tmp_dir):
    await service.remember(
        project_root=str(tmp_dir),
        kind="decision",
        content="The project uses event sourcing with CQRS pattern for the core domain logic and command handling.",
        why_useful_later="Future agents need this architectural decision to avoid implementing conflicting patterns.",
        confidence="high",
    )
    await service.remember(
        project_root=str(tmp_dir),
        kind="gotcha",
        content="SQLite WAL mode must be enabled before any other PRAGMA to avoid locking issues on concurrent reads.",
        why_useful_later="Future agents need to know WAL mode setup order to avoid database locking problems.",
        confidence="high",
    )
    brief = service.project_brief(str(tmp_dir))
    assert "decisions" in brief
    assert "pitfalls" in brief
    assert any("event sourcing" in m.content for m in brief["decisions"])
    assert any("WAL mode" in m.content for m in brief["pitfalls"])


async def test_default_database_path_uses_home():
    import os

    if "MYAGENTS_MEMORY_DIR" in os.environ:
        pytest.skip("MYAGENTS_MEMORY_DIR is set; default path check is not applicable.")
    path = default_database_path()
    assert "myagents" in path
    assert path.endswith("memory.sqlite")


async def test_normalize_project_root_is_absolute(tmp_dir):
    root = normalize_project_root(str(tmp_dir))
    assert root == str(tmp_dir.resolve())


async def test_user_remember_and_search(user_service: UserMemoryService):
    memory = await user_service.remember(
        kind="preference",
        content="User strongly prefers concise function names that accurately describe what the function does without abbreviation.",
        why_useful_later="Agents should avoid abbreviated function names and prefer clarity when naming functions.",
        confidence="high",
    )
    results = await user_service.search(query="naming functions concise")
    assert memory.id > 0
    assert len(results) >= 1


async def test_user_rejects_duplicate(user_service: UserMemoryService):
    content = "User strongly prefers concise function names that accurately describe what the function does without abbreviation."
    why = "Agents should avoid abbreviated function names and prefer clarity when naming functions."
    await user_service.remember(kind="preference", content=content, why_useful_later=why)
    with pytest.raises(MemoryQualityError, match="duplicates"):
        await user_service.remember(kind="preference", content=content, why_useful_later=why)


async def test_user_brief_groups_correctly(user_service: UserMemoryService):
    await user_service.remember(
        kind="preference",
        content="User prefers TypeScript strict mode enabled in all projects and treats type errors as build failures.",
        why_useful_later="Agents should enable strict mode and never use any-casts when writing TypeScript for this user.",
        confidence="high",
    )
    await user_service.remember(
        kind="context",
        content="User is a senior backend engineer with eight years of experience primarily in Go and TypeScript systems.",
        why_useful_later="Agents can assume deep language knowledge and skip basic explanations for this user.",
        confidence="high",
    )
    brief = user_service.brief()
    assert any("strict mode" in m.content for m in brief["preferences"])
    assert any("senior" in m.content for m in brief["context"])


async def test_user_forget_archives(user_service: UserMemoryService):
    memory = await user_service.remember(
        kind="tool_preference",
        content="User previously used Yarn for package management but has since migrated all projects to pnpm for better performance.",
        why_useful_later="Agents should use pnpm and not suggest Yarn for this user's projects.",
        confidence="high",
    )
    result = user_service.forget(memory.id, reason="Already migrated.")
    assert result["archived"] is True
