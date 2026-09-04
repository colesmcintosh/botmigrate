"""CLI-facing errors with path, expected, and found context."""

from __future__ import annotations


class BotmigrateError(Exception):
    """Base error. `exit_code` is used by the CLI."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownFormatError(BotmigrateError):
    def __init__(self, path: str, found: str) -> None:
        expected = (
            "grok share JSON, grok agent directory, Hermes distribution, "
            "Hermes live profile, or Hermes export tarball"
        )
        super().__init__(f"unknown format at {path}\n  expected: {expected}\n  found: {found}")
        self.path = path
        self.expected = expected
        self.found = found


class MissingRequiredFileError(BotmigrateError):
    def __init__(self, path: str, expected: str, found: str) -> None:
        super().__init__(
            f"missing required file at {path}\n  expected: {expected}\n  found: {found}"
        )
        self.path = path
        self.expected = expected
        self.found = found


class SecretCopyError(BotmigrateError):
    def __init__(self, path: str, found: str) -> None:
        super().__init__(
            f"refusing to copy secrets from {path}\n"
            "  expected: a bot profile or share bundle, never credentials\n"
            f"  found: {found}"
        )
        self.path = path
        self.found = found


class UsageError(BotmigrateError):
    pass
