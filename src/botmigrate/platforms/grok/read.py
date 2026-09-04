"""Read Grok share JSON and on-disk agent directories into the portable IR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from botmigrate.connectors import connector_from_grok_plugin
from botmigrate.errors import MissingRequiredFileError, UnknownFormatError
from botmigrate.formats import FormatKind
from botmigrate.ids import kebab
from botmigrate.io import list_names, read_json, read_text
from botmigrate.ir.extras import merge_extras
from botmigrate.ir.models import Identity, Memory, PortableBot, Routine, Skill
from botmigrate.memorymd import parse_memory_lines
from botmigrate.platforms.grok.models import GrokProfile, GrokShare
from botmigrate.schedule import extract_cron, schedule_from_cron_string, schedule_from_grok_trigger
from botmigrate.sidecar import load_sidecar
from botmigrate.skillmd import parse_skill_md, read_skill_dir


def detect(path: Path) -> FormatKind | None:
    if path.is_file():
        if path.suffix.lower() != ".json":
            return None
        try:
            raw = read_json(path)
        except Exception as exc:
            raise UnknownFormatError(str(path), f"invalid JSON ({exc})") from exc
        profile = raw.get("profile") if isinstance(raw, dict) else None
        return FormatKind.grok_share if isinstance(profile, dict) and profile.get("name") else None
    if (path / "profile.json").is_file():
        return FormatKind.grok_directory
    return None


def read(path: Path, *, skills_dir: Path | None = None) -> PortableBot:
    path = path.expanduser().resolve()
    if path.is_file():
        return _read_share(path, skills_dir)
    if not path.is_dir():
        raise MissingRequiredFileError(
            str(path), "a Grok share JSON file or agent directory", "nothing"
        )
    return _read_directory(path, skills_dir)


def _read_share(path: Path, skills_dir: Path | None) -> PortableBot:
    raw = read_json(path)
    if not isinstance(raw, dict) or "profile" not in raw:
        raise MissingRequiredFileError(
            str(path), "Grok share JSON with a profile object", "JSON without profile"
        )
    share = GrokShare.model_validate(raw)
    extras = _extras(share.profile, visibility=share.visibility)
    if share.gettingStarted:
        extras["grok"]["gettingStarted"] = share.gettingStarted.model_dump()
    return _bot(
        share.profile,
        memories=[
            Memory(kind=item.kind, content=item.content.strip(), created_at=item.createdAt)
            for item in share.memory
            if item.content.strip()
        ],
        skills=_with_skills_dir(
            [_skill_from_share(s.name, s.description, s.content) for s in share.skills], skills_dir
        ),
        routines=[
            _routine_from_share(r.slug, r.name, r.description, r.content) for r in share.routines
        ],
        connectors=[
            connector_from_grok_plugin(p.pluginId, p.name, p.description) for p in share.plugins
        ],
        extras=extras,
        sidecar_root=path.parent,
        note=f"Read Grok share JSON {path.name}",
    )


def _read_directory(path: Path, skills_dir: Path | None) -> PortableBot:
    profile_path = path / "profile.json"
    if not profile_path.is_file():
        raise MissingRequiredFileError(str(path), "profile.json", list_names(path, 12))
    raw = read_json(profile_path)
    if not isinstance(raw, dict) or not raw.get("name"):
        raise MissingRequiredFileError(
            str(profile_path), "profile.json with a name field", "object without name"
        )
    profile = GrokProfile.model_validate(raw)
    return _bot(
        profile,
        memories=_read_memories(path / "memory"),
        skills=_with_skills_dir(_skills_from_dir(path / "skills"), skills_dir),
        routines=_read_automations(path / "automations"),
        connectors=[],
        extras=_extras(profile),
        sidecar_root=path,
        note=f"Read Grok agent directory {path.name}",
    )


def _bot(
    profile: GrokProfile,
    *,
    memories: list[Memory],
    skills: list[Skill],
    routines: list[Routine],
    connectors: list,
    extras: dict[str, Any],
    sidecar_root: Path,
    note: str,
) -> PortableBot:
    sidecar = load_sidecar(sidecar_root)
    if sidecar:
        extras = merge_extras(sidecar.extras, extras)
    identity = Identity(
        name=profile.name,
        slug=kebab(profile.name, fallback="bot"),
        title=profile.title,
        description=profile.description,
    )
    return PortableBot(
        identity=identity,
        memories=memories,
        skills=skills,
        routines=routines,
        connectors=connectors,
        extras=extras,
        notes=[note],
    ).sorted()


def _extras(profile: GrokProfile, **more: Any) -> dict[str, Any]:
    return {
        "grok": {
            "avatarShape": profile.avatarShape,
            "avatarColor": profile.avatarColor,
            "profile": profile.model_dump(),
            **more,
        }
    }


def _skill_from_share(name: str, description: str, content: str) -> Skill:
    meta, body = parse_skill_md(content) if content.lstrip().startswith("---") else ({}, content)
    return Skill(
        slug=kebab(meta.get("name") or name, fallback="skill"),
        name=meta.get("name") or name,
        description=meta.get("description") or description,
        content=body.strip(),
    )


def _routine_from_share(slug: str, name: str, description: str, content: str) -> Routine:
    cron = extract_cron(f"{description}\n{content}")
    return Routine(
        slug=slug or kebab(name, fallback="routine"),
        name=name,
        description=description,
        prompt=content,
        schedule=schedule_from_cron_string(cron) if cron else None,
    )


def _skills_from_dir(root: Path) -> list[Skill]:
    if not root.is_dir():
        return []
    skills: list[Skill] = []
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        parsed = read_skill_dir(child)
        if not parsed:
            continue
        meta, body = parsed
        skills.append(
            Skill(
                slug=kebab(child.name, fallback="skill"),
                name=meta.get("name") or child.name,
                description=meta.get("description", ""),
                content=body.strip(),
            )
        )
    return skills


def _with_skills_dir(skills: list[Skill], skills_dir: Path | None) -> list[Skill]:
    """Skills inside the bot win over shared ones found in --skills-dir."""
    if not skills_dir:
        return skills
    by_slug = {s.slug: s for s in _skills_from_dir(skills_dir)}
    by_slug.update({s.slug: s for s in skills})
    return list(by_slug.values())


def _read_memories(root: Path) -> list[Memory]:
    memories: list[Memory] = []
    if (root / "profile.md").is_file():
        memories.extend(parse_memory_lines(read_text(root / "profile.md"), "profile"))
    for log_file in sorted((root / "log").glob("*.md")) if (root / "log").is_dir() else []:
        memories.extend(parse_memory_lines(read_text(log_file), "log"))
    return memories


def _read_automations(root: Path) -> list[Routine]:
    if not root.is_dir():
        return []
    routines: list[Routine] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        auto_path = folder / "automation.json"
        if not auto_path.is_file():
            continue
        raw = read_json(auto_path)
        if not isinstance(raw, dict):
            continue
        slug = kebab(folder.name, fallback="routine")
        schedule = schedule_from_grok_trigger(raw)
        description = str(raw.get("description") or "")
        if not description and schedule:
            if schedule.kind == "cron" and schedule.cron:
                description = f"Runs on cron schedule {schedule.cron}."
            elif schedule.kind == "event":
                description = f"Grok event trigger ({schedule.display})."
        routines.append(
            Routine(
                slug=slug,
                name=str(raw.get("name") or slug),
                description=description,
                prompt=str(raw.get("prompt") or raw.get("content") or ""),
                schedule=schedule,
                enabled=bool(raw.get("enabled", True)),
            )
        )
    return routines
