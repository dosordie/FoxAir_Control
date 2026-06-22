"""Validation helpers for WarmLink cloud-to-local register mappings."""

from __future__ import annotations

from typing import Any, Mapping


def register_code_from_definition(definition: Any, fallback_name: str = "") -> str:
    """Return the local register code from a static register-map definition."""
    if isinstance(definition, Mapping):
        code = str(definition.get("code") or "").strip().upper()
        if code:
            return code
        name = str(definition.get("name") or fallback_name or "").strip()
    else:
        name = str(fallback_name or definition or "").strip()
    # Keep this intentionally small and dependency-free so cloud helpers can use
    # it without importing the GUI module.
    import re

    match = re.match(r"^\s*([A-Z]{1,3})(\d{1,3}(?:-\d+)?)\b", name)
    if not match:
        return ""
    return f"{match.group(1).upper()}{match.group(2)}"


def cloud_hint_matches_local_code(cloud_code: str, hint: Mapping[str, Any], local_code: str) -> bool:
    """Return True when a Cloud hint is allowed to target a local register code."""
    cloud_code = str(cloud_code or "").strip()
    local_code = str(local_code or "").strip().upper()
    if not cloud_code or not local_code:
        return False
    if cloud_code.upper() == local_code:
        return True
    hinted_local_code = str(hint.get("local_code") or "").strip().upper()
    if hinted_local_code and hinted_local_code == local_code:
        return True
    return bool(hint.get("allow_code_mismatch"))
