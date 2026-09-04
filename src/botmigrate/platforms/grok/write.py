"""Write Grok share JSON and self-contained agent directories."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from botmigrate.connectors import grok_plugin_payload
from botmigrate.io import write_json, write_text
from botmigrate.ir.models import Memory, PortableBot, Routine
from botmigrate.memorymd import render_memory_line
from botmigrate.platforms.grok.models import AVATAR_COLORS, AVATAR_SHAPES
from botmigrate.schedule import grok_trigger_presentation
from botmigrate.sidecar import write_sidecar
from botmigrate.skillmd import write_skill_dir


def write_share(bot: PortableBot, out: Path, *, include_memories: bool) -> None:
    bot = bot.sorted()
    grok = bot.extras.get("grok") or {}
    payload: dict[str, Any] = {
        "profile": _profile_payload(bot, grok),
        "memory": [_memory_item(m) for m in bot.memories] if include_memories else [],
        "skills": [
            {"name": s.name, "description": s.description, "content": s.content} for s in bot.skills
        ],
        "routines": [_share_routine(r) for r in bot.routines],
        "plugins": [p for p in map(grok_plugin_payload, bot.connectors) if p],
        "visibility": grok.get("visibility") or "public",
    }
    if grok.get("gettingStarted"):
        payload["gettingStarted"] = grok["gettingStarted"]
    write_json(out, payload)
    write_sidecar(out, bot, "grok-share-json")


def write_directory(bot: PortableBot, out: Path, *, include_memories: bool) -> None:
    bot = bot.sorted()
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "profile.json", _profile_payload(bot, bot.extras.get("grok") or {}))
    if include_memories:
        _write_memories(out / "memory", bot.memories)
    for skill in bot.skills:
        write_skill_dir(out / "skills", skill.slug, skill.slug, skill.description, skill.content)
    for routine in bot.routines:
        write_json(out / "automations" / routine.slug / "automation.json", _automation(routine))
    write_sidecar(out, bot, "grok-directory")


def _profile_payload(bot: PortableBot, grok: dict) -> dict:
    stored = grok.get("profile") if isinstance(grok.get("profile"), dict) else {}
    shape = grok.get("avatarShape") or stored.get("avatarShape")
    color = grok.get("avatarColor") or stored.get("avatarColor")
    return {
        "name": stored.get("name") or bot.identity.name,
        "description": bot.identity.description or stored.get("description") or "",
        "title": bot.identity.title or stored.get("title") or "",
        "avatarShape": shape if shape in AVATAR_SHAPES else "blob",
        "avatarColor": color if color in AVATAR_COLORS else "black",
    }


def _memory_item(memory: Memory) -> dict:
    item = {"kind": memory.kind, "content": memory.content}
    if memory.created_at:
        item["createdAt"] = memory.created_at
    return item


def _share_routine(routine: Routine) -> dict:
    """Share JSON has no schedule field, so the cron rides along in the description."""
    description = routine.description
    cron = routine.schedule.cron if routine.schedule else None
    if cron and cron not in description:
        suffix = f"Runs on cron schedule {cron}."
        description = f"{description} {suffix}".strip() if description else suffix
    return {
        "slug": routine.slug,
        "name": routine.name,
        "description": description,
        "content": routine.prompt,
    }


def _write_memories(root: Path, memories: list[Memory]) -> None:
    profile = [render_memory_line(m) for m in memories if m.kind == "profile"]
    if profile:
        write_text(root / "profile.md", "\n".join(profile))
    by_month: dict[str, list[str]] = defaultdict(list)
    for memory in memories:
        if memory.kind == "log":
            by_month[(memory.created_at or "1970-01-01")[:7]].append(render_memory_line(memory))
    for month, lines in sorted(by_month.items()):
        write_text(root / "log" / f"{month}.md", "\n".join(lines))


def _automation(routine: Routine) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": routine.name, "prompt": routine.prompt, "enabled": True}
    schedule = routine.schedule
    if not schedule:
        return payload
    presentation = grok_trigger_presentation(schedule)
    if schedule.kind == "event":
        # Event listeners stay event-only; a fake cron is never invented.
        if presentation:
            payload["triggerPresentation"] = presentation
    elif schedule.cron:
        payload["schedule"] = schedule.cron
        payload["triggerPresentation"] = presentation
    return payload
