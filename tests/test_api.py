"""Python API and the pieces shared between platform adapters."""

from pathlib import Path

import pytest

from botmigrate import FormatKind, convert, load_bot, platforms, sync
from botmigrate.errors import UsageError
from botmigrate.memorymd import parse_memory_lines, render_memory_line


def test_convert_and_sync_from_python(fixtures: Path, tmp_path: Path) -> None:
    result = convert(fixtures / "grok_share.json", tmp_path / "bot")
    assert result.dest_kind is FormatKind.hermes_distribution
    assert result.memories is False
    plan = sync(fixtures / "hermes_dist", tmp_path / "bot")
    assert plan.applied is False
    assert any(line.startswith("Would") for line in plan.changes)


def test_load_bot_strips_memories_on_request(fixtures: Path) -> None:
    with_memories, _ = load_bot(fixtures / "grok_dir")
    without, _ = load_bot(fixtures / "grok_dir", memories=False)
    assert with_memories.memories and not without.memories


def test_target_defaults_to_other_platform(tmp_path: Path) -> None:
    assert (
        platforms.target_kind(tmp_path / "x", source_kind=FormatKind.grok_share)
        is FormatKind.hermes_distribution
    )
    assert (
        platforms.target_kind(tmp_path / "x.json", source_kind=FormatKind.hermes_profile)
        is FormatKind.grok_share
    )
    assert (
        platforms.target_kind(tmp_path / "x", source_kind=FormatKind.hermes_profile)
        is FormatKind.grok_directory
    )


def test_target_keeps_existing_kind(tmp_path: Path) -> None:
    kind = platforms.target_kind(
        tmp_path / "x", source_kind=FormatKind.grok_share, existing=FormatKind.hermes_profile
    )
    assert kind is FormatKind.hermes_profile


def test_layout_overrides_existing_kind(tmp_path: Path) -> None:
    kind = platforms.target_kind(
        tmp_path / "x",
        source_kind=FormatKind.grok_share,
        existing=FormatKind.hermes_distribution,
        layout="profile",
    )
    assert kind is FormatKind.hermes_profile


def test_unknown_platform_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(UsageError):
        platforms.target_kind(tmp_path / "x", source_kind=FormatKind.grok_share, to="openai")


def test_every_kind_has_exactly_one_owner() -> None:
    for kind in FormatKind:
        owners = [a.name for a in platforms.ADAPTERS.values() if a.owns(kind)]
        assert len(owners) == 1, (kind, owners)


def test_memory_lines_roundtrip() -> None:
    text = "# Facts\n\n- (2024-05-01) Likes tea\n- Prefers short answers\nplain line\n"
    memories = parse_memory_lines(text, "profile")
    assert [(m.content, m.created_at) for m in memories] == [
        ("Likes tea", "2024-05-01"),
        ("Prefers short answers", None),
        ("plain line", None),
    ]
    assert render_memory_line(memories[0]) == "- (2024-05-01) Likes tea"
    assert render_memory_line(memories[1]) == "- Prefers short answers"
