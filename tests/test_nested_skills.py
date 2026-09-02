"""Live Hermes profiles nest skills under a category directory."""

from pathlib import Path

from botmigrate.hermes.read import MAX_SKILL_DEPTH, _read_skills


def _write_skill(path: Path, name: str, description: str = "d") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nBody of {name}.\n"
    )


def test_reads_flat_layout(tmp_path: Path) -> None:
    _write_skill(tmp_path / "arxiv-brief", "arxiv-brief")
    assert [s.slug for s in _read_skills(tmp_path)] == ["arxiv-brief"]


def test_reads_nested_category_layout(tmp_path: Path) -> None:
    _write_skill(tmp_path / "apple" / "imessage", "imessage")
    _write_skill(tmp_path / "apple" / "findmy", "findmy")
    _write_skill(tmp_path / "research" / "arxiv-brief", "arxiv-brief")
    assert sorted(s.slug for s in _read_skills(tmp_path)) == [
        "arxiv-brief",
        "findmy",
        "imessage",
    ]


def test_mixed_flat_and_nested(tmp_path: Path) -> None:
    _write_skill(tmp_path / "top-level", "top-level")
    _write_skill(tmp_path / "apple" / "imessage", "imessage")
    assert sorted(s.slug for s in _read_skills(tmp_path)) == ["imessage", "top-level"]


def test_content_survives_nesting(tmp_path: Path) -> None:
    _write_skill(tmp_path / "apple" / "imessage", "imessage", description="Send texts")
    skill = _read_skills(tmp_path)[0]
    assert skill.description == "Send texts"
    assert "Body of imessage." in skill.content


def test_colliding_names_are_both_kept(tmp_path: Path) -> None:
    _write_skill(tmp_path / "github" / "issues", "issues")
    _write_skill(tmp_path / "linear" / "issues", "issues")
    slugs = sorted(s.slug for s in _read_skills(tmp_path))
    assert len(slugs) == 2, "a collision must not silently drop a skill"
    assert slugs == ["issues", "issues-2"]


def test_hidden_entries_are_skipped(tmp_path: Path) -> None:
    _write_skill(tmp_path / "real", "real")
    _write_skill(tmp_path / ".curator_state" / "cached", "cached")
    assert [s.slug for s in _read_skills(tmp_path)] == ["real"]


def test_depth_is_capped(tmp_path: Path) -> None:
    deep = tmp_path
    for i in range(MAX_SKILL_DEPTH + 3):
        deep = deep / f"lvl{i}"
    _write_skill(deep, "too-deep")
    assert _read_skills(tmp_path) == []


def test_category_without_skills_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "empty-category").mkdir()
    assert _read_skills(tmp_path) == []


def test_source_path_is_recorded_for_nested_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path / "apple" / "imessage", "imessage")
    assert _read_skills(tmp_path)[0].source_path == "apple/imessage"


def test_source_path_is_empty_for_flat_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path / "arxiv-brief", "arxiv-brief")
    assert _read_skills(tmp_path)[0].source_path == ""


def test_profile_write_keeps_skill_in_its_category(tmp_path: Path) -> None:
    """Syncing a live profile must not leave a flat copy beside the original."""
    from botmigrate.hermes.write import write_hermes_profile
    from botmigrate.ir.models import Identity, PortableBot, Skill

    bot = PortableBot(
        identity=Identity(name="bot", slug="bot"),
        skills=[
            Skill(slug="imessage", name="imessage", source_path="apple/imessage"),
            Skill(slug="arxiv-brief", name="arxiv-brief"),
        ],
    )
    out = tmp_path / "profile"
    write_hermes_profile(bot, out, include_memories=False)
    written = sorted(p.relative_to(out).as_posix() for p in out.glob("skills/**/SKILL.md"))
    assert written == ["skills/apple/imessage/SKILL.md", "skills/arxiv-brief/SKILL.md"]


def test_distribution_write_flattens_skills(tmp_path: Path) -> None:
    from botmigrate.hermes.write import write_hermes_distribution
    from botmigrate.ir.models import Identity, PortableBot, Skill

    bot = PortableBot(
        identity=Identity(name="bot", slug="bot"),
        skills=[Skill(slug="imessage", name="imessage", source_path="apple/imessage")],
    )
    out = tmp_path / "dist"
    write_hermes_distribution(bot, out, include_memories=False)
    written = [p.relative_to(out).as_posix() for p in out.glob("skills/**/SKILL.md")]
    assert written == ["skills/imessage/SKILL.md"]
