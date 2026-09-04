from conftest import cli


def test_help() -> None:
    result = cli("--help")
    assert result.exit_code == 0
    for command in ("inspect", "convert", "sync"):
        assert command in result.stdout


def test_convert_help_mentions_memories_and_layouts() -> None:
    result = cli("convert", "--help")
    assert result.exit_code == 0
    assert "--memories" in result.stdout
    assert "--no-memories" in result.stdout
    assert "distribution|profile" in result.stdout
    assert "share|directory" in result.stdout


def test_sync_help_mentions_dry_run() -> None:
    result = cli("sync", "--help")
    assert result.exit_code == 0
    assert "--apply" in result.stdout
    assert "dry-run" in result.stdout.lower()
