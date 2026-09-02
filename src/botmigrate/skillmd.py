"""agentskills.io SKILL.md parse/write (YAML frontmatter + markdown body)."""

from __future__ import annotations

from pathlib import Path

import yaml

from botmigrate.ids import is_skill_name, kebab
from botmigrate.io import read_text, write_text


def parse_skill_md(text: str) -> tuple[dict[str, str], str]:
    stripped = text.lstrip("\ufeff")
    if not stripped.startswith("---"):
        return {}, stripped.strip() + ("\n" if stripped.strip() else "")
    rest = stripped[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return {}, stripped.strip() + "\n"
    raw_meta = rest[:end]
    body = rest[end + 4 :].lstrip("\n")
    meta = yaml.safe_load(raw_meta) or {}
    if not isinstance(meta, dict):
        meta = {}
    clean = {str(k): "" if v is None else str(v) if not isinstance(v, str) else v for k, v in meta.items()}
    return clean, body


def render_skill_md(name: str, description: str, body: str, extra: dict[str, str] | None = None) -> str:
    front_name = name if is_skill_name(name) else kebab(name, fallback="skill")
    lines = ["---", f"name: {front_name}", f"description: {description}"]
    for key, value in (extra or {}).items():
        if key in {"name", "description"} or not value:
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    content = body.strip("\n")
    if content:
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def read_skill_dir(skill_dir: Path) -> tuple[dict[str, str], str] | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    return parse_skill_md(read_text(skill_md))


def write_skill_dir(root: Path, slug: str, name: str, description: str, body: str) -> None:
    write_text(root / slug / "SKILL.md", render_skill_md(name, description, body))
