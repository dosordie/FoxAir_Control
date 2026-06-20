"""Pure helper functions for WarmLink cloud write preparation."""

from __future__ import annotations

from typing import Any, Mapping

from cloud.warmlink_codes import (
    WARMLINK_CLOUD_CODE_HINTS,
    WARMLINK_CLOUD_WRITE_TEST_CODES,
    cloud_hint,
)


def cloud_code_is_write_candidate(code: str, hint: Mapping[str, Any]) -> bool:
    """Return whether a mapped cloud code is safe to offer for writing."""
    if bool(hint.get("write_allowed")):
        return True
    if not hint.get("modbus_register"):
        return False
    confidence = str(hint.get("confidence") or "").lower()
    if confidence not in {"confirmed", "candidate"}:
        return False
    code_text = str(code or "")
    # T/O/S/F/E are mostly live values, outputs, switch/error states in our
    # mapping list. Do not auto-enable write actions for those codes.
    if code_text.startswith(("T", "O", "S", "F", "E")):
        return False
    if hint.get("write_values") or hint.get("rangeStart") not in (None, "") or hint.get("rangeEnd") not in (None, ""):
        return True
    data_type = str(hint.get("cloud_dataType") or "").upper()
    return data_type in {"ENUM", "TEMP", "DIGI1", "DIGI5"} and code_text[:1] in {"A", "H", "P", "R", "Z", "C", "D", "G", "M"}


def cloud_code_for_register(reg_no: int, require_write_allowed: bool = False) -> str | None:
    """Find the best mapped WarmLink cloud code for a local register."""
    try:
        target = int(reg_no)
    except Exception:
        return None
    best: tuple[int, str] | None = None
    rank = {"confirmed": 0, "candidate": 1, "": 2, "unknown": 3}
    for code, hint in WARMLINK_CLOUD_CODE_HINTS.items():
        try:
            mapped = int(hint.get("modbus_register")) if hint.get("modbus_register") not in (None, "") else None
        except Exception:
            mapped = None
        if mapped != target:
            continue
        if require_write_allowed and not cloud_code_is_write_candidate(str(code), hint):
            continue
        confidence = str(hint.get("confidence") or "")
        item = (rank.get(confidence, 5), str(code))
        if best is None or item < best:
            best = item
    return best[1] if best else None


def cloud_write_values_for_code(cloud_code: str) -> Any:
    """Return configured write value choices for a cloud code, if any."""
    hint = cloud_hint(cloud_code)
    return hint.get("write_values") or WARMLINK_CLOUD_WRITE_TEST_CODES.get(cloud_code, {}).get("values")


def current_raw_text_for_cloud_write(register: Any) -> str:
    """Return the current raw register value as text for cloud-write dialogs."""
    if register is None:
        return ""
    try:
        return str(int(getattr(register, "raw_value")))
    except Exception:
        return str(getattr(register, "raw_value", "") or "")


def cloud_write_choice_options(values: Any, current_raw: str = "") -> tuple[list[tuple[str, str]], int]:
    """Build value/label choices and selected index for enumerated cloud writes."""
    if not isinstance(values, dict) or not values:
        return [], 0
    options: list[tuple[str, str]] = [(str(v), f"{v} - {label}") for v, label in values.items()]
    current_index = 0
    for i, (value, _label) in enumerate(options):
        if current_raw and value == current_raw:
            current_index = i
            break
    return options, current_index


def cloud_write_value_from_label(options: list[tuple[str, str]], selected_label: str) -> str | None:
    """Resolve a selected display label back to the cloud value string."""
    for value, label in options:
        if label == selected_label:
            return value
    return None
