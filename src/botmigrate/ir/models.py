"""Canonical portable bot IR. Adapters read/write this; they never call each other."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    title: str = ""
    description: str = ""
    soul: str = ""


class Memory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["profile", "log"]
    content: str
    created_at: str | None = None


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    description: str = ""
    content: str = ""
    source_path: str = ""
    """Path of the skill directory relative to `skills/`, when it was nested.

    Live Hermes profiles group skills under a category. Distributions are flat,
    so this is empty for them and the slug alone locates the directory.
    """


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["cron", "relative", "interval", "iso", "event"]
    cron: str | None = None
    display: str = ""
    original: dict[str, Any] = Field(default_factory=dict)


class Routine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    description: str = ""
    prompt: str = ""
    schedule: Schedule | None = None
    enabled: bool = False


class Connector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["plugin", "mcp"]
    id: str
    name: str
    description: str = ""
    config_without_secrets: dict[str, Any] = Field(default_factory=dict)
    env_requires: list[str] = Field(default_factory=list)
    mapped: bool = True


class PortableBot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: Identity
    memories: list[Memory] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    routines: list[Routine] = Field(default_factory=list)
    connectors: list[Connector] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    def sorted(self) -> PortableBot:
        return self.model_copy(
            update={
                "memories": list(self.memories),
                "skills": sorted(self.skills, key=lambda s: s.slug),
                "routines": sorted(self.routines, key=lambda r: r.slug),
                "connectors": sorted(self.connectors, key=lambda c: (c.kind, c.id)),
            }
        )

    def profile_memories(self) -> list[Memory]:
        return [m for m in self.memories if m.kind == "profile"]

    def log_memories(self) -> list[Memory]:
        return [m for m in self.memories if m.kind == "log"]


class Sidecar(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: int = 1
    generated_by: str = "botmigrate"
    source_format: str = ""
    extras: dict[str, Any] = Field(default_factory=dict)
