import hashlib
import logging
import os
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def default_database_path() -> str:
    if memory_dir := os.environ.get("AGENT_MEMORY_DIR"):
        dir_path = Path(memory_dir).resolve()
        dir_path.mkdir(parents=True, exist_ok=True)
        return str(dir_path / "memory.sqlite")
    dir_path = Path.home() / ".myagents" / "agent-memory"
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path / "memory.sqlite")


def normalize_project_root(project_root: str) -> str:
    return str(Path(project_root).resolve())


def project_name_from_root(root_path: str) -> str:
    return Path(root_path).name or root_path


def get_git_root(root_path: str) -> str | None:
    if not Path(root_path).exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", root_path, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        git_root = result.stdout.strip()
        return str(Path(git_root).resolve()) if git_root else None
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("git root lookup failed for %s: %s", root_path, exc)
        return None


def canonical_project_root(project_root: str) -> str:
    """Return the git repo root for any path inside a repo. Raises ValueError if the path is not inside a git repo."""
    normalized = normalize_project_root(project_root)
    git_root = get_git_root(normalized)
    if git_root is None:
        raise ValueError(
            f"Project root is not a git repository: {normalized}. Only git repositories can have project memory."
        )
    return git_root


def get_git_remote(root_path: str) -> str | None:
    if not Path(root_path).exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", root_path, "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
        )
        remote = result.stdout.strip()
        return _normalize_git_remote(remote) if remote else None
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("git remote lookup failed for %s: %s", root_path, exc)
        return None


def _normalize_git_remote(remote: str) -> str:
    normalized = remote.strip()
    normalized = re.sub(r"^https?://([^/@]+@)?", "https://", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^git@([^:]+):", r"https://\1/", normalized)
    normalized = re.sub(r"\.git$", "", normalized, flags=re.IGNORECASE)
    return normalized.lower()


def fingerprint_remote(remote: str | None) -> str | None:
    if not remote:
        return None
    return hashlib.sha256(remote.encode()).hexdigest()
