"""On-disk formats botmigrate can read or write.

Which platform owns a kind, and how it is read or written, lives in
`botmigrate.platforms`. This enum is just the shared vocabulary.
"""

from __future__ import annotations

from enum import Enum


class FormatKind(str, Enum):
    grok_share = "grok-share-json"
    grok_directory = "grok-directory"
    hermes_distribution = "hermes-distribution"
    hermes_profile = "hermes-profile"
    hermes_tarball = "hermes-tarball"
