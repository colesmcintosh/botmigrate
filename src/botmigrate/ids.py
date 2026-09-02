"""Stable slugs and ids."""

from __future__ import annotations

import hashlib
import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_HYPHEN = re.compile(r"-{2,}")


def kebab(value: str, fallback: str = "item") -> str:
    text = _NON_ALNUM.sub("-", value.strip().lower()).strip("-")
    text = _MULTI_HYPHEN.sub("-", text)
    return text[:64] or fallback


def skill_name(slug: str) -> str:
    """agentskills.io frontmatter name: lowercase, digits, hyphens."""
    return kebab(slug, fallback="skill")


def stable_id(seed: str, length: int = 12) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:length]


def is_skill_name(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value)) and 1 <= len(value) <= 64
