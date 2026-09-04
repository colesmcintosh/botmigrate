from pathlib import Path

from conftest import cli

from botmigrate.io import read_json, write_json, write_text


def _seed_dest(dst: Path) -> None:
    dst.mkdir()
    write_text(dst / "distribution.yaml", "name: old-bot\nversion: 1.0.0\ndescription: old\n")
    write_text(dst / "SOUL.md", "# Old\n")
    write_text(dst / ".env", "KEEP_ME=yes\n")


def test_sync_dry_run_default_does_not_write(fixtures: Path, tmp_path: Path) -> None:
    dst = tmp_path / "dest"
    _seed_dest(dst)
    result = cli("sync", fixtures / "hermes_dist", dst)
    assert result.exit_code == 0, result.output
    assert "Dry-run" in result.stdout
    assert "Would update persona / SOUL.md" in result.stdout
    assert "Would add skill: arxiv-brief" in result.stdout
    assert (dst / ".env").read_text() == "KEEP_ME=yes\n"
    assert "# Old" in (dst / "SOUL.md").read_text()


def test_sync_apply_keeps_dest_platform_and_env(fixtures: Path, tmp_path: Path) -> None:
    """A Grok source synced onto an existing Hermes dest stays Hermes without --to."""
    dst = tmp_path / "dest"
    _seed_dest(dst)
    result = cli("sync", fixtures / "grok_share.json", dst, "--apply")
    assert result.exit_code == 0, result.output
    assert "Wrote hermes-distribution" in result.stdout
    assert (dst / ".env").read_text() == "KEEP_ME=yes\n"
    # Grok has no persona file, so the destination's SOUL.md is left alone.
    assert (dst / "SOUL.md").read_text() == "# Old\n"
    assert "arXiv" in (dst / "distribution.yaml").read_text()
    assert (dst / "skills" / "arxiv-brief" / "SKILL.md").is_file()


def test_sync_to_conflicting_platform_is_refused(fixtures: Path, tmp_path: Path) -> None:
    dst = tmp_path / "dest"
    _seed_dest(dst)
    result = cli("sync", fixtures / "grok_share.json", dst, "--to", "grok")
    assert result.exit_code != 0
    assert "would overwrite it with another platform" in result.output


def test_sync_into_missing_dest_creates_it(fixtures: Path, tmp_path: Path) -> None:
    dst = tmp_path / "fresh"
    result = cli("sync", fixtures / "grok_share.json", dst, "--apply")
    assert result.exit_code == 0, result.output
    assert "Would create identity: Research Bot" in result.stdout
    assert (dst / "distribution.yaml").is_file()


def test_sync_apply_preserves_dest_env_and_unknown_cron(fixtures: Path, tmp_path: Path) -> None:
    dst = tmp_path / "dest"
    # Seed a live-ish hermes dest with an extra cron job and a secret file.
    assert (
        cli(
            "convert", fixtures / "hermes_dist", dst, "--to", "hermes", "--layout", "profile"
        ).exit_code
        == 0
    )
    write_text(dst / ".env", "KEEP_ME=yes\n")
    jobs = read_json(dst / "cron" / "jobs.json")
    jobs.append(
        {
            "id": "deadbeefcafe",
            "name": "Local only job",
            "prompt": "Stay put",
            "schedule": {"kind": "cron", "expr": "0 6 * * *", "display": "0 6 * * *"},
            "enabled": True,
        }
    )
    write_json(dst / "cron" / "jobs.json", jobs)

    result = cli("sync", fixtures / "grok_share.json", dst, "--apply", "--layout", "profile")
    assert result.exit_code == 0, result.output
    assert (dst / ".env").read_text() == "KEEP_ME=yes\n"
    merged = read_json(dst / "cron" / "jobs.json")
    names = {j["name"] for j in merged}
    assert {"Local only job", "Weekly digest"} <= names
    assert next(j for j in merged if j["name"] == "Local only job")["enabled"] is True
    assert next(j for j in merged if j["name"] == "Weekly digest")["enabled"] is False
