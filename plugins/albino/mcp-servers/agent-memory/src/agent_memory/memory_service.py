import logging
import re
from datetime import UTC, datetime, timedelta

from .db import AgentMemoryStore, pack_vector
from .embedding import embed, memory_embed_text
from .quality import evaluate_memory_quality, evaluate_user_memory_quality, looks_like_secret
from .types import (
    Confidence,
    MemoryKind,
    MemoryRecord,
    UserMemoryKind,
    UserMemoryRecord,
)

logger = logging.getLogger(__name__)


class MemoryQualityError(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__(f"Memory rejected: {' '.join(reasons)}")
        self.reasons = reasons


def _normalize_tags(tags: list[str] | None) -> list[str]:
    seen: set[str] = set()
    result = []
    for tag in tags or []:
        cleaned = tag.strip().lower()
        if cleaned and re.match(r"^[a-z0-9][a-z0-9_-]*$", cleaned) and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return sorted(result)


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
        kind: MemoryKind,
        content: str,
        why_useful_later: str,
        summary: str | None = None,
        tags: list[str] | None = None,
        confidence: Confidence = "medium",
        source: str | None = None,
        source_ref: str | None = None,
    ) -> MemoryRecord:
        project = self._store.get_or_create_project(project_root)
        existing = self._store.list_active_memories(project.id)
        existing_contents = [m.content for m in existing]
        ok, reasons = evaluate_memory_quality(content, why_useful_later, existing_contents)
        if not ok:
            logger.warning("memory rejected for project %s: %s", project.id, "; ".join(reasons))
            raise MemoryQualityError(reasons)

        normalized_tags = _normalize_tags(tags)
        cleaned_content = content.strip()
        cleaned_summary = _clean_optional(summary)

        text = memory_embed_text(cleaned_content, cleaned_summary, normalized_tags)
        vectors = await embed([text])
        if not vectors:
            raise RuntimeError("Embedding returned empty result.")

        return self._store.create_memory(
            project_id=project.id,
            kind=kind,
            content=cleaned_content,
            summary=cleaned_summary,
            why_useful_later=why_useful_later.strip(),
            tags=normalized_tags,
            confidence=confidence,
            source=_clean_optional(source),
            source_ref=_clean_optional(source_ref),
            vector=vectors[0],
        )

    async def search(
        self,
        project_root: str,
        query: str,
        k: int = 8,
        offset: int = 0,
        kinds: list[MemoryKind] | None = None,
        tags: list[str] | None = None,
        include_archived: bool = False,
    ) -> list[MemoryRecord]:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        limit = _clamp(k, 1, 25)
        skip = _clamp(offset, 0, 100)

        vectors = await embed([query])
        if not vectors:
            raise RuntimeError("Embedding returned empty result.")
        query_vector = pack_vector(vectors[0])

        return self._store.search_memories(
            project_id=project.id,
            query_vector=query_vector,
            limit=limit,
            offset=skip,
            include_archived=include_archived,
            kinds=kinds or None,
            tags=_normalize_tags(tags) or None,
        )

    def project_brief(self, project_root: str, limit_per_category: int = 8) -> dict[str, list[MemoryRecord]]:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        limit = _clamp(limit_per_category, 1, 25)
        return self._store.project_brief(project.id, limit_per_category=limit)

    def purge_archived(self, project_root: str, days: int = 90) -> int:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        before = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()
        return self._store.purge_archived_memories(project.id, before)

    async def update(
        self,
        project_root: str,
        memory_id: int,
        content: str | None = None,
        summary: str | None = None,
        why_useful_later: str | None = None,
        tags: list[str] | None = None,
        confidence: Confidence | None = None,
        archive: bool = False,
        reason: str | None = None,
    ) -> MemoryRecord:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        memory = self._store.get_memory(memory_id)
        if not memory or memory.project_id != project.id:
            raise ValueError(f"Memory not found for project: {memory_id}")

        if content and looks_like_secret(content):
            raise MemoryQualityError(["Updated memory content looks like it may contain a secret or credential."])
        if why_useful_later and looks_like_secret(why_useful_later):
            raise MemoryQualityError(["Updated usefulness rationale looks like it may contain a secret or credential."])

        vector = None
        if not archive:
            content_for_embed = content.strip() if content else memory.content
            summary_for_embed = _clean_optional(summary) if summary is not None else memory.summary
            tags_for_embed = _normalize_tags(tags) if tags is not None else memory.tags
            text = memory_embed_text(content_for_embed, summary_for_embed, tags_for_embed)
            vectors = await embed([text])
            if not vectors:
                raise RuntimeError("Embedding returned empty result.")
            vector = vectors[0]

        return self._store.update_memory(
            memory_id=memory_id,
            content=content.strip() if content else None,
            summary=_clean_optional(summary),
            why_useful_later=why_useful_later.strip() if why_useful_later else None,
            tags=_normalize_tags(tags) if tags is not None else None,
            confidence=confidence,
            archived_at=datetime.now(tz=UTC).isoformat() if archive else None,
            reason=reason or "Memory updated.",
            vector=vector,
        )

    def forget(self, project_root: str, memory_id: int, hard_delete: bool = False, reason: str | None = None) -> dict:
        project = self._store.get_project(project_root)
        if not project:
            raise ValueError(f"Project not found: {project_root}")

        memory = self._store.get_memory(memory_id)
        if not memory or memory.project_id != project.id:
            raise ValueError(f"Memory not found for project: {memory_id}")

        r = reason or "Memory forgotten by request."
        if hard_delete:
            self._store.hard_delete_memory(memory_id, r, project.id)
            return {"archived": False, "deleted": True}

        self._store.archive_memory(memory_id, r)
        return {"archived": True, "deleted": False}


class UserMemoryService:
    def __init__(self, store: AgentMemoryStore) -> None:
        self._store = store

    async def remember(
        self,
        kind: UserMemoryKind,
        content: str,
        why_useful_later: str,
        summary: str | None = None,
        tags: list[str] | None = None,
        confidence: Confidence = "medium",
        source: str | None = None,
        source_ref: str | None = None,
    ) -> UserMemoryRecord:
        existing = self._store.list_active_user_memories()
        existing_contents = [m.content for m in existing]
        ok, reasons = evaluate_user_memory_quality(content, why_useful_later, existing_contents)
        if not ok:
            logger.warning("user memory rejected: %s", "; ".join(reasons))
            raise MemoryQualityError(reasons)

        normalized_tags = _normalize_tags(tags)
        cleaned_content = content.strip()
        cleaned_summary = _clean_optional(summary)

        text = memory_embed_text(cleaned_content, cleaned_summary, normalized_tags)
        vectors = await embed([text])
        if not vectors:
            raise RuntimeError("Embedding returned empty result.")

        return self._store.create_user_memory(
            kind=kind,
            content=cleaned_content,
            summary=cleaned_summary,
            why_useful_later=why_useful_later.strip(),
            tags=normalized_tags,
            confidence=confidence,
            source=_clean_optional(source),
            source_ref=_clean_optional(source_ref),
            vector=vectors[0],
        )

    async def search(
        self,
        query: str,
        k: int = 8,
        offset: int = 0,
        kinds: list[UserMemoryKind] | None = None,
        tags: list[str] | None = None,
        include_archived: bool = False,
    ) -> list[UserMemoryRecord]:
        limit = _clamp(k, 1, 25)
        skip = _clamp(offset, 0, 100)

        vectors = await embed([query])
        if not vectors:
            raise RuntimeError("Embedding returned empty result.")
        query_vector = pack_vector(vectors[0])

        return self._store.search_user_memories(
            query_vector=query_vector,
            limit=limit,
            offset=skip,
            include_archived=include_archived,
            kinds=kinds or None,
            tags=_normalize_tags(tags) or None,
        )

    def brief(self) -> dict[str, list[UserMemoryRecord]]:
        return self._store.user_memory_brief()

    def purge_archived(self, days: int = 90) -> int:
        before = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()
        return self._store.purge_archived_user_memories(before)

    async def update(
        self,
        memory_id: int,
        content: str | None = None,
        summary: str | None = None,
        why_useful_later: str | None = None,
        tags: list[str] | None = None,
        confidence: Confidence | None = None,
        archive: bool = False,
        reason: str | None = None,
    ) -> UserMemoryRecord:
        memory = self._store.get_user_memory(memory_id)
        if not memory:
            raise ValueError(f"User memory not found: {memory_id}")

        if content and looks_like_secret(content):
            raise MemoryQualityError(["Updated memory content looks like it may contain a secret or credential."])
        if why_useful_later and looks_like_secret(why_useful_later):
            raise MemoryQualityError(["Updated usefulness rationale looks like it may contain a secret or credential."])

        vector = None
        if not archive:
            content_for_embed = content.strip() if content else memory.content
            summary_for_embed = _clean_optional(summary) if summary is not None else memory.summary
            tags_for_embed = _normalize_tags(tags) if tags is not None else memory.tags
            text = memory_embed_text(content_for_embed, summary_for_embed, tags_for_embed)
            vectors = await embed([text])
            if not vectors:
                raise RuntimeError("Embedding returned empty result.")
            vector = vectors[0]

        return self._store.update_user_memory(
            memory_id=memory_id,
            content=content.strip() if content else None,
            summary=_clean_optional(summary),
            why_useful_later=why_useful_later.strip() if why_useful_later else None,
            tags=_normalize_tags(tags) if tags is not None else None,
            confidence=confidence,
            archived_at=datetime.now(tz=UTC).isoformat() if archive else None,
            reason=reason or "User memory updated.",
            vector=vector,
        )

    def forget(self, memory_id: int, hard_delete: bool = False, reason: str | None = None) -> dict:
        memory = self._store.get_user_memory(memory_id)
        if not memory:
            raise ValueError(f"User memory not found: {memory_id}")

        r = reason or "User memory forgotten by request."
        if hard_delete:
            self._store.hard_delete_user_memory(memory_id, r)
            return {"archived": False, "deleted": True}

        self._store.archive_user_memory(memory_id, r)
        return {"archived": True, "deleted": False}
