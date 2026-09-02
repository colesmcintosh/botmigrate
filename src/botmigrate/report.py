"""Inspect summary and MIGRATION.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from botmigrate.formats import FormatKind
from botmigrate.io import write_text
from botmigrate.ir.models import PortableBot


def inspect_payload(bot: PortableBot, kind: FormatKind) -> dict[str, Any]:
    profile_n = len(bot.profile_memories())
    log_n = len(bot.log_memories())
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
        "memories": {"profile": profile_n, "log": log_n},
        "connectors": [
            {"kind": c.kind, "id": c.id, "name": c.name, "mapped": c.mapped}
            for c in bot.connectors
        ],
    }


def inspect_text(bot: PortableBot, kind: FormatKind) -> str:
    data = inspect_payload(bot, kind)
    skill_names = ", ".join(s["slug"] for s in data["skills"]) or "(none)"
    routine_bits = []
    for r in data["routines"]:
        if r["cron"]:
            routine_bits.append(f"{r['slug']} (cron {r['cron']})")
        elif r["schedule"] == "event":
            routine_bits.append(f"{r['slug']} (event)")
        elif r["schedule"]:
            routine_bits.append(f"{r['slug']} ({r['schedule']})")
        else:
            routine_bits.append(r["slug"])
    routines = ", ".join(routine_bits) or "(none)"
    connectors = ", ".join(f"{c['id']} ({c['kind']})" for c in data["connectors"]) or "(none)"
    lines = [
        f"Format: {data['format']}",
        f"Name: {data['name']}",
        f"Title: {data['title'] or '—'}",
        f"Skills ({len(data['skills'])}): {skill_names}",
        f"Routines ({len(data['routines'])}): {routines}",
        f"Memories: {data['memories']['profile']} profile, {data['memories']['log']} log",
        f"Connectors: {connectors}",
    ]
    return "\n".join(lines)


def write_migration_md(
    out: Path,
    bot: PortableBot,
    *,
    source_kind: FormatKind,
    dest_kind: FormatKind,
    include_memories: bool,
) -> None:
    dest_dir = out if out.is_dir() or out.suffix == "" else out.parent
    if out.suffix == ".json":
        dest_dir = out.parent
    write_text(dest_dir / "MIGRATION.md", migration_markdown(bot, source_kind, dest_kind, include_memories))


def migration_markdown(
    bot: PortableBot,
    source_kind: FormatKind,
    dest_kind: FormatKind,
    include_memories: bool,
) -> str:
    converted: list[str] = [
        f"- Identity: {bot.identity.name}",
        f"- Skills ({len(bot.skills)}): {_csv(s.slug for s in bot.skills)}",
    ]
    cron = [r for r in bot.routines if r.schedule is None or r.schedule.kind != "event"]
    events = [r for r in bot.routines if r.schedule and r.schedule.kind == "event"]
    if cron:
        converted.append(
            f"- Cron routines ({len(cron)}): {_csv(r.slug for r in cron)}"
            " — imported jobs stay disabled until you enable them"
        )
    mapped = [c for c in bot.connectors if c.mapped and _usable_on(c, dest_kind)]
    if mapped:
        converted.append(f"- Connectors: {_csv(c.id for c in mapped)}")
    if include_memories:
        converted.append(
            f"- Memories: {len(bot.profile_memories())} profile, {len(bot.log_memories())} log"
        )
    else:
        converted.append("- Memories: not written (shareable distribution / excluded)")

    skipped: list[str] = []
    for routine in events:
        trigger = (routine.schedule.display if routine.schedule else "event")
        skipped.append(
            f"- Event routine `{routine.slug}` ({trigger}) has no Hermes cron equivalent. "
            "Original trigger is stored in `.botmigrate.json` for a Grok round-trip."
        )
    for connector in bot.connectors:
        if dest_kind.value.startswith("grok") and not connector.mapped:
            skipped.append(
                f"- Connector `{connector.id}` has no documented Grok marketplace plugin id. "
                "Reconnect it manually."
            )
        if dest_kind.value.startswith("hermes") and connector.kind == "plugin" and not connector.mapped:
            skipped.append(
                f"- Grok plugin `{connector.id}` could not be mapped to an MCP stub. "
                "Add it to `mcp.json` yourself."
            )
    if dest_kind.value.startswith("hermes"):
        if not ((bot.extras or {}).get("hermes") or {}).get("config"):
            skipped.append("- No model pin was copied (Grok has none; Hermes `config.yaml` was not invented).")

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
    ]
    lines.extend(f"- Note: {note}" for note in bot.notes)
    lines.append("")
    return "\n".join(lines)


def _csv(items) -> str:
    values = list(items)
    return ", ".join(values) if values else "(none)"


def _usable_on(connector, dest_kind: FormatKind) -> bool:
    if dest_kind.value.startswith("hermes"):
        return True
    from botmigrate.connectors import grok_plugin_payload

    return grok_plugin_payload(connector) is not None
