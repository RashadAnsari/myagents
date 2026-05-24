"""MCP integration tests: exercise tools, resources, and prompts through FastMCP's in-process Client."""

import json

import pytest
from fastmcp import Client


def _text(result) -> str:
    """Extract first text content from a call_tool result."""
    for item in result.content:
        if hasattr(item, "text"):
            return item.text
    return ""


async def test_exposes_expected_project_tools_resources_prompts(mcp_server):
    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

    tool_names = {t.name for t in tools}
    resource_uris = {str(r.uri) for r in resources}
    prompt_names = {p.name for p in prompts}

    assert tool_names == {
        "memory.remember",
        "memory.search",
        "memory.project_brief",
        "memory.update",
        "memory.forget",
        "memory.purge",
        "user.remember",
        "user.search",
        "user.brief",
        "user.update",
        "user.forget",
        "user.purge",
    }
    assert resource_uris == {"memory://project/current/brief", "memory://user/brief"}
    assert {
        "memory_bootstrap",
        "memory_handoff",
        "memory_cleanup",
        "user_memory_bootstrap",
        "user_memory_update",
    } <= prompt_names


async def test_stores_and_retrieves_memory_through_mcp(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "memory.remember",
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
            "memory.search",
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
                "memory.remember",
                {
                    "project_root": str(tmp_dir),
                    "kind": "handoff",
                    "content": "fixed the issue",
                    "why_useful_later": "Useful later because this says what happened.",
                },
            )


async def test_reads_resource_and_gets_prompt(mcp_server, tmp_dir):
    from agent_memory.paths import current_project_root

    root = current_project_root()
    async with Client(mcp_server) as client:
        await client.call_tool(
            "memory.remember",
            {
                "project_root": root,
                "kind": "convention",
                "content": "Resource tests should read the project memory brief through the MCP resource interface.",
                "why_useful_later": "Future maintainers need resource coverage when changing MCP server registration.",
                "tags": ["resource"],
                "confidence": "high",
            },
        )
        resource = await client.read_resource("memory://project/current/brief")
        prompt = await client.get_prompt("memory_bootstrap", {"task": "Review project memory coverage"})

    resource_text = resource[0].text if resource else ""
    assert "conventions" in resource_text

    prompt_text = prompt.messages[0].content.text if prompt and prompt.messages else ""
    assert "Review project memory coverage" in prompt_text


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


async def test_memory_handoff_and_cleanup_prompts(mcp_server):
    async with Client(mcp_server) as client:
        handoff = await client.get_prompt(
            "memory_handoff",
            {"task_summary": "Refactored auth module", "tests_run": "pytest tests/"},
        )
        cleanup = await client.get_prompt("memory_cleanup", {"topic": "auth"})

    handoff_text = handoff.messages[0].content.text if handoff and handoff.messages else ""
    assert "Refactored auth module" in handoff_text
    assert "pytest tests/" in handoff_text

    cleanup_text = cleanup.messages[0].content.text if cleanup and cleanup.messages else ""
    assert "auth" in cleanup_text


async def test_reads_user_brief_resource_and_prompts(mcp_server):
    async with Client(mcp_server) as client:
        await client.call_tool(
            "user.remember",
            {
                "kind": "communication",
                "content": "User prefers responses structured with clear headers and short sections rather than long unbroken prose blocks.",
                "why_useful_later": "Agents should structure responses with headers and short sections for this user.",
                "confidence": "high",
            },
        )
        resource = await client.read_resource("memory://user/brief")
        bootstrap = await client.get_prompt("user_memory_bootstrap", {})
        update = await client.get_prompt("user_memory_update", {"session_summary": "Helped user refactor auth module."})

    brief_text = resource[0].text if resource else ""
    assert "preferences" in brief_text

    bootstrap_text = bootstrap.messages[0].content.text if bootstrap and bootstrap.messages else ""
    assert "memory://user/brief" in bootstrap_text

    update_text = update.messages[0].content.text if update and update.messages else ""
    assert "Helped user refactor auth module" in update_text


async def test_memory_update(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "memory.remember",
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
            "memory.update",
            {
                "project_root": str(tmp_dir),
                "id": remembered["id"],
                "confidence": "high",
                "reason": "Confirmed across all service files.",
            },
        )
        updated = json.loads(_text(update_result))

    assert updated["confidence"] == "high"


async def test_memory_forget_archives(mcp_server, tmp_dir):
    async with Client(mcp_server) as client:
        remember_result = await client.call_tool(
            "memory.remember",
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
            "memory.forget",
            {
                "project_root": str(tmp_dir),
                "id": remembered["id"],
                "reason": "Issue resolved by using separate temp dirs per test.",
            },
        )
        forgotten = json.loads(_text(forget_result))

    assert forgotten["archived"] is True
    assert forgotten["deleted"] is False
