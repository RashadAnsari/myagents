import json
import logging
import sqlite3
import struct
from datetime import UTC, datetime
from pathlib import Path

import sqlite_vec

from .embedding import EMBEDDING_DIM
from .paths import canonical_project_root, fingerprint_remote, get_git_remote, project_name_from_root
from .types import (
    Confidence,
    MemoryKind,
    MemoryRecord,
    ProjectRecord,
    UserMemoryKind,
    UserMemoryRecord,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _parse_json_array(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
        return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []
    except Exception as exc:
        logger.warning("failed to parse JSON array (%s): %r", exc, value)
        return []


def _sql_str(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


class AgentMemoryStore:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            # check_same_thread=False is intentional: this server is asyncio-based and all DB
            # calls are synchronous (never awaited), so only one coroutine accesses the
            # connection at a time on the single event-loop thread.
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA journal_size_limit = 67108864;")
            self._conn.execute("PRAGMA wal_autocheckpoint = 1000;")
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._migrate()
        except Exception as exc:
            logger.error("database initialization failed for %s: %s", db_path, exc)
            raise

    def close(self) -> None:
        self._conn.close()

    def _commit(self, context: str) -> None:
        try:
            self._conn.commit()
        except Exception as exc:
            logger.error("commit failed in %s: %s", context, exc)
            raise

    def get_or_create_project(self, project_root: str) -> ProjectRecord:
        root_path = canonical_project_root(project_root)
        git_remote = get_git_remote(root_path)
        remote_fingerprint = fingerprint_remote(git_remote)
        now = _now()

        if remote_fingerprint:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE remote_fingerprint = ?", (remote_fingerprint,)
            ).fetchone()
            if row:
                project = _map_project(row)
                if root_path not in project.known_paths:
                    updated_paths = json.dumps(sorted({*project.known_paths, root_path}))
                    self._conn.execute(
                        "UPDATE projects SET known_paths_json = ?, updated_at = ? WHERE id = ?",
                        (updated_paths, now, project.id),
                    )
                    self._commit("get_or_create_project")
                    row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project.id,)).fetchone()
                return _map_project(row)

            # Check for a legacy row (repo may have had no remote when first registered).
            legacy = self._conn.execute(
                "SELECT * FROM projects WHERE root_path = ? AND remote_fingerprint IS NULL", (root_path,)
            ).fetchone()
            if legacy:
                paths = _parse_json_array(legacy["known_paths_json"])
                if root_path not in paths:
                    paths.append(root_path)
                self._conn.execute(
                    "UPDATE projects SET git_remote = ?, remote_fingerprint = ?, known_paths_json = ?, updated_at = ? WHERE id = ?",
                    (git_remote, remote_fingerprint, json.dumps(sorted(set(paths))), now, legacy["id"]),
                )
                self._commit("get_or_create_project")
                row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (legacy["id"],)).fetchone()
                return _map_project(row)
        else:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE root_path = ? AND remote_fingerprint IS NULL", (root_path,)
            ).fetchone()
            if row:
                return _map_project(row)

        self._conn.execute(
            """INSERT INTO projects
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
        if remote_fingerprint:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE remote_fingerprint = ?", (remote_fingerprint,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE root_path = ? AND remote_fingerprint IS NULL", (root_path,)
            ).fetchone()
        return _map_project(row)

    def get_project(self, project_root: str) -> ProjectRecord | None:
        root_path = canonical_project_root(project_root)
        remote_fingerprint = fingerprint_remote(get_git_remote(root_path))
        if remote_fingerprint:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE remote_fingerprint = ?", (remote_fingerprint,)
            ).fetchone()
            if row:
                return _map_project(row)
        row = self._conn.execute("SELECT * FROM projects WHERE root_path = ?", (root_path,)).fetchone()
        return _map_project(row) if row else None

    def list_active_project_memories(self, project_id: int) -> list[MemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM project_memories WHERE project_id = ? AND archived_at IS NULL ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
        return [_map_project_memory(r) for r in rows]

    def get_project_memory(self, memory_id: int) -> MemoryRecord | None:
        row = self._conn.execute("SELECT * FROM project_memories WHERE id = ?", (memory_id,)).fetchone()
        return _map_project_memory(row) if row else None

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
        now = _now()
        result = self._conn.execute(
            """INSERT INTO project_memories
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
        memory = self.get_project_memory(result.lastrowid)
        if not memory:
            raise RuntimeError("Failed to create project memory.")
        logger.info("project memory created id=%s project_id=%s kind=%s", memory.id, project_id, kind)
        self._add_project_event(memory.id, "created", why_useful_later, project_id=project_id)
        self._write_embedding("project_memory_vec", memory.id, vector)
        self._commit("create_project_memory")
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
        now = _now()
        self._conn.execute(
            """UPDATE project_memories
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
        memory = self.get_project_memory(memory_id)
        if not memory:
            raise RuntimeError(f"Project memory not found after update: {memory_id}")
        self._add_project_event(memory.id, "updated", reason, project_id=existing.project_id)
        if vector is not None:
            self._write_embedding("project_memory_vec", memory_id, vector)
        self._commit("update_project_memory")
        return memory

    def archive_project_memory(self, memory_id: int, reason: str) -> MemoryRecord:
        archived_at = _now()
        self._conn.execute(
            "UPDATE project_memories SET archived_at = ?, updated_at = ? WHERE id = ?",
            (archived_at, archived_at, memory_id),
        )
        memory = self.get_project_memory(memory_id)
        if not memory:
            raise RuntimeError(f"Project memory not found after archive: {memory_id}")
        # Keep the embedding so include_archived=True searches can still find this memory.
        # The KNN JOIN+WHERE filters it from normal searches via archived_at IS NULL.
        logger.info("project memory archived id=%s", memory_id)
        self._add_project_event(memory_id, "forgotten", reason, project_id=memory.project_id)
        self._commit("archive_project_memory")
        return memory

    def hard_delete_project_memory(self, memory_id: int, reason: str, project_id: int) -> None:
        # Audit event created before delete so the FK is satisfied at insert time.
        # ON DELETE SET NULL clears memory_id in the event once the row is removed.
        logger.info("project memory hard-deleted id=%s", memory_id)
        self._add_project_event(memory_id, "hard_deleted", reason, project_id=project_id)
        self._conn.execute("DELETE FROM project_memory_vec WHERE memory_id = ?", (memory_id,))
        self._conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))
        self._commit("hard_delete_project_memory")

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
        memories = [_map_project_memory(r) for r in rows]
        self._mark_project_memories_used([m.id for m in memories])
        return memories

    def purge_archived_project_memories(self, project_id: int, before_iso: str) -> int:
        rows = self._conn.execute(
            "SELECT id FROM project_memories WHERE project_id = ? AND archived_at IS NOT NULL AND archived_at < ?",
            (project_id, before_iso),
        ).fetchall()
        ids = [r["id"] for r in rows]
        for memory_id in ids:
            self._add_project_event(memory_id, "purged", f"Purged (before {before_iso})", project_id=project_id)
            self._conn.execute("DELETE FROM project_memory_vec WHERE memory_id = ?", (memory_id,))
            self._conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))
        if ids:
            self._commit("purge_archived_project_memories")
            logger.info("purged %d archived project memories for project %s", len(ids), project_id)
        return len(ids)

    def _write_embedding(self, table: str, memory_id: int, vector: list[float]) -> None:
        self._conn.execute(f"DELETE FROM {table} WHERE memory_id = ?", (memory_id,))
        self._conn.execute(
            f"INSERT INTO {table} (memory_id, embedding) VALUES (?, ?)",
            (memory_id, pack_vector(vector)),
        )

    def _mark_project_memories_used(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self._conn.execute(
            f"UPDATE project_memories SET last_used_at = ?, use_count = use_count + 1 WHERE id IN ({placeholders})",
            (_now(), *ids),
        )
        self._commit("_mark_project_memories_used")

    def _add_project_event(self, memory_id: int, action: str, reason: str | None, *, project_id: int) -> None:
        self._conn.execute(
            "INSERT INTO project_memory_events (project_id, memory_id, action, reason, created_at) VALUES (?, ?, ?, ?, ?)",
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
        vector: list[float],
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
        logger.info("user memory created id=%s kind=%s", memory.id, kind)
        self._add_user_event(memory.id, "created", why_useful_later)
        self._write_embedding("user_memory_vec", memory.id, vector)
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
        vector: list[float] | None = None,
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
        if vector is not None:
            self._write_embedding("user_memory_vec", memory_id, vector)
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
        logger.info("user memory archived id=%s", memory_id)
        self._add_user_event(memory_id, "forgotten", reason)
        self._commit("archive_user_memory")
        return memory

    def hard_delete_user_memory(self, memory_id: int, reason: str) -> None:
        existing = self.get_user_memory(memory_id)
        if not existing:
            raise ValueError(f"User memory not found: {memory_id}")
        # Audit event created before delete so the FK is satisfied at insert time.
        # ON DELETE SET NULL clears memory_id in the event once the row is removed.
        logger.info("user memory hard-deleted id=%s", memory_id)
        self._add_user_event(memory_id, "hard_deleted", reason)
        self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
        self._conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
        self._commit("hard_delete_user_memory")

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
        memories = [_map_user_memory(r) for r in rows]
        self._mark_user_memories_used([m.id for m in memories])
        return memories

    def purge_archived_user_memories(self, before_iso: str) -> int:
        rows = self._conn.execute(
            "SELECT id FROM user_memories WHERE archived_at IS NOT NULL AND archived_at < ?",
            (before_iso,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        for memory_id in ids:
            self._add_user_event(memory_id, "purged", f"Purged (before {before_iso})")
            self._conn.execute("DELETE FROM user_memory_vec WHERE memory_id = ?", (memory_id,))
            self._conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
        if ids:
            self._commit("purge_archived_user_memories")
            logger.info("purged %d archived user memories", len(ids))
        return len(ids)

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

    def _apply_migration_v2(self) -> None:
        rows = self._conn.execute("SELECT * FROM projects").fetchall()

        fingerprint_groups: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            fp = row["remote_fingerprint"]
            if fp:
                fingerprint_groups.setdefault(fp, []).append(row)

        remap: dict[int, int] = {}
        merged_paths: dict[int, list[str]] = {}
        for group in fingerprint_groups.values():
            if len(group) <= 1:
                continue
            group_sorted = sorted(group, key=lambda r: r["id"])
            primary_id = group_sorted[0]["id"]
            all_paths: set[str] = set()
            for r in group_sorted:
                all_paths.update(_parse_json_array(r["known_paths_json"]))
            merged_paths[primary_id] = sorted(all_paths)
            for r in group_sorted[1:]:
                remap[r["id"]] = primary_id

        insert_stmts: list[str] = []
        for row in rows:
            if row["id"] in remap:
                continue
            paths = merged_paths.get(row["id"])
            paths_json = json.dumps(paths) if paths is not None else (row["known_paths_json"] or "[]")
            insert_stmts.append(
                f"INSERT INTO projects_new "
                f"(id, root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at) "
                f"VALUES ({row['id']}, {_sql_str(row['root_path'])}, {_sql_str(row['name'])}, "
                f"{_sql_str(row['git_remote'])}, {_sql_str(row['remote_fingerprint'])}, "
                f"{_sql_str(paths_json)}, {_sql_str(row['created_at'])}, {_sql_str(row['updated_at'])});"
            )

        reparent_stmts: list[str] = []
        for secondary_id, primary_id in remap.items():
            reparent_stmts.append(
                f"UPDATE project_memories SET project_id = {primary_id} WHERE project_id = {secondary_id};"
            )
            reparent_stmts.append(
                f"UPDATE project_memory_events SET project_id = {primary_id} WHERE project_id = {secondary_id};"
            )

        now_str = _sql_str(_now())
        script_parts = [
            "PRAGMA foreign_keys = OFF;",
            "BEGIN;",
            "DROP TABLE IF EXISTS projects_new;",
            "CREATE TABLE projects_new (",
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,",
            "    root_path TEXT NOT NULL,",
            "    name TEXT NOT NULL,",
            "    git_remote TEXT,",
            "    remote_fingerprint TEXT,",
            "    known_paths_json TEXT NOT NULL DEFAULT '[]',",
            "    created_at TEXT NOT NULL,",
            "    updated_at TEXT NOT NULL",
            ");",
            *insert_stmts,
            *reparent_stmts,
            "DROP TABLE IF EXISTS projects;",
            "ALTER TABLE projects_new RENAME TO projects;",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_fingerprint_unique",
            "    ON projects(remote_fingerprint)",
            "    WHERE remote_fingerprint IS NOT NULL;",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_root_path_local",
            "    ON projects(root_path)",
            "    WHERE remote_fingerprint IS NULL;",
            f"INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (2, {now_str});",
            "COMMIT;",
            "PRAGMA foreign_keys = ON;",
        ]
        self._conn.executescript("\n".join(script_parts))
        logger.info("migration v2 applied: projects keyed by remote_fingerprint")

    def _migrate(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

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

            CREATE TABLE IF NOT EXISTS project_memories (
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

            CREATE INDEX IF NOT EXISTS idx_project_memories_project_active ON project_memories(project_id, archived_at);
            CREATE INDEX IF NOT EXISTS idx_project_memories_kind ON project_memories(kind);
            CREATE INDEX IF NOT EXISTS idx_project_memories_updated_at ON project_memories(updated_at);

            CREATE TABLE IF NOT EXISTS project_memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                memory_id INTEGER REFERENCES project_memories(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_project_memory_events_memory_id ON project_memory_events(memory_id);
            CREATE INDEX IF NOT EXISTS idx_project_memory_events_created_at ON project_memory_events(created_at);

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
            CREATE INDEX IF NOT EXISTS idx_user_memory_events_created_at ON user_memory_events(created_at);

        """)
        self._conn.executescript(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS project_memory_vec USING vec0(
                memory_id INTEGER PRIMARY KEY,
                embedding float[{EMBEDDING_DIM}]
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS user_memory_vec USING vec0(
                memory_id INTEGER PRIMARY KEY,
                embedding float[{EMBEDDING_DIM}]
            );
        """)
        applied = {r[0] for r in self._conn.execute("SELECT version FROM schema_migrations").fetchall()}
        if 2 not in applied:
            self._apply_migration_v2()


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


def _map_project_memory(row: sqlite3.Row) -> MemoryRecord:
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
