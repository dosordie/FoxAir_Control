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


SENSITIVE_DEVICE_KEYS = frozenset({
    "iccid", "dtuiccid", "imei", "dtuimeimac", "imeimac", "msisdn", "imsi",
    "email", "emailaddress", "useremail", "phone", "telephone", "tel",
    "phonenumber", "phoneno", "mobile", "mobilephone", "mobileno", "userid",
})


def mask_identifier(value: Any) -> str:
    text = str(value if value is not None else "")
    if not text:
        return text
    return "••••" if len(text) <= 8 else text[:4] + "…" + text[-4:]


def redacted_device_metadata(value: Any) -> Any:
    """Create a display/export view; retain unmasked identifiers only internally."""
    value = safe_device_metadata(value)
    if isinstance(value, dict):
        return {
            key: (mask_identifier(item)
                  if re.sub(r"[^a-z0-9]", "", key.lower()) in SENSITIVE_DEVICE_KEYS
                  else redacted_device_metadata(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redacted_device_metadata(item) for item in value]
    return value


def device_iccid(device: Any) -> str | None:
    """Use the selected device's discovered metadata, never a guessed identifier."""
    value = device.get("dtuIccid") if isinstance(device, dict) else None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    return str(value).strip() or None


SIM_STATUS_FIELDS = (
    "expireDays", "expireTime", "activeTime", "openTime", "cardState",
    "onlineState", "netType", "cardType", "cardPlatform", "dataService", "renewYear",
)


def safe_sim_status(value: Any) -> dict[str, Any]:
    """Allowlist scalar status fields, dropping identifiers and complete JSON trees."""
    data = safe_device_metadata(value) if isinstance(value, dict) else {}
    private_values = {
        str(item) for key, item in data.items()
        if re.sub(r"[^a-z0-9]", "", key.lower()) in SENSITIVE_DEVICE_KEYS
        and isinstance(item, (str, int)) and len(str(item)) >= 8
    }
    result = {}
    for field in SIM_STATUS_FIELDS:
        item = data.get(field)
        if not isinstance(item, (str, int, float, bool)):
            item = None
        elif str(item) in private_values:
            item = mask_identifier(item)
        result[field] = item
    return result


SIM_VALUE_TRANSLATIONS = {
    "物联卡": "IoT-SIM-Karte",
}


def debug_sim_status(value: Any) -> dict[str, Any]:
    """Return all SIM API fields for the debug UI, excluding auth secrets only."""
    data = safe_device_metadata(value) if isinstance(value, dict) else {}
    return dict(data)


def sim_display_value(value: Any) -> str:
    """Human-readable debug display while preserving non-obvious raw values."""
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        return str(value)
    text = str(value)
    translated = SIM_VALUE_TRANSLATIONS.get(text)
    return f"{translated} ({text})" if translated else text
