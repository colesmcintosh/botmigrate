"""Hermes Agent: profile distribution, live profile tree, or export tarball."""

from __future__ import annotations

from pathlib import Path

from botmigrate.formats import FormatKind
from botmigrate.platforms.base import Adapter
from botmigrate.platforms.hermes.read import detect, read
from botmigrate.platforms.hermes.write import write_distribution, write_profile


def default_kind(out: Path) -> FormatKind:
    del out
    return FormatKind.hermes_distribution


ADAPTER = Adapter(
    name="hermes",
    detect=detect,
    read=read,
    writers={
        FormatKind.hermes_distribution: write_distribution,
        FormatKind.hermes_profile: write_profile,
    },
    layouts={"distribution": FormatKind.hermes_distribution, "profile": FormatKind.hermes_profile},
    default_kind=default_kind,
    readable=(FormatKind.hermes_distribution, FormatKind.hermes_profile, FormatKind.hermes_tarball),
    no_memories_by_default=frozenset({FormatKind.hermes_distribution}),
)

__all__ = ["ADAPTER", "read", "write_distribution", "write_profile"]
