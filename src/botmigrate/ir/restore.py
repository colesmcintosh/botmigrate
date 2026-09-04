"""Snapshot / restore extras so round-trips keep name, schedules, and events."""

from __future__ import annotations

from botmigrate.ir.models import Identity, PortableBot, Routine, Schedule
from botmigrate.schedule import extract_cron, schedule_from_cron_string


def snapshot_extras(bot: PortableBot) -> PortableBot:
    extras = dict(bot.extras)
    extras["identity"] = bot.identity.model_dump()
    extras["routine_schedules"] = {
        r.slug: r.schedule.model_dump() for r in bot.routines if r.schedule
    }
    extras["untranslated_routines"] = [
        r.model_dump() for r in bot.routines if r.schedule and r.schedule.kind == "event"
    ]
    grok = dict(extras.get("grok") or {})
    profile = dict(grok.get("profile") or {})
    profile.setdefault("name", bot.identity.name)
    profile.setdefault("title", bot.identity.title)
    profile.setdefault("description", bot.identity.description)
    grok["profile"] = profile
    extras["grok"] = grok
    return bot.model_copy(update={"extras": extras})


def restore_from_extras(bot: PortableBot) -> PortableBot:
    extras = bot.extras or {}
    schedules = extras.get("routine_schedules") or {}
    routines: list[Routine] = []
    seen: set[str] = set()
    for routine in bot.routines:
        if routine.schedule is None and routine.slug in schedules:
            routine = routine.model_copy(
                update={"schedule": Schedule.model_validate(schedules[routine.slug])}
            )
        if routine.schedule is None:
            inferred = _cron_from_text(f"{routine.description}\n{routine.prompt}")
            if inferred:
                routine = routine.model_copy(update={"schedule": inferred})
        routines.append(routine)
        seen.add(routine.slug)
    for raw in extras.get("untranslated_routines") or []:
        extra_r = Routine.model_validate(raw)
        if extra_r.slug not in seen:
            routines.append(extra_r)
            seen.add(extra_r.slug)
    identity = _restore_identity(bot.identity, extras)
    return bot.model_copy(
        update={"identity": identity, "routines": routines, "extras": extras}
    ).sorted()


def _restore_identity(identity: Identity, extras: dict) -> Identity:
    stored = (extras.get("grok") or {}).get("profile") or extras.get("identity") or {}
    updates = {}
    if stored.get("name"):
        updates["name"] = stored["name"]
    if stored.get("title"):
        updates["title"] = stored["title"]
    if stored.get("description") and not identity.description:
        updates["description"] = stored["description"]
    return identity.model_copy(update=updates) if updates else identity


def _cron_from_text(text: str) -> Schedule | None:
    expr = extract_cron(text)
    if not expr:
        return None
    return schedule_from_cron_string(expr)
