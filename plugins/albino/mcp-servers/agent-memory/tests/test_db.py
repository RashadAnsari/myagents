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
    assert {"projects", "project_memories", "user_memories"}.issubset(tables)


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
        content="Use postgres for all persistent storage to keep infrastructure simple.",
        source="test",
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    assert memory.id > 0
    assert memory.source == "test"

    fetched = bare_store.get_project_memory(memory.id)
    assert fetched is not None
    assert fetched.id == memory.id
    assert fetched.content == memory.content


def test_list_active_memories_excludes_archived(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    m1 = bare_store.create_project_memory(
        project_id=project.id,
        content="Active memory that should appear in active listing for this project.",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    m2 = bare_store.create_project_memory(
        project_id=project.id,
        content="Archived memory that should not appear in active listing after archival.",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    bare_store.archive_project_memory(m2.id)

    active = bare_store.list_active_project_memories(project.id)
    ids = [m.id for m in active]
    assert m1.id in ids
    assert m2.id not in ids


def test_update_memory_content(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        content="Original content about using snake_case for all Python identifiers.",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    updated = bare_store.update_project_memory(
        memory_id=memory.id,
        content="Updated content about using snake_case for all Python identifiers and module names.",
        archived_at=None,
    )
    assert "module names" in updated.content


def test_update_memory_preserves_source(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        content="Use snake_case for all Python identifiers including functions and variables.",
        source="test",
        source_ref="some-ref",
        vector=_DUMMY_VECTOR,
    )
    updated = bare_store.update_project_memory(
        memory_id=memory.id,
        content=None,
        archived_at=None,
    )
    assert updated.source == "test"
    assert updated.source_ref == "some-ref"


def test_archive_memory(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        content="Avoid using mutable default arguments in Python function definitions.",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    archived = bare_store.archive_project_memory(memory.id)
    assert archived.archived_at is not None

    active = bare_store.list_active_project_memories(project.id)
    assert all(m.id != memory.id for m in active)


def test_hard_delete_memory_removes_row(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_project_memory(
        project_id=project.id,
        content="Hard delete test memory that must be fully removed from the database.",
        source=None,
        source_ref=None,
        vector=_DUMMY_VECTOR,
    )
    memory_id = memory.id
    bare_store.hard_delete_project_memory(memory_id, project.id)

    assert bare_store.get_project_memory(memory_id) is None
    vec_row = bare_store._conn.execute("SELECT * FROM project_memory_vec WHERE memory_id = ?", (memory_id,)).fetchone()
    assert vec_row is None


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

    agent_store = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    proj_a = agent_store.get_or_create_project(str(path_a))
    proj_b = agent_store.get_or_create_project(str(path_b))
    agent_store.close()

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

    agent_store = AgentMemoryStore(str(tmp_path / "memory.sqlite"))
    agent_store.get_or_create_project(str(path_a))
    proj = agent_store.get_or_create_project(str(path_b))
    agent_store.close()

    assert str(path_a.resolve()) in proj.known_paths
    assert str(path_b.resolve()) in proj.known_paths


def test_migration_v2_merges_duplicate_projects(tmp_path):
    """A v1 database with two rows sharing a fingerprint is merged by migration v2."""
    db_path = str(tmp_path / "memory.sqlite")

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
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

    agent_store = AgentMemoryStore(db_path)

    project_rows = agent_store._conn.execute("SELECT * FROM projects").fetchall()
    assert len(project_rows) == 1
    surviving_id = project_rows[0]["id"]

    mem_rows = agent_store._conn.execute(
        "SELECT id FROM project_memories WHERE project_id = ?", (surviving_id,)
    ).fetchall()
    assert len(mem_rows) == 2

    paths = json.loads(project_rows[0]["known_paths_json"])
    assert "/home/alice/myapp" in paths
    assert "/home/bob/myapp" in paths

    agent_store.close()


def test_legacy_v2_database_bootstraps_without_remigration(tmp_path):
    """A post-v2 old-code database is bootstrapped: both migrations marked applied, data preserved."""
    db_path = str(tmp_path / "memory.sqlite")

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            root_path TEXT NOT NULL,
            name TEXT NOT NULL,
            git_remote TEXT,
            remote_fingerprint TEXT,
            known_paths_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_projects_fingerprint_unique
            ON projects(remote_fingerprint)
            WHERE remote_fingerprint IS NOT NULL;
        CREATE UNIQUE INDEX idx_projects_root_path_local
            ON projects(root_path)
            WHERE remote_fingerprint IS NULL;
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
    conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (2, ?)", (now,))
    conn.execute(
        "INSERT INTO projects (root_path, name, git_remote, remote_fingerprint, known_paths_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        ("/home/alice/myapp", "myapp", "https://github.com/org/myapp", "fp1", '["/home/alice/myapp"]', now, now),
    )
    conn.execute(
        "INSERT INTO project_memories (project_id, kind, content, why_useful_later, tags_json, confidence, created_at, updated_at, use_count) VALUES (1,'decision','Preserved memory.','Test.','[]','high',?,?,0)",
        (now, now),
    )
    conn.commit()
    conn.close()

    agent_store = AgentMemoryStore(db_path)

    project_rows = agent_store._conn.execute("SELECT * FROM projects").fetchall()
    assert len(project_rows) == 1
    assert project_rows[0]["root_path"] == "/home/alice/myapp"

    mem_rows = agent_store._conn.execute("SELECT content FROM project_memories WHERE project_id = 1").fetchall()
    assert len(mem_rows) == 1
    assert mem_rows[0]["content"] == "Preserved memory."

    applied = {r[0] for r in agent_store._conn.execute("SELECT migration_id FROM _yoyo_migration").fetchall()}
    assert "001_initial" in applied
    assert "002_fingerprint" in applied

    agent_store.close()
