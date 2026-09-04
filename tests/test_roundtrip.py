from pathlib import Path

from conftest import cli

from botmigrate.io import read_json


def test_grok_share_roundtrip_keeps_name_skills_cron(fixtures: Path, tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    back = tmp_path / "back.json"
    first = cli("convert", fixtures / "grok_share.json", hermes)
    assert first.exit_code == 0, first.output
    second = cli("convert", hermes, back)
    assert second.exit_code == 0, second.output
    share = read_json(back)
    assert share["profile"]["name"] == "Research Bot"
    skill = next(s for s in share["skills"] if "arxiv" in s["name"])
    assert "one-page brief" in skill["content"]
    routine = next(r for r in share["routines"] if r["slug"] == "weekly-digest")
    assert "Summarize new arXiv" in routine["content"]
    assert "0 9 * * 1" in routine["description"]


def test_grok_dir_roundtrip_keeps_cron_schedule(fixtures: Path, tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    back = tmp_path / "grok"
    assert cli("convert", fixtures / "grok_dir", hermes).exit_code == 0
    assert cli("convert", hermes, back).exit_code == 0
    auto = read_json(back / "automations" / "weekly-digest" / "automation.json")
    assert auto["prompt"] == "Write the weekly ops digest from open incidents."
    assert auto["schedule"] == "0 9 * * 1"
    assert auto["triggerPresentation"]["trigger"]["type"] == "cron"
    assert read_json(back / "profile.json")["name"] == "Ops Bot"
    assert "timeline" in (back / "skills" / "incident-brief" / "SKILL.md").read_text()


def test_grok_dir_memories_roundtrip(fixtures: Path, tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    back = tmp_path / "grok"
    assert cli("convert", fixtures / "grok_dir", hermes, "--memories").exit_code == 0
    assert cli("convert", hermes, back).exit_code == 0
    original = (fixtures / "grok_dir" / "memory" / "profile.md").read_text().strip()
    assert (back / "memory" / "profile.md").read_text().strip() == original
