"""`.botmigrate.json` sidecar: extras written beside every output so a later
sync or round-trip can restore what the destination format cannot hold."""

from __future__ import annotations

from pathlib import Path

from botmigrate.io import output_dir, read_json, write_json
from botmigrate.ir.models import PortableBot, Sidecar

SIDECAR_NAME = ".botmigrate.json"


def sidecar_path(target: Path) -> Path:
    return output_dir(target) / SIDECAR_NAME


def load_sidecar(target: Path) -> Sidecar | None:
    path = target if target.name == SIDECAR_NAME else sidecar_path(target)
    if not path.is_file():
        return None
    raw = read_json(path)
    return Sidecar.model_validate(raw) if isinstance(raw, dict) else None


def write_sidecar(target: Path, bot: PortableBot, source_format: str) -> None:
    write_json(
        sidecar_path(target),
        Sidecar(source_format=source_format, extras=bot.extras).model_dump(),
    )
