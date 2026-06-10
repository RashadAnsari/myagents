import logging
import sqlite3

from ..types import UserMemoryRecord
from ._utils import map_user_memory, now_iso

logger = logging.getLogger(__name__)


class UserMemoriesMixin:
    _conn: sqlite3.Connection

    def list_active_user_memories(self) -> list[UserMemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM user_memories WHERE archived_at IS NULL ORDER BY updated_at DESC"
        ).fetchall()
        return [map_user_memory(r) for r in rows]

    def get_user_memory(self, memory_id: int) -> UserMemoryRecord | None:
        row = self._conn.execute("SELECT * FROM user_memories WHERE id = ?", (memory_id,)).fetchone()
        return map_user_memory(row) if row else None

    def create_user_memory(
        self,
        content: str,
        source: str | None,
        source_ref: str | None,
        vector: list[float],
    ) -> UserMemoryRecord:
        now = now_iso()
        with self._transaction():
            result = self._conn.execute(
                "INSERT INTO user_memories (content, source, source_ref, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (content, source, source_ref, now, now),
            )
            memory = self.get_user_memory(result.lastrowid)
            if not memory:
                raise RuntimeError("Failed to create user memory.")
            logger.info("user memory created id=%s", memory.id)
            self._write_embedding("user_memory_vec", memory.id, vector)
        return memory

    def update_user_memory(
        self,
        memory_id: int,
        content: str | None,
        archived_at: str | None,
        vector: list[float] | None = None,
    ) -> UserMemoryRecord:
        existing = self.get_user_memory(memory_id)
        if not existing:
            raise ValueError(f"User memory not found: {memory_id}")
        now = now_iso()
        with self._transaction():
            self._conn.execute(
                "UPDATE user_memories SET content = ?, archived_at = ?, updated_at = ? WHERE id = ?",
                (
                    content if content is not None else existing.content,
                    archived_at if archived_at is not None else existing.archived_at,
                    now,
                    memory_id,
                ),
            )
            memory = self.get_user_memory(memory_id)
            if not memory:
                raise RuntimeError(f"User memory not found after update: {memory_id}")
            logger.debug("user memory updated id=%s", memory_id)
            if vector is not None:
                self._write_embedding("user_memory_vec", memory_id, vector)
        return memory

    def archive_user_memory(self, memory_id: int) -> UserMemoryRecord:
        archived_at = now_iso()
        with self._transaction():
            self._conn.execute(
                "UPDATE user_memories SET archived_at = ?, updated_at = ? WHERE id = ?",
                (archived_at, archived_at, memory_id),
            )
            memory = self.get_user_memory(memory_id)
            if not memory:
                raise RuntimeError(f"User memory not found after archive: {memory_id}")
            logger.info("user memory archived id=%s", memory_id)
        return memory

    def hard_delete_user_memory(self, memory_id: int) -> None:
        existing = self.get_user_memory(memory_id)
        if not existing:
            raise ValueError(f"User memory not found: {memory_id}")
        logger.info("user memory hard-deleted id=%s", memory_id)
        with self._transaction():
            self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
            self._conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))

    def search_user_memories(
        self,
        query_vector: bytes,
        limit: int,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[UserMemoryRecord]:
        archived_where = "" if include_archived else "AND user_memories.archived_at IS NULL"
        rows = self._conn.execute(
            f"""WITH knn AS (
                    SELECT memory_id, distance
                    FROM user_memory_vec
                    WHERE embedding MATCH ?
                      AND k = ?
                )
                SELECT user_memories.*
                FROM knn
                JOIN user_memories ON user_memories.id = knn.memory_id
                WHERE 1=1
                  {archived_where}
                ORDER BY knn.distance
                LIMIT ? OFFSET ?""",
            (query_vector, limit + offset, limit, offset),
        ).fetchall()
        return [map_user_memory(r) for r in rows]

    def purge_archived_user_memories(self, before_iso: str) -> int:
        rows = self._conn.execute(
            "SELECT id FROM user_memories WHERE archived_at IS NOT NULL AND archived_at < ?",
            (before_iso,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        with self._transaction():
            for memory_id in ids:
                self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
                self._conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
        if ids:
            logger.info("purged %d archived user memories", len(ids))
        return len(ids)
