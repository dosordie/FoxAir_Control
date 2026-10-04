# -*- coding: utf-8 -*-
"""Pure helpers for persistent, already-authorized WarmLink device codes."""

from __future__ import annotations

from typing import Any, Iterable


def normalize_known_device_codes(values: Any) -> list[str]:
    """Return unique, non-empty device codes while preserving their order."""
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw = value.get("deviceCode") if isinstance(value, dict) else value
        code = str(raw or "").strip()
        if code and code not in seen:
            result.append(code)
            seen.add(code)
    return result


def merge_discovered_and_known_devices(
    discovered: Iterable[dict[str, Any]], known_device_codes: Any,
) -> list[dict[str, Any]]:
    """Append stored codes missing from discovery, deduplicated by deviceCode.

    Discovery records are inserted first and are never updated from sparse
    manual placeholders, so all cloud metadata remains authoritative.
    """
    return merge_device_sources(discovered, [], known_device_codes)


def merge_device_sources(
    discovered: Iterable[dict[str, Any]],
    house_devices: Iterable[dict[str, Any]],
    known_device_codes: Any,
) -> list[dict[str, Any]]:
    """Merge deviceList > House/Residence > manual, keyed by deviceCode."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, devices in (("deviceList", discovered), ("house", house_devices)):
        for raw in devices:
            if not isinstance(raw, dict):
                continue
            device = dict(raw)
            code = str(device.get("deviceCode") or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            device["deviceCode"] = code
            device.setdefault("discoverySource", source)
            result.append(device)
    for code in normalize_known_device_codes(known_device_codes):
        if code not in seen:
            result.append({"deviceCode": code, "discoverySource": "manual"})
            seen.add(code)
    return result


def remove_known_device_code(values: Any, device_code: str) -> list[str]:
    """Remove only the persistent manual registration for *device_code*."""
    remove = str(device_code or "").strip()
    return [code for code in normalize_known_device_codes(values) if code != remove]


def add_known_device_code(values: Any, device_code: str) -> list[str]:
    """Append one code without ever replacing existing persistent entries."""
    result = normalize_known_device_codes(values)
    code = str(device_code or "").strip()
    if code and code not in result:
        result.append(code)
    return result


def select_available_device_code(
    devices: Iterable[dict[str, Any]], selected_device_code: str | None,
) -> str | None:
    """Keep an exact saved selection; otherwise choose the first usable code."""
    codes = [
        str(device.get("deviceCode") or "").strip()
        for device in devices if isinstance(device, dict)
    ]
    selected = str(selected_device_code or "").strip()
    if selected and selected in codes:
        return selected
    return next((code for code in codes if code), None)


def validation_has_value(rows: Iterable[dict[str, Any]]) -> bool:
    """A validation succeeds only when the cloud returned a real typed value."""
    for row in rows:
        if not isinstance(row, dict) or not row.get("supported"):
            continue
        if row.get("value") is not None or row.get("dataType") is not None:
            return True
    return False
