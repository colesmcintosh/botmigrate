"""Write Hermes profile distributions and live profile directories."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from botmigrate.connectors import hermes_mcp_entry
from botmigrate.ids import kebab, stable_id
from botmigrate.io import read_json, write_json, write_text, write_yaml
from botmigrate.ir.models import Memory, PortableBot, Routine
from botmigrate.memorymd import render_memory_line
from botmigrate.schedule import hermes_schedule_object
from botmigrate.secrets import strip_secrets
from botmigrate.sidecar import write_sidecar
from botmigrate.skillmd import write_skill_dir

HERMES_GITIGNORE = """# Credentials & secrets — NEVER commit
auth.json
.env
.env.EXAMPLE

# Runtime databases & state
state.db
state.db-shm
state.db-wal
hermes_state.db
response_store.db
response_store.db-shm
response_store.db-wal
gateway.pid
gateway_state.json
processes.json
auth.lock
active_profile
.update_check

# User data — NEVER commit
memories/
sessions/
logs/
plans/
workspace/
home/

# Caches & generated artifacts
image_cache/
audio_cache/
document_cache/
browser_screenshots/
cache/

# Infrastructure
hermes-agent/
.worktrees/
profiles/
bin/
node_modules/

# User customization namespace
local/

# Checkpoints & backups
checkpoints/
sandboxes/
backups/

# Logs
errors.log
.hermes_history
"""


def write_distribution(bot: PortableBot, out: Path, *, include_memories: bool) -> None:
    """Installable, shareable bundle: flat skills, one `cron/<slug>.json` per job."""
    bot = _write_common(bot, out, include_memories=include_memories, flat_skills=True)
    for routine in _cron_routines(bot):
        write_json(out / "cron" / f"{routine.slug}.json", _distribution_job(routine))
    write_sidecar(out, bot, "hermes-distribution")


def write_profile(bot: PortableBot, out: Path, *, include_memories: bool) -> None:
    """Live `~/.hermes`-style tree: skills keep their category, jobs merge into `cron/jobs.json`."""
    bot = _write_common(bot, out, include_memories=include_memories, flat_skills=False)
    jobs_path = out / "cron" / "jobs.json"
    existing = _load_jobs(read_json(jobs_path)) if jobs_path.is_file() else []
    write_json(jobs_path, _merge_jobs(existing, [_live_job(r) for r in _cron_routines(bot)]))
    write_sidecar(out, bot, "hermes-profile")


def _write_common(
    bot: PortableBot, out: Path, *, include_memories: bool, flat_skills: bool
) -> PortableBot:
    bot = bot.sorted()
    out.mkdir(parents=True, exist_ok=True)
    slug = kebab(bot.identity.slug or bot.identity.name, fallback="bot")
    write_yaml(out / "distribution.yaml", _manifest(bot, slug))
    write_text(out / "SOUL.md", _soul_markdown(bot))
    write_text(out / "README.md", _readme(bot, slug))
    write_text(out / ".gitignore", HERMES_GITIGNORE)
    _write_config(out, bot)
    _write_mcp(out, bot)
    _write_env_example(out, bot)
    for skill in bot.skills:
        # A live profile keeps a skill in the category it came from, so syncing
        # does not leave a flat copy beside the nested original.
        target = skill.slug if flat_skills or not skill.source_path else skill.source_path
        write_skill_dir(out / "skills", target, skill.slug, skill.description, skill.content)
    if include_memories:
        _write_memories(out, bot.memories)
    return bot


def _cron_routines(bot: PortableBot) -> list[Routine]:
    """Event listeners have no Hermes equivalent; they live in the sidecar only."""
    return [r for r in bot.routines if not (r.schedule and r.schedule.kind == "event")]


def _manifest(bot: PortableBot, slug: str) -> dict[str, Any]:
    stored = (bot.extras.get("hermes") or {}).get("distribution") or {}
    return {
        "name": stored.get("name") or slug,
        "version": stored.get("version") or "1.0.0",
        "description": bot.identity.description or stored.get("description") or "",
        "hermes_requires": stored.get("hermes_requires") or ">=0.12.0",
        "author": stored.get("author") or "botmigrate",
        "license": stored.get("license") or "MIT",
        "env_requires": _env_requires(bot),
    }


def _env_requires(bot: PortableBot) -> list[dict[str, Any]]:
    names = dict.fromkeys(n for c in bot.connectors for n in c.env_requires if n)
    return [
        {
            "name": name,
            "description": f"Required by connector {name.split('_')[0].title()}",
            "required": True,
        }
        for name in names
    ]


def _soul_markdown(bot: PortableBot) -> str:
    if bot.identity.soul.strip():
        return bot.identity.soul.strip()
    lines = [f"# {bot.identity.title or bot.identity.name}", ""]
    if bot.identity.description:
        lines += [bot.identity.description.strip(), ""]
    lines.append(f"You are {bot.identity.name}.")
    if bot.identity.title and bot.identity.title != bot.identity.name:
        lines.append(f"Role: {bot.identity.title}.")
    standing = [m.content for m in bot.profile_memories() if _looks_like_instruction(m.content)]
    if standing:
        lines += ["", "## Standing instructions", "", *(f"- {fact}" for fact in standing)]
    return "\n".join(lines)


def _looks_like_instruction(text: str) -> bool:
    return text.lower().startswith(("always ", "never ", "prefer ", "when ", "do not ", "don't "))


def _readme(bot: PortableBot, slug: str) -> str:
    return (
        f"# {bot.identity.name}\n\n"
        f"{bot.identity.description or 'Migrated Hermes profile.'}\n\n"
        "Install with:\n\n"
        f"```bash\nhermes profile install ./{slug} --alias\n```\n\n"
        "See `MIGRATION.md` for what was converted and what you still need to do.\n"
    )


def _write_config(out: Path, bot: PortableBot) -> None:
    config = (bot.extras.get("hermes") or {}).get("config")
    if config:
        write_yaml(out / "config.yaml", strip_secrets(config))


def _write_mcp(out: Path, bot: PortableBot) -> None:
    servers = dict(entry for entry in map(hermes_mcp_entry, bot.connectors) if entry)
    if servers:
        write_json(out / "mcp.json", {"mcpServers": servers})


def _write_env_example(out: Path, bot: PortableBot) -> None:
    requires = _env_requires(bot)
    if not requires:
        return
    lines = [
        "# Environment variables required by this Hermes distribution.",
        "# Copy to `.env` and fill in your own values before running.",
        "",
    ]
    for item in requires:
        lines += [f"# {item['description']}", "# (required)", f"{item['name']}=", ""]
    write_text(out / ".env.EXAMPLE", "\n".join(lines))


def _distribution_job(routine: Routine) -> dict[str, Any]:
    job: dict[str, Any] = {"name": routine.name, "prompt": routine.prompt, "enabled": False}
    if routine.schedule:
        job["schedule"] = hermes_schedule_object(routine.schedule)
    return job


def _live_job(routine: Routine) -> dict[str, Any]:
    return {"id": stable_id(routine.slug), **_distribution_job(routine), "state": "paused"}


def _load_jobs(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict) and isinstance(raw.get("jobs"), list):
        raw = raw["jobs"]
    return [j for j in raw if isinstance(j, dict)] if isinstance(raw, list) else []


def _merge_jobs(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Upsert by job name. Destination-only jobs and their enabled state are kept."""
    merged = {_job_key(job): job for job in existing}
    for job in incoming:
        key = _job_key(job)
        if key in merged:
            kept = {**merged[key], "name": job["name"], "prompt": job["prompt"]}
            if "schedule" in job:
                kept["schedule"] = job["schedule"]
            merged[key] = kept
        else:
            merged[key] = job
    return list(merged.values())


def _job_key(job: dict[str, Any]) -> str:
    return kebab(str(job.get("name") or job.get("id") or "job"))


def _write_memories(out: Path, memories: list[Memory]) -> None:
    for kind, filename in (("profile", "USER.md"), ("log", "MEMORY.md")):
        lines = [render_memory_line(m) for m in memories if m.kind == kind]
        if lines:
            write_text(out / filename, "\n".join(lines))
