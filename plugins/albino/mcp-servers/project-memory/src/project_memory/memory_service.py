import re
import sys
from datetime import UTC, datetime

from .db import ProjectMemoryStore, pack_vector
from .embedding import embed, memory_embed_text
from .quality import evaluate_memory_quality, evaluate_user_memory_quality, looks_like_secret
from .types import (
    Confidence,
    MemoryKind,
    MemoryRecord,
    UserMemoryKind,
    UserMemoryRecord,
)


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
    def __init__(self, store: ProjectMemoryStore) -> None:
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
            print(
                f"[WARNING] project-memory: memory rejected for project {project.id} — {'; '.join(reasons)}",
                file=sys.stderr,
            )
            raise MemoryQualityError(reasons)

        normalized_tags = _normalize_tags(tags)
        memory = self._store.create_memory(
            project_id=project.id,
            kind=kind,
            content=content.strip(),
            summary=_clean_optional(summary),
            why_useful_later=why_useful_later.strip(),
            tags=normalized_tags,
            confidence=confidence,
            source=_clean_optional(source),
            source_ref=_clean_optional(source_ref),
        )
        try:
            text = memory_embed_text(memory.content, memory.summary, memory.tags)
            vectors = await embed([text])
            if not vectors:
                raise RuntimeError("Embedding returned empty result.")
            self._store.upsert_embedding(memory.id, vectors[0])
        except Exception as exc:
            print(f"project-memory: embedding failed for memory {memory.id}, rolling back: {exc}", file=sys.stderr)
            try:
                self._store.hard_delete_memory(memory.id, "Embedding failed during creation.", project.id)
            except Exception as cleanup_exc:
                print(f"project-memory: cleanup of memory {memory.id} also failed: {cleanup_exc}", file=sys.stderr)
            raise
        return memory

    async def search(
        self,
        project_root: str,
        query: str,
        k: int = 8,
        kinds: list[MemoryKind] | None = None,
        tags: list[str] | None = None,
        include_archived: bool = False,
    ) -> list[MemoryRecord]:
        project = self._store.get_or_create_project(project_root)
        limit = _clamp(k, 1, 25)

        vectors = await embed([query])
        if not vectors:
            raise RuntimeError("Embedding returned empty result.")
        query_vector = pack_vector(vectors[0])

        return self._store.search_memories(
            project_id=project.id,
            query_vector=query_vector,
            limit=limit,
            include_archived=include_archived,
            kinds=kinds if kinds else None,
            tags=_normalize_tags(tags) if tags else None,
        )

    def project_brief(self, project_root: str) -> dict[str, list[MemoryRecord]]:
        project = self._store.get_or_create_project(project_root)
        return self._store.project_brief(project.id)

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
        project = self._store.get_or_create_project(project_root)
        memory = self._store.get_memory(memory_id)
        if not memory or memory.project_id != project.id:
            raise ValueError(f"Memory not found for project: {memory_id}")

        if content and looks_like_secret(content):
            raise MemoryQualityError(["Updated memory content looks like it may contain a secret or credential."])
        if why_useful_later and looks_like_secret(why_useful_later):
            raise MemoryQualityError(["Updated usefulness rationale looks like it may contain a secret or credential."])

        updated = self._store.update_memory(
            memory_id=memory_id,
            content=content.strip() if content else None,
            summary=_clean_optional(summary),
            why_useful_later=why_useful_later.strip() if why_useful_later else None,
            tags=_normalize_tags(tags) if tags is not None else None,
            confidence=confidence,
            archived_at=datetime.now(tz=UTC).isoformat() if archive else None,
            reason=reason or "Memory updated.",
        )
        if not updated.archived_at:
            text = memory_embed_text(updated.content, updated.summary, updated.tags)
            vectors = await embed([text])
            if not vectors:
                raise RuntimeError("Embedding returned empty result.")
            self._store.upsert_embedding(updated.id, vectors[0])
        return updated

    def forget(self, project_root: str, memory_id: int, hard_delete: bool = False, reason: str | None = None) -> dict:
        project = self._store.get_or_create_project(project_root)
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
    def __init__(self, store: ProjectMemoryStore) -> None:
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
            print(f"[WARNING] project-memory: user memory rejected — {'; '.join(reasons)}", file=sys.stderr)
            raise MemoryQualityError(reasons)

        normalized_tags = _normalize_tags(tags)
        memory = self._store.create_user_memory(
            kind=kind,
            content=content.strip(),
            summary=_clean_optional(summary),
            why_useful_later=why_useful_later.strip(),
            tags=normalized_tags,
            confidence=confidence,
            source=_clean_optional(source),
            source_ref=_clean_optional(source_ref),
        )
        try:
            text = memory_embed_text(memory.content, memory.summary, memory.tags)
            vectors = await embed([text])
            if not vectors:
                raise RuntimeError("Embedding returned empty result.")
            self._store.upsert_user_embedding(memory.id, vectors[0])
        except Exception as exc:
            print(f"project-memory: embedding failed for user memory {memory.id}, rolling back: {exc}", file=sys.stderr)
            try:
                self._store.hard_delete_user_memory(memory.id, "Embedding failed during creation.")
            except Exception as cleanup_exc:
                print(f"project-memory: cleanup of user memory {memory.id} also failed: {cleanup_exc}", file=sys.stderr)
            raise
        return memory

    async def search(
        self,
        query: str,
        k: int = 8,
        kinds: list[UserMemoryKind] | None = None,
        tags: list[str] | None = None,
        include_archived: bool = False,
    ) -> list[UserMemoryRecord]:
        limit = _clamp(k, 1, 25)

        vectors = await embed([query])
        if not vectors:
            raise RuntimeError("Embedding returned empty result.")
        query_vector = pack_vector(vectors[0])

        return self._store.search_user_memories(
            query_vector=query_vector,
            limit=limit,
            include_archived=include_archived,
            kinds=kinds if kinds else None,
            tags=_normalize_tags(tags) if tags else None,
        )

    def brief(self) -> dict[str, list[UserMemoryRecord]]:
        return self._store.user_memory_brief()

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

        updated = self._store.update_user_memory(
            memory_id=memory_id,
            content=content.strip() if content else None,
            summary=_clean_optional(summary),
            why_useful_later=why_useful_later.strip() if why_useful_later else None,
            tags=_normalize_tags(tags) if tags is not None else None,
            confidence=confidence,
            archived_at=datetime.now(tz=UTC).isoformat() if archive else None,
            reason=reason or "User memory updated.",
        )
        if not updated.archived_at:
            text = memory_embed_text(updated.content, updated.summary, updated.tags)
            vectors = await embed([text])
            if not vectors:
                raise RuntimeError("Embedding returned empty result.")
            self._store.upsert_user_embedding(updated.id, vectors[0])
        return updated

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
