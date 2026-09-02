"""Detect Grok vs Hermes layouts from a path."""

from __future__ import annotations

from pathlib import Path

from botmigrate.errors import UnknownFormatError
from botmigrate.formats import FormatKind
from botmigrate.io import read_json
from botmigrate.secrets import assert_src_not_secret_file


def detect(path: Path) -> FormatKind:
    path = path.expanduser().resolve()
    assert_src_not_secret_file(path)
    if not path.exists():
        raise UnknownFormatError(str(path), "path does not exist")
    if path.is_file():
        return _detect_file(path)
    return _detect_dir(path)


def _detect_file(path: Path) -> FormatKind:
    name = path.name.lower()
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        return FormatKind.hermes_tarball
    if name.endswith(".json"):
        try:
            raw = read_json(path)
        except Exception as exc:
            raise UnknownFormatError(str(path), f"invalid JSON ({exc})") from exc
        if isinstance(raw, dict) and isinstance(raw.get("profile"), dict) and raw["profile"].get("name"):
            return FormatKind.grok_share
        raise UnknownFormatError(str(path), "JSON without a Grok profile.name")
    raise UnknownFormatError(str(path), f"file {path.name}")


def _detect_dir(path: Path) -> FormatKind:
    names = {p.name for p in path.iterdir()}
    has_dist = "distribution.yaml" in names
    has_profile_json = "profile.json" in names
    has_soul = "SOUL.md" in names
    has_config = "config.yaml" in names
    live_markers = names & {"MEMORY.md", "USER.md", "memories", "sessions", "state.db"}
    has_skills_or_cron = "skills" in names or "cron" in names

    if has_profile_json and not has_dist and not has_soul:
        return FormatKind.grok_directory
    if has_dist and live_markers:
        return FormatKind.hermes_profile
    if has_dist:
        return FormatKind.hermes_distribution
    if has_soul or (has_config and has_skills_or_cron):
        return FormatKind.hermes_profile
    if has_profile_json:
        return FormatKind.grok_directory

    found = ", ".join(sorted(names)[:16]) or "an empty directory"
    raise UnknownFormatError(str(path), found)


def detect_platform(path: Path, forced: str | None) -> FormatKind:
    kind = detect(path)
    if forced == "grok" and kind not in {FormatKind.grok_share, FormatKind.grok_directory}:
        raise UnknownFormatError(str(path), f"{kind.value} (expected a Grok source)")
    if forced == "hermes" and kind not in {
        FormatKind.hermes_distribution,
        FormatKind.hermes_profile,
        FormatKind.hermes_tarball,
    }:
        raise UnknownFormatError(str(path), f"{kind.value} (expected a Hermes source)")
    return kind
