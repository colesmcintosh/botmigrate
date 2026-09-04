from pathlib import Path

import yaml
from conftest import cli

from botmigrate.io import read_json


def test_grok_share_to_hermes_distribution(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "research-bot"
    result = cli("convert", fixtures / "grok_share.json", out)
    assert result.exit_code == 0, result.output
    assert "grok-share-json → hermes-distribution" in result.stdout
    dist = yaml.safe_load((out / "distribution.yaml").read_text())
    assert dist["name"] == "research-bot"
    assert "arXiv" in dist["description"]
    assert "Research" in (out / "SOUL.md").read_text()
    assert "one-page brief" in (out / "skills" / "arxiv-brief" / "SKILL.md").read_text()
    cron = read_json(out / "cron" / "weekly-digest.json")
    assert cron["name"] == "Weekly digest"
    assert cron["prompt"].startswith("Summarize new arXiv")
    assert cron["schedule"]["expr"] == "0 9 * * 1"
    assert cron["enabled"] is False
    assert (out / "MIGRATION.md").is_file()
    assert (out / ".botmigrate.json").is_file()
    assert (out / ".gitignore").is_file()
    assert "github" in read_json(out / "mcp.json")["mcpServers"]
    assert not (out / "USER.md").exists()
    assert not (out / "MEMORY.md").exists()


def test_hermes_distribution_to_grok_share(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "research-bot.json"
    result = cli("convert", fixtures / "hermes_dist", out)
    assert result.exit_code == 0, result.output
    share = read_json(out)
    assert share["profile"]["title"] == "Research specialist"
    skill = next(s for s in share["skills"] if "arxiv" in s["name"])
    assert "one-page brief" in skill["content"]
    routine = next(r for r in share["routines"] if r["slug"] == "weekly-digest")
    assert "Summarize new arXiv" in routine["content"]
    assert any(p["pluginId"] == "github" for p in share["plugins"])
    assert (out.parent / "MIGRATION.md").is_file()


def test_explicit_from_and_to_still_work(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = cli("convert", fixtures / "grok_share.json", out, "--from", "grok", "--to", "hermes")
    assert result.exit_code == 0, result.output
    assert (out / "distribution.yaml").is_file()


def test_wrong_from_is_an_error(fixtures: Path, tmp_path: Path) -> None:
    result = cli("convert", fixtures / "grok_share.json", tmp_path / "out", "--from", "hermes")
    assert result.exit_code != 0
    assert "expected a hermes source" in result.output


def test_memories_flag_writes_user_md(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "with-memories"
    result = cli("convert", fixtures / "grok_share.json", out, "--memories")
    assert result.exit_code == 0, result.output
    assert (out / "USER.md").is_file() or (out / "MEMORY.md").is_file()


def test_layout_profile_writes_jobs_json(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "profile"
    result = cli("convert", fixtures / "grok_share.json", out, "--layout", "profile")
    assert result.exit_code == 0, result.output
    assert (out / "cron" / "jobs.json").is_file()


def test_unknown_layout_is_an_error(fixtures: Path, tmp_path: Path) -> None:
    result = cli("convert", fixtures / "grok_share.json", tmp_path / "out", "--layout", "share")
    assert result.exit_code != 0
    assert "hermes has no layout 'share'" in result.output
