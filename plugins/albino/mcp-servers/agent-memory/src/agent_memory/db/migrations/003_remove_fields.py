"""
Clean up legacy schema fields from project_memories and user_memories, and drop
the audit-event tables that are no longer used.

Removes from project_memories and user_memories:
  - kind, summary, why_useful_later, tags_json, confidence (metadata noise)
  - last_used_at, use_count (usage tracking not needed)

Drops entirely:
  - project_memory_events
  - user_memory_events

Fully idempotent: checks for column/table existence before acting, so it is
safe to run against both old databases (full legacy schema) and new ones
(already created without these columns/tables via the updated 001_initial.sql).
"""

from yoyo import step

__depends__ = {"002_fingerprint"}

_DROP_COLS = ("kind", "summary", "why_useful_later", "tags_json", "confidence", "last_used_at", "use_count")


def apply_step(conn):
    project_cols = {r[1] for r in conn.execute("PRAGMA table_info(project_memories)").fetchall()}

    if not project_cols & set(_DROP_COLS):
        return  # already clean

    conn.execute("DROP INDEX IF EXISTS idx_project_memories_kind")
    conn.execute("DROP INDEX IF EXISTS idx_user_memories_kind")
    conn.execute("DROP INDEX IF EXISTS idx_project_memory_events_memory_id")
    conn.execute("DROP INDEX IF EXISTS idx_project_memory_events_created_at")
    conn.execute("DROP INDEX IF EXISTS idx_user_memory_events_memory_id")
    conn.execute("DROP INDEX IF EXISTS idx_user_memory_events_created_at")

    user_cols = {r[1] for r in conn.execute("PRAGMA table_info(user_memories)").fetchall()}

    for col in _DROP_COLS:
        if col in project_cols:
            conn.execute(f"ALTER TABLE project_memories DROP COLUMN {col}")
        if col in user_cols:
            conn.execute(f"ALTER TABLE user_memories DROP COLUMN {col}")

    conn.execute("DROP TABLE IF EXISTS project_memory_events")
    conn.execute("DROP TABLE IF EXISTS user_memory_events")


steps = [step(apply_step)]
