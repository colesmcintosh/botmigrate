from pathlib import Path

from typer.testing import CliRunner

from botmigrate.cli import app
from botmigrate.io import read_json

runner = CliRunner()


def test_event_listener_does_not_become_cron(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "hermes"
    result = runner.invoke(
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
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    cron_files = {p.name for p in (out / "cron").glob("*.json")}
    assert "weekly-digest.json" in cron_files
    assert "slack-triage.json" not in cron_files
    jobs = list((out / "cron").glob("*.json"))
    for path in jobs:
        payload = read_json(path)
        schedule = payload.get("schedule") or {}
        assert schedule.get("kind") != "event"
        expr = str(schedule.get("expr") or "")
        assert "slack" not in expr.lower()
    migration = (out / "MIGRATION.md").read_text()
    assert "slack-triage" in migration
    assert "no Hermes cron equivalent" in migration
    sidecar = read_json(out / ".botmigrate.json")
    extras = sidecar["extras"]
    untranslated = extras.get("untranslated_routines") or []
    slugs = {item["slug"] for item in untranslated}
    assert "slack-triage" in slugs
    event = next(item for item in untranslated if item["slug"] == "slack-triage")
    assert event["schedule"]["kind"] == "event"
    assert event["schedule"]["original"]["grok_trigger"]["type"] == "slack"


def test_event_restored_on_hermes_to_grok_roundtrip(fixtures: Path, tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    back = tmp_path / "grok"
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
    )
    result = runner.invoke(
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
    assert result.exit_code == 0, result.output
    event_auto = back / "automations" / "slack-triage" / "automation.json"
    assert event_auto.is_file()
    payload = read_json(event_auto)
    assert "schedule" not in payload
    assert payload["triggerPresentation"]["trigger"]["type"] == "slack"
    assert payload["prompt"].startswith("Triage new")
