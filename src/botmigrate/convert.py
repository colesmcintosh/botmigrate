"""One-shot convert: read source IR, write destination files."""

from __future__ import annotations

from pathlib import Path

from botmigrate.errors import UsageError
from botmigrate.formats import FormatKind
from botmigrate.grok.write import write_grok_directory, write_grok_share
from botmigrate.hermes.write import write_hermes_distribution, write_hermes_profile
from botmigrate.ir.models import PortableBot
from botmigrate.ir.restore import restore_from_extras, snapshot_extras
from botmigrate.load import load_bot
from botmigrate.report import write_migration_md


def resolve_include_memories(
    *,
    dest_kind: FormatKind,
    include: bool,
    exclude: bool,
    command: str,
) -> bool:
    if include and exclude:
        raise UsageError("use only one of --include-memories / --exclude-memories")
    if include:
        return True
    if exclude:
        return False
    if dest_kind in {FormatKind.hermes_distribution, FormatKind.grok_share}:
        return False if dest_kind is FormatKind.hermes_distribution else True
    if dest_kind is FormatKind.hermes_profile:
        return True
    if dest_kind is FormatKind.grok_directory:
        return True
    return command == "sync"


def choose_dest_kind(to_platform: str, out: Path, hermes_layout: str | None) -> FormatKind:
    if to_platform == "grok":
        if out.suffix.lower() == ".json":
            return FormatKind.grok_share
        return FormatKind.grok_directory
    if hermes_layout == "profile":
        return FormatKind.hermes_profile
    return FormatKind.hermes_distribution


def convert(
    *,
    src: Path,
    out: Path,
    from_platform: str,
    to_platform: str,
    include_memories: bool,
    exclude_memories: bool,
    skills_dir: Path | None,
    hermes_layout: str | None,
) -> tuple[PortableBot, FormatKind, FormatKind]:
    dest_kind = choose_dest_kind(to_platform, out, hermes_layout)
    include = resolve_include_memories(
        dest_kind=dest_kind,
        include=include_memories,
        exclude=exclude_memories,
        command="convert",
    )
    bot, source_kind = load_bot(
        src,
        from_platform,
        include_memories=True,
        skills_dir=skills_dir,
    )
    # Always load memories into IR; writers honor `include`.
    if not include:
        bot = bot.model_copy(update={"memories": []})
    bot = snapshot_extras(restore_from_extras(bot))
    write_bot(bot, out, dest_kind, include_memories=include)
    write_migration_md(out, bot, source_kind=source_kind, dest_kind=dest_kind, include_memories=include)
    return bot, source_kind, dest_kind


def write_bot(bot: PortableBot, out: Path, dest_kind: FormatKind, *, include_memories: bool) -> None:
    if dest_kind is FormatKind.grok_share:
        write_grok_share(bot, out, include_memories=include_memories)
        return
    if dest_kind is FormatKind.grok_directory:
        write_grok_directory(bot, out, include_memories=include_memories)
        return
    if dest_kind is FormatKind.hermes_profile:
        write_hermes_profile(bot, out, include_memories=include_memories)
        return
    if dest_kind is FormatKind.hermes_distribution:
        write_hermes_distribution(bot, out, include_memories=include_memories)
        return
    raise UsageError(f"cannot write format {dest_kind.value}")
