"""Authoritative WarmLink cloud-code to current local-register resolution."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

from cloud.mapping_validation import register_code_from_definition


# Confirmed cloud aliases whose target has no suitable ``code`` field in the
# local register map.  Keep this deliberately explicit: spelling alone must
# never turn an unknown/candidate cloud code into a mapping.
CONFIRMED_REGISTER_ALIASES: dict[str, int] = {
    "2014": 2014,
    "2146": 2146,
    "Power": 1011,
    "Mode": 1012,
    "ModeState": 2012,
    "O01~023": 2019,
    "O15": 2020,
    "O17": 2022,
    "S01~S10": 2034,
    "Timer_Mute_On_En": 1244,
    "TimerMuteOnHour": 1245,
    "TimerMuteOnMinute": 1246,
    "Timer_Mute_Off_En": 1247,
    "TimerMuteOffHour": 1248,
    "TimerMuteOffMinute": 1249,
    "compensate_slope": 1234,
    "compensate_offset": 1235,
    "code_version": 2104,
    "MainBoard Version": 2105,
}


@lru_cache(maxsize=1)
def current_register_definitions() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "foxair_phnix_registers.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def resolve_cloud_register(
    cloud_code: str,
    hint: Mapping[str, Any],
    register_defs: Mapping[str, Any] | None = None,
) -> int | None:
    """Resolve a confirmed cloud hint against the *current* register map.

    A unique ``local_code`` match takes precedence over the historical address
    stored in the hint.  Only reviewed aliases may bypass that code lookup.
    """
    code = str(cloud_code or "").strip()
    if str(hint.get("confidence") or "").strip().lower() != "confirmed":
        return None
    definitions = register_defs if register_defs is not None else current_register_definitions()
    local_code = str(hint.get("local_code") or "").strip().upper()
    if local_code:
        matches: list[int] = []
        for reg_text, definition in definitions.items():
            if register_code_from_definition(definition).upper() != local_code:
                continue
            try:
                matches.append(int(reg_text))
            except (TypeError, ValueError):
                continue
        if len(matches) == 1:
            return matches[0]
    alias = CONFIRMED_REGISTER_ALIASES.get(code)
    if alias is not None and str(alias) in definitions:
        return alias
    return None

