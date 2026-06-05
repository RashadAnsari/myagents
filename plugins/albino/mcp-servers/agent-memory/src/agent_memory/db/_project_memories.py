import json
import logging
import sqlite3

from ..types import Confidence, MemoryKind, MemoryRecord
from ._utils import map_project_memory, now_iso

logger = logging.getLogger(__name__)


class ProjectMemoriesMixin:
    _conn: sqlite3.Connection

    def list_active_project_memories(self, project_id: int) -> list[MemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM project_memories WHERE project_id = ? AND archived_at IS NULL ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
        return [map_project_memory(r) for r in rows]

    def get_project_memory(self, memory_id: int) -> MemoryRecord | None:
        row = self._conn.execute("SELECT * FROM project_memories WHERE id = ?", (memory_id,)).fetchone()
        return map_project_memory(row) if row else None

    def create_project_memory(
        self,
        project_id: int,
        kind: MemoryKind,
        content: str,
        summary: str | None,
        why_useful_later: str,
        tags: list[str],
        confidence: Confidence,
        source: str | None,
        source_ref: str | None,
        vector: list[float],
    ) -> MemoryRecord:
        now = now_iso()
        with self._transaction():
            result = self._conn.execute(
                "INSERT INTO project_memories"
                " (project_id, kind, content, summary, why_useful_later, tags_json, confidence,"
                "  source, source_ref, created_at, updated_at, use_count)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    project_id,
                    kind,
                    content,
                    summary,
                    why_useful_later,
                    json.dumps(tags),
                    confidence,
                    source,
                    source_ref,
                    now,
                    now,
                ),
            )
            memory = self.get_project_memory(result.lastrowid)
            if not memory:
                raise RuntimeError("Failed to create project memory.")
            logger.info("project memory created id=%s project_id=%s kind=%s", memory.id, project_id, kind)
            self._add_project_event(memory.id, "created", why_useful_later, project_id=project_id)
            self._write_embedding("project_memory_vec", memory.id, vector)
        return memory

    def update_project_memory(
        self,
        memory_id: int,
        content: str | None,
        summary: str | None,
        why_useful_later: str | None,
        tags: list[str] | None,
        confidence: Confidence | None,
        archived_at: str | None,
        reason: str,
        vector: list[float] | None = None,
    ) -> MemoryRecord:
        existing = self.get_project_memory(memory_id)
        if not existing:
            raise ValueError(f"Project memory not found: {memory_id}")
        now = now_iso()
        with self._transaction():
            self._conn.execute(
                "UPDATE project_memories"
                " SET content = ?, summary = ?, why_useful_later = ?, tags_json = ?,"
                "     confidence = ?, archived_at = ?, updated_at = ?"
                " WHERE id = ?",
                (
                    content if content is not None else existing.content,
                    summary if summary is not None else existing.summary,
                    why_useful_later if why_useful_later is not None else existing.why_useful_later,
                    json.dumps(tags if tags is not None else existing.tags),
                    confidence if confidence is not None else existing.confidence,
                    archived_at if archived_at is not None else existing.archived_at,
                    now,
                    memory_id,
                ),
            )
            memory = self.get_project_memory(memory_id)
            if not memory:
                raise RuntimeError(f"Project memory not found after update: {memory_id}")
            self._add_project_event(memory.id, "updated", reason, project_id=existing.project_id)
            if vector is not None:
                self._write_embedding("project_memory_vec", memory_id, vector)
        return memory

    def archive_project_memory(self, memory_id: int, reason: str) -> MemoryRecord:
        archived_at = now_iso()
        with self._transaction():
            self._conn.execute(
                "UPDATE project_memories SET archived_at = ?, updated_at = ? WHERE id = ?",
                (archived_at, archived_at, memory_id),
            )
            memory = self.get_project_memory(memory_id)
            if not memory:
                raise RuntimeError(f"Project memory not found after archive: {memory_id}")
            logger.info("project memory archived id=%s", memory_id)
            self._add_project_event(memory_id, "forgotten", reason, project_id=memory.project_id)
        return memory

    def hard_delete_project_memory(self, memory_id: int, reason: str, project_id: int) -> None:
        logger.info("project memory hard-deleted id=%s", memory_id)
        with self._transaction():
            self._add_project_event(memory_id, "hard_deleted", reason, project_id=project_id)
            self._conn.execute("DELETE FROM project_memory_vec WHERE memory_id = ?", (memory_id,))
            self._conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))

    def search_project_memories(
        self,
        project_id: int,
        query_vector: bytes,
        limit: int,
        offset: int = 0,
        include_archived: bool = False,
        kinds: list[MemoryKind] | None = None,
        tags: list[str] | None = None,
    ) -> list[MemoryRecord]:
        archived_where = "" if include_archived else "AND project_memories.archived_at IS NULL"
        kinds_where = f"AND project_memories.kind IN ({','.join('?' * len(kinds))})" if kinds else ""
        tags_where = (
            " ".join("AND EXISTS (SELECT 1 FROM json_each(project_memories.tags_json) WHERE value = ?)" for _ in tags)
            if tags
            else ""
        )
        rows = self._conn.execute(
            f"""WITH knn AS (
                    SELECT memory_id, distance
                    FROM project_memory_vec
                    WHERE embedding MATCH ?
                      AND k = ?
                )
                SELECT project_memories.*
                FROM knn
                JOIN project_memories ON project_memories.id = knn.memory_id
                WHERE project_memories.project_id = ?
                  {archived_where}
                  {kinds_where}
                  {tags_where}
                ORDER BY knn.distance
                LIMIT ? OFFSET ?""",
            (query_vector, limit + offset, project_id, *(kinds or []), *(tags or []), limit, offset),
        ).fetchall()
        memories = [map_project_memory(r) for r in rows]
        self._mark_project_memories_used([m.id for m in memories])
        return memories

    def purge_archived_project_memories(self, project_id: int, before_iso: str) -> int:
        rows = self._conn.execute(
            "SELECT id FROM project_memories WHERE project_id = ? AND archived_at IS NOT NULL AND archived_at < ?",
            (project_id, before_iso),
        ).fetchall()
        ids = [r["id"] for r in rows]
        with self._transaction():
            for memory_id in ids:
                self._add_project_event(memory_id, "purged", f"Purged (before {before_iso})", project_id=project_id)
                self._conn.execute("DELETE FROM project_memory_vec WHERE memory_id = ?", (memory_id,))
                self._conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))
        if ids:
            logger.info("purged %d archived project memories for project %s", len(ids), project_id)
        return len(ids)

    def _add_project_event(self, memory_id: int, action: str, reason: str | None, *, project_id: int) -> None:
        self._conn.execute(
            "INSERT INTO project_memory_events (project_id, memory_id, action, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, memory_id, action, reason, now_iso()),
        )

    def _mark_project_memories_used(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with self._transaction():
            self._conn.execute(
                f"UPDATE project_memories SET last_used_at = ?, use_count = use_count + 1 WHERE id IN ({placeholders})",
                (now_iso(), *ids),
            )
