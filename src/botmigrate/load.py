"""Load a path into the portable IR."""

from __future__ import annotations

from pathlib import Path

from botmigrate.detect import detect_platform
from botmigrate.formats import FormatKind, is_grok
from botmigrate.grok.read import read_grok
from botmigrate.hermes.read import read_hermes
from botmigrate.ir.models import PortableBot
from botmigrate.ir.restore import restore_from_extras


def load_bot(
    path: Path,
    platform: str | None,
    *,
    include_memories: bool,
    skills_dir: Path | None = None,
) -> tuple[PortableBot, FormatKind]:
    kind = detect_platform(path, platform)
    if is_grok(kind):
        bot = read_grok(path, skills_dir=skills_dir)
    else:
        bot = read_hermes(path, include_memories=include_memories)
    return restore_from_extras(bot), kind
