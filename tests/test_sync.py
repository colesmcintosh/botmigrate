from pathlib import Path

from typer.testing import CliRunner

from botmigrate.cli import app
from botmigrate.io import read_json, write_json, write_text

runner = CliRunner()


def test_sync_dry_run_default_does_not_write(fixtures: Path, tmp_path: Path) -> None:
    dst = tmp_path / "dest"
    dst.mkdir()
    write_text(
        dst / "distribution.yaml",
        "name: old-bot\nversion: 1.0.0\ndescription: old\n",
    )
    write_text(dst / "SOUL.md", "# Old\n")
    write_text(dst / ".env", "KEEP_ME=yes\n")
    result = runner.invoke(
        app,
        [
            "sync",
            "--from",
            "hermes",
            "--to",
            "hermes",
            "--src",
            str(fixtures / "hermes_dist"),
            "--dst",
            str(dst),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Dry-run" in result.stdout
    assert (dst / ".env").read_text() == "KEEP_ME=yes\n"
    assert "# Old" in (dst / "SOUL.md").read_text()


def test_sync_apply_preserves_dest_env_and_unknown_cron(fixtures: Path, tmp_path: Path) -> None:
    dst = tmp_path / "dest"
    # Seed a live-ish hermes dest with an extra cron job and a secret file.
    runner.invoke(
        app,
        [
            "convert",
            "--from",
            "hermes",
            "--to",
            "hermes",
            "--src",
            str(fixtures / "hermes_dist"),
            "--out",
            str(dst),
            "--hermes-layout",
            "profile",
        ],
    )
    write_text(dst / ".env", "KEEP_ME=yes\n")
    extra = {
        "id": "deadbeefcafe",
        "name": "Local only job",
        "prompt": "Stay put",
        "schedule": {"kind": "cron", "expr": "0 6 * * *", "display": "0 6 * * *"},
        "enabled": True,
    }
    jobs = read_json(dst / "cron" / "jobs.json")
    assert isinstance(jobs, list)
    jobs.append(extra)
    write_json(dst / "cron" / "jobs.json", jobs)

    result = runner.invoke(
        app,
        [
            "sync",
            "--from",
            "grok",
            "--to",
            "hermes",
            "--src",
            str(fixtures / "grok_share.json"),
            "--dst",
            str(dst),
            "--apply",
            "--hermes-layout",
            "profile",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (dst / ".env").read_text() == "KEEP_ME=yes\n"
    merged = read_json(dst / "cron" / "jobs.json")
    names = {j["name"] for j in merged}
    assert "Local only job" in names
    assert "Weekly digest" in names
    weekly = next(j for j in merged if j["name"] == "Weekly digest")
    assert weekly["enabled"] is False
