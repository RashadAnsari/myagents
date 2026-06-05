import json
import logging
import sqlite3

from ..types import Confidence, UserMemoryKind, UserMemoryRecord
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
        kind: UserMemoryKind,
        content: str,
        summary: str | None,
        why_useful_later: str,
        tags: list[str],
        confidence: Confidence,
        source: str | None,
        source_ref: str | None,
        vector: list[float],
    ) -> UserMemoryRecord:
        now = now_iso()
        with self._transaction():
            result = self._conn.execute(
                "INSERT INTO user_memories"
                " (kind, content, summary, why_useful_later, tags_json, confidence,"
                "  source, source_ref, created_at, updated_at, use_count)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (kind, content, summary, why_useful_later, json.dumps(tags), confidence, source, source_ref, now, now),
            )
            memory = self.get_user_memory(result.lastrowid)
            if not memory:
                raise RuntimeError("Failed to create user memory.")
            logger.info("user memory created id=%s kind=%s", memory.id, kind)
            self._add_user_event(memory.id, "created", why_useful_later)
            self._write_embedding("user_memory_vec", memory.id, vector)
        return memory

    def update_user_memory(
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
    ) -> UserMemoryRecord:
        existing = self.get_user_memory(memory_id)
        if not existing:
            raise ValueError(f"User memory not found: {memory_id}")
        now = now_iso()
        with self._transaction():
            self._conn.execute(
                "UPDATE user_memories"
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
            memory = self.get_user_memory(memory_id)
            if not memory:
                raise RuntimeError(f"User memory not found after update: {memory_id}")
            self._add_user_event(memory_id, "updated", reason)
            if vector is not None:
                self._write_embedding("user_memory_vec", memory_id, vector)
        return memory

    def archive_user_memory(self, memory_id: int, reason: str) -> UserMemoryRecord:
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
            self._add_user_event(memory_id, "forgotten", reason)
        return memory

    def hard_delete_user_memory(self, memory_id: int, reason: str) -> None:
        existing = self.get_user_memory(memory_id)
        if not existing:
            raise ValueError(f"User memory not found: {memory_id}")
        logger.info("user memory hard-deleted id=%s", memory_id)
        with self._transaction():
            self._add_user_event(memory_id, "hard_deleted", reason)
            self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
            self._conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))

    def search_user_memories(
        self,
        query_vector: bytes,
        limit: int,
        offset: int = 0,
        include_archived: bool = False,
        kinds: list[UserMemoryKind] | None = None,
        tags: list[str] | None = None,
    ) -> list[UserMemoryRecord]:
        archived_where = "" if include_archived else "AND user_memories.archived_at IS NULL"
        kinds_where = f"AND user_memories.kind IN ({','.join('?' * len(kinds))})" if kinds else ""
        tags_where = (
            " ".join("AND EXISTS (SELECT 1 FROM json_each(user_memories.tags_json) WHERE value = ?)" for _ in tags)
            if tags
            else ""
        )
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
                  {kinds_where}
                  {tags_where}
                ORDER BY knn.distance
                LIMIT ? OFFSET ?""",
            (query_vector, limit + offset, *(kinds or []), *(tags or []), limit, offset),
        ).fetchall()
        memories = [map_user_memory(r) for r in rows]
        self._mark_user_memories_used([m.id for m in memories])
        return memories

    def purge_archived_user_memories(self, before_iso: str) -> int:
        rows = self._conn.execute(
            "SELECT id FROM user_memories WHERE archived_at IS NOT NULL AND archived_at < ?",
            (before_iso,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        with self._transaction():
            for memory_id in ids:
                self._add_user_event(memory_id, "purged", f"Purged (before {before_iso})")
                self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
                self._conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
        if ids:
            logger.info("purged %d archived user memories", len(ids))
        return len(ids)

    def _add_user_event(self, memory_id: int | None, action: str, reason: str | None) -> None:
        if memory_id is None and action != "hard_deleted":
            raise ValueError(f"memory_id must not be None for action '{action}'")
        self._conn.execute(
            "INSERT INTO user_memory_events (memory_id, action, reason, created_at) VALUES (?, ?, ?, ?)",
            (memory_id, action, reason, now_iso()),
        )

    def _mark_user_memories_used(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with self._transaction():
            self._conn.execute(
                f"UPDATE user_memories SET last_used_at = ?, use_count = use_count + 1 WHERE id IN ({placeholders})",
                (now_iso(), *ids),
            )
