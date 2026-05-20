import hashlib
import os
import re
import subprocess
from pathlib import Path


def default_database_path() -> str:
    if memory_dir := os.environ.get("MYAGENTS_MEMORY_DIR"):
        dir_path = Path(memory_dir).resolve()
        dir_path.mkdir(parents=True, exist_ok=True)
        return str(dir_path / "memory.sqlite")
    dir_path = Path.home() / ".myagents" / "project-memory"
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path / "memory.sqlite")


def normalize_project_root(project_root: str) -> str:
    return str(Path(project_root).resolve())


def current_project_root() -> str:
    return normalize_project_root(
        os.environ.get("MYAGENTS_PROJECT_ROOT") or os.environ.get("INIT_CWD") or os.environ.get("PWD") or os.getcwd()
    )


def project_name_from_root(root_path: str) -> str:
    return Path(root_path).name or root_path


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
    except (subprocess.SubprocessError, OSError):
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
