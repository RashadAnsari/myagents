-- depends:

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
