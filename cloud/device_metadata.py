"""Safe, lossless device metadata for discovery, display and account-bound cache."""
from __future__ import annotations

import re
from typing import Any


def safe_device_metadata(value: Any) -> Any:
    """Retain backend fields and IDs, recursively excluding authentication secrets."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized.startswith("auth") or any(marker in normalized for marker in ("password", "passwd", "token", "secret", "credential")) or normalized in {
                "pwd", "auth", "apikey", "accesskey", "privatekey", "sessionid", "sessionkey", "sign", "signature",
            }:
                continue
            result[str(key)] = safe_device_metadata(item)
        return result
    if isinstance(value, list):
        return [safe_device_metadata(item) for item in value]
    return value


def cached_device_metadata(devices: Any) -> list[dict[str, Any]]:
    """Accept complete records with usable device codes, without creating placeholders."""
    from cloud.known_devices import merge_device_sources
    if not isinstance(devices, list):
        return []
    return merge_device_sources(
        [safe_device_metadata(device) for device in devices if isinstance(device, dict)], [], [])
