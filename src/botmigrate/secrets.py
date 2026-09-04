"""Refuse to copy credentials, tokens, session DBs, and env files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from botmigrate.errors import SecretCopyError

SECRET_FILENAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "auth.json",
        "auth.lock",
        "store.db",
        "conversation-blobs.db",
        "audit.jsonl",
        "state.db",
        "state.db-shm",
        "state.db-wal",
        "hermes_state.db",
        "response_store.db",
        "response_store.db-shm",
        "response_store.db-wal",
        "gateway.pid",
        "gateway_state.json",
        "processes.json",
    }
)

SECRET_DIRNAMES = frozenset(
    {
        "sessions",
        "logs",
        "workspace",
        "plans",
        "home",
        "image_cache",
        "audio_cache",
        "document_cache",
        "browser_screenshots",
        "cache",
        "checkpoints",
        "sandboxes",
        "backups",
    }
)

_SECRET_KEY = re.compile(
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|"
    r"authorization|private[_-]?key|client[_-]?secret|credential|auth_token)",
    re.IGNORECASE,
)

_SECRET_VALUE = re.compile(
    r"^(sk-|ghp_|gho_|xox[baprs]-|Bearer\s+\S+|eyJ[A-Za-z0-9_-]{20,})",
)


def is_secret_filename(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in SECRET_FILENAMES
        or lowered.startswith(".env")
        or lowered.endswith((".db", ".db-shm", ".db-wal"))
    )


def is_secret_path(path: Path) -> bool:
    if is_secret_filename(path.name):
        return True
    return any(part.lower() in SECRET_DIRNAMES for part in path.parts)


def assert_src_not_secret_file(path: Path) -> None:
    if path.is_file() and is_secret_filename(path.name):
        raise SecretCopyError(str(path), f"secret or credential file {path.name!r}")


def strip_secrets(data: Any) -> Any:
    """Drop secret keys and secret-looking values from mappings/lists."""
    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if _SECRET_KEY.search(str(key)):
                continue
            cleaned[key] = strip_secrets(value)
        return cleaned
    if isinstance(data, list):
        return [strip_secrets(item) for item in data]
    if isinstance(data, str) and _SECRET_VALUE.search(data.strip()):
        return ""
    return data


def env_names_from_mapping(data: Any) -> list[str]:
    """Collect environment variable *names* (never values) from MCP-like configs."""
    names: list[str] = []
    if isinstance(data, dict):
        env = data.get("env")
        if isinstance(env, dict):
            names.extend(str(key) for key in env)
        for value in data.values():
            names.extend(env_names_from_mapping(value))
    elif isinstance(data, list):
        for item in data:
            names.extend(env_names_from_mapping(item))
    return names
