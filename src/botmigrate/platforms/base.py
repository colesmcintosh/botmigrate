"""The contract a platform adapter fulfils.

An adapter turns on-disk files into the portable IR and back. Adapters only
know about the IR and the shared helpers; they never call each other.
To add a platform, create `platforms/<name>/` exposing an `ADAPTER` and
register it in `platforms/__init__.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from botmigrate.formats import FormatKind
from botmigrate.ir.models import PortableBot


class Reader(Protocol):
    def __call__(self, path: Path, *, skills_dir: Path | None = None) -> PortableBot: ...


class Writer(Protocol):
    def __call__(self, bot: PortableBot, out: Path, *, include_memories: bool) -> None: ...


@dataclass(frozen=True)
class Adapter:
    name: str
    """CLI value for --from / --to, e.g. "grok"."""

    detect: Callable[[Path], FormatKind | None]
    """Return the kind at `path` if this adapter recognises it, else None."""

    read: Reader
    """Read any of `readable` into the IR. Always reads memories; callers strip."""

    writers: dict[FormatKind, Writer]
    """One writer per kind this adapter can produce."""

    layouts: dict[str, FormatKind]
    """Names accepted by --layout, mapped to the kind they produce."""

    default_kind: Callable[[Path], FormatKind]
    """Kind to write when no --layout is given, chosen from the output path."""

    readable: tuple[FormatKind, ...]
    """Kinds `read` accepts (a superset of `writers`)."""

    no_memories_by_default: frozenset[FormatKind] = field(default_factory=frozenset)
    """Kinds meant to be shared, so memories stay out unless --memories is passed."""

    @property
    def kinds(self) -> tuple[FormatKind, ...]:
        return tuple(dict.fromkeys([*self.readable, *self.writers]))

    def owns(self, kind: FormatKind) -> bool:
        return kind in self.kinds

    def write(
        self, bot: PortableBot, out: Path, kind: FormatKind, *, include_memories: bool
    ) -> None:
        writer = self.writers.get(kind)
        if writer is None:
            raise ValueError(f"{self.name} cannot write {kind.value}")
        writer(bot, out, include_memories=include_memories)
