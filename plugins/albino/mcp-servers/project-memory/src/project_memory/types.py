from dataclasses import dataclass
from typing import Literal, get_args

MemoryKind = Literal[
    "decision",
    "convention",
    "architecture",
    "workflow",
    "preference",
    "gotcha",
    "bug",
    "dependency",
    "testing",
    "handoff",
]
MEMORY_KINDS: list[str] = list(get_args(MemoryKind))

Confidence = Literal["low", "medium", "high"]
CONFIDENCE_VALUES: list[str] = list(get_args(Confidence))

UserMemoryKind = Literal[
    "preference",
    "behavior",
    "context",
    "workflow",
    "convention",
    "tool_preference",
    "communication",
]
USER_MEMORY_KINDS: list[str] = list(get_args(UserMemoryKind))


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
class MemoryRecord:
    id: int
    project_id: int
    kind: MemoryKind
    content: str
    summary: str | None
    why_useful_later: str
    tags: list[str]
    confidence: Confidence
    source: str | None
    source_ref: str | None
    created_at: str
    updated_at: str
    last_used_at: str | None
    use_count: int
    archived_at: str | None


@dataclass
class UserMemoryRecord:
    id: int
    kind: UserMemoryKind
    content: str
    summary: str | None
    why_useful_later: str
    tags: list[str]
    confidence: Confidence
    source: str | None
    source_ref: str | None
    created_at: str
    updated_at: str
    last_used_at: str | None
    use_count: int
    archived_at: str | None
