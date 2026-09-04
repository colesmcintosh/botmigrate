"""Pydantic models for Grok share JSON and on-disk agent files."""

from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

AvatarShape = Literal[
    "blob",
    "pebble",
    "bean",
    "egg",
    "squircle",
    "tablet",
    "capsule",
    "cylinder",
    "hex",
    "gem",
    "crystal",
    "wedge",
    "shield",
    "dome",
    "arch",
    "cloud",
    "teardrop",
    "leaf",
]

AvatarColor = Literal[
    "black",
    "brown",
    "red",
    "orange",
    "yellow",
    "green",
    "cyan",
    "blue",
    "violet",
    "magenta",
    "gray",
]

AVATAR_SHAPES = frozenset(get_args(AvatarShape))
AVATAR_COLORS = frozenset(get_args(AvatarColor))


class GrokProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    title: str = ""
    avatarShape: str = "blob"
    avatarColor: str = "black"


class GrokMemoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["profile", "log"]
    createdAt: str | None = None
    content: str = ""


class GrokSkillItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    content: str = ""


class GrokRoutineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slug: str = ""
    name: str
    description: str = ""
    content: str = ""


class GrokPluginItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pluginId: str
    name: str = ""
    description: str = ""


class GrokGettingStarted(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skill: str = ""


class GrokShare(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: GrokProfile
    memory: list[GrokMemoryItem] = Field(default_factory=list)
    skills: list[GrokSkillItem] = Field(default_factory=list)
    routines: list[GrokRoutineItem] = Field(default_factory=list)
    plugins: list[GrokPluginItem] = Field(default_factory=list)
    gettingStarted: GrokGettingStarted | None = None
    visibility: str = "public"


class GrokAutomation(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    prompt: str = ""
    schedule: str | None = None
    triggerPresentation: dict[str, Any] | None = None
    enabled: bool = True
