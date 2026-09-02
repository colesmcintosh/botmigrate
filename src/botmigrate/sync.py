"""Apply portable fields onto an existing destination. Dry-run by default."""

from __future__ import annotations

from pathlib import Path

from botmigrate.convert import choose_dest_kind, resolve_include_memories, write_bot
from botmigrate.detect import detect
from botmigrate.formats import FormatKind
from botmigrate.ir.models import Connector, PortableBot, Routine, Skill
from botmigrate.ir.restore import restore_from_extras, snapshot_extras
from botmigrate.load import load_bot
from botmigrate.report import write_migration_md


def sync(
    *,
    src: Path,
    dst: Path,
    from_platform: str,
    to_platform: str,
    apply: bool,
    include_memories: bool,
    exclude_memories: bool,
    skills_dir: Path | None,
    hermes_layout: str | None,
) -> tuple[list[str], PortableBot | None]:
    src_bot, source_kind = load_bot(src, from_platform, include_memories=True, skills_dir=skills_dir)
    src_bot = restore_from_extras(src_bot)

    dest_kind = _dest_kind(dst, to_platform, hermes_layout)
    include = resolve_include_memories(
        dest_kind=dest_kind,
        include=include_memories,
        exclude=exclude_memories,
        command="sync",
    )

    dest_bot: PortableBot | None = None
    if dst.exists():
        dest_bot, _ = load_bot(dst, to_platform, include_memories=True, skills_dir=None)
        dest_bot = restore_from_extras(dest_bot)

    merged = merge_bots(src_bot, dest_bot, include_memories=include)
    merged = snapshot_extras(merged)
    changes = diff_bots(dest_bot, merged)
    changes.append("Destination-only secrets and user data (.env, auth.json, sessions/) are never written.")

    if not apply:
        changes.append("Dry-run: no files written (pass --apply to write).")
        return changes, merged

    write_bot(merged, dst, dest_kind, include_memories=include)
    write_migration_md(dst, merged, source_kind=source_kind, dest_kind=dest_kind, include_memories=include)
    changes.append(f"Wrote {dest_kind.value} to {dst}")
    return changes, merged


def _dest_kind(dst: Path, to_platform: str, hermes_layout: str | None) -> FormatKind:
    if dst.exists():
        try:
            return detect(dst)
        except Exception:
            pass
    return choose_dest_kind(to_platform, dst, hermes_layout)


def merge_bots(src: PortableBot, dest: PortableBot | None, *, include_memories: bool) -> PortableBot:
    if dest is None:
        if not include_memories:
            return src.model_copy(update={"memories": []})
        return src

    extras = dict(dest.extras)
    for key, value in src.extras.items():
        if key in extras and isinstance(extras[key], dict) and isinstance(value, dict):
            extras[key] = {**extras[key], **value}
        else:
            extras[key] = value

    identity = dest.identity.model_copy(
        update={
            "name": src.identity.name or dest.identity.name,
            "slug": src.identity.slug or dest.identity.slug,
            "title": src.identity.title or dest.identity.title,
            "description": src.identity.description or dest.identity.description,
            "soul": src.identity.soul or dest.identity.soul,
        }
    )
    memories = src.memories if include_memories else dest.memories
    return PortableBot(
        identity=identity,
        memories=memories,
        skills=_upsert_skills(dest.skills, src.skills),
        routines=_upsert_routines(dest.routines, src.routines),
        connectors=_upsert_connectors(dest.connectors, src.connectors),
        extras=extras,
        notes=list(dict.fromkeys([*dest.notes, *src.notes, "Synced portable fields onto existing destination"])),
    ).sorted()


def _upsert_skills(dest: list[Skill], src: list[Skill]) -> list[Skill]:
    by_slug = {s.slug: s for s in dest}
    for skill in src:
        by_slug[skill.slug] = skill
    return list(by_slug.values())


def _upsert_routines(dest: list[Routine], src: list[Routine]) -> list[Routine]:
    by_slug = {r.slug: r for r in dest}
    by_name = {r.name.lower(): r.slug for r in dest}
    for routine in src:
        key = by_name.get(routine.name.lower(), routine.slug)
        by_slug[key] = routine.model_copy(update={"slug": key})
    return list(by_slug.values())


def _upsert_connectors(dest: list[Connector], src: list[Connector]) -> list[Connector]:
    by_id = {c.id: c for c in dest}
    for connector in src:
        by_id[connector.id] = connector
    return list(by_id.values())


def diff_bots(before: PortableBot | None, after: PortableBot) -> list[str]:
    lines: list[str] = []
    if before is None:
        lines.append(f"Would create identity: {after.identity.name}")
        lines.append(f"Would add {len(after.skills)} skill(s), {len(after.routines)} routine(s)")
        return lines
    if before.identity.name != after.identity.name:
        lines.append(f"Would update identity.name: {before.identity.name!r} → {after.identity.name!r}")
    if before.identity.soul != after.identity.soul:
        lines.append("Would update persona / SOUL.md")
    before_skills = {s.slug for s in before.skills}
    after_skills = {s.slug for s in after.skills}
    for slug in sorted(after_skills - before_skills):
        lines.append(f"Would add skill: {slug}")
    for slug in sorted(before_skills & after_skills):
        b = next(s for s in before.skills if s.slug == slug)
        a = next(s for s in after.skills if s.slug == slug)
        if b.content != a.content or b.description != a.description:
            lines.append(f"Would update skill: {slug}")
    before_r = {r.slug: r for r in before.routines}
    after_r = {r.slug: r for r in after.routines}
    for slug in sorted(set(after_r) - set(before_r)):
        lines.append(f"Would add routine: {slug}")
    for slug in sorted(set(after_r) & set(before_r)):
        if before_r[slug].prompt != after_r[slug].prompt or (
            (before_r[slug].schedule.cron if before_r[slug].schedule else None)
            != (after_r[slug].schedule.cron if after_r[slug].schedule else None)
        ):
            lines.append(f"Would update routine: {slug}")
    dest_only = sorted(set(before_r) - set(after_r))
    for slug in dest_only:
        lines.append(f"Would keep dest-only routine: {slug}")
    if not lines:
        lines.append("No portable-field changes detected.")
    return lines
