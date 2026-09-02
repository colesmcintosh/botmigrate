"""Write Grok share JSON and self-contained agent directories."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from botmigrate.connectors import grok_plugin_payload
from botmigrate.io import write_json, write_text
from botmigrate.ir.models import Memory, PortableBot, Routine
from botmigrate.schedule import grok_trigger_presentation
from botmigrate.sidecar import write_sidecar
from botmigrate.skillmd import write_skill_dir

AVATAR_SHAPES = {
    "blob", "pebble", "bean", "egg", "squircle", "tablet", "capsule",
    "cylinder", "hex", "gem", "crystal", "wedge", "shield", "dome",
    "arch", "cloud", "teardrop", "leaf",
}
AVATAR_COLORS = {
    "black", "brown", "red", "orange", "yellow", "green", "cyan",
    "blue", "violet", "magenta", "gray",
}


def write_grok_share(bot: PortableBot, out: Path, *, include_memories: bool) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    grok = (bot.extras or {}).get("grok") or {}
    profile = _profile_payload(bot, grok)
    memories = [_memory_item(m) for m in bot.memories] if include_memories else []
    skills = [
        {"name": skill.name, "description": skill.description, "content": skill.content}
        for skill in sorted(bot.skills, key=lambda s: s.slug)
    ]
    routines = [_share_routine(r) for r in sorted(bot.routines, key=lambda r: r.slug)]
    plugins = []
    for connector in sorted(bot.connectors, key=lambda c: c.id):
        payload = grok_plugin_payload(connector)
        if payload:
            plugins.append(payload)
    payload = {
        "profile": profile,
        "memory": memories,
        "skills": skills,
        "routines": routines,
        "plugins": plugins,
        "visibility": grok.get("visibility") or "public",
    }
    getting = grok.get("gettingStarted")
    if getting:
        payload["gettingStarted"] = getting
    write_json(out, payload)
    write_sidecar(out, bot, "grok-share-json")


def write_grok_directory(bot: PortableBot, out: Path, *, include_memories: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    grok = (bot.extras or {}).get("grok") or {}
    write_json(out / "profile.json", _profile_payload(bot, grok))
    if include_memories:
        _write_memories(out, bot.memories)
    for skill in sorted(bot.skills, key=lambda s: s.slug):
        write_skill_dir(out / "skills", skill.slug, skill.slug, skill.description, skill.content)
    for routine in sorted(bot.routines, key=lambda r: r.slug):
        _write_automation(out / "automations" / routine.slug, routine)
    write_sidecar(out, bot, "grok-directory")


def _profile_payload(bot: PortableBot, grok: dict) -> dict:
    stored = grok.get("profile") if isinstance(grok.get("profile"), dict) else {}
    shape = grok.get("avatarShape") or stored.get("avatarShape") or "blob"
    color = grok.get("avatarColor") or stored.get("avatarColor") or "black"
    if shape not in AVATAR_SHAPES:
        shape = "blob"
    if color not in AVATAR_COLORS:
        color = "black"
    return {
        "name": stored.get("name") or bot.identity.name,
        "description": bot.identity.description or stored.get("description") or "",
        "title": bot.identity.title or stored.get("title") or "",
        "avatarShape": shape,
        "avatarColor": color,
    }


def _memory_item(memory: Memory) -> dict:
    item = {"kind": memory.kind, "content": memory.content}
    if memory.created_at:
        item["createdAt"] = memory.created_at
    return item


def _share_routine(routine: Routine) -> dict:
    description = routine.description
    if routine.schedule and routine.schedule.cron and routine.schedule.cron not in description:
        suffix = f"Runs on cron schedule {routine.schedule.cron}."
        description = f"{description} {suffix}".strip() if description else suffix
    return {
        "slug": routine.slug,
        "name": routine.name,
        "description": description,
        "content": routine.prompt,
    }


def _write_memories(out: Path, memories: list[Memory]) -> None:
    profile_lines = [_memory_line(m) for m in memories if m.kind == "profile"]
    if profile_lines:
        write_text(out / "memory" / "profile.md", "\n".join(profile_lines) + "\n")
    by_month: dict[str, list[str]] = defaultdict(list)
    for memory in memories:
        if memory.kind != "log":
            continue
        month = (memory.created_at or "1970-01-01")[:7]
        by_month[month].append(_memory_line(memory))
    for month, lines in sorted(by_month.items()):
        write_text(out / "memory" / "log" / f"{month}.md", "\n".join(lines) + "\n")


def _memory_line(memory: Memory) -> str:
    if memory.created_at:
        return f"- ({memory.created_at}) {memory.content}"
    return f"- {memory.content}"


def _write_automation(folder: Path, routine: Routine) -> None:
    schedule = routine.schedule
    payload: dict = {
        "name": routine.name,
        "prompt": routine.prompt,
        "enabled": True,
    }
    if schedule and schedule.kind == "cron" and schedule.cron:
        payload["schedule"] = schedule.cron
        payload["triggerPresentation"] = grok_trigger_presentation(schedule)
    elif schedule and schedule.kind == "event":
        presentation = grok_trigger_presentation(schedule)
        if presentation:
            payload["triggerPresentation"] = presentation
        # No fake cron — event listeners stay event-only.
    elif schedule and schedule.cron:
        payload["schedule"] = schedule.cron
        payload["triggerPresentation"] = grok_trigger_presentation(schedule)
    write_json(folder / "automation.json", payload)

