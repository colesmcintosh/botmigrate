"""Write Hermes profile distributions and live profile directories."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from botmigrate.connectors import hermes_mcp_entry
from botmigrate.ids import kebab, stable_id
from botmigrate.io import read_json, write_json, write_text, write_yaml
from botmigrate.ir.models import Memory, PortableBot, Routine
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


def write_hermes_distribution(bot: PortableBot, out: Path, *, include_memories: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    slug = kebab(bot.identity.slug or bot.identity.name, fallback="bot")
    write_yaml(out / "distribution.yaml", _distribution_payload(bot, slug))
    write_text(out / "SOUL.md", _soul_markdown(bot))
    write_text(out / "README.md", _readme(bot, slug))
    write_text(out / ".gitignore", HERMES_GITIGNORE)
    _write_config(out, bot)
    _write_mcp(out, bot)
    _write_env_example(out, bot)
    for skill in sorted(bot.skills, key=lambda s: s.slug):
        write_skill_dir(out / "skills", skill.slug, skill.slug, skill.description, skill.content)
    for routine in sorted(bot.routines, key=lambda r: r.slug):
        if routine.schedule and routine.schedule.kind == "event":
            continue
        write_json(out / "cron" / f"{routine.slug}.json", _distribution_cron(routine))
    if include_memories:
        _write_memories(out, bot.memories)
    write_sidecar(out, bot, "hermes-distribution")


def write_hermes_profile(
    bot: PortableBot,
    out: Path,
    *,
    include_memories: bool,
    merge_jobs: bool = True,
) -> None:
    write_hermes_distribution(bot, out, include_memories=include_memories)
    write_sidecar(out, bot, "hermes-profile")
    cron_routines = [
        r for r in bot.routines if not (r.schedule and r.schedule.kind == "event")
    ]
    existing: list[dict[str, Any]] = []
    jobs_path = out / "cron" / "jobs.json"
    if merge_jobs and jobs_path.is_file():
        existing = _load_jobs(read_json(jobs_path))
    incoming = [_live_job(r) for r in sorted(cron_routines, key=lambda r: r.slug)]
    merged = _merge_jobs(existing, incoming)
    write_json(jobs_path, merged)


def _distribution_payload(bot: PortableBot, slug: str) -> dict[str, Any]:
    stored = ((bot.extras or {}).get("hermes") or {}).get("distribution") or {}
    env_requires = _env_requires(bot)
    return {
        "name": stored.get("name") or slug,
        "version": stored.get("version") or "1.0.0",
        "description": bot.identity.description or stored.get("description") or "",
        "hermes_requires": stored.get("hermes_requires") or ">=0.12.0",
        "author": stored.get("author") or "botmigrate",
        "license": stored.get("license") or "MIT",
        "env_requires": env_requires,
    }


def _env_requires(bot: PortableBot) -> list[dict[str, Any]]:
    names: list[str] = []
    for connector in bot.connectors:
        names.extend(connector.env_requires)
    unique = list(dict.fromkeys(n for n in names if n))
    return [
        {
            "name": name,
            "description": f"Required by connector {name.split('_')[0].title()}",
            "required": True,
        }
        for name in unique
    ]


def _soul_markdown(bot: PortableBot) -> str:
    if bot.identity.soul.strip():
        return bot.identity.soul.strip() + "\n"
    title = bot.identity.title or bot.identity.name
    lines = [f"# {title}", ""]
    if bot.identity.description:
        lines.append(bot.identity.description.strip())
        lines.append("")
    lines.append(f"You are {bot.identity.name}.")
    if bot.identity.title and bot.identity.title != bot.identity.name:
        lines.append(f"Role: {bot.identity.title}.")
    standing = [m.content for m in bot.profile_memories() if _looks_like_instruction(m.content)]
    if standing:
        lines.append("")
        lines.append("## Standing instructions")
        lines.append("")
        for fact in standing:
            lines.append(f"- {fact}")
    lines.append("")
    return "\n".join(lines)


def _looks_like_instruction(text: str) -> bool:
    lowered = text.lower()
    return lowered.startswith(("always ", "never ", "prefer ", "when ", "do not ", "don't "))


def _readme(bot: PortableBot, slug: str) -> str:
    desc = bot.identity.description or "Migrated Hermes profile."
    return (
        f"# {bot.identity.name}\n\n"
        f"{desc}\n\n"
        f"Install with:\n\n"
        f"```bash\n"
        f"hermes profile install ./{slug} --alias\n"
        f"```\n\n"
        f"See `MIGRATION.md` for what was converted and what you still need to do.\n"
    )


def _write_config(out: Path, bot: PortableBot) -> None:
    config = ((bot.extras or {}).get("hermes") or {}).get("config")
    if not config:
        return
    write_yaml(out / "config.yaml", strip_secrets(config))


def _write_mcp(out: Path, bot: PortableBot) -> None:
    servers: dict[str, Any] = {}
    for connector in sorted(bot.connectors, key=lambda c: c.id):
        entry = hermes_mcp_entry(connector)
        if entry:
            server_id, cfg = entry
            servers[server_id] = cfg
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
        lines.append(f"# {item['description']}")
        lines.append(f"# (required)")
        lines.append(f"{item['name']}=")
        lines.append("")
    write_text(out / ".env.EXAMPLE", "\n".join(lines))


def _distribution_cron(routine: Routine) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": routine.name,
        "prompt": routine.prompt,
        "enabled": False,
    }
    if routine.schedule:
        payload["schedule"] = hermes_schedule_object(routine.schedule)
    return payload


def _live_job(routine: Routine) -> dict[str, Any]:
    job: dict[str, Any] = {
        "id": stable_id(routine.slug),
        "name": routine.name,
        "prompt": routine.prompt,
        "enabled": False,
        "state": "paused",
    }
    if routine.schedule:
        job["schedule"] = hermes_schedule_object(routine.schedule)
    return job


def _load_jobs(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [j for j in raw if isinstance(j, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("jobs"), list):
        return [j for j in raw["jobs"] if isinstance(j, dict)]
    return []


def _merge_jobs(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def key_of(job: dict[str, Any]) -> str:
        return kebab(str(job.get("name") or job.get("id") or "job"))

    for job in existing:
        key = key_of(job)
        by_key[key] = job
        order.append(key)
    for job in incoming:
        key = key_of(job)
        if key in by_key:
            kept = dict(by_key[key])
            kept["name"] = job["name"]
            kept["prompt"] = job["prompt"]
            if "schedule" in job:
                kept["schedule"] = job["schedule"]
            by_key[key] = kept
        else:
            by_key[key] = job
            order.append(key)
    return [by_key[k] for k in order]


def _write_memories(out: Path, memories: list[Memory]) -> None:
    profile = [m for m in memories if m.kind == "profile"]
    log = [m for m in memories if m.kind == "log"]
    if profile:
        write_text(out / "USER.md", "\n".join(_mem_line(m) for m in profile) + "\n")
    if log:
        write_text(out / "MEMORY.md", "\n".join(_mem_line(m) for m in log) + "\n")


def _mem_line(memory: Memory) -> str:
    if memory.created_at:
        return f"- ({memory.created_at}) {memory.content}"
    return f"- {memory.content}"
