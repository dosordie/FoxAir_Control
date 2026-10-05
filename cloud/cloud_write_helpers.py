"""Pure helper functions for WarmLink cloud write preparation."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

from cloud.register_resolver import CONFIRMED_REGISTER_ALIASES, resolve_cloud_register
from cloud.mapping_validation import register_code_from_definition
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


def cloud_code_is_write_candidate(code: str, hint: Mapping[str, Any]) -> bool:
    """Return whether a mapped cloud code is safe to offer for writing."""
    if resolve_cloud_register(str(code), hint, _static_register_defs()) is None:
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
    definitions = _static_register_defs()
    local_code = register_code_from_definition(definitions.get(str(target), {})).upper()
    for code, hint in WARMLINK_CLOUD_CODE_HINTS.items():
        # A dialog refresh needs only this register. Avoid resolving the entire
        # catalog (each resolution scans the map) on every UI update.
        hinted_code = str(hint.get("local_code") or "").strip().upper()
        if not (local_code and hinted_code == local_code) and CONFIRMED_REGISTER_ALIASES.get(str(code)) != target:
            continue
        mapped = resolve_cloud_register(str(code), hint, definitions)
        if mapped != target:
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


def cloud_write_value_from_user_input(
    cloud_code: str, user_text: str, register: Any, parse_local_raw,
) -> str:
    """Convert the quick-write field to one unambiguous cloud engineering value."""
    text = str(user_text).strip()
    if not text:
        raise ValueError("Der Cloud-Schreibwert ist leer.")
    raw = int(parse_local_raw(text))
    values = cloud_write_values_for_code(cloud_code)
    if isinstance(values, Mapping) and values:
        if str(raw) not in {str(key) for key in values}:
            raise ValueError(f"Wert {raw} ist für Cloud-Code {cloud_code} nicht freigegeben.")
        return str(raw)
    dtype = str(getattr(register, "dtype", "") or "").upper()
    scaled = {"TEMP", "TEMP1", "TEMP05", "TEMP_0_5", "STEP_0_5C", "DIGI5",
              "DIGI6", "DIGI19", "DIGI4", "POWER_KW_X10", "KW_X10",
              "BAR_X10", "FLOW_M3H_X10", "FLOW_M3H_X100", "AMP_X10", "AMP_X2"}
    if dtype in scaled:
        # The quick-write field already contains the engineering value expected by Cloud.
        return text.replace(",", ".")
    return str(raw)
