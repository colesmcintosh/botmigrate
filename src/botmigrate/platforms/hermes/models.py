"""Pydantic model for the Hermes `distribution.yaml` manifest."""

from __future__ import annotations

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
