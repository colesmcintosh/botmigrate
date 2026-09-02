from typer.testing import CliRunner

from botmigrate.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "inspect" in result.stdout
    assert "convert" in result.stdout
    assert "sync" in result.stdout


def test_convert_help_mentions_memories() -> None:
    result = runner.invoke(app, ["convert", "--help"])
    assert result.exit_code == 0
    assert "--include-memories" in result.stdout
    assert "distribution" in result.stdout.lower()


def test_sync_help_mentions_dry_run() -> None:
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
    assert "--apply" in result.stdout
    assert "--dry-run" in result.stdout
