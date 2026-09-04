"""Detect a path's format and load it into the portable IR."""

from __future__ import annotations

from pathlib import Path

from botmigrate import platforms
from botmigrate.formats import FormatKind
from botmigrate.ir.models import PortableBot
from botmigrate.ir.restore import restore_from_extras
from botmigrate.platforms import detect

__all__ = ["detect", "load_bot"]


def load_bot(
    path: Path,
    platform: str | None = None,
    *,
    memories: bool = True,
    skills_dir: Path | None = None,
) -> tuple[PortableBot, FormatKind]:
    """Read any supported format. `platform` asserts the source ("grok" / "hermes")."""
    kind = detect(path, platform)
    bot = platforms.adapter_for(kind).read(path, skills_dir=skills_dir)
    if not memories:
        bot = bot.without_memories()
    return restore_from_extras(bot), kind
