from pathlib import Path

from conftest import cli

FORBIDDEN = (
    "sk-super-secret-do-not-copy",
    "ghp_should_never_appear",
    "secret-oauth-token",
    "secret-refresh",
    "sk-in-config-must-strip",
)


def _all_text(root: Path) -> str:
    return "\n".join(p.read_text(errors="replace") for p in root.rglob("*") if p.is_file())


def test_secrets_never_appear_in_output(fixtures: Path, tmp_path: Path) -> None:
    out = tmp_path / "safe.json"
    result = cli("convert", fixtures / "secrets_profile", out)
    assert result.exit_code == 0, result.output
    blob = _all_text(tmp_path)
    for secret in FORBIDDEN:
        assert secret not in blob
    assert not list(tmp_path.rglob(".env"))
    assert not list(tmp_path.rglob("auth.json"))


def test_src_env_file_exits_nonzero(fixtures: Path, tmp_path: Path) -> None:
    result = cli("convert", fixtures / "secrets_profile" / ".env", tmp_path / "out.json")
    assert result.exit_code != 0
    assert "refusing" in result.output.lower()


def test_hermes_write_strips_config_api_key(fixtures: Path, tmp_path: Path) -> None:
    """Hermes→Hermes still must not copy api_key values from config.yaml."""
    out = tmp_path / "dist"
    result = cli("convert", fixtures / "secrets_profile", out, "--to", "hermes")
    assert result.exit_code == 0, result.output
    blob = _all_text(out)
    for secret in FORBIDDEN:
        assert secret not in blob
    assert not (out / ".env").exists()
    assert not (out / "auth.json").exists()
    text = (out / "config.yaml").read_text()
    assert "api_key" not in text
    assert "claude-sonnet-4" in text
