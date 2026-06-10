import json
import logging
import sqlite3
import struct
from datetime import UTC, datetime

from ..types import (
    ProjectMemoryRecord,
    ProjectRecord,
    UserMemoryRecord,
)

logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def parse_json_array(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
        return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []
    except Exception as exc:
        logger.warning("failed to parse JSON array (%s): %r", exc, value)
        return []


def map_project(row: sqlite3.Row) -> ProjectRecord:
    return ProjectRecord(
        id=row["id"],
        root_path=row["root_path"],
        name=row["name"],
        git_remote=row["git_remote"],
        remote_fingerprint=row["remote_fingerprint"],
        known_paths=parse_json_array(row["known_paths_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def map_project_memory(row: sqlite3.Row) -> ProjectMemoryRecord:
    return ProjectMemoryRecord(
        id=row["id"],
        project_id=row["project_id"],
        content=row["content"],
        source=row["source"],
        source_ref=row["source_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
    )


def map_user_memory(row: sqlite3.Row) -> UserMemoryRecord:
    return UserMemoryRecord(
        id=row["id"],
        content=row["content"],
        source=row["source"],
        source_ref=row["source_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
    )
