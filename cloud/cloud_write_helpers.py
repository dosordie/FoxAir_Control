"""Pure helper functions for WarmLink cloud write preparation."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

from cloud.register_resolver import CONFIRMED_REGISTER_ALIASES, resolve_cloud_register
from cloud.mapping_validation import register_code_from_definition
from cloud.warmlink_codes import WARMLINK_CLOUD_CODE_HINTS, cloud_hint


SILENT_TIMER_CODES = {
    1244: "Timer_Mute_On_En", 1245: "TimerMuteOnHour", 1246: "TimerMuteOnMinute",
    1247: "Timer_Mute_Off_En", 1248: "TimerMuteOffHour", 1249: "TimerMuteOffMinute",
}

SILENT_TIMER_LIMITS = dict(zip(SILENT_TIMER_CODES.values(), (1, 23, 59, 1, 23, 59)))


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
    # Use the exact configuration codes, even when a read-only numeric alias
    # for the same register is also present in the discovery catalog.
    preferred = {**SILENT_TIMER_CODES, 1234: "compensate_slope", 1235: "compensate_offset",
                 1250: "CP1-1", 1251: "CP1-2", 1252: "CP1-3",
                 1253: "CP1-5", 1254: "CP1-6", 1255: "CP1-7",
                 **{1333 + i: f"SG{i:02}" for i in range(1, 9)}, 2133: "SG Status"}
    definitions = _static_register_defs()
    local_code = register_code_from_definition(definitions.get(str(target), {})).upper()
    for code, hint in WARMLINK_CLOUD_CODE_HINTS.items():
        if target in preferred and code != preferred[target]:
            continue
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
        item = (0, str(code))
        if best is None or item < best:
            best = item
    return best[1] if best else None


def cloud_write_values_for_code(cloud_code: str) -> Any:
    """Return configured write value choices for a cloud code, if any."""
    hint = cloud_hint(cloud_code)
    return hint.get("write_values")


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


def cloud_write_value_from_register_value(cloud_code, raw_value, register, engineering_value=None):
    """Prepare a normal control value using the same conversion as quick-write.

    Decode a local word only when the caller has no engineering value. Never
    treat the raw carrier of a Cloud-only row as a local value.
    """
    from core.foxair_phnix_core import numeric_value_by_type
    import math

    if engineering_value is None:
        engineering_value = numeric_value_by_type(int(raw_value), register.dtype)
    if not math.isfinite(float(engineering_value)):
        raise ValueError("Der Cloud-Schreibwert muss eine endliche Zahl sein.")
    text = str(engineering_value)
    return cloud_write_value_from_user_input(cloud_code, text, register, lambda _text: int(raw_value))


def cloud_readback_matches(code, requested, row):
    """Compare fresh engineering numbers within half one register step."""
    import math
    from core.foxair_phnix_core import numeric_value_by_type
    if (not row.get("supported") or row.get("value") is None
            or any(row.get(flag) for flag in ("cached", "stale", "currentEmpty"))):
        return False
    try:
        expected, actual = float(requested), float(row["value"])
        if code in SILENT_TIMER_CODES.values() and not (expected.is_integer() and actual.is_integer()):
            return False
        register = resolve_cloud_register(code, cloud_hint(code), _static_register_defs())
        definition = _static_register_defs().get(str(register), {})
        dtype = definition.get("type", "DIGI1")
        step = abs(numeric_value_by_type(1, dtype) - numeric_value_by_type(0, dtype)) or 1.0
        return math.isfinite(expected) and math.isfinite(actual) and math.isclose(
            expected, actual, rel_tol=0, abs_tol=step / 2 + 1e-9)
    except (ValueError, TypeError, KeyError):
        return False


def validate_cloud_commands(commands):
    """Validate the entire batch before any network I/O, including every grant."""
    import math
    from cloud.metadata import resolve_cloud_range

    result = []
    seen = set()
    for code, value in commands:
        code, value = str(code).strip(), str(value).strip().replace(",", ".")
        hint = cloud_hint(code)
        if not cloud_code_is_write_candidate(code, hint):
            raise ValueError(f"Cloud-Schreiben für {code} ist nicht freigegeben.")
        if code in seen:
            raise ValueError(f"Doppelter Cloud-Schreibcode: {code}")
        try:
            number = float(value)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Ungültiger Cloud-Wert für {code}") from exc
        if not math.isfinite(number):
            raise ValueError(f"Cloud-Wert für {code} muss endlich sein.")
        if code in SILENT_TIMER_LIMITS:
            if not number.is_integer() or not 0 <= number <= SILENT_TIMER_LIMITS[code]:
                raise ValueError(f"Cloud-Timerwert für {code} muss ganzzahlig zwischen 0 und {SILENT_TIMER_LIMITS[code]} liegen.")
        choices = cloud_write_values_for_code(code)
        if choices and number not in {float(key) for key in choices}:
            raise ValueError(f"Wert für {code} ist nicht freigegeben.")
        bounds = resolve_cloud_range(code, hint, {})
        for limit, lower in ((bounds.minimum, True), (bounds.maximum, False)) if bounds.confirmed else ():
            try:
                outside = number < float(limit) if lower else number > float(limit)
            except (ValueError, TypeError):
                outside = False
            if outside:
                raise ValueError(f"Cloud-Wert für {code} liegt außerhalb des Wertebereichs.")
        seen.add(code)
        result.append((code, value))
    if not result:
        raise ValueError("Leerer Cloud-Schreibauftrag.")
    return tuple(result)




def cloud_command_batches(commands):
    """Verified barriers: disable first, parameters together, enable last."""
    barriers = {"SG01", "Timer_Mute_On_En", "Timer_Mute_Off_En"}
    disable = tuple(item for item in commands if item[0] in barriers and float(item[1]) == 0)
    parameters = tuple(item for item in commands if item[0] not in barriers)
    enable = tuple(item for item in commands if item[0] in barriers and float(item[1]) != 0)
    return tuple(group for group in (disable, parameters, enable) if group)
