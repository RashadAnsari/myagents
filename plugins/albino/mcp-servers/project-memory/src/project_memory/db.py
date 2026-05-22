import json
import sqlite3
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path

import sqlite_vec

from .embedding import EMBEDDING_DIM
from .paths import fingerprint_remote, get_git_remote, normalize_project_root, project_name_from_root
from .types import (
    Confidence,
    MemoryKind,
    MemoryRecord,
    ProjectRecord,
    UserMemoryKind,
    UserMemoryRecord,
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _parse_json_array(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
        return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []
    except Exception as exc:
        print(f"[WARNING] project-memory: failed to parse JSON array ({exc}): {value!r}", file=sys.stderr)
        return []


class ProjectMemoryStore:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            # check_same_thread=False is intentional: this server is asyncio-based and all DB
            # calls are synchronous (never awaited), so only one coroutine accesses the
            # connection at a time on the single event-loop thread.
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._vec_available = False
            try:
                self._conn.enable_load_extension(True)
                sqlite_vec.load(self._conn)
                self._conn.enable_load_extension(False)
                self._vec_available = True
            except Exception as exc:
                print(
                    f"[WARNING] project-memory: sqlite-vec failed to load ({exc}); vector search disabled for {db_path}",
                    file=sys.stderr,
                )
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA journal_size_limit = 67108864;")
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._migrate()
        except Exception as exc:
            print(f"[ERROR] project-memory: database initialization failed for {db_path}: {exc}", file=sys.stderr)
            raise

    def close(self) -> None:
        self._conn.close()

    def _commit(self, context: str) -> None:
        try:
            self._conn.commit()
        except Exception as exc:
            print(f"[ERROR] project-memory: commit failed in {context}: {exc}", file=sys.stderr)
            raise

    def get_or_create_project(self, project_root: str) -> ProjectRecord:
        root_path = normalize_project_root(project_root)
        git_remote = get_git_remote(root_path)
        remote_fingerprint = fingerprint_remote(git_remote)
        now = _now()
        # INSERT OR IGNORE is safe here: all DB calls are synchronous on the single asyncio
        # event-loop thread, so there is no true concurrent access to this connection.
        self._conn.execute(
            """INSERT OR IGNORE INTO projects
               (root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                root_path,
                project_name_from_root(root_path),
                git_remote,
                remote_fingerprint,
                json.dumps([root_path]),
                now,
                now,
            ),
        )
        self._commit("get_or_create_project")
        row = self._conn.execute("SELECT * FROM projects WHERE root_path = ?", (root_path,)).fetchone()
        return _map_project(row)

    def get_project_by_id(self, project_id: int) -> ProjectRecord:
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            raise ValueError(f"Project not found: {project_id}")
        return _map_project(row)

    def list_active_memories(self, project_id: int) -> list[MemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE project_id = ? AND archived_at IS NULL ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
        return [_map_memory(r) for r in rows]

    def get_memory(self, memory_id: int) -> MemoryRecord | None:
        row = self._conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return _map_memory(row) if row else None

    def create_memory(
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
    ) -> MemoryRecord:
        now = _now()
        result = self._conn.execute(
            """INSERT INTO memories
               (project_id, kind, content, summary, why_useful_later, tags_json, confidence,
                source, source_ref, created_at, updated_at, use_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
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
        memory = self.get_memory(result.lastrowid)
        if not memory:
            raise RuntimeError("Failed to create memory.")
        self._add_event(memory.id, "created", why_useful_later, project_id=project_id)
        self._commit("create_memory")
        return memory

    def update_memory(
        self,
        memory_id: int,
        content: str | None,
        summary: str | None,
        why_useful_later: str | None,
        tags: list[str] | None,
        confidence: Confidence | None,
        archived_at: str | None,
        reason: str,
    ) -> MemoryRecord:
        existing = self.get_memory(memory_id)
        if not existing:
            raise ValueError(f"Memory not found: {memory_id}")
        now = _now()
        self._conn.execute(
            """UPDATE memories
               SET content = ?, summary = ?, why_useful_later = ?, tags_json = ?,
                   confidence = ?, archived_at = ?, updated_at = ?
               WHERE id = ?""",
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
        memory = self.get_memory(memory_id)
        if not memory:
            raise RuntimeError(f"Memory not found after update: {memory_id}")
        self._add_event(memory.id, "updated", reason, project_id=existing.project_id)
        self._commit("update_memory")
        return memory

    def archive_memory(self, memory_id: int, reason: str) -> MemoryRecord:
        archived_at = _now()
        self._conn.execute(
            "UPDATE memories SET archived_at = ?, updated_at = ? WHERE id = ?",
            (archived_at, archived_at, memory_id),
        )
        memory = self.get_memory(memory_id)
        if not memory:
            raise RuntimeError(f"Memory not found after archive: {memory_id}")
        # Keep the embedding so include_archived=True searches can still find this memory.
        # The KNN JOIN+WHERE filters it from normal searches via archived_at IS NULL.
        self._add_event(memory_id, "forgotten", reason, project_id=memory.project_id)
        self._commit("archive_memory")
        return memory

    def hard_delete_memory(self, memory_id: int, reason: str, project_id: int) -> None:
        # Audit event created before delete so the FK is satisfied at insert time.
        # ON DELETE SET NULL clears memory_id in the event once the row is removed.
        self._add_event(memory_id, "hard_deleted", reason, project_id=project_id)
        self._conn.execute("DELETE FROM memory_vec WHERE memory_id = ?", (memory_id,))
        self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._commit("hard_delete_memory")

    def search_memories(
        self,
        project_id: int,
        query_vector: bytes,
        limit: int,
        include_archived: bool = False,
        kinds: list[MemoryKind] | None = None,
        tags: list[str] | None = None,
    ) -> list[MemoryRecord]:
        if not self._vec_available:
            return []
        archived_where = "" if include_archived else "AND memories.archived_at IS NULL"
        kinds_where = f"AND memories.kind IN ({','.join('?' * len(kinds))})" if kinds else ""
        tags_where = (
            " ".join("AND EXISTS (SELECT 1 FROM json_each(memories.tags_json) WHERE value = ?)" for _ in tags)
            if tags
            else ""
        )
        rows = self._conn.execute(
            f"""WITH knn AS (
                    SELECT memory_id, distance
                    FROM memory_vec
                    WHERE embedding MATCH ?
                      AND k = ?
                )
                SELECT memories.*
                FROM knn
                JOIN memories ON memories.id = knn.memory_id
                WHERE memories.project_id = ?
                  {archived_where}
                  {kinds_where}
                  {tags_where}
                ORDER BY knn.distance""",
            (query_vector, limit, project_id, *(kinds or []), *(tags or [])),
        ).fetchall()
        memories = [_map_memory(r) for r in rows]
        self._mark_used([m.id for m in memories])
        return memories

    def project_brief(self, project_id: int) -> dict[str, list[MemoryRecord]]:
        active = self.list_active_memories(project_id)

        def by_kind(kinds: list[MemoryKind], limit: int) -> list[MemoryRecord]:
            return sorted(
                [m for m in active if m.kind in kinds],
                key=_brief_sort_key,
            )[:limit]

        return {
            "conventions": by_kind(["convention", "preference"], 8),
            "decisions": by_kind(["decision", "architecture"], 8),
            "pitfalls": by_kind(["gotcha", "bug"], 8),
            "recent": sorted(active, key=lambda m: m.updated_at, reverse=True)[:8],
        }

    def upsert_embedding(self, memory_id: int, vector: list[float]) -> None:
        if not self._vec_available:
            return
        self._conn.execute("DELETE FROM memory_vec WHERE memory_id = ?", (memory_id,))
        self._conn.execute(
            "INSERT INTO memory_vec (memory_id, embedding) VALUES (?, ?)",
            (memory_id, pack_vector(vector)),
        )
        self._commit("upsert_embedding")

    def _mark_used(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self._conn.execute(
            f"UPDATE memories SET last_used_at = ?, use_count = use_count + 1 WHERE id IN ({placeholders})",
            (_now(), *ids),
        )
        self._commit("_mark_used")

    def _add_event(self, memory_id: int, action: str, reason: str | None, *, project_id: int) -> None:
        self._conn.execute(
            "INSERT INTO memory_events (project_id, memory_id, action, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, memory_id, action, reason, _now()),
        )

    def list_active_user_memories(self) -> list[UserMemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM user_memories WHERE archived_at IS NULL ORDER BY updated_at DESC"
        ).fetchall()
        return [_map_user_memory(r) for r in rows]

    def get_user_memory(self, memory_id: int) -> UserMemoryRecord | None:
        row = self._conn.execute("SELECT * FROM user_memories WHERE id = ?", (memory_id,)).fetchone()
        return _map_user_memory(row) if row else None

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
    ) -> UserMemoryRecord:
        now = _now()
        result = self._conn.execute(
            """INSERT INTO user_memories
               (kind, content, summary, why_useful_later, tags_json, confidence,
                source, source_ref, created_at, updated_at, use_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (kind, content, summary, why_useful_later, json.dumps(tags), confidence, source, source_ref, now, now),
        )
        memory = self.get_user_memory(result.lastrowid)
        if not memory:
            raise RuntimeError("Failed to create user memory.")
        self._add_user_event(memory.id, "created", why_useful_later)
        self._commit("create_user_memory")
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
    ) -> UserMemoryRecord:
        existing = self.get_user_memory(memory_id)
        if not existing:
            raise ValueError(f"User memory not found: {memory_id}")
        now = _now()
        self._conn.execute(
            """UPDATE user_memories
               SET content = ?, summary = ?, why_useful_later = ?, tags_json = ?,
                   confidence = ?, archived_at = ?, updated_at = ?
               WHERE id = ?""",
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
        self._commit("update_user_memory")
        return memory

    def archive_user_memory(self, memory_id: int, reason: str) -> UserMemoryRecord:
        archived_at = _now()
        self._conn.execute(
            "UPDATE user_memories SET archived_at = ?, updated_at = ? WHERE id = ?",
            (archived_at, archived_at, memory_id),
        )
        memory = self.get_user_memory(memory_id)
        if not memory:
            raise RuntimeError(f"User memory not found after archive: {memory_id}")
        # Keep the embedding so include_archived=True searches can still find this memory.
        self._add_user_event(memory_id, "forgotten", reason)
        self._commit("archive_user_memory")
        return memory

    def hard_delete_user_memory(self, memory_id: int, reason: str) -> None:
        existing = self.get_user_memory(memory_id)
        if not existing:
            raise ValueError(f"User memory not found: {memory_id}")
        # Audit event created before delete so the FK is satisfied at insert time.
        # ON DELETE SET NULL clears memory_id in the event once the row is removed.
        self._add_user_event(memory_id, "hard_deleted", reason)
        self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
        self._conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
        self._commit("hard_delete_user_memory")

    def search_user_memories(
        self,
        query_vector: bytes,
        limit: int,
        include_archived: bool = False,
        kinds: list[UserMemoryKind] | None = None,
        tags: list[str] | None = None,
    ) -> list[UserMemoryRecord]:
        if not self._vec_available:
            return []
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
                ORDER BY knn.distance""",
            (query_vector, limit, *(kinds or []), *(tags or [])),
        ).fetchall()
        memories = [_map_user_memory(r) for r in rows]
        self._mark_user_memories_used([m.id for m in memories])
        return memories

    def user_memory_brief(self) -> dict[str, list[UserMemoryRecord]]:
        active = self.list_active_user_memories()

        def by_kind(kinds: list[UserMemoryKind], limit: int) -> list[UserMemoryRecord]:
            return sorted([m for m in active if m.kind in kinds], key=_user_brief_sort_key)[:limit]

        return {
            "preferences": by_kind(["preference", "convention", "tool_preference"], 8),
            "behaviors": by_kind(["behavior", "workflow", "communication"], 8),
            "context": by_kind(["context"], 8),
            "recent": sorted(active, key=lambda m: m.updated_at, reverse=True)[:8],
        }

    def upsert_user_embedding(self, memory_id: int, vector: list[float]) -> None:
        if not self._vec_available:
            return
        self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
        self._conn.execute(
            "INSERT INTO user_memory_vec (memory_id, embedding) VALUES (?, ?)",
            (memory_id, pack_vector(vector)),
        )
        self._commit("upsert_user_embedding")

    def _add_user_event(self, memory_id: int | None, action: str, reason: str | None) -> None:
        if memory_id is None and action != "hard_deleted":
            raise ValueError(f"memory_id must not be None for action '{action}'")
        self._conn.execute(
            "INSERT INTO user_memory_events (memory_id, action, reason, created_at) VALUES (?, ?, ?, ?)",
            (memory_id, action, reason, _now()),
        )

    def _mark_user_memories_used(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self._conn.execute(
            f"UPDATE user_memories SET last_used_at = ?, use_count = use_count + 1 WHERE id IN ({placeholders})",
            (_now(), *ids),
        )
        self._commit("_mark_user_memories_used")

    def _migrate(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_path TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                git_remote TEXT,
                remote_fingerprint TEXT,
                known_paths_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_projects_remote_fingerprint ON projects(remote_fingerprint);

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                why_useful_later TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                confidence TEXT NOT NULL DEFAULT 'medium' CHECK(confidence IN ('low', 'medium', 'high')),
                source TEXT,
                source_ref TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,
                use_count INTEGER NOT NULL DEFAULT 0,
                archived_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_memories_project_active ON memories(project_id, archived_at);
            CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
            CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at);

            CREATE TABLE IF NOT EXISTS memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                memory_id INTEGER REFERENCES memories(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memory_events_memory_id ON memory_events(memory_id);

            CREATE TABLE IF NOT EXISTS user_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                why_useful_later TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                confidence TEXT NOT NULL DEFAULT 'medium' CHECK(confidence IN ('low', 'medium', 'high')),
                source TEXT,
                source_ref TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,
                use_count INTEGER NOT NULL DEFAULT 0,
                archived_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_user_memories_active ON user_memories(archived_at);
            CREATE INDEX IF NOT EXISTS idx_user_memories_kind ON user_memories(kind);
            CREATE INDEX IF NOT EXISTS idx_user_memories_updated_at ON user_memories(updated_at);

            CREATE TABLE IF NOT EXISTS user_memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER REFERENCES user_memories(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_user_memory_events_memory_id ON user_memory_events(memory_id);

        """)
        if self._vec_available:
            self._conn.executescript(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec USING vec0(
                    memory_id INTEGER PRIMARY KEY,
                    embedding float[{EMBEDDING_DIM}]
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS user_memory_vec USING vec0(
                    memory_id INTEGER PRIMARY KEY,
                    embedding float[{EMBEDDING_DIM}]
                );
            """)


def _map_project(row: sqlite3.Row) -> ProjectRecord:
    return ProjectRecord(
        id=row["id"],
        root_path=row["root_path"],
        name=row["name"],
        git_remote=row["git_remote"],
        remote_fingerprint=row["remote_fingerprint"],
        known_paths=_parse_json_array(row["known_paths_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _map_memory(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        project_id=row["project_id"],
        kind=row["kind"],
        content=row["content"],
        summary=row["summary"],
        why_useful_later=row["why_useful_later"],
        tags=_parse_json_array(row["tags_json"]),
        confidence=row["confidence"],
        source=row["source"],
        source_ref=row["source_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_used_at=row["last_used_at"],
        use_count=row["use_count"],
        archived_at=row["archived_at"],
    )


def _map_user_memory(row: sqlite3.Row) -> UserMemoryRecord:
    return UserMemoryRecord(
        id=row["id"],
        kind=row["kind"],
        content=row["content"],
        summary=row["summary"],
        why_useful_later=row["why_useful_later"],
        tags=_parse_json_array(row["tags_json"]),
        confidence=row["confidence"],
        source=row["source"],
        source_ref=row["source_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_used_at=row["last_used_at"],
        use_count=row["use_count"],
        archived_at=row["archived_at"],
    )


def _confidence_score(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 2)


def _brief_sort_key(m: MemoryRecord) -> tuple:
    return (-_confidence_score(m.confidence), -m.use_count, m.updated_at)


def _user_brief_sort_key(m: UserMemoryRecord) -> tuple:
    return (-_confidence_score(m.confidence), -m.use_count, m.updated_at)
