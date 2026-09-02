from pathlib import Path

import yaml
from typer.testing import CliRunner

from botmigrate.cli import app
from botmigrate.io import read_json

runner = CliRunner()


def test_grok_share_to_hermes_distribution(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "research-bot"
    result = runner.invoke(
        app,
        [
            "convert",
            "--from",
            "grok",
            "--to",
            "hermes",
            "--src",
            str(fixtures / "grok_share.json"),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    dist = yaml.safe_load((out / "distribution.yaml").read_text())
    assert dist["name"] == "research-bot"
    assert "arXiv" in dist["description"]
    soul = (out / "SOUL.md").read_text()
    assert "Research" in soul
    skill = (out / "skills" / "arxiv-brief" / "SKILL.md").read_text()
    assert "one-page brief" in skill
    cron = read_json(out / "cron" / "weekly-digest.json")
    assert cron["name"] == "Weekly digest"
    assert cron["prompt"].startswith("Summarize new arXiv")
    assert cron["schedule"]["expr"] == "0 9 * * 1"
    assert cron["enabled"] is False
    assert (out / "MIGRATION.md").is_file()
    assert (out / ".botmigrate.json").is_file()
    assert (out / ".gitignore").is_file()
    mcp = read_json(out / "mcp.json")
    assert "github" in mcp["mcpServers"]
    assert not (out / "USER.md").exists()
    assert not (out / "MEMORY.md").exists()


def test_hermes_distribution_to_grok_share(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "research-bot.json"
    result = runner.invoke(
        app,
        [
            "convert",
            "--from",
            "hermes",
            "--to",
            "grok",
            "--src",
            str(fixtures / "hermes_dist"),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    share = read_json(out)
    assert share["profile"]["title"] == "Research specialist"
    assert any(s["name"] == "arxiv-brief" for s in share["skills"])
    skill = next(s for s in share["skills"] if "arxiv" in s["name"])
    assert "one-page brief" in skill["content"]
    routine = next(r for r in share["routines"] if r["slug"] == "weekly-digest")
    assert "Summarize new arXiv" in routine["content"]
    assert any(p["pluginId"] == "github" for p in share["plugins"])
    assert (out.parent / "MIGRATION.md").is_file()
