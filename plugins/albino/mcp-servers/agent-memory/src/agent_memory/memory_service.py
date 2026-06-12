import logging
from datetime import UTC, datetime, timedelta

from .db import AgentMemoryStore, pack_vector
from .embedding import embed_one
from .quality import evaluate_memory_quality, evaluate_user_memory_quality, looks_like_secret
from .types import ProjectMemoryRecord, UserMemoryRecord

logger = logging.getLogger(__name__)


class MemoryQualityError(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__(f"Memory rejected: {' '.join(reasons)}")
        self.reasons = reasons


def _clean_optional(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned if cleaned else None


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


class ProjectMemoryService:
    def __init__(self, store: AgentMemoryStore) -> None:
        self._store = store

    async def remember(
        self,
        project_root: str,
        content: str,
        source: str | None = None,
        source_ref: str | None = None,
    ) -> ProjectMemoryRecord:
        project = self._store.get_or_create_project(project_root)
        existing = self._store.list_active_project_memories(project.id)
        existing_contents = [m.content for m in existing]
        ok, reasons = evaluate_memory_quality(content, existing_contents)
        if not ok:
            logger.warning("memory rejected for project %s: %s", project.id, "; ".join(reasons))
            raise MemoryQualityError(reasons)

        cleaned_content = content.strip()
        vector = await embed_one(cleaned_content)

        return self._store.create_project_memory(
            project_id=project.id,
            content=cleaned_content,
            source=_clean_optional(source),
            source_ref=_clean_optional(source_ref),
            vector=vector,
        )

    async def search(
        self,
        project_root: str,
        query: str,
        k: int = 8,
        offset: int = 0,
        include_archived: bool = False,
        all_projects: bool = False,
    ) -> list[ProjectMemoryRecord]:
        limit = _clamp(k, 1, 25)
        skip = _clamp(offset, 0, 100)

        if all_projects:
            query_vector = pack_vector(await embed_one(query))
            return self._store.search_all_project_memories(
                query_vector=query_vector,
                limit=limit,
                offset=skip,
                include_archived=include_archived,
            )

        project = self._store.get_project(project_root)
        if not project:
            return []

        query_vector = pack_vector(await embed_one(query))

        return self._store.search_project_memories(
            project_id=project.id,
            query_vector=query_vector,
            limit=limit,
            offset=skip,
            include_archived=include_archived,
        )

    def purge_archived(self, project_root: str, days: int = 90) -> int:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        before = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()
        return self._store.purge_archived_project_memories(project.id, before)

    async def update(
        self,
        project_root: str,
        memory_id: int,
        content: str | None = None,
        archive: bool = False,
    ) -> ProjectMemoryRecord:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        memory = self._store.get_project_memory(memory_id)
        if not memory or memory.project_id != project.id:
            raise ValueError(f"Memory not found for project: {memory_id}")

        if content and looks_like_secret(content):
            raise MemoryQualityError(["Updated memory content looks like it may contain a secret or credential."])

        vector = None
        if not archive:
            content_for_embed = content.strip() if content else memory.content
            vector = await embed_one(content_for_embed)

        return self._store.update_project_memory(
            memory_id=memory_id,
            content=content.strip() if content else None,
            archived_at=datetime.now(tz=UTC).isoformat() if archive else None,
            vector=vector,
        )

    def forget(self, project_root: str, memory_id: int, hard_delete: bool = False) -> dict:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        memory = self._store.get_project_memory(memory_id)
        if not memory or memory.project_id != project.id:
            raise ValueError(f"Memory not found for project: {memory_id}")

        if hard_delete:
            self._store.hard_delete_project_memory(memory_id, project.id)
            return {"archived": False, "deleted": True}

        self._store.archive_project_memory(memory_id)
        return {"archived": True, "deleted": False}


class UserMemoryService:
    def __init__(self, store: AgentMemoryStore) -> None:
        self._store = store

    async def remember(
        self,
        content: str,
        source: str | None = None,
        source_ref: str | None = None,
    ) -> UserMemoryRecord:
        existing = self._store.list_active_user_memories()
        existing_contents = [m.content for m in existing]
        ok, reasons = evaluate_user_memory_quality(content, existing_contents)
        if not ok:
            logger.warning("user memory rejected: %s", "; ".join(reasons))
            raise MemoryQualityError(reasons)

        cleaned_content = content.strip()
        vector = await embed_one(cleaned_content)

        return self._store.create_user_memory(
            content=cleaned_content,
            source=_clean_optional(source),
            source_ref=_clean_optional(source_ref),
            vector=vector,
        )

    async def search(
        self,
        query: str,
        k: int = 8,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[UserMemoryRecord]:
        limit = _clamp(k, 1, 25)
        skip = _clamp(offset, 0, 100)

        query_vector = pack_vector(await embed_one(query))

        return self._store.search_user_memories(
            query_vector=query_vector,
            limit=limit,
            offset=skip,
            include_archived=include_archived,
        )

    def purge_archived(self, days: int = 90) -> int:
        before = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()
        return self._store.purge_archived_user_memories(before)

    async def update(
        self,
        memory_id: int,
        content: str | None = None,
        archive: bool = False,
    ) -> UserMemoryRecord:
        memory = self._store.get_user_memory(memory_id)
        if not memory:
            raise ValueError(f"User memory not found: {memory_id}")

        if content and looks_like_secret(content):
            raise MemoryQualityError(["Updated memory content looks like it may contain a secret or credential."])

        vector = None
        if not archive:
            content_for_embed = content.strip() if content else memory.content
            vector = await embed_one(content_for_embed)

        return self._store.update_user_memory(
            memory_id=memory_id,
            content=content.strip() if content else None,
            archived_at=datetime.now(tz=UTC).isoformat() if archive else None,
            vector=vector,
        )

    def forget(self, memory_id: int, hard_delete: bool = False) -> dict:
        memory = self._store.get_user_memory(memory_id)
        if not memory:
            raise ValueError(f"User memory not found: {memory_id}")

        if hard_delete:
            self._store.hard_delete_user_memory(memory_id)
            return {"archived": False, "deleted": True}

        self._store.archive_user_memory(memory_id)
        return {"archived": True, "deleted": False}
