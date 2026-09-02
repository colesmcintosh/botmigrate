# botmigrate

Convert and sync AI agent bots between **Grok Bot** (Cursor Grok / sandbox assistants) and **Hermes Agent** (Nous Research Hermes, including Bot Mode profiles).

v0.1 is a local CLI: files in, files out. No hosted service, no API keys, no calls to Grok or Hermes servers.

Public repo: <https://github.com/colesmcintosh/botmigrate>

```bash
pip install botmigrate
# or
uv tool install botmigrate
# or from git
uv tool install git+https://github.com/colesmcintosh/botmigrate
```

```bash
git clone https://github.com/colesmcintosh/botmigrate.git
cd botmigrate
uv sync --extra dev
```

```bash
botmigrate inspect ./research-bot.json
botmigrate convert --from grok --to hermes --src ./research-bot.json --out ./research-bot
botmigrate convert --from hermes --to grok --src ./research-bot --out ./research-bot.json
botmigrate sync --from grok --to hermes --src ./research-bot.json --dst ~/.hermes/profiles/research-bot
botmigrate sync --from grok --to hermes --src ./research-bot.json --dst ~/.hermes/profiles/research-bot --apply
```

Sync is a **dry-run by default**. Pass `--apply` to write.

Python 3.11+ is required. After a local clone, `uv run botmigrate --help` should work.

## Worked example: Grok share JSON → Hermes distribution

The repo ships a tiny Grok template at `examples/grok-share/research-bot.json`.

```bash
botmigrate convert \
  --from grok \
  --to hermes \
  --src examples/grok-share/research-bot.json \
  --out ./out/research-bot
```

That writes an installable Hermes profile distribution:

```
out/research-bot/
  distribution.yaml
  SOUL.md
  skills/arxiv-brief/SKILL.md
  cron/weekly-digest.json    # enabled: false
  mcp.json                   # GitHub stub, no tokens
  .gitignore
  .env.EXAMPLE               # env *names* only
  MIGRATION.md
  .botmigrate.json
```

Install it with Hermes (you do this on your machine; botmigrate never talks to Hermes):

```bash
hermes profile install ./out/research-bot --alias
# Review SOUL.md and skills, copy .env.EXAMPLE → .env, then:
# hermes -p research-bot cron list
```

Imported cron jobs stay **disabled**. Hermes itself does not auto-schedule imported crons; enable them after you read the prompts.

Memories from the Grok JSON are **not** written into a shareable Hermes distribution unless you pass `--include-memories`. A distribution is meant to be committed or handed to someone else.

## Worked example: Hermes distribution → Grok share JSON

```bash
botmigrate convert \
  --from hermes \
  --to grok \
  --src examples/hermes-dist/research-bot \
  --out ./out/research-bot.json
```

The JSON is the Grok share / template shape (`profile`, `memory`, `skills`, `routines`, `plugins`). Point `--out` at a directory instead of a `.json` file to write an on-disk Grok agent folder (`profile.json`, `automations/<slug>/automation.json`, `skills/<slug>/SKILL.md`).

## Commands

| Command | What it does |
|---|---|
| `inspect <path>` | Detect format; print name, skills, routines/cron, memory counts, plugins/MCP. `--json` for machines. |
| `convert --from grok\|hermes --to grok\|hermes --src <path> --out <path>` | One-shot convert. |
| `sync --from … --to … --src <path> --dst <path>` | Apply portable fields onto an existing dest. Dry-run default; `--apply` writes. |

Useful flags:

- `--skills-dir` — Grok shared workflows live outside the agent folder; pass their parent so SKILL.md trees are picked up. Writes always emit `skills/<slug>/SKILL.md` inside the output so the bundle is self-contained.
- `--include-memories` / `--exclude-memories` — override the memory default (see below).
- `--hermes-layout distribution\|profile` — installable distribution (default) vs a live profile tree (may also emit `cron/jobs.json`).
- `--json` — `inspect` only.

Exit non-zero on unknown format, missing required files, or an attempted secret copy (for example pointing `--src` at `.env`).

### Memory defaults

| Target | Default |
|---|---|
| Hermes **distribution** (shareable) | memories **excluded** |
| Hermes **live profile** | memories **included** |
| Grok share JSON or Grok directory | memories **included** |
| `sync` onto a live dest | memories **included** unless dest looks like a distribution |

Hermes memories that may be converted (only with the include path): `USER.md` (profile facts), `MEMORY.md` (log), and `memories/*.md`. Conversation transcripts and `sessions/` are never copied.

## Mapping

| Portable field | Grok | Hermes |
|---|---|---|
| Name | `profile.name` | `distribution.yaml` name (kebab-case) + folder |
| Title | `profile.title` | First heading in `SOUL.md` |
| Description | `profile.description` | `distribution.yaml` description + SOUL role paragraph |
| Persona | description + optional soul skill | `SOUL.md` |
| Profile memory | `memory` kind=profile / `memory/profile.md` | `USER.md` |
| Log memory | `memory` kind=log / `memory/log` | `MEMORY.md` |
| Skills | `skills[]` / `SKILL.md` | `skills/<slug>/SKILL.md` |
| Cron routines | automations with a cron schedule | `cron/*.json` or `cron/jobs.json` |
| Event routines | slack / github / origin / … triggers | `MIGRATION.md` + `.botmigrate.json` sidecar |
| Marketplace plugins | `plugins[].pluginId` | `mcp.json` stub when the name is known |
| MCP servers | (none native; noted in MIGRATION.md) | `mcp.json` minus secrets |
| Avatar | `avatarShape` + `avatarColor` | sidecar only |
| Model pin | n/a | `config.yaml` preserved if present; **never invented** on Grok→Hermes |

Skills use the [agentskills.io](https://agentskills.io/specification) `SKILL.md` shape (YAML frontmatter + markdown body). Slug comes from the folder name or a kebab-case of `name`.

An internal JSON Schema for the portable model lives at `src/botmigrate/ir/schema.json`. Adapters read and write that IR; they do not call each other.

`.botmigrate.json` is written next to every output so a later sync or round-trip can restore extras (Grok avatar, event triggers, Hermes `config.yaml`, non-cron Hermes schedules).

## What is NOT synced

- Secrets, credentials, tokens, `.env`, `auth.json`
- Conversation transcripts and session databases (`sessions/`, `store.db`, `conversation-blobs.db`, `state.db*`)
- `audit.jsonl`, attachments, caches, logs
- Hermes desktop theme / layout (`desktop.json`)
- Grok event-listener automations as Hermes cron (they cannot be cron; they are noted and stored in the sidecar)
- Invented Grok marketplace plugin ids
- Invented Hermes model pins

## Known plugin ↔ MCP names

Only these names are mapped. Anything else is listed in `MIGRATION.md` as a manual follow-up.

| Name | Grok `pluginId` | Hermes MCP stub | Env names (no values) |
|---|---|---|---|
| github | `github` | `npx -y @modelcontextprotocol/server-github` | `GITHUB_TOKEN` |
| notion | `notion` | `npx -y @notionhq/notion-mcp-server` | `NOTION_TOKEN` |
| linear | `linear` | `npx -y mcp-linear` | `LINEAR_API_KEY` |
| slack | `slack` | `npx -y @modelcontextprotocol/server-slack` | `SLACK_BOT_TOKEN` |

Stubs use `command` / `args` placeholders. Tokens stay on your machine.

## Formats

**Grok** — share JSON (preferred interchange) or an on-disk agent directory (`profile.json`, `memory/`, `automations/<slug>/automation.json`). Event triggers (`slack`, `github`, `origin`, `microsoftTeams`, `linear`, `sentry`, `pagerduty`, `webhook`, `group`) are not converted into fake cron.

**Hermes** — profile distribution directory (`distribution.yaml` required), a live profile (`~/.hermes` or `~/.hermes/profiles/<name>/`), or a `hermes profile export` `.tar.gz`. Cron jobs from a conversion are written `enabled: false`. Sync merges `cron/jobs.json` by job name and does not drop dest-only jobs.

## Security

- Never copies `.env`, `auth.json`, or session/state databases.
- Strips secret-looking keys (`api_key`, `token`, `password`, …) from `config.yaml` / `mcp.json`.
- `env_requires` and `.env.EXAMPLE` list **names only**.
- Pointing `--src` at a secret file exits non-zero.
- No telemetry. Convert and sync do not open a network connection.

If you are publishing a Hermes distribution, keep the generated `.gitignore` and run `git status` before the first commit.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run botmigrate inspect examples/grok-share/research-bot.json
```

MIT licensed. See `LICENSE`.
