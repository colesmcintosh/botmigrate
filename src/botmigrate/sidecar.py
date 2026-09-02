"""`.botmigrate.json` sidecar for extras / round-trip metadata."""

from __future__ import annotations

from pathlib import Path

from botmigrate.io import read_json, write_json
from botmigrate.ir.models import PortableBot, Sidecar

SIDECAR_NAME = ".botmigrate.json"


def sidecar_path(target: Path) -> Path:
    if target.is_file() or target.suffix == ".json":
        return target.parent / SIDECAR_NAME
    return target / SIDECAR_NAME


def load_sidecar(target: Path) -> Sidecar | None:
    path = target if target.name == SIDECAR_NAME else sidecar_path(target)
    if not path.is_file():
        return None
    raw = read_json(path)
    if not isinstance(raw, dict):
        return None
    return Sidecar.model_validate(raw)


def write_sidecar(target: Path, bot: PortableBot, source_format: str) -> None:
    write_json(
        sidecar_path(target),
        Sidecar(source_format=source_format, extras=bot.extras).model_dump(),
    )
