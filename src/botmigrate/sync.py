"""Apply portable fields onto an existing destination. Dry-run unless `apply`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from botmigrate import platforms
from botmigrate.convert import write_bot
from botmigrate.formats import FormatKind
from botmigrate.ir.extras import merge_extras
from botmigrate.ir.models import PortableBot, Routine, Skill
from botmigrate.ir.restore import snapshot_extras
from botmigrate.load import load_bot
from botmigrate.report import write_migration_md


@dataclass(frozen=True)
class SyncResult:
    bot: PortableBot
    dest_kind: FormatKind
    dst: Path
    applied: bool
    changes: list[str] = field(default_factory=list)


def sync(
    src: Path,
    dst: Path,
    *,
    apply: bool = False,
    to: str | None = None,
    from_: str | None = None,
    layout: str | None = None,
    memories: bool | None = None,
    skills_dir: Path | None = None,
) -> SyncResult:
    """Merge `src` onto `dst`. Destination-only skills, routines, secrets, and user data are kept."""
    source, source_kind = load_bot(src, from_, skills_dir=skills_dir)
    existing = _existing_kind(dst)
    dest_kind = platforms.target_kind(
        dst, source_kind=source_kind, to=to, layout=layout, existing=existing
    )
    include = platforms.writes_memories_by_default(dest_kind) if memories is None else memories

    dest = load_bot(dst, platforms.platform_of(existing))[0] if existing else None
    merged = snapshot_extras(merge_bots(source, dest, include_memories=include))
    changes = diff_bots(dest, merged)
    changes.append(
        "Destination-only secrets and user data (.env, auth.json, sessions/) are never written."
    )

    if not apply:
        changes.append("Dry-run: no files written (pass --apply to write).")
        return SyncResult(merged, dest_kind, dst, False, changes)

    write_bot(merged, dst, dest_kind, include_memories=include)
    write_migration_md(
        dst, merged, source_kind=source_kind, dest_kind=dest_kind, include_memories=include
    )
    changes.append(f"Wrote {dest_kind.value} to {dst}")
    return SyncResult(merged, dest_kind, dst, True, changes)


def _existing_kind(dst: Path) -> FormatKind | None:
    """Kind already at `dst`, or None when it is missing or an empty directory.

    Anything else that is not recognised raises, so sync never writes over
    files it does not understand.
    """
    if not dst.exists() or (dst.is_dir() and not any(dst.iterdir())):
        return None
    return platforms.detect(dst)


def merge_bots(
    src: PortableBot, dest: PortableBot | None, *, include_memories: bool
) -> PortableBot:
    if dest is None:
        return src if include_memories else src.without_memories()
    identity = dest.identity.model_copy(
        update={
            key: getattr(src.identity, key) or getattr(dest.identity, key)
            for key in ("name", "slug", "title", "description", "soul")
        }
    )
    return PortableBot(
        identity=identity,
        memories=src.memories if include_memories else dest.memories,
        skills=_upsert(dest.skills, src.skills, key=lambda s: s.slug),
        routines=_upsert_routines(dest.routines, src.routines),
        connectors=_upsert(dest.connectors, src.connectors, key=lambda c: c.id),
        extras=merge_extras(dest.extras, src.extras),
        notes=list(
            dict.fromkeys(
                [*dest.notes, *src.notes, "Synced portable fields onto existing destination"]
            )
        ),
    ).sorted()


def _upsert(dest: list, src: list, *, key) -> list:
    merged = {key(item): item for item in dest}
    merged.update({key(item): item for item in src})
    return list(merged.values())


def _upsert_routines(dest: list[Routine], src: list[Routine]) -> list[Routine]:
    """Routines match by slug, or by name so a renamed slug updates the existing job."""
    merged = {r.slug: r for r in dest}
    slug_by_name = {r.name.lower(): r.slug for r in dest}
    for routine in src:
        slug = slug_by_name.get(routine.name.lower(), routine.slug)
        merged[slug] = routine.model_copy(update={"slug": slug})
    return list(merged.values())


def diff_bots(before: PortableBot | None, after: PortableBot) -> list[str]:
    if before is None:
        return [
            f"Would create identity: {after.identity.name}",
            f"Would add {len(after.skills)} skill(s), {len(after.routines)} routine(s)",
        ]
    lines: list[str] = []
    if before.identity.name != after.identity.name:
        lines.append(
            f"Would update identity.name: {before.identity.name!r} → {after.identity.name!r}"
        )
    if before.identity.soul != after.identity.soul:
        lines.append("Would update persona / SOUL.md")
    lines += _diff_items("skill", before.skills, after.skills, _skill_changed)
    lines += _diff_items("routine", before.routines, after.routines, _routine_changed)
    return lines or ["No portable-field changes detected."]


def _diff_items(label: str, before: list, after: list, changed) -> list[str]:
    old = {item.slug: item for item in before}
    new = {item.slug: item for item in after}
    lines = [f"Would add {label}: {slug}" for slug in sorted(new.keys() - old.keys())]
    lines += [
        f"Would update {label}: {slug}"
        for slug in sorted(old.keys() & new.keys())
        if changed(old[slug], new[slug])
    ]
    lines += [f"Would keep dest-only {label}: {slug}" for slug in sorted(old.keys() - new.keys())]
    return lines


def _skill_changed(a: Skill, b: Skill) -> bool:
    return a.content != b.content or a.description != b.description


def _routine_changed(a: Routine, b: Routine) -> bool:
    cron = lambda r: r.schedule.cron if r.schedule else None
    return a.prompt != b.prompt or cron(a) != cron(b)
