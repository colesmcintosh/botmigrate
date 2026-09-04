"""Read Hermes distributions, live profiles, and export tarballs."""

from __future__ import annotations

import re
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from botmigrate.connectors import connector_from_mcp
from botmigrate.errors import MissingRequiredFileError, SecretCopyError
from botmigrate.formats import FormatKind
from botmigrate.ids import kebab
from botmigrate.io import read_json, read_text, read_yaml
from botmigrate.ir.extras import merge_extras
from botmigrate.ir.models import Connector, Identity, Memory, PortableBot, Routine, Skill
from botmigrate.memorymd import parse_memory_lines
from botmigrate.platforms.hermes.models import HermesDistribution
from botmigrate.schedule import schedule_from_hermes
from botmigrate.secrets import is_secret_filename, is_secret_path, strip_secrets
from botmigrate.sidecar import load_sidecar
from botmigrate.skillmd import parse_skill_md, read_skill_dir

LIVE_MARKERS = frozenset({"MEMORY.md", "USER.md", "memories", "sessions", "state.db"})
"""Files that only exist in a live profile, never in a shareable distribution."""

MAX_SKILL_DEPTH = 4
"""How far to descend into `skills/` looking for skill directories.

Distributions keep skills flat (`skills/<slug>/SKILL.md`), but live Hermes
profiles group them under a category (`skills/<category>/<slug>/SKILL.md`).
The cap also bounds recursion if a symlink points back up the tree.
"""

_DATED_NAME = re.compile(r"\d{4}-\d{2}")


def detect(path: Path) -> FormatKind | None:
    if path.is_file():
        return FormatKind.hermes_tarball if _is_tarball(path) else None
    names = {p.name for p in path.iterdir()}
    if "distribution.yaml" in names:
        return FormatKind.hermes_profile if names & LIVE_MARKERS else FormatKind.hermes_distribution
    if "SOUL.md" in names or ("config.yaml" in names and names & {"skills", "cron"}):
        return FormatKind.hermes_profile
    return None


def read(path: Path, *, skills_dir: Path | None = None) -> PortableBot:
    del skills_dir  # Grok-only option; Hermes skills always live inside the profile
    path = path.expanduser().resolve()
    if _is_tarball(path):
        return _read_tarball(path)
    if path.is_file():
        raise MissingRequiredFileError(
            str(path),
            "Hermes distribution directory, live profile, or .tar.gz export",
            f"file {path.name}",
        )
    if not path.is_dir():
        raise MissingRequiredFileError(str(path), "a Hermes profile directory", "nothing")
    return _read_directory(path)


def _is_tarball(path: Path) -> bool:
    return path.is_file() and path.name.lower().endswith((".tar.gz", ".tgz"))


def _read_tarball(path: Path) -> PortableBot:
    with tarfile.open(path, "r:*") as archive:
        members = archive.getmembers()
        secret = [m.name for m in members if is_secret_filename(Path(m.name).name)]
        if secret:
            # Exports should already omit these; refuse rather than extract them.
            raise SecretCopyError(str(path), f"tarball contains {', '.join(secret[:4])}")
        with tempfile.TemporaryDirectory(prefix="botmigrate-hermes-") as tmp:
            safe = [m for m in members if _safe_tar_member(m)]
            try:
                archive.extractall(tmp, members=safe, filter="data")
            except TypeError:  # Python < 3.11.4 has no extraction filter
                archive.extractall(tmp, members=safe)
            extracted = Path(tmp)
            root = _single_root(extracted) or extracted
            bot = _read_directory(root)
            return bot.model_copy(
                update={"notes": [*bot.notes, f"Read Hermes export tarball {path.name}"]}
            )


def _single_root(extracted: Path) -> Path | None:
    """Exports usually wrap the profile in one top-level folder."""
    if (extracted / "SOUL.md").exists() or (extracted / "distribution.yaml").exists():
        return None
    dirs = [p for p in extracted.iterdir() if p.is_dir()]
    return dirs[0] if len(dirs) == 1 else None


def _safe_tar_member(member: tarfile.TarInfo) -> bool:
    name = Path(member.name)
    return not (name.is_absolute() or ".." in name.parts or is_secret_path(name))


def _read_directory(path: Path) -> PortableBot:
    dist = _read_manifest(path / "distribution.yaml")
    soul = read_text(path / "SOUL.md").strip() if (path / "SOUL.md").is_file() else ""
    title, role = _soul_title_and_role(soul)
    name = dist.name if dist else path.name
    identity = Identity(
        name=_display_name(name, title),
        slug=kebab(name, fallback="bot"),
        title=title,
        description=(dist.description if dist else "") or role,
        soul=soul,
    )

    extras: dict[str, Any] = {"hermes": {}}
    if dist:
        extras["hermes"]["distribution"] = dist.model_dump()
    if (path / "config.yaml").is_file():
        extras["hermes"]["config"] = strip_secrets(read_yaml(path / "config.yaml"))
    sidecar = load_sidecar(path)
    if sidecar:
        extras = merge_extras(sidecar.extras, extras)

    return PortableBot(
        identity=identity,
        memories=_read_memories(path),
        skills=_read_skills(path / "skills"),
        routines=_read_cron(path / "cron"),
        connectors=_read_mcp(path / "mcp.json"),
        extras=extras,
        notes=[f"Read Hermes profile {path.name}"],
    ).sorted()


def _read_manifest(path: Path) -> HermesDistribution | None:
    if not path.is_file():
        return None
    raw = read_yaml(path)
    if not isinstance(raw, dict) or not raw.get("name"):
        raise MissingRequiredFileError(
            str(path), "distribution.yaml with a name field", "incomplete manifest"
        )
    return HermesDistribution.model_validate(raw)


def _display_name(slug_or_name: str, title: str) -> str:
    """A kebab-case manifest name is an id, so prefer the SOUL.md heading for display."""
    if slug_or_name != kebab(slug_or_name):
        return slug_or_name
    return title or slug_or_name


def _soul_title_and_role(soul: str) -> tuple[str, str]:
    title = ""
    paragraphs: list[str] = []
    for line in soul.splitlines():
        stripped = line.strip()
        if not title and stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
        elif stripped and not stripped.startswith("#"):
            paragraphs.append(stripped)
    return title, paragraphs[0] if paragraphs else ""


def _read_skills(root: Path) -> list[Skill]:
    skills: list[Skill] = []
    if root.is_dir():
        _collect_skills(root, skills, depth=0, skills_root=root)
    return skills


def _collect_skills(root: Path, skills: list[Skill], *, depth: int, skills_root: Path) -> None:
    for child in sorted(root.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_file():
            if child.name == "SKILL.md":
                meta, body = parse_skill_md(read_text(child))
                slug = kebab(meta.get("name") or child.parent.name, fallback="skill")
                _append_skill(skills, slug, meta.get("name") or slug, meta, body, "")
            continue
        parsed = read_skill_dir(child)
        if parsed:
            meta, body = parsed
            relative = child.relative_to(skills_root).as_posix()
            _append_skill(
                skills,
                kebab(child.name, fallback="skill"),
                meta.get("name") or child.name,
                meta,
                body,
                relative if relative != child.name else "",
            )
        elif depth < MAX_SKILL_DEPTH:
            _collect_skills(child, skills, depth=depth + 1, skills_root=skills_root)


def _append_skill(
    skills: list[Skill], slug: str, name: str, meta: dict[str, str], body: str, source_path: str
) -> None:
    """Add a skill, qualifying the slug if a same-named skill already exists.

    Categories are flattened away, so two categories can hold skills with the
    same directory name. Later writes key off the slug, so a collision would
    silently drop one of them.
    """
    taken = {s.slug for s in skills}
    base, counter = slug, 2
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


def _read_cron(cron_dir: Path) -> list[Routine]:
    """`cron/jobs.json` (live) wins over per-job `cron/<slug>.json` (distribution)."""
    if not cron_dir.is_dir():
        return []
    routines: dict[str, Routine] = {}
    jobs_path = cron_dir / "jobs.json"
    if jobs_path.is_file():
        for job in _iter_jobs(read_json(jobs_path)):
            routine = _job_to_routine(job)
            routines[routine.slug] = routine
    for path in sorted(cron_dir.glob("*.json")):
        if path == jobs_path:
            continue
        raw = read_json(path)
        if isinstance(raw, dict):
            routine = _job_to_routine(raw, slug_hint=path.stem)
            routines.setdefault(routine.slug, routine)
    return list(routines.values())


def _iter_jobs(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        if isinstance(raw.get("jobs"), list):
            raw = raw["jobs"]
        elif "name" in raw or "prompt" in raw:
            raw = [raw]
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _job_to_routine(job: dict[str, Any], slug_hint: str | None = None) -> Routine:
    name = _strip_bot_prefix(str(job.get("name") or slug_hint or "routine"))
    schedule = schedule_from_hermes(job.get("schedule"))
    description = str(job.get("description") or "")
    if not description and schedule:
        if schedule.kind == "cron" and schedule.cron:
            description = f"Scheduled cron job ({schedule.cron})."
        else:
            description = f"Scheduled job ({schedule.display or schedule.kind})."
    if schedule:
        keep = {
            k: job[k]
            for k in ("id", "deliver", "skills", "script", "model")
            if job.get(k) is not None
        }
        schedule.original = {**schedule.original, "hermes_job": keep}
    return Routine(
        slug=kebab(slug_hint or name, fallback="routine"),
        name=name,
        description=description,
        prompt=str(job.get("prompt") or ""),
        schedule=schedule,
        enabled=False,
    )


def _strip_bot_prefix(name: str) -> str:
    if name.startswith("[bot:") and "]" in name:
        return name.split("]", 1)[1].strip() or name
    return name


def _read_mcp(path: Path) -> list[Connector]:
    if not path.is_file():
        return []
    raw = read_json(path)
    if not isinstance(raw, dict):
        return []
    servers = raw.get("mcpServers") or raw.get("servers") or raw
    if not isinstance(servers, dict):
        return []
    return [
        connector_from_mcp(str(server_id), config if isinstance(config, dict) else {})
        for server_id, config in servers.items()
        if server_id not in {"mcpServers", "servers"}
    ]


def _read_memories(root: Path) -> list[Memory]:
    memories: list[Memory] = []
    if (root / "USER.md").is_file():
        memories.extend(parse_memory_lines(read_text(root / "USER.md"), "profile"))
    if (root / "MEMORY.md").is_file():
        memories.extend(parse_memory_lines(read_text(root / "MEMORY.md"), "log"))
    mem_dir = root / "memories"
    if mem_dir.is_dir():
        for md in sorted(mem_dir.rglob("*.md")):
            text = read_text(md)
            if _looks_like_transcript(text):
                continue
            is_log = "log" in md.name.lower() or bool(_DATED_NAME.match(md.name))
            memories.extend(parse_memory_lines(text, "log" if is_log else "profile"))
    return memories


def _looks_like_transcript(text: str) -> bool:
    lowered = text[:400].lower()
    return "user:" in lowered and ("assistant:" in lowered or "hermes:" in lowered)
