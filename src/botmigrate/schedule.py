"""Cron / Hermes schedule parsing. Never invent a cron for event listeners."""

from __future__ import annotations

import re
from typing import Any

from botmigrate.ir.models import Schedule

CRON_5 = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$")
RELATIVE = re.compile(r"^\d+\s*[smhdw]$", re.IGNORECASE)
INTERVAL = re.compile(r"^every\s+\d+\s*[smhdw]$", re.IGNORECASE)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T")

GROK_EVENT_TYPES = frozenset(
    {
        "slack",
        "github",
        "origin",
        "microsoftteams",
        "linear",
        "sentry",
        "pagerduty",
        "webhook",
        "group",
    }
)


_CRON_FIELD = re.compile(r"(?:[0-9*,/\-?]+|[A-Za-z]{3}(?:-[A-Za-z]{3})?)$")


def _looks_like_cron_field(part: str) -> bool:
    return bool(_CRON_FIELD.fullmatch(part))


def is_cron_5(value: str) -> bool:
    parts = value.strip().split()
    return len(parts) == 5 and all(_looks_like_cron_field(p) for p in parts)


def extract_cron(text: str) -> str | None:
    """Find a 5-field cron even when it sits inside a sentence."""
    tokens = [t.rstrip(".,;:)") for t in text.split()]
    for i in range(len(tokens) - 4):
        expr = " ".join(tokens[i : i + 5])
        if is_cron_5(expr):
            return expr
    return None


def schedule_from_cron_string(expr: str, original: dict[str, Any] | None = None) -> Schedule:
    expr = expr.strip()
    return Schedule(
        kind="cron",
        cron=expr,
        display=expr,
        original=original or {"kind": "cron", "expr": expr, "display": expr},
    )


def schedule_from_hermes(raw: Any) -> Schedule | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return schedule_from_text(raw)
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "").lower()
    expr = str(raw.get("expr") or raw.get("schedule") or raw.get("display") or "").strip()
    display = str(raw.get("display") or expr)
    if kind == "cron" or (not kind and is_cron_5(expr)):
        cron = expr if is_cron_5(expr) else None
        return Schedule(kind="cron" if cron else "interval", cron=cron, display=display, original=dict(raw))
    if kind == "relative" or (not kind and RELATIVE.fullmatch(expr)):
        return Schedule(kind="relative", display=display or expr, original=dict(raw))
    if kind == "interval" or (not kind and INTERVAL.fullmatch(expr)):
        return Schedule(kind="interval", display=display or expr, original=dict(raw))
    if kind in {"iso", "timestamp"} or ISO.match(expr):
        return Schedule(kind="iso", display=display or expr, original=dict(raw))
    if expr:
        return schedule_from_text(expr, original=dict(raw))
    return Schedule(kind="interval", display=display, original=dict(raw))


def schedule_from_text(text: str, original: dict[str, Any] | None = None) -> Schedule:
    value = text.strip()
    orig = original or {"expr": value, "display": value}
    if is_cron_5(value):
        return Schedule(kind="cron", cron=value, display=value, original=orig)
    if INTERVAL.fullmatch(value):
        return Schedule(kind="interval", display=value, original=orig)
    if RELATIVE.fullmatch(value):
        return Schedule(kind="relative", display=value, original=orig)
    if ISO.match(value):
        return Schedule(kind="iso", display=value, original=orig)
    return Schedule(kind="interval", display=value, original=orig)


def schedule_from_grok_trigger(automation: dict[str, Any]) -> Schedule | None:
    presentation = automation.get("triggerPresentation") or {}
    trigger = presentation.get("trigger") if isinstance(presentation, dict) else None
    trigger = trigger if isinstance(trigger, dict) else {}
    trigger_type = str(trigger.get("type") or "").strip()
    raw_schedule = automation.get("schedule") or trigger.get("schedule") or ""

    if trigger_type.lower() == "cron" or (not trigger_type and raw_schedule and is_cron_5(str(raw_schedule))):
        expr = str(raw_schedule or trigger.get("schedule") or "").strip()
        if is_cron_5(expr):
            return schedule_from_cron_string(expr, original={"grok_trigger": trigger, "schedule": expr})
        return Schedule(kind="interval", display=expr, original={"grok_trigger": trigger})

    if trigger_type.lower() in GROK_EVENT_TYPES or trigger_type:
        return Schedule(
            kind="event",
            display=trigger_type or "event",
            original={"grok_trigger": trigger, "triggerPresentation": presentation},
        )

    if raw_schedule and is_cron_5(str(raw_schedule)):
        return schedule_from_cron_string(str(raw_schedule))
    if raw_schedule:
        return Schedule(kind="interval", display=str(raw_schedule), original={"schedule": raw_schedule})
    return None


def hermes_schedule_object(schedule: Schedule) -> dict[str, Any]:
    if schedule.kind == "cron" and schedule.cron:
        return {"kind": "cron", "expr": schedule.cron, "display": schedule.display or schedule.cron}
    if schedule.original and "kind" in schedule.original:
        cleaned = {k: v for k, v in schedule.original.items() if k != "grok_trigger"}
        if "kind" in cleaned:
            return cleaned
    return {
        "kind": schedule.kind if schedule.kind != "event" else "interval",
        "expr": schedule.display,
        "display": schedule.display,
    }


def grok_trigger_presentation(schedule: Schedule) -> dict[str, Any] | None:
    if schedule.kind == "cron" and schedule.cron:
        return {
            "version": 1,
            "trigger": {"type": "cron", "schedule": schedule.cron},
        }
    original = schedule.original or {}
    if "triggerPresentation" in original and isinstance(original["triggerPresentation"], dict):
        return original["triggerPresentation"]
    if "grok_trigger" in original and isinstance(original["grok_trigger"], dict):
        return {"version": 1, "trigger": original["grok_trigger"]}
    return None
