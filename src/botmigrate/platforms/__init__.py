"""Registry of platform adapters. This is the only place that lists them."""

from __future__ import annotations

from pathlib import Path

from botmigrate.errors import UnknownFormatError, UsageError
from botmigrate.formats import FormatKind
from botmigrate.io import list_names
from botmigrate.platforms.base import Adapter
from botmigrate.platforms.grok import ADAPTER as GROK
from botmigrate.platforms.hermes import ADAPTER as HERMES
from botmigrate.secrets import assert_src_not_secret_file

# Detection runs in this order; the first adapter to recognise a path wins.
ADAPTERS: dict[str, Adapter] = {a.name: a for a in (HERMES, GROK)}


def names() -> list[str]:
    return sorted(ADAPTERS)


def adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]
    except KeyError:
        raise UsageError(f"unknown platform {name!r}; choose one of {', '.join(names())}") from None


def adapter_for(kind: FormatKind) -> Adapter:
    for candidate in ADAPTERS.values():
        if candidate.owns(kind):
            return candidate
    raise ValueError(f"no adapter owns {kind.value}")


def platform_of(kind: FormatKind) -> str:
    return adapter_for(kind).name


def layout_help() -> str:
    parts = [f"{a.name}: {'|'.join(a.layouts)}" for a in ADAPTERS.values()]
    return "; ".join(sorted(parts))


def detect(path: Path, platform: str | None = None) -> FormatKind:
    """Detect the format at `path`. `platform` asserts which adapter must own it."""
    path = path.expanduser().resolve()
    assert_src_not_secret_file(path)
    if not path.exists():
        raise UnknownFormatError(str(path), "path does not exist")
    for candidate in ADAPTERS.values():
        kind = candidate.detect(path)
        if kind is None:
            continue
        if platform and candidate.name != platform:
            raise UnknownFormatError(str(path), f"{kind.value} (expected a {platform} source)")
        return kind
    found = f"file {path.name}" if path.is_file() else list_names(path)
    raise UnknownFormatError(str(path), found)


def other_platform(kind: FormatKind) -> Adapter:
    """The adapter to target when --to is omitted: the one that is not the source."""
    others = [a for a in ADAPTERS.values() if not a.owns(kind)]
    if len(others) != 1:
        raise UsageError("pass --to: more than one platform could be the target")
    return others[0]


def target_kind(
    out: Path,
    *,
    source_kind: FormatKind,
    to: str | None = None,
    layout: str | None = None,
    existing: FormatKind | None = None,
) -> FormatKind:
    """Decide what to write at `out`.

    An explicit --to / --layout wins. Otherwise an existing destination keeps
    its detected kind, and a fresh one targets the other platform.
    """
    if existing is not None and to and not adapter(to).owns(existing):
        raise UsageError(
            f"{out} is a {existing.value}; --to {to} would overwrite it with another platform"
        )
    if to:
        target = adapter(to)
    elif existing is not None:
        target = adapter_for(existing)
    else:
        target = other_platform(source_kind)
    if layout:
        try:
            return target.layouts[layout]
        except KeyError:
            raise UsageError(
                f"{target.name} has no layout {layout!r}; choose one of {', '.join(target.layouts)}"
            ) from None
    if existing is not None and target.owns(existing) and existing in target.writers:
        return existing
    return target.default_kind(out)


def writes_memories_by_default(kind: FormatKind) -> bool:
    return kind not in adapter_for(kind).no_memories_by_default
