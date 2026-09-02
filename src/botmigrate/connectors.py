"""Documented Grok plugin ↔ Hermes MCP mappings.

Only these marketplace / MCP ids are considered known. Unknown connectors
are listed in MIGRATION.md and never get an invented Grok pluginId.
"""

from __future__ import annotations

from typing import Any

from botmigrate.ir.models import Connector
from botmigrate.secrets import env_names_from_mapping, strip_secrets

# Fuzzy aliases → canonical id. plugin_id is only emitted when we have a
# documented Grok marketplace id (same as the canonical name here).
KNOWN: dict[str, dict[str, Any]] = {
    "github": {
        "aliases": ("github", "gh", "github-mcp"),
        "plugin_id": "github",
        "mcp_id": "github",
        "mcp_stub": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
        },
        "env_requires": ["GITHUB_TOKEN"],
        "description": "GitHub repositories, issues, and pull requests",
    },
    "notion": {
        "aliases": ("notion", "notion-mcp"),
        "plugin_id": "notion",
        "mcp_id": "notion",
        "mcp_stub": {
            "command": "npx",
            "args": ["-y", "@notionhq/notion-mcp-server"],
        },
        "env_requires": ["NOTION_TOKEN"],
        "description": "Notion pages and databases",
    },
    "linear": {
        "aliases": ("linear", "linear-mcp"),
        "plugin_id": "linear",
        "mcp_id": "linear",
        "mcp_stub": {
            "command": "npx",
            "args": ["-y", "mcp-linear"],
        },
        "env_requires": ["LINEAR_API_KEY"],
        "description": "Linear issues and projects",
    },
    "slack": {
        "aliases": ("slack", "slack-mcp"),
        "plugin_id": "slack",
        "mcp_id": "slack",
        "mcp_stub": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-slack"],
        },
        "env_requires": ["SLACK_BOT_TOKEN"],
        "description": "Slack channels and messages",
    },
}

_ALIAS_TO_ID = {alias: cid for cid, spec in KNOWN.items() for alias in spec["aliases"]}


def resolve_known(name_or_id: str) -> str | None:
    key = name_or_id.strip().lower().replace("_", "-")
    return _ALIAS_TO_ID.get(key)


def connector_from_grok_plugin(plugin_id: str, name: str, description: str) -> Connector:
    known = resolve_known(plugin_id) or resolve_known(name)
    if known:
        spec = KNOWN[known]
        return Connector(
            kind="plugin",
            id=spec["plugin_id"],
            name=name or spec["plugin_id"],
            description=description or spec["description"],
            config_without_secrets={"mcp_stub": spec["mcp_stub"]},
            env_requires=list(spec["env_requires"]),
            mapped=True,
        )
    return Connector(
        kind="plugin",
        id=plugin_id or name,
        name=name or plugin_id,
        description=description,
        mapped=False,
    )


def connector_from_mcp(server_id: str, config: dict[str, Any]) -> Connector:
    cleaned = strip_secrets(config) if isinstance(config, dict) else {}
    env_names = env_names_from_mapping(config)
    known = resolve_known(server_id)
    if known:
        spec = KNOWN[known]
        env = list(dict.fromkeys([*env_names, *spec["env_requires"]]))
        return Connector(
            kind="mcp",
            id=spec["mcp_id"],
            name=server_id,
            description=spec["description"],
            config_without_secrets=cleaned if cleaned else {"mcp_stub": spec["mcp_stub"]},
            env_requires=env,
            mapped=True,
        )
    return Connector(
        kind="mcp",
        id=server_id,
        name=server_id,
        description="",
        config_without_secrets=cleaned,
        env_requires=env_names,
        mapped=True,  # native MCP is representable on Hermes; Grok plugin id is not invented
    )


def grok_plugin_payload(connector: Connector) -> dict[str, str] | None:
    """Return a Grok plugins[] entry only when the pluginId is documented."""
    known = resolve_known(connector.id) or resolve_known(connector.name)
    if not known:
        return None
    spec = KNOWN[known]
    return {
        "pluginId": spec["plugin_id"],
        "name": connector.name or spec["plugin_id"],
        "description": connector.description or spec["description"],
    }


def hermes_mcp_entry(connector: Connector) -> tuple[str, dict[str, Any]] | None:
    known = resolve_known(connector.id) or resolve_known(connector.name)
    if known:
        spec = KNOWN[known]
        stub = dict(spec["mcp_stub"])
        if connector.config_without_secrets and "command" in connector.config_without_secrets:
            stub = {k: v for k, v in connector.config_without_secrets.items() if k != "mcp_stub"}
        return spec["mcp_id"], stub
    if connector.kind == "mcp" and connector.config_without_secrets:
        cfg = {k: v for k, v in connector.config_without_secrets.items() if k != "mcp_stub"}
        if cfg:
            return connector.id, cfg
    return None
