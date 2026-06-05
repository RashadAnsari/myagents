import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import sqlite_vec
import yoyo

from ..embedding import EMBEDDING_DIM
from ._project_memories import ProjectMemoriesMixin
from ._projects import ProjectsMixin
from ._user_memories import UserMemoriesMixin
from ._utils import pack_vector

# Python 3.12 deprecated the built-in sqlite3 datetime adapter. Yoyo triggers it
# when logging migration timestamps. Registering an explicit adapter fixes the root cause.
sqlite3.register_adapter(datetime, lambda d: d.isoformat())

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class AgentMemoryStore(ProjectsMixin, ProjectMemoriesMixin, UserMemoriesMixin):
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._apply_migrations(db_path)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA journal_size_limit = 67108864;")
            self._conn.execute("PRAGMA wal_autocheckpoint = 1000;")
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._ensure_vec_tables()
        except Exception as exc:
            logger.error("database initialization failed for %s: %s", db_path, exc)
            raise

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _transaction(self):
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _write_embedding(self, table: str, memory_id: int, vector: list[float]) -> None:
        self._conn.execute(f"DELETE FROM {table} WHERE memory_id = ?", (memory_id,))
        self._conn.execute(
            f"INSERT INTO {table} (memory_id, embedding) VALUES (?, ?)",
            (memory_id, pack_vector(vector)),
        )

    def _apply_migrations(self, db_path: str) -> None:
        uri = f"sqlite:///{db_path}"
        backend = yoyo.get_backend(uri)
        migrations = yoyo.read_migrations(str(_MIGRATIONS_DIR))

        # Bootstrap: if this is a pre-yoyo database (has tables but no yoyo tracking),
        # mark the migrations that were already applied so yoyo doesn't re-run them.
        pending = backend.to_apply(migrations)
        if pending:
            already_applied = self._legacy_applied_ids(db_path)
            if already_applied:
                to_mark = [m for m in pending if m.id in already_applied]
                if to_mark:
                    backend.mark_migrations(to_mark)
                    pending = backend.to_apply(migrations)

        with backend.lock():
            backend.apply_migrations(pending)

    def _legacy_applied_ids(self, db_path: str) -> set[str]:
        """Return migration IDs already applied in a pre-yoyo database.

        Uses the schema_migrations table that the old hand-rolled system maintained,
        which is the authoritative record of what was applied before yoyo took over.
        """
        try:
            conn = sqlite3.connect(db_path)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            conn.close()
        except Exception:
            return set()

        if "projects" not in tables:
            return set()

        applied = {"001_initial"}

        if "schema_migrations" in tables:
            try:
                conn = sqlite3.connect(db_path)
                row = conn.execute("SELECT 1 FROM schema_migrations WHERE version = 2").fetchone()
                conn.close()
                if row:
                    applied.add("002_fingerprint")
            except Exception:
                pass

        return applied

    def _ensure_vec_tables(self) -> None:
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
