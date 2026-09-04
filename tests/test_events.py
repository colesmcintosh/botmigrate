from pathlib import Path

from conftest import cli

from botmigrate.io import read_json


def test_event_listener_does_not_become_cron(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "hermes"
    result = cli("convert", fixtures / "grok_dir", out)
    assert result.exit_code == 0, result.output
    cron_files = {p.name for p in (out / "cron").glob("*.json")}
    assert "weekly-digest.json" in cron_files
    assert "slack-triage.json" not in cron_files
    for path in (out / "cron").glob("*.json"):
        schedule = read_json(path).get("schedule") or {}
        assert schedule.get("kind") != "event"
        assert "slack" not in str(schedule.get("expr") or "").lower()
    migration = (out / "MIGRATION.md").read_text()
    assert "slack-triage" in migration
    assert "no Hermes cron equivalent" in migration
    untranslated = read_json(out / ".botmigrate.json")["extras"]["untranslated_routines"]
    event = next(item for item in untranslated if item["slug"] == "slack-triage")
    assert event["schedule"]["kind"] == "event"
    assert event["schedule"]["original"]["grok_trigger"]["type"] == "slack"


def test_event_restored_on_hermes_to_grok_roundtrip(fixtures: Path, tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    back = tmp_path / "grok"
    assert cli("convert", fixtures / "grok_dir", hermes).exit_code == 0
    result = cli("convert", hermes, back)
    assert result.exit_code == 0, result.output
    payload = read_json(back / "automations" / "slack-triage" / "automation.json")
    assert "schedule" not in payload
    assert payload["triggerPresentation"]["trigger"]["type"] == "slack"
    assert payload["prompt"].startswith("Triage new")
