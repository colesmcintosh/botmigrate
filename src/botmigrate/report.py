"""Inspect summary and the MIGRATION.md written beside every output."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from botmigrate import platforms
from botmigrate.connectors import grok_plugin_payload
from botmigrate.formats import FormatKind
from botmigrate.io import output_dir, write_text
from botmigrate.ir.models import Connector, PortableBot


def inspect_payload(bot: PortableBot, kind: FormatKind) -> dict[str, Any]:
    return {
        "format": kind.value,
        "name": bot.identity.name,
        "slug": bot.identity.slug,
        "title": bot.identity.title,
        "description": bot.identity.description,
        "skills": [
            {"slug": s.slug, "name": s.name, "description": s.description} for s in bot.skills
        ],
        "routines": [
            {
                "slug": r.slug,
                "name": r.name,
                "schedule": r.schedule.kind if r.schedule else None,
                "cron": r.schedule.cron if r.schedule else None,
            }
            for r in bot.routines
        ],
        "memories": {"profile": len(bot.profile_memories()), "log": len(bot.log_memories())},
        "connectors": [
            {"kind": c.kind, "id": c.id, "name": c.name, "mapped": c.mapped} for c in bot.connectors
        ],
    }


def inspect_text(bot: PortableBot, kind: FormatKind) -> str:
    data = inspect_payload(bot, kind)
    routines = []
    for r in data["routines"]:
        detail = f"cron {r['cron']}" if r["cron"] else r["schedule"]
        routines.append(f"{r['slug']} ({detail})" if detail else r["slug"])
    connectors = [f"{c['id']} ({c['kind']})" for c in data["connectors"]]
    return "\n".join(
        [
            f"Format: {data['format']}",
            f"Name: {data['name']}",
            f"Title: {data['title'] or '—'}",
            f"Skills ({len(data['skills'])}): {_csv(s['slug'] for s in data['skills'])}",
            f"Routines ({len(data['routines'])}): {_csv(routines)}",
            f"Memories: {data['memories']['profile']} profile, {data['memories']['log']} log",
            f"Connectors: {_csv(connectors)}",
        ]
    )


def write_migration_md(
    out: Path,
    bot: PortableBot,
    *,
    source_kind: FormatKind,
    dest_kind: FormatKind,
    include_memories: bool,
) -> None:
    write_text(
        output_dir(out) / "MIGRATION.md",
        migration_markdown(bot, source_kind, dest_kind, include_memories),
    )


def migration_markdown(
    bot: PortableBot,
    source_kind: FormatKind,
    dest_kind: FormatKind,
    include_memories: bool,
) -> str:
    platform = platforms.platform_of(dest_kind)
    cron = [r for r in bot.routines if not (r.schedule and r.schedule.kind == "event")]
    events = [r for r in bot.routines if r.schedule and r.schedule.kind == "event"]
    usable = [c for c in bot.connectors if c.mapped and _usable_on(c, platform)]

    converted = [
        f"- Identity: {bot.identity.name}",
        f"- Skills ({len(bot.skills)}): {_csv(s.slug for s in bot.skills)}",
    ]
    if cron:
        converted.append(
            f"- Cron routines ({len(cron)}): {_csv(r.slug for r in cron)}"
            " — imported jobs stay disabled until you enable them"
        )
    if usable:
        converted.append(f"- Connectors: {_csv(c.id for c in usable)}")
    if include_memories:
        converted.append(
            f"- Memories: {len(bot.profile_memories())} profile, {len(bot.log_memories())} log"
        )
    else:
        converted.append("- Memories: not written (shareable distribution / excluded)")

    skipped = [
        f"- Event routine `{r.slug}` ({r.schedule.display if r.schedule else 'event'}) has no Hermes cron "
        "equivalent. Original trigger is stored in `.botmigrate.json` for a Grok round-trip."
        for r in events
    ]
    for c in bot.connectors:
        if platform == "grok" and not c.mapped:
            skipped.append(
                f"- Connector `{c.id}` has no documented Grok marketplace plugin id. Reconnect it manually."
            )
        if platform == "hermes" and c.kind == "plugin" and not c.mapped:
            skipped.append(
                f"- Grok plugin `{c.id}` could not be mapped to an MCP stub. Add it to `mcp.json` yourself."
            )
    if platform == "hermes" and not (bot.extras.get("hermes") or {}).get("config"):
        skipped.append(
            "- No model pin was copied (Grok has none; Hermes `config.yaml` was not invented)."
        )

    todo = [
        "1. Read `SOUL.md` / `profile.json` and confirm the persona.",
        "2. Enable cron jobs after review (`hermes -p <name> cron list`, then resume).",
        "3. Copy `.env.EXAMPLE` to `.env` if present and fill values — never commit them.",
        "4. Reconnect MCP servers / marketplace plugins and paste tokens locally.",
        "5. Keep `.botmigrate.json` next to the bot if you plan to sync or round-trip.",
    ]
    lines = [
        "# Migration report",
        "",
        f"Converted **{source_kind.value}** → **{dest_kind.value}**.",
        "",
        "## Converted",
        "",
        *converted,
        "",
        "## Skipped / needs attention",
        "",
        *(skipped or ["- Nothing extra was skipped."]),
        "",
        "## What you must do",
        "",
        *todo,
        "",
        *(f"- Note: {note}" for note in bot.notes),
        "",
    ]
    return "\n".join(lines)


def _usable_on(connector: Connector, platform: str) -> bool:
    return platform != "grok" or grok_plugin_payload(connector) is not None


def _csv(items: Iterable[str]) -> str:
    values = list(items)
    return ", ".join(values) if values else "(none)"
