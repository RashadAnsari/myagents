"""MCP integration tests: exercise tools through FastMCP's in-process Client."""

import json

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
        "project.remember",
        "project.search",
        "project.brief",
        "project.update",
        "project.forget",
        "project.purge",
        "user.remember",
        "user.search",
        "user.brief",
        "user.update",
        "user.forget",
        "user.purge",
    }


async def test_stores_and_retrieves_memory_through_mcp(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "project.remember",
            {
                "project_root": str(tmp_dir),
                "kind": "decision",
                "content": "MCP integration tests should verify tool calls through the protocol rather than only service methods.",
                "why_useful_later": "Future maintainers need protocol-level coverage when changing MCP server registration.",
                "tags": ["mcp", "test"],
                "confidence": "high",
            },
        )
        remembered = json.loads(_text(remember_result))

        search_result = await client.call_tool(
            "project.search",
            {
                "project_root": str(tmp_dir),
                "query": "protocol coverage",
                "k": 5,
            },
        )
        matches = json.loads(_text(search_result))

    assert remembered["id"] > 0
    assert len(matches) == 1
    assert "mcp" in matches[0]["tags"]


async def test_rejects_low_quality_memory_as_error(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="too short"):
            await client.call_tool(
                "project.remember",
                {
                    "project_root": str(tmp_dir),
                    "kind": "handoff",
                    "content": "fixed the issue",
                    "why_useful_later": "Useful later because this says what happened.",
                },
            )


async def test_stores_and_retrieves_user_memory_through_mcp(mcp_server):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "user.remember",
            {
                "kind": "preference",
                "content": "User prefers verbose commit messages that explain the why behind changes rather than just the what was done.",
                "why_useful_later": "Agents should write detailed commit messages explaining reasoning rather than just listing changes.",
                "tags": ["git", "commits"],
                "confidence": "high",
            },
        )
        remembered = json.loads(_text(remember_result))

        search_result = await client.call_tool(
            "user.search",
            {
                "query": "commit messages why reasoning",
                "k": 5,
            },
        )
        matches = json.loads(_text(search_result))

    assert remembered["id"] > 0
    assert remembered["kind"] == "preference"
    assert len(matches) == 1
    assert "git" in matches[0]["tags"]


async def test_rejects_low_quality_user_memory(mcp_server):
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="too short"):
            await client.call_tool(
                "user.remember",
                {
                    "kind": "behavior",
                    "content": "fixed the issue",
                    "why_useful_later": "Useful later.",
                },
            )


async def test_user_update_confidence(mcp_server):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "user.remember",
            {
                "kind": "tool_preference",
                "content": "User strongly prefers Visual Studio Code as their primary editor over other IDEs for all development work.",
                "why_useful_later": "Agents should suggest VS Code extensions and shortcuts rather than alternatives.",
                "confidence": "medium",
            },
        )
        remembered = json.loads(_text(remember_result))

        update_result = await client.call_tool(
            "user.update",
            {
                "id": remembered["id"],
                "confidence": "high",
                "reason": "User confirmed this is still accurate.",
            },
        )
        updated = json.loads(_text(update_result))

    assert updated["confidence"] == "high"


async def test_user_forget_archives(mcp_server):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "user.remember",
            {
                "kind": "workflow",
                "content": "User prefers to work in short focused sessions of ninety minutes followed by a break before switching tasks.",
                "why_useful_later": "Agents should avoid scheduling long uninterrupted tasks when planning work for this user.",
                "confidence": "medium",
            },
        )
        remembered = json.loads(_text(remember_result))

        forget_result = await client.call_tool(
            "user.forget",
            {
                "id": remembered["id"],
                "reason": "Outdated workflow preference.",
            },
        )
        forgotten = json.loads(_text(forget_result))

    assert forgotten["archived"] is True
    assert forgotten["deleted"] is False


async def test_project_update(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "project.remember",
            {
                "project_root": str(tmp_dir),
                "kind": "convention",
                "content": "All service methods must return typed result objects instead of throwing exceptions for expected error cases.",
                "why_useful_later": "Future agents should use result types rather than exceptions when implementing service methods.",
                "confidence": "medium",
            },
        )
        remembered = json.loads(_text(remember_result))

        update_result = await client.call_tool(
            "project.update",
            {
                "project_root": str(tmp_dir),
                "id": remembered["id"],
                "confidence": "high",
                "reason": "Confirmed across all service files.",
            },
        )
        updated = json.loads(_text(update_result))

    assert updated["confidence"] == "high"


async def test_project_forget_archives(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "project.remember",
            {
                "project_root": str(tmp_dir),
                "kind": "gotcha",
                "content": "Running tests in parallel caused intermittent failures due to shared test database state not being cleaned up properly.",
                "why_useful_later": "Future agents need to know parallel tests require isolated databases to avoid non-deterministic failures.",
                "confidence": "high",
            },
        )
        remembered = json.loads(_text(remember_result))

        forget_result = await client.call_tool(
            "project.forget",
            {
                "project_root": str(tmp_dir),
                "id": remembered["id"],
                "reason": "Issue resolved by using separate temp dirs per test.",
            },
        )
        forgotten = json.loads(_text(forget_result))

    assert forgotten["archived"] is True
    assert forgotten["deleted"] is False
