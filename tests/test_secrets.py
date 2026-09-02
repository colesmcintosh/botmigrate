from pathlib import Path

from typer.testing import CliRunner

from botmigrate.cli import app

runner = CliRunner()

FORBIDDEN = (
    "sk-super-secret-do-not-copy",
    "ghp_should_never_appear",
    "secret-oauth-token",
    "secret-refresh",
    "sk-in-config-must-strip",
)


def _all_text(root: Path) -> str:
    chunks: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            chunks.append(path.read_text(errors="replace"))
    return "\n".join(chunks)


def test_secrets_never_appear_in_output(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "safe.json"
    result = runner.invoke(
        app,
        [
            "convert",
            "--from",
            "hermes",
            "--to",
            "grok",
            "--src",
            str(fixtures / "secrets_profile"),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    blob = _all_text(tmp_path)
    for secret in FORBIDDEN:
        assert secret not in blob
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / "auth.json").exists()
    assert not list(tmp_path.rglob(".env"))
    assert not list(tmp_path.rglob("auth.json"))


def test_src_env_file_exits_nonzero(fixtures: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "convert",
            "--from",
            "hermes",
            "--to",
            "grok",
            "--src",
            str(fixtures / "secrets_profile" / ".env"),
            "--out",
            str(tmp_path / "out.json"),
        ],
    )
    assert result.exit_code != 0
    assert "secret" in result.output.lower() or "refusing" in result.output.lower()


def test_hermes_write_strips_config_api_key(fixtures: Path, tmp_path: Path) -> None:
    """Hermes→Hermes still must not copy api_key values from config.yaml."""
    out = tmp_path / "dist"
    result = runner.invoke(
        app,
        [
            "convert",
            "--from",
            "hermes",
            "--to",
            "hermes",
            "--src",
            str(fixtures / "secrets_profile"),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    blob = _all_text(out)
    for secret in FORBIDDEN:
        assert secret not in blob
    assert not (out / ".env").exists()
    assert not (out / "auth.json").exists()
    if (out / "config.yaml").exists():
        text = (out / "config.yaml").read_text()
        assert "api_key" not in text
        assert "claude-sonnet-4" in text
