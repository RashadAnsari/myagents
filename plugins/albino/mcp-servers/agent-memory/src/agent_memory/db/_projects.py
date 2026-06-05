import json
import sqlite3
import sys

from ..paths import project_name_from_root
from ..types import ProjectRecord
from ._utils import map_project, now_iso, parse_json_array


def _db():
    """Return the agent_memory.db package module (already in sys.modules).

    Accessing path helpers through the package lets test monkeypatches on
    agent_memory.db.<name> take effect without circular imports.
    """
    return sys.modules["agent_memory.db"]


class ProjectsMixin:
    _conn: sqlite3.Connection

    def get_or_create_project(self, project_root: str) -> ProjectRecord:
        db = _db()
        root_path = db.canonical_project_root(project_root)
        git_remote = db.get_git_remote(root_path)
        remote_fingerprint = db.fingerprint_remote(git_remote)
        now = now_iso()

        if remote_fingerprint:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE remote_fingerprint = ?", (remote_fingerprint,)
            ).fetchone()
            if row:
                project = map_project(row)
                if root_path not in project.known_paths:
                    with self._transaction():
                        self._conn.execute(
                            "UPDATE projects SET known_paths_json = ?, updated_at = ? WHERE id = ?",
                            (json.dumps(sorted({*project.known_paths, root_path})), now, project.id),
                        )
                    row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project.id,)).fetchone()
                return map_project(row)

            legacy = self._conn.execute(
                "SELECT * FROM projects WHERE root_path = ? AND remote_fingerprint IS NULL", (root_path,)
            ).fetchone()
            if legacy:
                paths = parse_json_array(legacy["known_paths_json"])
                if root_path not in paths:
                    paths.append(root_path)
                with self._transaction():
                    self._conn.execute(
                        "UPDATE projects SET git_remote = ?, remote_fingerprint = ?, known_paths_json = ?, updated_at = ? WHERE id = ?",
                        (git_remote, remote_fingerprint, json.dumps(sorted(set(paths))), now, legacy["id"]),
                    )
                row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (legacy["id"],)).fetchone()
                return map_project(row)
        else:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE root_path = ? AND remote_fingerprint IS NULL", (root_path,)
            ).fetchone()
            if row:
                return map_project(row)

        with self._transaction():
            self._conn.execute(
                "INSERT INTO projects"
                " (root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
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

        if remote_fingerprint:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE remote_fingerprint = ?", (remote_fingerprint,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE root_path = ? AND remote_fingerprint IS NULL", (root_path,)
            ).fetchone()
        return map_project(row)

    def get_project(self, project_root: str) -> ProjectRecord | None:
        db = _db()
        root_path = db.canonical_project_root(project_root)
        remote_fingerprint = db.fingerprint_remote(db.get_git_remote(root_path))
        if remote_fingerprint:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE remote_fingerprint = ?", (remote_fingerprint,)
            ).fetchone()
            if row:
                return map_project(row)
        row = self._conn.execute("SELECT * FROM projects WHERE root_path = ?", (root_path,)).fetchone()
        return map_project(row) if row else None
