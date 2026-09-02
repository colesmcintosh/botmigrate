"""Detected on-disk formats."""

from __future__ import annotations

from enum import Enum


class FormatKind(str, Enum):
    grok_share = "grok-share-json"
    grok_directory = "grok-directory"
    hermes_distribution = "hermes-distribution"
    hermes_profile = "hermes-profile"
    hermes_tarball = "hermes-tarball"


def is_grok(kind: FormatKind) -> bool:
    return kind in {FormatKind.grok_share, FormatKind.grok_directory}


def is_hermes(kind: FormatKind) -> bool:
    return kind in {
        FormatKind.hermes_distribution,
        FormatKind.hermes_profile,
        FormatKind.hermes_tarball,
    }


def is_shareable(kind: FormatKind) -> bool:
    return kind in {FormatKind.grok_share, FormatKind.hermes_distribution}
