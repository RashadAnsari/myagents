import logging
import sqlite3

from ..types import ProjectMemoryRecord
from ._utils import map_project_memory, now_iso

logger = logging.getLogger(__name__)


class ProjectMemoriesMixin:
    _conn: sqlite3.Connection

    def list_active_project_memories(self, project_id: int) -> list[ProjectMemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM project_memories WHERE project_id = ? AND archived_at IS NULL ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
        return [map_project_memory(r) for r in rows]

    def get_project_memory(self, memory_id: int) -> ProjectMemoryRecord | None:
        row = self._conn.execute("SELECT * FROM project_memories WHERE id = ?", (memory_id,)).fetchone()
        return map_project_memory(row) if row else None

    def create_project_memory(
        self,
        project_id: int,
        content: str,
        source: str | None,
        source_ref: str | None,
        vector: list[float],
    ) -> ProjectMemoryRecord:
        now = now_iso()
        with self._transaction():
            result = self._conn.execute(
                "INSERT INTO project_memories"
                " (project_id, content, source, source_ref, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, content, source, source_ref, now, now),
            )
            memory = self.get_project_memory(result.lastrowid)
            if not memory:
                raise RuntimeError("Failed to create project memory.")
            logger.info("project memory created id=%s project_id=%s", memory.id, project_id)
            self._write_embedding("project_memory_vec", memory.id, vector)
        return memory

    def update_project_memory(
        self,
        memory_id: int,
        content: str | None,
        archived_at: str | None,
        vector: list[float] | None = None,
    ) -> ProjectMemoryRecord:
        existing = self.get_project_memory(memory_id)
        if not existing:
            raise ValueError(f"Project memory not found: {memory_id}")
        now = now_iso()
        with self._transaction():
            self._conn.execute(
                "UPDATE project_memories SET content = ?, archived_at = ?, updated_at = ? WHERE id = ?",
                (
                    content if content is not None else existing.content,
                    archived_at if archived_at is not None else existing.archived_at,
                    now,
                    memory_id,
                ),
            )
            memory = self.get_project_memory(memory_id)
            if not memory:
                raise RuntimeError(f"Project memory not found after update: {memory_id}")
            logger.debug("project memory updated id=%s", memory_id)
            if vector is not None:
                self._write_embedding("project_memory_vec", memory_id, vector)
        return memory

    def archive_project_memory(self, memory_id: int) -> ProjectMemoryRecord:
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
        return memory

    def hard_delete_project_memory(self, memory_id: int, project_id: int) -> None:
        logger.info("project memory hard-deleted id=%s", memory_id)
        with self._transaction():
            self._conn.execute("DELETE FROM project_memory_vec WHERE memory_id = ?", (memory_id,))
            self._conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))

    def search_project_memories(
        self,
        project_id: int,
        query_vector: bytes,
        limit: int,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[ProjectMemoryRecord]:
        archived_where = "" if include_archived else "AND project_memories.archived_at IS NULL"
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
                ORDER BY knn.distance
                LIMIT ? OFFSET ?""",
            (query_vector, limit + offset, project_id, limit, offset),
        ).fetchall()
        return [map_project_memory(r) for r in rows]

    def purge_archived_project_memories(self, project_id: int, before_iso: str) -> int:
        rows = self._conn.execute(
            "SELECT id FROM project_memories WHERE project_id = ? AND archived_at IS NOT NULL AND archived_at < ?",
            (project_id, before_iso),
        ).fetchall()
        ids = [r["id"] for r in rows]
        with self._transaction():
            for memory_id in ids:
                self._conn.execute("DELETE FROM project_memory_vec WHERE memory_id = ?", (memory_id,))
                self._conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))
        if ids:
            logger.info("purged %d archived project memories for project %s", len(ids), project_id)
        return len(ids)
