from pathlib import Path

from typer.testing import CliRunner

from botmigrate.cli import app
from botmigrate.io import read_json

runner = CliRunner()


def test_grok_share_roundtrip_keeps_name_skills_cron(fixtures: Path, tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    back = tmp_path / "back.json"
    first = runner.invoke(
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
            str(hermes),
        ],
    )
    assert first.exit_code == 0, first.output
    second = runner.invoke(
        app,
        [
            "convert",
            "--from",
            "hermes",
            "--to",
            "grok",
            "--src",
            str(hermes),
            "--out",
            str(back),
        ],
    )
    assert second.exit_code == 0, second.output
    share = read_json(back)
    assert share["profile"]["name"] == "Research Bot"
    skill = next(s for s in share["skills"] if "arxiv" in s["name"] or s["name"] == "arxiv-brief")
    assert "one-page brief" in skill["content"]
    routine = next(r for r in share["routines"] if r["slug"] == "weekly-digest")
    assert "Summarize new arXiv" in routine["content"]
    assert "0 9 * * 1" in routine["description"]


def test_grok_dir_roundtrip_keeps_cron_schedule(fixtures: Path, tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    back = tmp_path / "grok"
    assert (
        runner.invoke(
            app,
            [
                "convert",
                "--from",
                "grok",
                "--to",
                "hermes",
                "--src",
                str(fixtures / "grok_dir"),
                "--out",
                str(hermes),
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "convert",
                "--from",
                "hermes",
                "--to",
                "grok",
                "--src",
                str(hermes),
                "--out",
                str(back),
            ],
        ).exit_code
        == 0
    )
    auto = read_json(back / "automations" / "weekly-digest" / "automation.json")
    assert auto["prompt"] == "Write the weekly ops digest from open incidents."
    assert auto["schedule"] == "0 9 * * 1"
    assert auto["triggerPresentation"]["trigger"]["type"] == "cron"
    profile = read_json(back / "profile.json")
    assert profile["name"] == "Ops Bot"
    skill = (back / "skills" / "incident-brief" / "SKILL.md").read_text()
    assert "timeline" in skill
