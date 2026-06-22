"""Pure helper functions for WarmLink cloud write preparation."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

from cloud.mapping_validation import cloud_hint_matches_local_code, register_code_from_definition
from cloud.warmlink_codes import WARMLINK_CLOUD_CODE_HINTS, cloud_hint

try:
    from cloud.warmlink_codes import WARMLINK_CLOUD_WRITE_TEST_CODES
except ImportError:
    # Backwards-compatible fallback: older/generated mapping files may not
    # contain this optional helper table. Keep startup working and still offer
    # the small, explicit write choices for Mode/Power.
    WARMLINK_CLOUD_WRITE_TEST_CODES: dict[str, dict[str, object]] = {
        "Mode": {
            "name": "Betriebsart umschalten",
            "values": {
                "0": "Warmwasser",
                "1": "Heizen",
                "2": "Kühlen",
                "3": "WW+Heizen",
                "4": "WW+Kühlen",
            },
            "note": "Testcode fuer Heizen/Kuehlen/WW-Umschaltung. Nur mit Extra-Bestaetigung senden.",
        },
        "Power": {
            "name": "WP Ein/Aus",
            "values": {"0": "Aus", "1": "Ein"},
            "note": "Optionaler Schreibtest.",
        },
    }


@lru_cache(maxsize=1)
def _static_register_defs() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "foxair_phnix_registers.json"
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _static_local_code_for_register(reg_no: int) -> str:
    defs = _static_register_defs()
    definition = defs.get(str(int(reg_no)))
    if definition is None:
        return ""
    return register_code_from_definition(definition)


def _cloud_mapping_is_valid_for_register(code: str, hint: Mapping[str, Any], reg_no: int) -> bool:
    local_code = _static_local_code_for_register(reg_no)
    return cloud_hint_matches_local_code(code, hint, local_code)


def cloud_code_is_write_candidate(code: str, hint: Mapping[str, Any]) -> bool:
    """Return whether a mapped cloud code is safe to offer for writing."""
    if not hint.get("modbus_register"):
        return False
    try:
        mapped_register = int(hint.get("modbus_register"))
    except Exception:
        return False
    if not _cloud_mapping_is_valid_for_register(str(code), hint, mapped_register):
        return False
    if str(hint.get("confidence") or "").lower() != "confirmed":
        return False
    return bool(hint.get("write_allowed"))


def cloud_code_for_register(reg_no: int, require_write_allowed: bool = False) -> str | None:
    """Find the best mapped WarmLink cloud code for a local register."""
    try:
        target = int(reg_no)
    except Exception:
        return None
    best: tuple[int, str] | None = None
    rank = {"confirmed": 0}
    for code, hint in WARMLINK_CLOUD_CODE_HINTS.items():
        try:
            mapped = int(hint.get("modbus_register")) if hint.get("modbus_register") not in (None, "") else None
        except Exception:
            mapped = None
        if mapped != target:
            continue
        if not _cloud_mapping_is_valid_for_register(str(code), hint, target):
            continue
        if require_write_allowed and not cloud_code_is_write_candidate(str(code), hint):
            continue
        confidence = str(hint.get("confidence") or "")
        if confidence != "confirmed":
            continue
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
