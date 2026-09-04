"""Grok Bot: share JSON (interchange) or an on-disk agent directory."""

from __future__ import annotations

from pathlib import Path

from botmigrate.formats import FormatKind
from botmigrate.platforms.base import Adapter
from botmigrate.platforms.grok.read import detect, read
from botmigrate.platforms.grok.write import write_directory, write_share


def default_kind(out: Path) -> FormatKind:
    return FormatKind.grok_share if out.suffix.lower() == ".json" else FormatKind.grok_directory


ADAPTER = Adapter(
    name="grok",
    detect=detect,
    read=read,
    writers={FormatKind.grok_share: write_share, FormatKind.grok_directory: write_directory},
    layouts={"share": FormatKind.grok_share, "directory": FormatKind.grok_directory},
    default_kind=default_kind,
    readable=(FormatKind.grok_share, FormatKind.grok_directory),
)

__all__ = ["ADAPTER", "read", "write_directory", "write_share"]
