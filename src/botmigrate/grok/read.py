"""Read Grok share JSON and on-disk agent directories into the portable IR."""

from __future__ import annotations

import re
from pathlib import Path

from botmigrate.connectors import connector_from_grok_plugin
from botmigrate.errors import MissingRequiredFileError
from botmigrate.ids import kebab
from botmigrate.io import read_json, read_text
from botmigrate.ir.models import Identity, Memory, PortableBot, Routine, Skill
from botmigrate.grok.models import GrokShare
from botmigrate.schedule import extract_cron, schedule_from_cron_string, schedule_from_grok_trigger
from botmigrate.secrets import assert_src_not_secret_file
from botmigrate.skillmd import parse_skill_md, read_skill_dir
from botmigrate.sidecar import load_sidecar

_PROFILE_LINE = re.compile(
    r"^-\s*(?:\((\d{4}-\d{2}-\d{2})\)\s*)?(.*)$"
)


def read_grok(path: Path, skills_dir: Path | None = None) -> PortableBot:
    path = path.expanduser().resolve()
    assert_src_not_secret_file(path)
    if path.is_file():
        return _read_share(path, skills_dir)
    if not path.is_dir():
        raise MissingRequiredFileError(str(path), "a Grok share JSON file or agent directory", "nothing")
    return _read_directory(path, skills_dir)


def _read_share(path: Path, skills_dir: Path | None) -> PortableBot:
    raw = read_json(path)
    if not isinstance(raw, dict) or "profile" not in raw:
        raise MissingRequiredFileError(str(path), "Grok share JSON with a profile object", "JSON without profile")
    share = GrokShare.model_validate(raw)
    profile = share.profile
    identity = Identity(
        name=profile.name,
        slug=kebab(profile.name, fallback="bot"),
        title=profile.title,
        description=profile.description,
        soul="",
    )
    memories = [
        Memory(kind=item.kind, content=item.content.strip(), created_at=item.createdAt)
        for item in share.memory
        if item.content.strip()
    ]
    skills = [_skill_from_share(item.name, item.description, item.content) for item in share.skills]
    if skills_dir:
        skills = _merge_skills(skills, _skills_from_dir(skills_dir))
    routines = [_routine_from_share(item.slug, item.name, item.description, item.content) for item in share.routines]
    connectors = [
        connector_from_grok_plugin(p.pluginId, p.name, p.description) for p in share.plugins
    ]
    extras: dict = {
        "grok": {
            "avatarShape": profile.avatarShape,
            "avatarColor": profile.avatarColor,
            "visibility": share.visibility,
            "profile": profile.model_dump(),
        }
    }
    if share.gettingStarted:
        extras["grok"]["gettingStarted"] = share.gettingStarted.model_dump()
    sidecar = load_sidecar(path.parent)
    if sidecar:
        extras = _merge_extras(sidecar.extras, extras)
    notes = [f"Read Grok share JSON {path.name}"]
    return PortableBot(
        identity=identity,
        memories=memories,
        skills=skills,
        routines=routines,
        connectors=connectors,
        extras=extras,
        notes=notes,
    ).sorted()


def _read_directory(path: Path, skills_dir: Path | None) -> PortableBot:
    profile_path = path / "profile.json"
    if not profile_path.is_file():
        raise MissingRequiredFileError(str(path), "profile.json", _found_names(path))
    raw = read_json(profile_path)
    if not isinstance(raw, dict) or not raw.get("name"):
        raise MissingRequiredFileError(str(profile_path), "profile.json with a name field", "object without name")
    share = GrokShare.model_validate({"profile": raw})
    profile = share.profile
    identity = Identity(
        name=profile.name,
        slug=kebab(profile.name, fallback="bot"),
        title=profile.title,
        description=profile.description,
        soul="",
    )
    memories = _read_grok_memories(path)
    skills = _skills_from_dir(path / "skills")
    if skills_dir:
        skills = _merge_skills(skills, _skills_from_dir(skills_dir))
    routines = _read_automations(path / "automations")
    extras = {
        "grok": {
            "avatarShape": profile.avatarShape,
            "avatarColor": profile.avatarColor,
            "profile": profile.model_dump(),
        }
    }
    sidecar = load_sidecar(path)
    if sidecar:
        extras = _merge_extras(sidecar.extras, extras)
    return PortableBot(
        identity=identity,
        memories=memories,
        skills=skills,
        routines=routines,
        connectors=[],
        extras=extras,
        notes=[f"Read Grok agent directory {path.name}"],
    ).sorted()


def _skill_from_share(name: str, description: str, content: str) -> Skill:
    meta, body = parse_skill_md(content) if content.lstrip().startswith("---") else ({}, content)
    slug = kebab(meta.get("name") or name, fallback="skill")
    return Skill(
        slug=slug,
        name=meta.get("name") or name,
        description=meta.get("description") or description,
        content=body.strip(),
    )


def _routine_from_share(slug: str, name: str, description: str, content: str) -> Routine:
    resolved = slug or kebab(name, fallback="routine")
    cron = extract_cron(f"{description}\n{content}")
    schedule = schedule_from_cron_string(cron) if cron else None
    return Routine(
        slug=resolved,
        name=name,
        description=description,
        prompt=content,
        schedule=schedule,
    )


def _skills_from_dir(root: Path) -> list[Skill]:
    if not root.is_dir():
        return []
    skills: list[Skill] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        parsed = read_skill_dir(child)
        if not parsed:
            continue
        meta, body = parsed
        slug = kebab(child.name, fallback="skill")
        skills.append(
            Skill(
                slug=slug,
                name=meta.get("name") or child.name,
                description=meta.get("description", ""),
                content=body.strip(),
            )
        )
    return skills


def _merge_skills(primary: list[Skill], extra: list[Skill]) -> list[Skill]:
    by_slug = {s.slug: s for s in extra}
    by_slug.update({s.slug: s for s in primary})
    return list(by_slug.values())


def _read_grok_memories(root: Path) -> list[Memory]:
    memories: list[Memory] = []
    profile_md = root / "memory" / "profile.md"
    if profile_md.is_file():
        memories.extend(_parse_memory_md(read_text(profile_md), kind="profile"))
    log_dir = root / "memory" / "log"
    if log_dir.is_dir():
        for log_file in sorted(log_dir.glob("*.md")):
            memories.extend(_parse_memory_md(read_text(log_file), kind="log"))
    return [m for m in memories if m.content.strip()]


def _parse_memory_md(text: str, kind: str) -> list[Memory]:
    items: list[Memory] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PROFILE_LINE.match(line)
        if match:
            created, content = match.group(1), match.group(2).strip()
            if content:
                items.append(Memory(kind=kind, content=content, created_at=created))  # type: ignore[arg-type]
        elif line:
            items.append(Memory(kind=kind, content=line.lstrip("- ").strip(), created_at=None))  # type: ignore[arg-type]
    return items


def _read_automations(root: Path) -> list[Routine]:
    if not root.is_dir():
        return []
    routines: list[Routine] = []
    for child in sorted(root.iterdir()):
        auto_path = child / "automation.json" if child.is_dir() else None
        if child.is_file() and child.name == "automation.json":
            auto_path = child
            slug = kebab(child.parent.name, fallback="routine")
        elif auto_path and auto_path.is_file():
            slug = kebab(child.name, fallback="routine")
        else:
            continue
        raw = read_json(auto_path)
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or slug)
        prompt = str(raw.get("prompt") or raw.get("content") or "")
        schedule = schedule_from_grok_trigger(raw)
        description = str(raw.get("description") or "")
        if not description and schedule and schedule.kind == "cron" and schedule.cron:
            description = f"Runs on cron schedule {schedule.cron}."
        elif not description and schedule and schedule.kind == "event":
            description = f"Grok event trigger ({schedule.display})."
        routines.append(
            Routine(
                slug=slug,
                name=name,
                description=description,
                prompt=prompt,
                schedule=schedule,
                enabled=bool(raw.get("enabled", True)),
            )
        )
    return routines


def _found_names(path: Path) -> str:
    names = sorted(p.name for p in path.iterdir())[:12]
    return ", ".join(names) if names else "an empty directory"


def _merge_extras(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged
