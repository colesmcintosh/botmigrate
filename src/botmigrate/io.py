"""Deterministic JSON/YAML and text reads and writes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(read_text(path)) or {}


def write_yaml(path: Path, data: Any) -> None:
    write_text(
        path,
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
    )


def output_dir(target: Path) -> Path:
    """Directory that holds side files (MIGRATION.md, .botmigrate.json) for an output.

    A `.json` target is a single share file, so its parent directory is used.
    """
    if target.suffix.lower() == ".json" or target.is_file():
        return target.parent
    return target


def list_names(path: Path, limit: int = 16) -> str:
    """Short, human-readable listing of a directory for error messages."""
    names = sorted(p.name for p in path.iterdir())[:limit]
    return ", ".join(names) if names else "an empty directory"
