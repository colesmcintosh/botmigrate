from pathlib import Path

import pytest
from typer.testing import CliRunner

from botmigrate.cli import app
from botmigrate.detect import detect
from botmigrate.errors import SecretCopyError, UnknownFormatError
from botmigrate.formats import FormatKind

runner = CliRunner()


def test_detect_grok_share(fixtures: Path) -> None:
    assert detect(fixtures / "grok_share.json") is FormatKind.grok_share


def test_detect_grok_dir(fixtures: Path) -> None:
    assert detect(fixtures / "grok_dir") is FormatKind.grok_directory


def test_detect_hermes_dist(fixtures: Path) -> None:
    assert detect(fixtures / "hermes_dist") is FormatKind.hermes_distribution


def test_unknown_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(UnknownFormatError) as exc:
        detect(empty)
    assert "empty" in exc.value.message


def test_secret_file_is_refused(fixtures: Path) -> None:
    with pytest.raises(SecretCopyError):
        detect(fixtures / "secrets_profile" / ".env")


def test_cli_inspect_json(fixtures: Path) -> None:
    result = runner.invoke(app, ["inspect", str(fixtures / "grok_share.json"), "--json"])
    assert result.exit_code == 0
    assert '"name": "Research Bot"' in result.stdout
    assert "arxiv-brief" in result.stdout
    assert "weekly-digest" in result.stdout
