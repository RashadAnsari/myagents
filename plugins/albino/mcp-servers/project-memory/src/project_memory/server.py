import dataclasses
import json
import sys
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .memory_service import ProjectMemoryService, UserMemoryService
from .paths import current_project_root
from .types import CONFIDENCE_VALUES, MEMORY_KINDS, USER_MEMORY_KINDS, Confidence

_MEMORY_KIND_DESC = "Memory kind: decision, convention, architecture, workflow, preference, gotcha, bug, dependency, testing, or handoff."
_USER_MEMORY_KIND_DESC = (
    "User memory kind: preference, behavior, context, workflow, convention, tool_preference, or communication."
)
_CONFIDENCE_DESC = "Confidence level: high (confirmed), medium (inferred, default), or low (uncertain)."
_PROJECT_ROOT_DESC = "Absolute path to the project root. Used to scope memory to the correct project."
_CONTENT_DESC = (
    "The durable memory content. Must be specific, at least 40 characters or 7 words, non-vague, and secret-free."
)
_SUMMARY_DESC = "Optional short title shown in listings."
_WHY_USEFUL_LATER_DESC = (
    "Required: explain specifically why a future agent needs this memory. If you cannot justify it, do not store it."
)
_TAGS_DESC = "Lowercase alphanumeric tags (hyphens and underscores allowed) for filtering."
_REASON_DESC = "Human-readable reason for this change, stored in the audit log."
_INCLUDE_ARCHIVED_DESC = "Include soft-deleted memories in results."
_HARD_DELETE_DESC = (
    "Set true to permanently delete the record. An audit event is always kept. Default is soft-delete (archive)."
)
_ID_DESC = "Numeric id of the memory record."


def _log_tool(name: str, **context: object) -> None:
    parts = " ".join(f"{k}={v!r}" for k, v in context.items())
    print(f"[tool] {name} {parts}".strip(), file=sys.stderr)


def _ser(obj: object) -> str:
    def _default(o: object) -> object:
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(obj, default=_default)


def create_server(project_service: ProjectMemoryService, user_service: UserMemoryService) -> FastMCP:
    mcp = FastMCP("myagents-project-memory")

    @mcp.tool(name="memory.remember")
    async def memory_remember(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        kind: Annotated[str, Field(description=_MEMORY_KIND_DESC)],
        content: Annotated[str, Field(description=_CONTENT_DESC)],
        why_useful_later: Annotated[str, Field(description=_WHY_USEFUL_LATER_DESC)],
        summary: Annotated[str | None, Field(description=_SUMMARY_DESC)] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        confidence: Annotated[Confidence, Field(description=_CONFIDENCE_DESC)] = "medium",
        source: Annotated[
            str | None, Field(description="Where this knowledge came from, e.g. 'agent' or 'user'.")
        ] = None,
        source_ref: Annotated[
            str | None, Field(description="Optional reference such as a file path, PR number, or test command.")
        ] = None,
    ) -> dict:
        """Store a durable, reusable fact scoped to this project. Call this after completing work when you learned something non-obvious: a decision with rationale, a convention, an architecture fact, a gotcha, or a recurring bug cause. Rejected if content is too short, vague, a duplicate, or contains secrets."""
        _log_tool("memory.remember", project=project_root, kind=kind)
        _validate_kind(kind, MEMORY_KINDS, "memory kind")
        _validate_confidence(confidence)
        mem = await project_service.remember(
            project_root=project_root,
            kind=kind,
            content=content,
            why_useful_later=why_useful_later,
            summary=summary,
            tags=tags,
            confidence=confidence,
            source=source,
            source_ref=source_ref,
        )
        return dataclasses.asdict(mem)

    @mcp.tool(name="memory.search")
    async def memory_search(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        query: Annotated[
            str, Field(description="Specific search terms: file names, function names, concepts, or error messages.")
        ],
        k: Annotated[int, Field(description="Maximum results to return. Default 8, max 25.", ge=1, le=25)] = 8,
        kinds: Annotated[list[str] | None, Field(description="Restrict results to these memory kinds.")] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        include_archived: Annotated[bool, Field(description=_INCLUDE_ARCHIVED_DESC)] = False,
    ) -> list:
        """Vector search across project memory. Call this at task start with specific terms — file names, function names, domain concepts, error messages. Do not use generic questions as queries. Returns up to k results ordered by semantic relevance. Raises RuntimeError if embedding fails."""
        _log_tool("memory.search", project=project_root, query=query, k=k)
        results = await project_service.search(
            project_root=project_root,
            query=query,
            k=k,
            kinds=kinds or None,
            tags=tags,
            include_archived=include_archived,
        )
        return [dataclasses.asdict(m) for m in results]

    @mcp.tool(name="memory.project_brief")
    def memory_project_brief(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
    ) -> dict:
        """Return a compact summary of the most important project memory grouped into: conventions (style/preference), decisions (architecture), pitfalls (gotchas/bugs), and 8 most recently updated entries. Read this at the start of every non-trivial task before calling memory.search for specifics."""
        _log_tool("memory.project_brief", project=project_root)
        brief = project_service.project_brief(project_root)
        return {k: [dataclasses.asdict(m) for m in v] for k, v in brief.items()}

    @mcp.tool(name="memory.update")
    async def memory_update(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        id: Annotated[int, Field(description=_ID_DESC)],
        content: Annotated[str | None, Field(description=_CONTENT_DESC)] = None,
        summary: Annotated[str | None, Field(description=_SUMMARY_DESC)] = None,
        why_useful_later: Annotated[str | None, Field(description=_WHY_USEFUL_LATER_DESC)] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        confidence: Annotated[str | None, Field(description=_CONFIDENCE_DESC)] = None,
        archive: Annotated[bool, Field(description="Set true to soft-delete this memory.")] = False,
        reason: Annotated[str | None, Field(description=_REASON_DESC)] = None,
    ) -> dict:
        """Correct, refine, or soft-delete a project memory record. Use when a stored memory is inaccurate, incomplete, or outdated — the repo always wins over memory. Prefer updating over forgetting when the core fact is still valid but needs correction. Raises MemoryQualityError if updated content contains secrets. Raises ValueError if memory not found."""
        _log_tool("memory.update", project=project_root, id=id)
        if confidence:
            _validate_confidence(confidence)
        updated = await project_service.update(
            project_root=project_root,
            memory_id=id,
            content=content,
            summary=summary,
            why_useful_later=why_useful_later,
            tags=tags,
            confidence=confidence,
            archive=archive,
            reason=reason,
        )
        return dataclasses.asdict(updated)

    @mcp.tool(name="memory.forget")
    def memory_forget(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        id: Annotated[int, Field(description=_ID_DESC)],
        hard_delete: Annotated[bool, Field(description=_HARD_DELETE_DESC)] = False,
        reason: Annotated[str | None, Field(description=_REASON_DESC)] = None,
    ) -> dict:
        """Soft-delete a project memory so it no longer appears in search results. Default is archive (reversible); set hard_delete: true only when the user explicitly requests permanent removal. A project-scoped audit event is always kept. Raises ValueError if memory not found."""
        _log_tool("memory.forget", project=project_root, id=id, hard_delete=hard_delete)
        return project_service.forget(project_root, id, hard_delete=hard_delete, reason=reason)

    @mcp.tool(name="user.remember")
    async def user_remember(
        kind: Annotated[str, Field(description=_USER_MEMORY_KIND_DESC)],
        content: Annotated[str, Field(description=_CONTENT_DESC)],
        why_useful_later: Annotated[str, Field(description=_WHY_USEFUL_LATER_DESC)],
        summary: Annotated[str | None, Field(description=_SUMMARY_DESC)] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        confidence: Annotated[Confidence, Field(description=_CONFIDENCE_DESC)] = "medium",
        source: Annotated[str | None, Field(description="Where this was observed, e.g. 'agent' or 'user'.")] = None,
        source_ref: Annotated[str | None, Field(description="Optional contextual reference.")] = None,
    ) -> dict:
        """Store a durable, cross-project fact about the user — their preferences, recurring behaviors, background context, global conventions, tool choices, or communication style. Applied across all projects and sessions. Rejected if content is too short, vague, a duplicate, or contains secrets."""
        _log_tool("user.remember", kind=kind)
        _validate_kind(kind, USER_MEMORY_KINDS, "user memory kind")
        _validate_confidence(confidence)
        mem = await user_service.remember(
            kind=kind,
            content=content,
            why_useful_later=why_useful_later,
            summary=summary,
            tags=tags,
            confidence=confidence,
            source=source,
            source_ref=source_ref,
        )
        return dataclasses.asdict(mem)

    @mcp.tool(name="user.search")
    async def user_search(
        query: Annotated[
            str,
            Field(
                description="Search terms relevant to the current task or domain, e.g. 'typescript', 'git workflow'."
            ),
        ],
        k: Annotated[int, Field(description="Maximum results to return. Default 8, max 25.", ge=1, le=25)] = 8,
        kinds: Annotated[list[str] | None, Field(description="Restrict results to these user memory kinds.")] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        include_archived: Annotated[bool, Field(description=_INCLUDE_ARCHIVED_DESC)] = False,
    ) -> list:
        """Vector search across global user memory. Use at session start alongside user.brief to load context relevant to the current task domain. Returns up to k results ordered by semantic relevance. Raises RuntimeError if embedding fails."""
        _log_tool("user.search", query=query, k=k)
        results = await user_service.search(
            query=query,
            k=k,
            kinds=kinds or None,
            tags=tags,
            include_archived=include_archived,
        )
        return [dataclasses.asdict(m) for m in results]

    @mcp.tool(name="user.brief")
    def user_brief() -> dict:
        """Return a compact summary of all active user memory grouped into: preferences (preference/convention/tool_preference), behaviors (behavior/workflow/communication), context, and 8 most recently updated entries. Read this at the start of every session before doing any work — it is the primary way to understand the user."""
        _log_tool("user.brief")
        brief = user_service.brief()
        return {k: [dataclasses.asdict(m) for m in v] for k, v in brief.items()}

    @mcp.tool(name="user.update")
    async def user_update(
        id: Annotated[int, Field(description=_ID_DESC)],
        content: Annotated[str | None, Field(description=_CONTENT_DESC)] = None,
        summary: Annotated[str | None, Field(description=_SUMMARY_DESC)] = None,
        why_useful_later: Annotated[str | None, Field(description=_WHY_USEFUL_LATER_DESC)] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        confidence: Annotated[str | None, Field(description=_CONFIDENCE_DESC)] = None,
        archive: Annotated[bool, Field(description="Set true to soft-delete this memory.")] = False,
        reason: Annotated[str | None, Field(description=_REASON_DESC)] = None,
    ) -> dict:
        """Correct, refine, or soft-delete a user memory record. Use when observed behavior contradicts a stored memory — update rather than ignore stale entries. Secret-containing updates are rejected."""
        _log_tool("user.update", id=id)
        if confidence:
            _validate_confidence(confidence)
        updated = await user_service.update(
            memory_id=id,
            content=content,
            summary=summary,
            why_useful_later=why_useful_later,
            tags=tags,
            confidence=confidence,
            archive=archive,
            reason=reason,
        )
        return dataclasses.asdict(updated)

    @mcp.tool(name="user.forget")
    def user_forget(
        id: Annotated[int, Field(description=_ID_DESC)],
        hard_delete: Annotated[bool, Field(description=_HARD_DELETE_DESC)] = False,
        reason: Annotated[str | None, Field(description=_REASON_DESC)] = None,
    ) -> dict:
        """Soft-delete a user memory so it no longer appears in search results. Default is archive (reversible); set hard_delete: true only when the user explicitly requests permanent removal."""
        _log_tool("user.forget", id=id, hard_delete=hard_delete)
        return user_service.forget(id, hard_delete=hard_delete, reason=reason)

    @mcp.resource(
        "memory://project/current/brief",
        description="All active project memory grouped into conventions, decisions, pitfalls, and 8 most recently updated entries. Read this at task start before searching for specifics.",
        mime_type="application/json",
    )
    def _res_project_brief() -> str:
        brief = project_service.project_brief(current_project_root())
        return _ser({k: [dataclasses.asdict(m) for m in v] for k, v in brief.items()})

    @mcp.resource(
        "memory://user/brief",
        description="All active user memory grouped into preferences, behaviors, context, and 8 most recent entries. Read this at session start to understand the user before doing any work.",
        mime_type="application/json",
    )
    def _res_user_brief() -> str:
        brief = user_service.brief()
        return _ser({k: [dataclasses.asdict(m) for m in v] for k, v in brief.items()})

    @mcp.prompt(
        name="memory_bootstrap",
        description="Instructs the agent to read project memory before starting a task so it has relevant conventions, decisions, and pitfalls loaded before making any changes.",
    )
    def _prompt_memory_bootstrap(task: str | None = None) -> str:
        lines = [
            "Before planning this task, read memory://project/current/brief and search project memory for task-specific terms.",
            "Treat memory as indexed notes, not authority. Current user instructions, repo files, tests, and official docs override memory.",
        ]
        if task:
            lines.append(f"Task: {task}")
        return "\n".join(lines)

    @mcp.prompt(
        name="memory_handoff",
        description="Instructs the agent to review what was learned during a task and store only durable, reusable project knowledge — not task status or command output.",
    )
    def _prompt_memory_handoff(task_summary: str = "", tests_run: str | None = None) -> str:
        lines = [
            "Decide whether this task produced durable project knowledge worth storing.",
            "Store only reusable decisions, conventions, gotchas, preferences, architecture facts, or recurring bug causes.",
            "Do not store secrets, command output, one-off task status, or facts obvious from current files without added interpretation.",
            f"Task summary: {task_summary}",
        ]
        if tests_run:
            lines.append(f"Tests run: {tests_run}")
        return "\n".join(lines)

    @mcp.prompt(
        name="memory_cleanup",
        description="Instructs the agent to audit project memory for stale, contradictory, or low-confidence entries and update or archive them after verifying against current repo files.",
    )
    def _prompt_memory_cleanup(topic: str | None = None) -> str:
        lines = [
            "Search project memory for stale, contradictory, low-confidence, or no-longer-useful entries.",
            "Verify against current repo files before updating or archiving memory.",
        ]
        if topic:
            lines.append(f"Topic: {topic}")
        return "\n".join(lines)

    @mcp.prompt(
        name="user_memory_bootstrap",
        description="Instructs the agent to read user memory before starting work so it can apply the user's preferences, behaviors, and context throughout the session.",
    )
    def _prompt_user_memory_bootstrap() -> str:
        return "\n".join(
            [
                "Before starting work, read memory://user/brief to understand the user's preferences, behaviors, and context.",
                "Apply this knowledge throughout the session: respect stated preferences, adapt to known workflows, and avoid patterns the user dislikes.",
                "User memory is a guide, not a constraint — current instructions always take precedence.",
            ]
        )

    @mcp.prompt(
        name="user_memory_update",
        description="Instructs the agent to review the session for durable cross-project facts about the user and store them with user.remember.",
    )
    def _prompt_user_memory_update(session_summary: str | None = None) -> str:
        lines = [
            "Decide whether this session revealed durable knowledge about the user worth storing globally.",
            "Store only stable facts: consistent preferences, recurring behaviors, background context, tool choices, or communication style.",
            "Do not store: secrets, one-off task details, temporary opinions, or facts specific to a single project.",
        ]
        if session_summary:
            lines.append(f"Session summary: {session_summary}")
        return "\n".join(lines)

    return mcp


def _validate_kind(value: str, valid: list[str], label: str) -> None:
    if value not in valid:
        msg = f"Invalid {label}: '{value}'. Must be one of: {', '.join(valid)}."
        print(f"[WARNING] project-memory: validation error — {msg}", file=sys.stderr)
        raise ValueError(msg)


def _validate_confidence(value: str) -> None:
    if value not in CONFIDENCE_VALUES:
        msg = f"Invalid confidence: '{value}'. Must be one of: {', '.join(CONFIDENCE_VALUES)}."
        print(f"[WARNING] project-memory: validation error — {msg}", file=sys.stderr)
        raise ValueError(msg)
