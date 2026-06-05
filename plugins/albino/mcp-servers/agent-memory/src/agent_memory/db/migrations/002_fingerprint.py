"""
Re-key projects by git remote fingerprint.

Drops the UNIQUE constraint on root_path, adds two partial unique indexes:
  - ON projects(remote_fingerprint) WHERE remote_fingerprint IS NOT NULL
  - ON projects(root_path) WHERE remote_fingerprint IS NULL

Also deduplicates any existing rows that share the same remote_fingerprint by
merging their known_paths and re-parenting memories/events to the surviving row.
"""

import json

from yoyo import step

__depends__ = {"001_initial"}
__transactional__ = False


def apply_step(conn):
    idx = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_projects_fingerprint_unique'"
    ).fetchone()
    if idx:
        return

    rows = conn.execute(
        "SELECT id, root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at"
        " FROM projects"
    ).fetchall()

    from collections import defaultdict

    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        fp = row[4]
        if fp:
            groups[fp].append(row)

    remap: dict[int, int] = {}
    merged_paths: dict[int, list[str]] = {}
    for group in groups.values():
        if len(group) <= 1:
            continue
        group_sorted = sorted(group, key=lambda r: r[0])
        primary_id = group_sorted[0][0]
        all_paths: set[str] = set()
        for r in group_sorted:
            try:
                all_paths.update(json.loads(r[5] or "[]"))
            except Exception:
                pass
        merged_paths[primary_id] = sorted(all_paths)
        for r in group_sorted[1:]:
            remap[r[0]] = primary_id

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    try:
        conn.execute("""
            CREATE TABLE projects_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_path TEXT NOT NULL,
                name TEXT NOT NULL,
                git_remote TEXT,
                remote_fingerprint TEXT,
                known_paths_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        for row in rows:
            if row[0] in remap:
                continue
            paths = merged_paths.get(row[0])
            paths_json = json.dumps(paths) if paths is not None else (row[5] or "[]")
            conn.execute(
                "INSERT INTO projects_new"
                " (id, root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row[0], row[1], row[2], row[3], row[4], paths_json, row[6], row[7]),
            )

        for secondary_id, primary_id in remap.items():
            conn.execute(
                "UPDATE project_memories SET project_id = ? WHERE project_id = ?",
                (primary_id, secondary_id),
            )
            conn.execute(
                "UPDATE project_memory_events SET project_id = ? WHERE project_id = ?",
                (primary_id, secondary_id),
            )

        conn.execute("DROP TABLE projects")
        conn.execute("ALTER TABLE projects_new RENAME TO projects")

        conn.execute("""
            CREATE UNIQUE INDEX idx_projects_fingerprint_unique
            ON projects(remote_fingerprint)
            WHERE remote_fingerprint IS NOT NULL
        """)
        conn.execute("""
            CREATE UNIQUE INDEX idx_projects_root_path_local
            ON projects(root_path)
            WHERE remote_fingerprint IS NULL
        """)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


steps = [step(apply_step)]
