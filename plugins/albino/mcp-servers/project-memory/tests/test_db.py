import pytest

from project_memory.db import ProjectMemoryStore


@pytest.fixture
def bare_store(tmp_path):
    """Store fixture that does NOT skip when sqlite-vec is unavailable."""
    s = ProjectMemoryStore(str(tmp_path / "memory.sqlite"))
    yield s
    s.close()


def test_store_initializes_schema(bare_store):
    tables = {
        row[0] for row in bare_store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"projects", "memories", "memory_events", "user_memories", "user_memory_events"}.issubset(tables)


def test_migrate_is_idempotent(tmp_path):
    path = str(tmp_path / "memory.sqlite")
    s1 = ProjectMemoryStore(path)
    s1.close()
    s2 = ProjectMemoryStore(path)
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
    memory = bare_store.create_memory(
        project_id=project.id,
        kind="decision",
        content="Use postgres for all persistent storage to keep infrastructure simple.",
        summary="Postgres for storage",
        why_useful_later="Avoids adding Redis/Mongo to the stack.",
        tags=["database", "infrastructure"],
        confidence="high",
        source="test",
        source_ref=None,
    )
    assert memory.id > 0
    assert memory.kind == "decision"
    assert memory.tags == ["database", "infrastructure"]

    fetched = bare_store.get_memory(memory.id)
    assert fetched is not None
    assert fetched.id == memory.id
    assert fetched.content == memory.content


def test_list_active_memories_excludes_archived(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    m1 = bare_store.create_memory(
        project_id=project.id,
        kind="decision",
        content="Active memory that should appear in active listing for this project.",
        summary=None,
        why_useful_later="Test.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
    )
    m2 = bare_store.create_memory(
        project_id=project.id,
        kind="gotcha",
        content="Archived memory that should not appear in active listing after archival.",
        summary=None,
        why_useful_later="Test.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
    )
    bare_store.archive_memory(m2.id, "test archive")

    active = bare_store.list_active_memories(project.id)
    ids = [m.id for m in active]
    assert m1.id in ids
    assert m2.id not in ids


def test_update_memory(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_memory(
        project_id=project.id,
        kind="convention",
        content="Use snake_case for all Python identifiers including functions and variables.",
        summary=None,
        why_useful_later="Consistency.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
    )
    updated = bare_store.update_memory(
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
    memory = bare_store.create_memory(
        project_id=project.id,
        kind="convention",
        content="Original content about using snake_case for all Python identifiers.",
        summary="original summary",
        why_useful_later="Consistency across codebase.",
        tags=["style"],
        confidence="medium",
        source=None,
        source_ref=None,
    )
    updated = bare_store.update_memory(
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
    memory = bare_store.create_memory(
        project_id=project.id,
        kind="gotcha",
        content="SQLite WAL mode must be enabled before foreign keys to avoid lock contention.",
        summary=None,
        why_useful_later="Original rationale that needs improvement.",
        tags=[],
        confidence="low",
        source=None,
        source_ref=None,
    )
    updated = bare_store.update_memory(
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
    memory = bare_store.create_memory(
        project_id=project.id,
        kind="gotcha",
        content="Avoid using mutable default arguments in Python function definitions.",
        summary=None,
        why_useful_later="Classic Python gotcha.",
        tags=[],
        confidence="high",
        source=None,
        source_ref=None,
    )
    archived = bare_store.archive_memory(memory.id, "no longer relevant")
    assert archived.archived_at is not None

    active = bare_store.list_active_memories(project.id)
    assert all(m.id != memory.id for m in active)


def test_hard_delete_memory_removes_row(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_memory(
        project_id=project.id,
        kind="decision",
        content="Hard delete test memory that must be fully removed from the database.",
        summary=None,
        why_useful_later="Testing hard delete.",
        tags=[],
        confidence="low",
        source=None,
        source_ref=None,
    )
    memory_id = memory.id
    bare_store.hard_delete_memory(memory_id, "test deletion", project.id)

    assert bare_store.get_memory(memory_id) is None
    vec_row = (
        bare_store._conn.execute("SELECT * FROM memory_vec WHERE memory_id = ?", (memory_id,)).fetchone()
        if bare_store._vec_available
        else None
    )
    assert vec_row is None


def test_hard_delete_keeps_audit_event(bare_store, tmp_path):
    project = bare_store.get_or_create_project(str(tmp_path))
    memory = bare_store.create_memory(
        project_id=project.id,
        kind="decision",
        content="Audit trail test memory verifying hard delete events are preserved.",
        summary=None,
        why_useful_later="Audit test.",
        tags=[],
        confidence="medium",
        source=None,
        source_ref=None,
    )
    memory_id = memory.id
    bare_store.hard_delete_memory(memory_id, "audit test", project.id)

    events = bare_store._conn.execute(
        "SELECT action FROM memory_events WHERE action = 'hard_deleted' AND project_id = ?",
        (project.id,),
    ).fetchall()
    assert len(events) >= 1


def test_search_returns_empty_when_vec_unavailable(bare_store):
    bare_store._vec_available = False
    results = bare_store.search_memories(
        project_id=1,
        query_vector=b"\x00" * 4,
        limit=5,
    )
    assert results == []


def test_upsert_embedding_noop_when_vec_unavailable(bare_store):
    bare_store._vec_available = False
    bare_store.upsert_embedding(999, [0.1, 0.2, 0.3])
