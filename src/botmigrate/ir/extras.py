"""Helpers for the opaque `extras` bag carried on a PortableBot."""

from __future__ import annotations

from typing import Any


def merge_extras(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Overlay wins; one level of dict values is merged instead of replaced."""
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged
