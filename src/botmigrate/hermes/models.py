"""Pydantic models for Hermes distribution and cron job files."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnvRequire(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    required: bool = True
    default: str = ""


class HermesDistribution(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    version: str = "1.0.0"
    description: str = ""
    hermes_requires: str = ">=0.12.0"
    author: str = "botmigrate"
    license: str = "MIT"
    env_requires: list[EnvRequire | str] = Field(default_factory=list)


class HermesCronJob(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str
    prompt: str = ""
    schedule: Any = None
    enabled: bool = False
    skills: list[str] = Field(default_factory=list)
    deliver: str | None = None
    state: str | None = None
