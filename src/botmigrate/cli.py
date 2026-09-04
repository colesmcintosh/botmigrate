"""botmigrate CLI: inspect, convert, sync."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import typer

from botmigrate import __version__, platforms
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
        "Move AI agent bots between Grok Bot and Hermes Agent. "
        "Local files only — no network, no API keys, never copies secrets."
    ),
)

Platform = Enum("Platform", {name: name for name in platforms.names()}, type=str)  # type: ignore[misc]

SRC = typer.Argument(
    ..., exists=True, help="Bot to read: share JSON, agent directory, or Hermes export."
)
FROM = typer.Option(
    None, "--from", help="Assert the source platform. Detected from the files by default."
)
TO = typer.Option(None, "--to", help="Target platform. Defaults to the other one.")
LAYOUT = typer.Option(
    None, "--layout", help=f"Output layout for the target ({platforms.layout_help()})."
)
MEMORIES = typer.Option(
    None,
    "--memories/--no-memories",
    help="Write memories. Default: yes, except for a shareable Hermes distribution.",
)
OUT = typer.Argument(..., help="Output: a .json share file or a directory.")
DST = typer.Argument(..., help="Destination to update. Created if missing.")
SKILLS_DIR = typer.Option(
    None,
    "--skills-dir",
    help="Extra Grok SKILL.md folders (shared workflows live outside the agent dir).",
)


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
    """Move Grok Bot ↔ Hermes Agent profiles."""


@app.command("inspect")
def inspect_cmd(
    path: Path = SRC,
    json_output: bool = typer.Option(False, "--json", help="Machine-readable payload."),
    skills_dir: Path | None = SKILLS_DIR,
    memories: bool = typer.Option(True, "--memories/--no-memories", help="Count memories."),
) -> None:
    """Detect the format and summarise name, skills, routines, memories, and connectors."""
    with _exit_on_error():
        bot, kind = load_bot(path, memories=memories, skills_dir=skills_dir)
        if json_output:
            typer.echo(json.dumps(inspect_payload(bot, kind), indent=2, ensure_ascii=False))
        else:
            typer.echo(inspect_text(bot, kind))


@app.command("convert")
def convert_cmd(
    src: Path = SRC,
    out: Path = OUT,
    to: Platform | None = TO,
    from_: Platform | None = FROM,
    layout: str | None = LAYOUT,
    memories: bool | None = MEMORIES,
    skills_dir: Path | None = SKILLS_DIR,
) -> None:
    """Convert a bot to the other platform. Writes MIGRATION.md and .botmigrate.json beside it."""
    with _exit_on_error():
        result = convert(
            src,
            out,
            to=_value(to),
            from_=_value(from_),
            layout=layout,
            memories=memories,
            skills_dir=skills_dir,
        )
    typer.echo(f"Converted {result.source_kind.value} → {result.dest_kind.value}")
    typer.echo(f"Wrote {out}")
    typer.echo(
        f"{len(result.bot.skills)} skill(s), {len(result.bot.routines)} routine(s). See MIGRATION.md."
    )


@app.command("sync")
def sync_cmd(
    src: Path = SRC,
    dst: Path = DST,
    apply: bool = typer.Option(False, "--apply", help="Write changes. Dry-run without it."),
    to: Platform | None = TO,
    from_: Platform | None = FROM,
    layout: str | None = LAYOUT,
    memories: bool | None = MEMORIES,
    skills_dir: Path | None = SKILLS_DIR,
) -> None:
    """Merge a bot onto an existing destination, keeping its secrets and dest-only data.

    Dry-run by default: prints the plan. Pass --apply to write.
    """
    with _exit_on_error():
        result = sync(
            src,
            dst,
            apply=apply,
            to=_value(to),
            from_=_value(from_),
            layout=layout,
            memories=memories,
            skills_dir=skills_dir,
        )
    typer.echo("\n".join(result.changes))


def _value(choice: Enum | None) -> str | None:
    return choice.value if choice else None


class _exit_on_error:
    """Turn a BotmigrateError into a message on stderr and its exit code."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        if isinstance(exc, BotmigrateError):
            typer.echo(exc.message, err=True)
            raise typer.Exit(exc.exit_code) from exc
        return False
