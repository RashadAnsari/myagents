import dataclasses
import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .memory_service import ProjectMemoryService, UserMemoryService

logger = logging.getLogger(__name__)

_PROJECT_ROOT_DESC = "Absolute path to the project root. Used to scope memory to the correct project."
_CONTENT_DESC = (
    "The durable memory content. Must be specific, at least 40 characters or 7 words, non-vague, and secret-free."
)
_INCLUDE_ARCHIVED_DESC = "Include soft-deleted memories in results."
_HARD_DELETE_DESC = (
    "Set true to permanently delete the record. An audit event is always kept. Default is soft-delete (archive)."
)
_ID_DESC = "Numeric id of the memory record."


def _log_tool(name: str, **context: object) -> None:
    parts = " ".join(f"{k}={v!r}" for k, v in context.items())
    logger.debug("tool %s %s", name, parts)


def _register_project_tools(mcp: FastMCP, project_service: ProjectMemoryService) -> None:
    @mcp.tool(name="project_remember")
    async def project_remember(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        content: Annotated[str, Field(description=_CONTENT_DESC)],
        source: Annotated[
            str | None, Field(description="Where this knowledge came from, e.g. 'agent' or 'user'.")
        ] = None,
        source_ref: Annotated[
            str | None, Field(description="Optional reference such as a file path, PR number, or test command.")
        ] = None,
    ) -> dict:
        """Store a durable, reusable fact scoped to this project. Call this after completing work when you learned something non-obvious: a decision with rationale, a convention, an architecture fact, a gotcha, or a recurring bug cause. Rejected if content is too short, vague, or contains secrets. Idempotent by content: a second call with identical content raises MemoryQualityError (reason: 'duplicates'), confirming the memory already exists without creating a duplicate."""
        _log_tool("project_remember", project=project_root)
        mem = await project_service.remember(
            project_root=project_root,
            content=content,
            source=source,
            source_ref=source_ref,
        )
        return dataclasses.asdict(mem)

    @mcp.tool(name="project_search")
    async def project_search(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        query: Annotated[
            str, Field(description="Specific search terms: file names, function names, concepts, or error messages.")
        ],
        k: Annotated[int, Field(description="Maximum results to return. Default 8, max 25.", ge=1, le=25)] = 8,
        offset: Annotated[
            int, Field(description="Number of results to skip for pagination. Default 0.", ge=0, le=100)
        ] = 0,
        include_archived: Annotated[bool, Field(description=_INCLUDE_ARCHIVED_DESC)] = False,
        all_projects: Annotated[
            bool,
            Field(
                description="Set true to search the memories of all known projects instead of only this one."
                " Results then include project_name and project_root showing which project each memory belongs to."
            ),
        ] = False,
    ) -> list:
        """Vector search across project memory. Call this at task start with specific terms: file names, function names, domain concepts, error messages. Do not use generic questions as queries. Set all_projects: true only when looking for knowledge from other repositories, such as a similar problem solved elsewhere or a convention shared across projects; memories from other projects may not apply to the current one, so check the project_name/project_root provenance on each result. Returns up to k results ordered by semantic relevance, starting at offset for pagination. Raises RuntimeError if embedding fails."""
        _log_tool("project_search", project=project_root, query=query, k=k, offset=offset, all_projects=all_projects)
        results = await project_service.search(
            project_root=project_root,
            query=query,
            k=k,
            offset=offset,
            include_archived=include_archived,
            all_projects=all_projects,
        )
        return [dataclasses.asdict(m) for m in results]

    @mcp.tool(name="project_update")
    async def project_update(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        id: Annotated[int, Field(description=_ID_DESC)],
        content: Annotated[str | None, Field(description=_CONTENT_DESC)] = None,
        archive: Annotated[bool, Field(description="Set true to soft-delete this memory.")] = False,
    ) -> dict:
        """Correct, refine, or soft-delete a project memory record. Use when a stored memory is inaccurate, incomplete, or outdated: the repo always wins over memory. Prefer updating over forgetting when the core fact is still valid but needs correction. Raises MemoryQualityError if updated content contains secrets. Raises ValueError if memory not found."""
        _log_tool("project_update", project=project_root, id=id)
        updated = await project_service.update(
            project_root=project_root,
            memory_id=id,
            content=content,
            archive=archive,
        )
        return dataclasses.asdict(updated)

    @mcp.tool(name="project_forget")
    def project_forget(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        id: Annotated[int, Field(description=_ID_DESC)],
        hard_delete: Annotated[bool, Field(description=_HARD_DELETE_DESC)] = False,
    ) -> dict:
        """Soft-delete a project memory so it no longer appears in search results. Default is archive (reversible); set hard_delete: true only when the user explicitly requests permanent removal. A project-scoped audit event is always kept. Raises ValueError if memory not found."""
        _log_tool("project_forget", project=project_root, id=id, hard_delete=hard_delete)
        return project_service.forget(project_root, id, hard_delete=hard_delete)

    @mcp.tool(name="project_purge")
    def project_purge(
        project_root: Annotated[str, Field(description=_PROJECT_ROOT_DESC)],
        days: Annotated[
            int, Field(description="Permanently delete archived memories older than this many days.", ge=1)
        ] = 90,
    ) -> dict:
        """Hard-delete archived project memories older than 'days' to prevent unbounded table growth. Safe to call during memory cleanup sessions. Audit events are always preserved. Returns count of records permanently removed."""
        _log_tool("project_purge", project=project_root, days=days)
        count = project_service.purge_archived(project_root, days)
        return {"purged": count}


def _register_user_tools(mcp: FastMCP, user_service: UserMemoryService) -> None:
    @mcp.tool(name="user_remember")
    async def user_remember(
        content: Annotated[str, Field(description=_CONTENT_DESC)],
        source: Annotated[str | None, Field(description="Where this was observed, e.g. 'agent' or 'user'.")] = None,
        source_ref: Annotated[str | None, Field(description="Optional contextual reference.")] = None,
    ) -> dict:
        """Store a durable, cross-project fact about the user: their preferences, recurring behaviors, background context, global conventions, tool choices, or communication style. Applied across all projects and sessions. Rejected if content is too short, vague, a duplicate, or contains secrets."""
        _log_tool("user_remember")
        mem = await user_service.remember(
            content=content,
            source=source,
            source_ref=source_ref,
        )
        return dataclasses.asdict(mem)

    @mcp.tool(name="user_search")
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
        include_archived: Annotated[bool, Field(description=_INCLUDE_ARCHIVED_DESC)] = False,
    ) -> list:
        """Vector search across global user memory. Use at session start with task-specific terms to load relevant context. Returns up to k results ordered by semantic relevance, starting at offset for pagination. Raises RuntimeError if embedding fails."""
        _log_tool("user_search", query=query, k=k, offset=offset)
        results = await user_service.search(
            query=query,
            k=k,
            offset=offset,
            include_archived=include_archived,
        )
        return [dataclasses.asdict(m) for m in results]

    @mcp.tool(name="user_update")
    async def user_update(
        id: Annotated[int, Field(description=_ID_DESC)],
        content: Annotated[str | None, Field(description=_CONTENT_DESC)] = None,
        archive: Annotated[bool, Field(description="Set true to soft-delete this memory.")] = False,
    ) -> dict:
        """Correct, refine, or soft-delete a user memory record. Use when observed behavior contradicts a stored memory: update rather than ignore stale entries. Secret-containing updates are rejected."""
        _log_tool("user_update", id=id)
        updated = await user_service.update(
            memory_id=id,
            content=content,
            archive=archive,
        )
        return dataclasses.asdict(updated)

    @mcp.tool(name="user_forget")
    def user_forget(
        id: Annotated[int, Field(description=_ID_DESC)],
        hard_delete: Annotated[bool, Field(description=_HARD_DELETE_DESC)] = False,
    ) -> dict:
        """Soft-delete a user memory so it no longer appears in search results. Default is archive (reversible); set hard_delete: true only when the user explicitly requests permanent removal."""
        _log_tool("user_forget", id=id, hard_delete=hard_delete)
        return user_service.forget(id, hard_delete=hard_delete)

    @mcp.tool(name="user_purge")
    def user_purge(
        days: Annotated[
            int, Field(description="Permanently delete archived user memories older than this many days.", ge=1)
        ] = 90,
    ) -> dict:
        """Hard-delete archived user memories older than 'days' to prevent unbounded growth. Audit events are always preserved. Returns count of records permanently removed."""
        _log_tool("user_purge", days=days)
        count = user_service.purge_archived(days)
        return {"purged": count}


def create_server(
    project_service: ProjectMemoryService,
    user_service: UserMemoryService,
    *,
    disable_project_memory: bool = False,
) -> FastMCP:
    mcp = FastMCP("agent-memory")

    if disable_project_memory:
        logger.info("project memory disabled via DISABLE_PROJECT_MEMORY; project_* tools not registered")
    else:
        _register_project_tools(mcp, project_service)

    _register_user_tools(mcp, user_service)

    return mcp
