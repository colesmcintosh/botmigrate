"""Memory bullets: `- (YYYY-MM-DD) fact` lines.

Grok `memory/*.md` and Hermes `USER.md` / `MEMORY.md` share this shape.
"""

from __future__ import annotations

import re

from botmigrate.ir.models import Memory, MemoryKind

_LINE = re.compile(r"^(?:-\s*)?(?:\((\d{4}-\d{2}-\d{2})\)\s*)?(.*)$")


def parse_memory_lines(text: str, kind: MemoryKind) -> list[Memory]:
    """One memory per non-empty, non-heading line. A leading `(date)` becomes `created_at`."""
    items: list[Memory] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE.match(line)
        created, content = (match.group(1), match.group(2).strip()) if match else (None, line)
        if content:
            items.append(Memory(kind=kind, content=content, created_at=created))
    return items


def render_memory_line(memory: Memory) -> str:
    if memory.created_at:
        return f"- ({memory.created_at}) {memory.content}"
    return f"- {memory.content}"
