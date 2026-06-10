from dataclasses import dataclass


@dataclass
class ProjectRecord:
    id: int
    root_path: str
    name: str
    git_remote: str | None
    remote_fingerprint: str | None
    known_paths: list[str]
    created_at: str
    updated_at: str


@dataclass
class ProjectMemoryRecord:
    id: int
    project_id: int
    content: str
    source: str | None
    source_ref: str | None
    created_at: str
    updated_at: str
    archived_at: str | None


@dataclass
class UserMemoryRecord:
    id: int
    content: str
    source: str | None
    source_ref: str | None
    created_at: str
    updated_at: str
    archived_at: str | None
