"""botmigrate CLI: inspect, convert, sync."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from botmigrate import __version__
from botmigrate.convert import convert
from botmigrate.errors import BotmigrateError
from botmigrate.load import load_bot
from botmigrate.report import inspect_payload, inspect_text
from botmigrate.sync import sync

app = typer.Typer(
    name="botmigrate",
    no_args_is_help=True,
    add_completion=False,
    help=(
        "Convert and sync AI agent bots between Grok Bot and Hermes Agent. "
        "Local files only — no network, no API keys, never copies secrets."
    ),
)


class Platform(str, Enum):
    grok = "grok"
    hermes = "hermes"


class HermesLayout(str, Enum):
    distribution = "distribution"
    profile = "profile"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Convert and sync Grok Bot ↔ Hermes Agent profiles."""


@app.command("inspect")
def inspect_cmd(
    path: Path = typer.Argument(..., exists=True, help="Share JSON, agent directory, or Hermes export."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable inspect payload."),
    skills_dir: Optional[Path] = typer.Option(
        None,
        "--skills-dir",
        help="Extra Grok SKILL.md folders (shared workflows live outside the agent dir).",
    ),
    exclude_memories: bool = typer.Option(
        False,
        "--exclude-memories",
        help="Skip Hermes USER.md / MEMORY.md / memories/ when inspecting.",
    ),
) -> None:
    """Detect format and print a short summary (name, skills, routines, memories, connectors)."""
    try:
        bot, kind = load_bot(
            path, None, include_memories=not exclude_memories, skills_dir=skills_dir
        )
        if json_output:
            typer.echo(json.dumps(inspect_payload(bot, kind), indent=2, ensure_ascii=False))
        else:
            typer.echo(inspect_text(bot, kind))
    except BotmigrateError as exc:
        typer.echo(exc.message, err=True)
        raise typer.Exit(exc.exit_code) from exc


@app.command("convert")
def convert_cmd(
    from_platform: Platform = typer.Option(..., "--from", help="Source platform."),
    to_platform: Platform = typer.Option(..., "--to", help="Destination platform."),
    src: Path = typer.Option(..., "--src", exists=True, help="Source share file, directory, or tarball."),
    out: Path = typer.Option(..., "--out", help="Output JSON file or directory."),
    skills_dir: Optional[Path] = typer.Option(None, "--skills-dir", help="Extra Grok SKILL.md root."),
    include_memories: bool = typer.Option(
        False,
        "--include-memories",
        help="Write memories. Default: include for Grok outputs and Hermes live profiles; exclude for Hermes distributions.",
    ),
    exclude_memories: bool = typer.Option(
        False,
        "--exclude-memories",
        help="Do not write memories (always the default for a shareable Hermes distribution).",
    ),
    hermes_layout: Optional[HermesLayout] = typer.Option(
        None,
        "--hermes-layout",
        help="When --to hermes: 'distribution' (default, installable) or 'profile' (live ~/.hermes style).",
    ),
) -> None:
    """One-shot convert. Writes MIGRATION.md and .botmigrate.json beside the output."""
    try:
        bot, source_kind, dest_kind = convert(
            src=src,
            out=out,
            from_platform=from_platform.value,
            to_platform=to_platform.value,
            include_memories=include_memories,
            exclude_memories=exclude_memories,
            skills_dir=skills_dir,
            hermes_layout=hermes_layout.value if hermes_layout else None,
        )
        typer.echo(f"Converted {source_kind.value} → {dest_kind.value}")
        typer.echo(f"Wrote {out}")
        typer.echo(f"{len(bot.skills)} skill(s), {len(bot.routines)} routine(s). See MIGRATION.md.")
    except BotmigrateError as exc:
        typer.echo(exc.message, err=True)
        raise typer.Exit(exc.exit_code) from exc


@app.command("sync")
def sync_cmd(
    from_platform: Platform = typer.Option(..., "--from", help="Source platform."),
    to_platform: Platform = typer.Option(..., "--to", help="Destination platform."),
    src: Path = typer.Option(..., "--src", exists=True, help="Source bot."),
    dst: Path = typer.Option(..., "--dst", help="Existing destination to update."),
    apply: bool = typer.Option(False, "--apply", help="Write changes. Without this flag, sync is a dry-run."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the plan without writing (default when --apply is omitted).",
    ),
    skills_dir: Optional[Path] = typer.Option(None, "--skills-dir", help="Extra Grok SKILL.md root."),
    include_memories: bool = typer.Option(
        False,
        "--include-memories",
        help="Overwrite dest memories from source. Default: include for live profiles / Grok dirs; exclude for Hermes distributions.",
    ),
    exclude_memories: bool = typer.Option(
        False,
        "--exclude-memories",
        help="Leave destination memories untouched.",
    ),
    hermes_layout: Optional[HermesLayout] = typer.Option(None, "--hermes-layout"),
) -> None:
    """Apply portable fields onto an existing dest. Preserves dest-only secrets and user data.

    Dry-run by default. Pass --apply to write.
    """
    del dry_run  # documented flag; default behavior is dry-run unless --apply
    try:
        changes, _ = sync(
            src=src,
            dst=dst,
            from_platform=from_platform.value,
            to_platform=to_platform.value,
            apply=apply,
            include_memories=include_memories,
            exclude_memories=exclude_memories,
            skills_dir=skills_dir,
            hermes_layout=hermes_layout.value if hermes_layout else None,
        )
        typer.echo("\n".join(changes))
    except BotmigrateError as exc:
        typer.echo(exc.message, err=True)
        raise typer.Exit(exc.exit_code) from exc
