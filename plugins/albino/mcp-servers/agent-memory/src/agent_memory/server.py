import dataclasses
import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .memory_service import ProjectMemoryService, UserMemoryService
from .types import CONFIDENCE_VALUES, MEMORY_KINDS, USER_MEMORY_KINDS, Confidence, MemoryKind, UserMemoryKind

logger = logging.getLogger(__name__)

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
    logger.debug("tool %s %s", name, parts)


def create_server(project_service: ProjectMemoryService, user_service: UserMemoryService) -> FastMCP:
    mcp = FastMCP("agent-memory")

    @mcp.tool(name="project.remember")
    async def project_remember(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        kind: Annotated[MemoryKind, Field(description=_MEMORY_KIND_DESC)],
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
        """Store a durable, reusable fact scoped to this project. Call this after completing work when you learned something non-obvious: a decision with rationale, a convention, an architecture fact, a gotcha, or a recurring bug cause. Rejected if content is too short, vague, or contains secrets. Idempotent by content: a second call with identical content raises MemoryQualityError (reason: 'duplicates'), confirming the memory already exists without creating a duplicate."""
        _log_tool("project.remember", project=project_root, kind=kind)
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

    @mcp.tool(name="project.search")
    async def project_search(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        query: Annotated[
            str, Field(description="Specific search terms: file names, function names, concepts, or error messages.")
        ],
        k: Annotated[int, Field(description="Maximum results to return. Default 8, max 25.", ge=1, le=25)] = 8,
        offset: Annotated[
            int, Field(description="Number of results to skip for pagination. Default 0.", ge=0, le=100)
        ] = 0,
        kinds: Annotated[list[MemoryKind] | None, Field(description="Restrict results to these memory kinds.")] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        include_archived: Annotated[bool, Field(description=_INCLUDE_ARCHIVED_DESC)] = False,
    ) -> list:
        """Vector search across project memory. Call this at task start with specific terms: file names, function names, domain concepts, error messages. Do not use generic questions as queries. Returns up to k results ordered by semantic relevance, starting at offset for pagination. Raises RuntimeError if embedding fails."""
        _log_tool("project.search", project=project_root, query=query, k=k, offset=offset)
        results = await project_service.search(
            project_root=project_root,
            query=query,
            k=k,
            offset=offset,
            kinds=kinds or None,
            tags=tags,
            include_archived=include_archived,
        )
        return [dataclasses.asdict(m) for m in results]

    @mcp.tool(name="project.brief")
    def project_brief(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        limit_per_category: Annotated[
            int, Field(description="Maximum entries per category. Default 8, max 25.", ge=1, le=25)
        ] = 8,
    ) -> dict:
        """Return a compact summary of the most important project memory grouped into: conventions (style/preference), decisions (architecture), pitfalls (gotchas/bugs), and most recently updated entries. Read this at the start of every non-trivial task before calling project.search for specifics. Increase limit_per_category to retrieve more entries per group."""
        _log_tool("project.brief", project=project_root, limit=limit_per_category)
        brief = project_service.project_brief(project_root, limit_per_category=limit_per_category)
        return {k: [dataclasses.asdict(m) for m in v] for k, v in brief.items()}

    @mcp.tool(name="project.update")
    async def project_update(
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
        """Correct, refine, or soft-delete a project memory record. Use when a stored memory is inaccurate, incomplete, or outdated: the repo always wins over memory. Prefer updating over forgetting when the core fact is still valid but needs correction. Raises MemoryQualityError if updated content contains secrets. Raises ValueError if memory not found."""
        _log_tool("project.update", project=project_root, id=id)
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

    @mcp.tool(name="project.forget")
    def project_forget(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        id: Annotated[int, Field(description=_ID_DESC)],
        hard_delete: Annotated[bool, Field(description=_HARD_DELETE_DESC)] = False,
        reason: Annotated[str | None, Field(description=_REASON_DESC)] = None,
    ) -> dict:
        """Soft-delete a project memory so it no longer appears in search results. Default is archive (reversible); set hard_delete: true only when the user explicitly requests permanent removal. A project-scoped audit event is always kept. Raises ValueError if memory not found."""
        _log_tool("project.forget", project=project_root, id=id, hard_delete=hard_delete)
        return project_service.forget(project_root, id, hard_delete=hard_delete, reason=reason)

    @mcp.tool(name="project.purge")
    def project_purge(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        days: Annotated[
            int, Field(description="Permanently delete archived memories older than this many days.", ge=1)
        ] = 90,
    ) -> dict:
        """Hard-delete archived project memories older than 'days' to prevent unbounded table growth. Safe to call during memory cleanup sessions. Audit events are always preserved. Returns count of records permanently removed."""
        _log_tool("project.purge", project=project_root, days=days)
        count = project_service.purge_archived(project_root, days)
        return {"purged": count}

    @mcp.tool(name="user.remember")
    async def user_remember(
        kind: Annotated[UserMemoryKind, Field(description=_USER_MEMORY_KIND_DESC)],
        content: Annotated[str, Field(description=_CONTENT_DESC)],
        why_useful_later: Annotated[str, Field(description=_WHY_USEFUL_LATER_DESC)],
        summary: Annotated[str | None, Field(description=_SUMMARY_DESC)] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        confidence: Annotated[Confidence, Field(description=_CONFIDENCE_DESC)] = "medium",
        source: Annotated[str | None, Field(description="Where this was observed, e.g. 'agent' or 'user'.")] = None,
        source_ref: Annotated[str | None, Field(description="Optional contextual reference.")] = None,
    ) -> dict:
        """Store a durable, cross-project fact about the user: their preferences, recurring behaviors, background context, global conventions, tool choices, or communication style. Applied across all projects and sessions. Rejected if content is too short, vague, a duplicate, or contains secrets."""
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
        offset: Annotated[
            int, Field(description="Number of results to skip for pagination. Default 0.", ge=0, le=100)
        ] = 0,
        kinds: Annotated[
            list[UserMemoryKind] | None, Field(description="Restrict results to these user memory kinds.")
        ] = None,
        tags: Annotated[list[str] | None, Field(description=_TAGS_DESC)] = None,
        include_archived: Annotated[bool, Field(description=_INCLUDE_ARCHIVED_DESC)] = False,
    ) -> list:
        """Vector search across global user memory. Use at session start alongside user.brief to load context relevant to the current task domain. Returns up to k results ordered by semantic relevance, starting at offset for pagination. Raises RuntimeError if embedding fails."""
        _log_tool("user.search", query=query, k=k, offset=offset)
        results = await user_service.search(
            query=query,
            k=k,
            offset=offset,
            kinds=kinds or None,
            tags=tags,
            include_archived=include_archived,
        )
        return [dataclasses.asdict(m) for m in results]

    @mcp.tool(name="user.brief")
    def user_brief() -> dict:
        """Return a compact summary of all active user memory grouped into: preferences (preference/convention/tool_preference), behaviors (behavior/workflow/communication), context, and 8 most recently updated entries. Read this at the start of every session before doing any work: it is the primary way to understand the user."""
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
        """Correct, refine, or soft-delete a user memory record. Use when observed behavior contradicts a stored memory: update rather than ignore stale entries. Secret-containing updates are rejected."""
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

    @mcp.tool(name="user.purge")
    def user_purge(
        days: Annotated[
            int, Field(description="Permanently delete archived user memories older than this many days.", ge=1)
        ] = 90,
    ) -> dict:
        """Hard-delete archived user memories older than 'days' to prevent unbounded growth. Audit events are always preserved. Returns count of records permanently removed."""
        _log_tool("user.purge", days=days)
        count = user_service.purge_archived(days)
        return {"purged": count}

    return mcp


def _validate_kind(value: str, valid: list[str], label: str) -> None:
    if value not in valid:
        msg = f"Invalid {label}: '{value}'. Must be one of: {', '.join(valid)}."
        logger.warning("validation error: %s", msg)
        raise ValueError(msg)


def _validate_confidence(value: str) -> None:
    if value not in CONFIDENCE_VALUES:
        msg = f"Invalid confidence: '{value}'. Must be one of: {', '.join(CONFIDENCE_VALUES)}."
        logger.warning("validation error: %s", msg)
        raise ValueError(msg)
