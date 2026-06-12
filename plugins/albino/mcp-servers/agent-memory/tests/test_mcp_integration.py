"""MCP integration tests: exercise tools through FastMCP's in-process Client."""

import json
import subprocess

import pytest
from fastmcp import Client


def _text(result) -> str:
    """Extract first text content from a call_tool result."""
    for item in result.content:
        if hasattr(item, "text"):
            return item.text
    return ""


async def test_exposes_expected_tools(mcp_server):
    async with Client(mcp_server) as client:
        tools = await client.list_tools()

    assert {t.name for t in tools} == {
        "project_remember",
        "project_search",
        "project_update",
        "project_forget",
        "project_purge",
        "user_remember",
        "user_search",
        "user_update",
        "user_forget",
        "user_purge",
    }


async def test_stores_and_retrieves_memory_through_mcp(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "project_remember",
            {
                "project_root": str(tmp_dir),
                "content": "MCP integration tests should verify tool calls through the protocol rather than only service methods.",
            },
        )
        remembered = json.loads(_text(remember_result))

        search_result = await client.call_tool(
            "project_search",
            {
                "project_root": str(tmp_dir),
                "query": "protocol coverage",
                "k": 5,
            },
        )
        matches = json.loads(_text(search_result))

    assert remembered["id"] > 0
    assert len(matches) == 1


async def test_project_search_all_projects_through_mcp(mcp_server, tmp_dir):
    project_a = tmp_dir / "alpha-service"
    project_b = tmp_dir / "beta-service"
    for project_dir in (project_a, project_b):
        project_dir.mkdir()
        subprocess.run(["git", "init"], cwd=str(project_dir), capture_output=True, check=False)

    async with Client(mcp_server) as client:
        await client.call_tool(
            "project_remember",
            {
                "project_root": str(project_a),
                "content": "Background jobs are processed by a Celery worker pool with Redis as the broker and result backend.",
            },
        )
        await client.call_tool(
            "project_remember",
            {
                "project_root": str(project_b),
                "content": "Asynchronous task queue uses BullMQ on top of Redis with exponential backoff retries for failed jobs.",
            },
        )

        scoped_result = await client.call_tool(
            "project_search",
            {
                "project_root": str(project_a),
                "query": "task queue worker Redis jobs",
                "k": 5,
            },
        )
        scoped = json.loads(_text(scoped_result))

        spanning_result = await client.call_tool(
            "project_search",
            {
                "project_root": str(project_a),
                "query": "task queue worker Redis jobs",
                "k": 5,
                "all_projects": True,
            },
        )
        spanning = json.loads(_text(spanning_result))

    assert len(scoped) == 1
    assert len(spanning) == 2
    assert {m["project_name"] for m in spanning} == {"alpha-service", "beta-service"}
    assert all(m["project_root"] for m in spanning)


async def test_rejects_low_quality_memory_as_error(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="too short"):
            await client.call_tool(
                "project_remember",
                {
                    "project_root": str(tmp_dir),
                    "content": "fixed the issue",
                },
            )


async def test_stores_and_retrieves_user_memory_through_mcp(mcp_server):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "user_remember",
            {
                "content": "User prefers verbose commit messages that explain the why behind changes rather than just the what was done.",
            },
        )
        remembered = json.loads(_text(remember_result))

        search_result = await client.call_tool(
            "user_search",
            {
                "query": "commit messages why reasoning",
                "k": 5,
            },
        )
        matches = json.loads(_text(search_result))

    assert remembered["id"] > 0
    assert len(matches) == 1


async def test_rejects_low_quality_user_memory(mcp_server):
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="too short"):
            await client.call_tool(
                "user_remember",
                {
                    "content": "fixed the issue",
                },
            )


async def test_user_update_content(mcp_server):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "user_remember",
            {
                "content": "User strongly prefers Visual Studio Code as their primary editor over other IDEs for all development work.",
            },
        )
        remembered = json.loads(_text(remember_result))

        update_result = await client.call_tool(
            "user_update",
            {
                "id": remembered["id"],
                "content": "User strongly prefers Visual Studio Code with Vim keybindings as their primary editor for all development.",
            },
        )
        updated = json.loads(_text(update_result))

    assert "Vim" in updated["content"]


async def test_user_forget_archives(mcp_server):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "user_remember",
            {
                "content": "User prefers to work in short focused sessions of ninety minutes followed by a break before switching tasks.",
            },
        )
        remembered = json.loads(_text(remember_result))

        forget_result = await client.call_tool(
            "user_forget",
            {
                "id": remembered["id"],
            },
        )
        forgotten = json.loads(_text(forget_result))

    assert forgotten["archived"] is True
    assert forgotten["deleted"] is False


async def test_project_update_content(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "project_remember",
            {
                "project_root": str(tmp_dir),
                "content": "All service methods must return typed result objects instead of throwing exceptions for expected error cases.",
            },
        )
        remembered = json.loads(_text(remember_result))

        update_result = await client.call_tool(
            "project_update",
            {
                "project_root": str(tmp_dir),
                "id": remembered["id"],
                "content": "All service methods must return typed result objects; callers are responsible for checking results.",
            },
        )
        updated = json.loads(_text(update_result))

    assert "callers are responsible" in updated["content"]


async def test_project_forget_archives(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "project_remember",
            {
                "project_root": str(tmp_dir),
                "content": "Running tests in parallel caused intermittent failures due to shared test database state not being cleaned up properly.",
            },
        )
        remembered = json.loads(_text(remember_result))

        forget_result = await client.call_tool(
            "project_forget",
            {
                "project_root": str(tmp_dir),
                "id": remembered["id"],
            },
        )
        forgotten = json.loads(_text(forget_result))

    assert forgotten["archived"] is True
    assert forgotten["deleted"] is False
