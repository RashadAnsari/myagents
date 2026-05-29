import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from agent_memory.db import AgentMemoryStore
from agent_memory.embedding import EMBEDDING_DIM

_DUMMY_VECTOR = [0.0] * EMBEDDING_DIM


@pytest.fixture
def bare_store(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=False)
    s = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    yield s
    s.close()


def test_store_initializes_schema(bare_store):
    tables = {
        row[0] for row in bare_store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"projects", "project_memories", "project_memory_events", "user_memories", "user_memory_events"}.issubset(
        tables
    )


def test_migrate_is_idempotent(tmp_path):
    path = str(tmp_path / "memory.sqlite")
    s1 = AgentMemoryStore(path)
    s1.close()
    s2 = AgentMemoryStore(path)
    s2.close()


def test_foreign_keys_enabled(bare_store):
    result = bare_store._conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1


def test_get_or_create_project_creates_new(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    assert project.id > 0
    assert project.root_path == str(tmp_path)


def test_get_or_create_project_is_idempotent(bare_store, tmp_path):
    p1 = bare_store.get_or_create_project(str(tmp_path))
    p2 = bare_store.get_or_create_project(str(tmp_path))
    assert p1.id == p2.id


def test_create_and_get_memory(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        kind="decision",
        content="Use postgres for all persistent storage to keep infrastructure simple.",
        summary="Postgres for storage",
        why_useful_later="Avoids adding Redis/Mongo to the stack.",
        tags=["database", "infrastructure"],
        confidence="high",
        source="test",
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    assert memory.id > 0
    assert memory.kind == "decision"
    assert memory.tags == ["database", "infrastructure"]

    fetched = bare_store.get_project_memory(memory.id)
    assert fetched is not None
    assert fetched.id == memory.id
    assert fetched.content == memory.content


def test_list_active_memories_excludes_archived(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    m1 = bare_store.create_project_memory(
        project_id=project.id,
        kind="decision",
        content="Active memory that should appear in active listing for this project.",
        summary=None,
        why_useful_later="Test.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    m2 = bare_store.create_project_memory(
        project_id=project.id,
        kind="gotcha",
        content="Archived memory that should not appear in active listing after archival.",
        summary=None,
        why_useful_later="Test.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    bare_store.archive_project_memory(m2.id, "test archive")

    active = bare_store.list_active_project_memories(project.id)
    ids = [m.id for m in active]
    assert m1.id in ids
    assert m2.id not in ids


def test_update_memory(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        kind="convention",
        content="Use snake_case for all Python identifiers including functions and variables.",
        summary=None,
        why_useful_later="Consistency.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    updated = bare_store.update_project_memory(
        memory_id=memory.id,
        content=None,
        summary="snake_case convention",
        why_useful_later=None,
        tags=["style"],
        confidence="high",
        archived_at=None,
        reason="added tag",
    )
    assert updated.summary == "snake_case convention"
    assert updated.confidence == "high"
    assert "style" in updated.tags


def test_update_memory_content_only(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        kind="convention",
        content="Original content about using snake_case for all Python identifiers.",
        summary="original summary",
        why_useful_later="Consistency across codebase.",
        tags=["style"],
        confidence="medium",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    updated = bare_store.update_project_memory(
        memory_id=memory.id,
        content="Updated content about using snake_case for all Python identifiers and module names.",
        summary=None,
        why_useful_later=None,
        tags=None,
        confidence=None,
        archived_at=None,
        reason="clarified scope",
    )
    assert "module names" in updated.content
    assert updated.summary == "original summary"
    assert updated.tags == ["style"]
    assert updated.confidence == "medium"


def test_update_memory_why_only(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        kind="gotcha",
        content="SQLite WAL mode must be enabled before foreign keys to avoid lock contention.",
        summary=None,
        why_useful_later="Original rationale that needs improvement.",
        tags=[],
        confidence="low",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    updated = bare_store.update_project_memory(
        memory_id=memory.id,
        content=None,
        summary=None,
        why_useful_later="Future agents need this ordering rule to avoid locking failures during SQLite initialization.",
        tags=None,
        confidence=None,
        archived_at=None,
        reason="improved rationale",
    )
    assert "locking failures" in updated.why_useful_later
    assert updated.confidence == "low"
    assert "WAL mode" in updated.content


def test_archive_memory(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        kind="gotcha",
        content="Avoid using mutable default arguments in Python function definitions.",
        summary=None,
        why_useful_later="Classic Python gotcha.",
        tags=[],
        confidence="high",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    archived = bare_store.archive_project_memory(memory.id, "no longer relevant")
    assert archived.archived_at is not None

    active = bare_store.list_active_project_memories(project.id)
    assert all(m.id != memory.id for m in active)


def test_hard_delete_memory_removes_row(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        kind="decision",
        content="Hard delete test memory that must be fully removed from the database.",
        summary=None,
        why_useful_later="Testing hard delete.",
        tags=[],
        confidence="low",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    memory_id = memory.id
    bare_store.hard_delete_project_memory(memory_id, "test deletion", project.id)

    assert bare_store.get_project_memory(memory_id) is None
    vec_row = bare_store._conn.execute("SELECT * FROM project_memory_vec WHERE memory_id = ?", (memory_id,)).fetchone()
    assert vec_row is None


def test_hard_delete_keeps_audit_event(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        kind="decision",
        content="Audit trail test memory verifying hard delete events are preserved.",
        summary=None,
        why_useful_later="Audit test.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    memory_id = memory.id
    bare_store.hard_delete_project_memory(memory_id, "audit test", project.id)

    events = bare_store._conn.execute(
        "SELECT action FROM project_memory_events WHERE action = 'hard_deleted' AND project_id = ?",
        (project.id,),
    ).fetchall()
    assert len(events) >= 1


def test_cross_device_same_remote_shares_project(tmp_path, monkeypatch):
    """Two clones at different paths with the same git remote return the same project_id."""
    import agent_memory.db as db_module

    path_a = tmp_path / "clone_a"
    path_b = tmp_path / "clone_b"
    path_a.mkdir()
    path_b.mkdir()
    for p in (path_a, path_b):
        subprocess.run(["git", "init"], cwd=str(p), capture_output=True, check=False)

    monkeypatch.setattr(db_module, "get_git_remote", lambda _: "https://github.com/org/myapp")
    monkeypatch.setattr(db_module, "fingerprint_remote", lambda r: "abc123" if r else None)
    monkeypatch.setattr(db_module, "canonical_project_root", lambda p: str(Path(p).resolve()))

    store = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    proj_a = store.get_or_create_project(str(path_a))
    proj_b = store.get_or_create_project(str(path_b))
    store.close()

    assert proj_a.id == proj_b.id


def test_cross_device_updates_known_paths(tmp_path, monkeypatch):
    """The second device's root_path is added to known_paths on first lookup."""
    import agent_memory.db as db_module

    path_a = tmp_path / "clone_a"
    path_b = tmp_path / "clone_b"
    path_a.mkdir()
    path_b.mkdir()
    for p in (path_a, path_b):
        subprocess.run(["git", "init"], cwd=str(p), capture_output=True, check=False)

    monkeypatch.setattr(db_module, "get_git_remote", lambda _: "https://github.com/org/myapp")
    monkeypatch.setattr(db_module, "fingerprint_remote", lambda r: "abc123" if r else None)
    monkeypatch.setattr(db_module, "canonical_project_root", lambda p: str(Path(p).resolve()))

    store = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    store.get_or_create_project(str(path_a))
    proj = store.get_or_create_project(str(path_b))
    store.close()

    assert str(path_a.resolve()) in proj.known_paths
    assert str(path_b.resolve()) in proj.known_paths


def test_migration_v2_merges_duplicate_projects(tmp_path):
    """A v1 database with two rows sharing a fingerprint is merged by migration v2."""
    db_path = str(tmp_path / "memory.sqlite")

    # Build a v1-style database manually (root_path UNIQUE, no schema_migrations).
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            root_path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            git_remote TEXT,
            remote_fingerprint TEXT,
            known_paths_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE project_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            why_useful_later TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            confidence TEXT NOT NULL DEFAULT 'medium',
            source TEXT,
            source_ref TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used_at TEXT,
            use_count INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT
        );
        CREATE TABLE project_memory_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            memory_id INTEGER,
            action TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            why_useful_later TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            confidence TEXT NOT NULL DEFAULT 'medium',
            source TEXT,
            source_ref TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used_at TEXT,
            use_count INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT
        );
        CREATE TABLE user_memory_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id INTEGER,
            action TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL
        );
    """)
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        "INSERT INTO projects (root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        ("/home/alice/myapp", "myapp", "https://github.com/org/myapp", "abc123", '["/home/alice/myapp"]', now, now),
    )
    conn.execute(
        "INSERT INTO projects (root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        ("/home/bob/myapp", "myapp", "https://github.com/org/myapp", "abc123", '["/home/bob/myapp"]', now, now),
    )
    conn.execute(
        "INSERT INTO project_memories (project_id, kind, content, why_useful_later, tags_json, confidence, created_at, updated_at, use_count) VALUES (1,'decision','Memory from Alice device.','Test.','[]','high',?,?,0)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO project_memories (project_id, kind, content, why_useful_later, tags_json, confidence, created_at, updated_at, use_count) VALUES (2,'convention','Memory from Bob device.','Test.','[]','medium',?,?,0)",
        (now, now),
    )
    conn.commit()
    conn.close()

    store = AgentMemoryStore(db_path)

    project_rows = store._conn.execute("SELECT * FROM projects").fetchall()
    assert len(project_rows) == 1
    surviving_id = project_rows[0]["id"]

    mem_rows = store._conn.execute("SELECT id FROM project_memories WHERE project_id = ?", (surviving_id,)).fetchall()
    assert len(mem_rows) == 2

    paths = json.loads(project_rows[0]["known_paths_json"])
    assert "/home/alice/myapp" in paths
    assert "/home/bob/myapp" in paths

    store.close()
