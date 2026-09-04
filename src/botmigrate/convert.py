"""One-shot convert: read the source into the IR, write the destination."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from botmigrate import platforms
from botmigrate.formats import FormatKind
from botmigrate.ir.models import PortableBot
from botmigrate.ir.restore import snapshot_extras
from botmigrate.load import load_bot
from botmigrate.report import write_migration_md


@dataclass(frozen=True)
class ConvertResult:
    bot: PortableBot
    source_kind: FormatKind
    dest_kind: FormatKind
    out: Path
    memories: bool


def convert(
    src: Path,
    out: Path,
    *,
    to: str | None = None,
    from_: str | None = None,
    layout: str | None = None,
    memories: bool | None = None,
    skills_dir: Path | None = None,
) -> ConvertResult:
    """Convert `src` and write it to `out`.

    `to` defaults to the other platform. `memories=None` uses the destination
    format's default (excluded only for a shareable Hermes distribution).
    """
    bot, source_kind = load_bot(src, from_, skills_dir=skills_dir)
    dest_kind = platforms.target_kind(out, source_kind=source_kind, to=to, layout=layout)
    include = platforms.writes_memories_by_default(dest_kind) if memories is None else memories
    bot = snapshot_extras(bot if include else bot.without_memories())
    write_bot(bot, out, dest_kind, include_memories=include)
    write_migration_md(
        out, bot, source_kind=source_kind, dest_kind=dest_kind, include_memories=include
    )
    return ConvertResult(bot, source_kind, dest_kind, out, include)


def write_bot(
    bot: PortableBot, out: Path, dest_kind: FormatKind, *, include_memories: bool
) -> None:
    platforms.adapter_for(dest_kind).write(bot, out, dest_kind, include_memories=include_memories)
