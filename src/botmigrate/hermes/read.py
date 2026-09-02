"""Read Hermes distributions, live profiles, and export tarballs."""

from __future__ import annotations

import re
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from botmigrate.connectors import connector_from_mcp
from botmigrate.errors import MissingRequiredFileError, SecretCopyError
from botmigrate.hermes.models import HermesDistribution
from botmigrate.ids import kebab
from botmigrate.io import read_json, read_text, read_yaml
from botmigrate.ir.models import Identity, Memory, PortableBot, Routine, Skill
from botmigrate.schedule import schedule_from_hermes
from botmigrate.secrets import SECRET_DIRNAMES, assert_src_not_secret_file, is_secret_filename, strip_secrets
from botmigrate.sidecar import load_sidecar
from botmigrate.skillmd import parse_skill_md, read_skill_dir

_DATED_NAME = re.compile(r"\d{4}-\d{2}")


def read_hermes(path: Path, *, include_memories: bool) -> PortableBot:
    path = path.expanduser().resolve()
    assert_src_not_secret_file(path)
    if _is_tarball(path):
        return _read_tarball(path, include_memories=include_memories)
    if path.is_file():
        raise MissingRequiredFileError(
            str(path),
            "Hermes distribution directory, live profile, or .tar.gz export",
            f"file {path.name}",
        )
    if not path.is_dir():
        raise MissingRequiredFileError(str(path), "a Hermes profile directory", "nothing")
    return _read_directory(path, include_memories=include_memories)


def _is_tarball(path: Path) -> bool:
    name = path.name.lower()
    return path.is_file() and (name.endswith(".tar.gz") or name.endswith(".tgz"))


def _read_tarball(path: Path, *, include_memories: bool) -> PortableBot:
    with tarfile.open(path, "r:*") as archive:
        members = archive.getmembers()
        secret_members = [
            m.name for m in members if is_secret_filename(Path(m.name).name)
        ]
        if secret_members:
            # Export files should already strip these; refuse if present.
            raise SecretCopyError(str(path), f"tarball contains {', '.join(secret_members[:4])}")
        with tempfile.TemporaryDirectory(prefix="botmigrate-hermes-") as tmp:
            safe = [m for m in members if _safe_tar_member(m)]
            try:
                archive.extractall(tmp, members=safe, filter="data")
            except TypeError:
                archive.extractall(tmp, members=safe)
            extracted = Path(tmp)
            roots = [p for p in extracted.iterdir() if p.is_dir()]
            root = roots[0] if len(roots) == 1 and not (extracted / "SOUL.md").exists() and not (extracted / "distribution.yaml").exists() else extracted
            bot = _read_directory(root, include_memories=include_memories)
            bot.notes.append(f"Read Hermes export tarball {path.name}")
            return bot


def _safe_tar_member(member: tarfile.TarInfo) -> bool:
    name = Path(member.name)
    if name.is_absolute() or ".." in name.parts:
        return False
    if is_secret_filename(name.name):
        return False
    if any(part.lower() in SECRET_DIRNAMES or part.lower() == "sessions" for part in name.parts):
        return False
    return True


def _read_directory(path: Path, *, include_memories: bool) -> PortableBot:
    dist_path = path / "distribution.yaml"
    dist: HermesDistribution | None = None
    if dist_path.is_file():
        raw = read_yaml(dist_path)
        if not isinstance(raw, dict) or not raw.get("name"):
            raise MissingRequiredFileError(str(dist_path), "distribution.yaml with a name field", "incomplete manifest")
        dist = HermesDistribution.model_validate(raw)

    soul_text = read_text(path / "SOUL.md") if (path / "SOUL.md").is_file() else ""
    title, role = _soul_title_and_role(soul_text)
    folder_name = path.name
    name = dist.name if dist else folder_name
    slug = kebab(name, fallback="bot")
    description = (dist.description if dist else "") or role
    identity = Identity(
        name=_display_name(name, title),
        slug=slug,
        title=title,
        description=description,
        soul=soul_text.strip(),
    )

    skills = _read_skills(path / "skills")
    routines = _read_cron(path)
    connectors = _read_mcp(path / "mcp.json")
    memories = _read_memories(path) if include_memories else []

    extras: dict[str, Any] = {"hermes": {}}
    if dist:
        extras["hermes"]["distribution"] = dist.model_dump()
    config_path = path / "config.yaml"
    if config_path.is_file():
        extras["hermes"]["config"] = strip_secrets(read_yaml(config_path))
    sidecar = load_sidecar(path)
    if sidecar:
        extras = _merge_extras(sidecar.extras, extras)

    notes = [f"Read Hermes profile {path.name}"]
    return PortableBot(
        identity=identity,
        memories=memories,
        skills=skills,
        routines=routines,
        connectors=connectors,
        extras=extras,
        notes=notes,
    ).sorted()


def _display_name(slug_or_name: str, title: str) -> str:
    if " " in slug_or_name or slug_or_name != kebab(slug_or_name):
        return slug_or_name
    if title:
        return title
    return slug_or_name


def _soul_title_and_role(soul: str) -> tuple[str, str]:
    title = ""
    paragraphs: list[str] = []
    for line in soul.splitlines():
        stripped = line.strip()
        if not title and stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            continue
        if stripped and not stripped.startswith("#"):
            paragraphs.append(stripped)
    role = paragraphs[0] if paragraphs else ""
    return title, role


MAX_SKILL_DEPTH = 4
"""How far to descend into `skills/` looking for skill directories.

Distributions keep skills flat (`skills/<slug>/SKILL.md`), but live Hermes
profiles group them under a category (`skills/<category>/<slug>/SKILL.md`).
The cap also bounds recursion if a symlink points back up the tree.
"""


def _read_skills(root: Path) -> list[Skill]:
    if not root.is_dir():
        return []
    skills: list[Skill] = []
    _collect_skills(root, skills, depth=0, skills_root=root)
    return skills


def _collect_skills(
    root: Path, skills: list[Skill], *, depth: int, skills_root: Path
) -> None:
    for child in sorted(root.iterdir()):
        if child.name.startswith("."):
            continue
        if not child.is_dir():
            if child.name == "SKILL.md":
                meta, body = parse_skill_md(read_text(child))
                slug = kebab(meta.get("name") or child.parent.name, fallback="skill")
                _append_skill(skills, slug, meta.get("name") or slug, meta, body, "")
            continue
        parsed = read_skill_dir(child)
        if parsed:
            meta, body = parsed
            slug = kebab(child.name, fallback="skill")
            relative = child.relative_to(skills_root).as_posix()
            _append_skill(
                skills,
                slug,
                meta.get("name") or child.name,
                meta,
                body,
                relative if relative != child.name else "",
            )
            continue
        if depth < MAX_SKILL_DEPTH:
            _collect_skills(child, skills, depth=depth + 1, skills_root=skills_root)


def _append_skill(
    skills: list[Skill],
    slug: str,
    name: str,
    meta: dict[str, str],
    body: str,
    source_path: str,
) -> None:
    """Add a skill, qualifying the slug if a same-named skill already exists.

    Categories are flattened away, so two categories can hold skills with the
    same directory name. Later writes key off the slug, so a collision would
    silently drop one of them.
    """
    taken = {s.slug for s in skills}
    if slug in taken:
        base = slug
        counter = 2
        while slug in taken:
            slug = f"{base}-{counter}"
            counter += 1
    skills.append(
        Skill(
            slug=slug,
            name=name,
            description=meta.get("description", ""),
            content=body.strip(),
            source_path=source_path,
        )
    )


def _read_cron(root: Path) -> list[Routine]:
    routines: list[Routine] = []
    seen: set[str] = set()
    cron_dir = root / "cron"
    if cron_dir.is_dir():
        jobs_path = cron_dir / "jobs.json"
        if jobs_path.is_file():
            for job in _iter_jobs(read_json(jobs_path)):
                routine = _job_to_routine(job)
                seen.add(routine.slug)
                routines.append(routine)
        for path in sorted(cron_dir.glob("*.json")):
            if path.name == "jobs.json":
                continue
            raw = read_json(path)
            if not isinstance(raw, dict):
                continue
            routine = _job_to_routine(raw, slug_hint=path.stem)
            if routine.slug not in seen:
                seen.add(routine.slug)
                routines.append(routine)
    return routines


def _iter_jobs(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        jobs = raw.get("jobs")
        if isinstance(jobs, list):
            return [item for item in jobs if isinstance(item, dict)]
        if "name" in raw or "prompt" in raw:
            return [raw]
    return []


def _job_to_routine(job: dict[str, Any], slug_hint: str | None = None) -> Routine:
    name = _strip_bot_prefix(str(job.get("name") or slug_hint or "routine"))
    slug = kebab(slug_hint or name, fallback="routine")
    prompt = str(job.get("prompt") or "")
    schedule = schedule_from_hermes(job.get("schedule"))
    description = str(job.get("description") or "")
    if not description and schedule:
        if schedule.kind == "cron" and schedule.cron:
            description = f"Scheduled cron job ({schedule.cron})."
        else:
            description = f"Scheduled job ({schedule.display or schedule.kind})."
    extras_schedule = dict(job)
    if schedule:
        schedule.original = {**schedule.original, "hermes_job": {k: extras_schedule.get(k) for k in ("id", "deliver", "skills", "script", "model") if extras_schedule.get(k) is not None}}
    return Routine(
        slug=slug,
        name=name,
        description=description,
        prompt=prompt,
        schedule=schedule,
        enabled=False,
    )


def _strip_bot_prefix(name: str) -> str:
    if name.startswith("[bot:") and "]" in name:
        rest = name.split("]", 1)[1].strip()
        return rest or name
    return name


def _read_mcp(path: Path) -> list:
    if not path.is_file():
        return []
    raw = read_json(path)
    if not isinstance(raw, dict):
        return []
    servers = raw.get("mcpServers") or raw.get("servers") or raw
    if not isinstance(servers, dict):
        return []
    connectors = []
    for server_id, config in servers.items():
        if server_id in {"mcpServers", "servers"}:
            continue
        if not isinstance(config, dict):
            config = {}
        connectors.append(connector_from_mcp(str(server_id), config))
    return connectors


def _read_memories(root: Path) -> list[Memory]:
    memories: list[Memory] = []
    user = root / "USER.md"
    if user.is_file():
        text = read_text(user).strip()
        if text:
            memories.extend(_split_memory_blocks(text, "profile"))
    memory_md = root / "MEMORY.md"
    if memory_md.is_file():
        text = read_text(memory_md).strip()
        if text:
            memories.extend(_split_memory_blocks(text, "log"))
    mem_dir = root / "memories"
    if mem_dir.is_dir():
        for md in sorted(mem_dir.rglob("*.md")):
            text = read_text(md).strip()
            if not text or _looks_like_episode(text):
                continue
            kind = "log" if "log" in md.name.lower() or _dated_name(md.name) else "profile"
            memories.extend(_split_memory_blocks(text, kind))
    return memories


def _split_memory_blocks(text: str, kind: str) -> list[Memory]:
    items: list[Memory] = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        if not stripped or stripped.startswith("#"):
            continue
        created = None
        if stripped.startswith("(") and ")" in stripped[:12]:
            maybe_date = stripped[1:11]
            if len(maybe_date) == 10 and maybe_date[4] == "-":
                created = maybe_date
                stripped = stripped[12:].strip()
        items.append(Memory(kind=kind, content=stripped, created_at=created))  # type: ignore[arg-type]
    return items


def _looks_like_episode(text: str) -> bool:
    lowered = text[:400].lower()
    return "user:" in lowered and ("assistant:" in lowered or "hermes:" in lowered)


def _dated_name(name: str) -> bool:
    return bool(_DATED_NAME.match(name))


def _merge_extras(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged
