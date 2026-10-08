"""Physical cloud metadata, independent of WarmLink transport data types."""

from __future__ import annotations

from typing import Any, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
from pathlib import Path

from cloud.register_resolver import current_register_definitions, resolve_cloud_register


def explicit_unit(metadata: Mapping[str, Any] | None) -> str:
    """Accept only an actual, nonempty unit string; never infer from TEMP."""
    value = (metadata or {}).get("unit")
    return value.strip() if isinstance(value, str) else ""


def resolve_cloud_unit(
    code: str,
    hint: Mapping[str, Any],
    live: Mapping[str, Any] | None = None,
    definition: Mapping[str, Any] | None = None,
) -> str:
    """Live unit > confirmed local definition > static hint > no unit."""
    unit = explicit_unit(live)
    if unit:
        return unit
    register = resolve_cloud_register(code, hint)
    if register is not None:
        local = definition if definition is not None else current_register_definitions().get(str(register), {})
        unit = explicit_unit(local)
        if unit:
            return unit
    return explicit_unit(hint)


def audit_cloud_units(hints: Mapping[str, Mapping[str, Any]], definitions=None) -> dict[str, Any]:
    """Report contradictory units only where both sides have confirmed evidence."""
    definitions = definitions if definitions is not None else current_register_definitions()
    checked = 0
    missing_local_unit = []
    conflicts = []
    for code, hint in hints.items():
        register = resolve_cloud_register(code, hint, definitions)
        if register is None:
            continue
        checked += 1
        local_unit = explicit_unit(definitions[str(register)])
        hint_unit = explicit_unit(hint)
        if not local_unit:
            missing_local_unit.append(code)
        elif hint_unit and hint_unit != local_unit:
            conflicts.append({"code": code, "register": register, "hint_unit": hint_unit, "local_unit": local_unit})
    return {"checked": checked, "conflicts": conflicts, "missing_local_unit": missing_local_unit}


@dataclass(frozen=True)
class CloudRange:
    minimum: Any = ""
    maximum: Any = ""
    source: str = "unknown"
    confirmed: bool = False
    unit: str = ""

    @property
    def description(self) -> str:
        return {
            "live": "Bereich aus aktueller Cloud-Antwort",
            "register": "Bestätigter Bereich aus Registerdefinition (Engineering-Werte)",
            "knowledge": "Bestätigter Bereich aus Projektwissen (Engineering-Werte)",
            "hint": "Statischer Cloud-Bereich, nicht bestätigt",
            "unknown": "Bereich unbekannt",
        }[self.source]


@lru_cache(maxsize=1)
def current_register_knowledge() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "foxair_phnix_knowledge.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _range_number(value: Any) -> Decimal | None:
    """Parse only explicit numeric fields, never descriptions or defaults."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _explicit_range(metadata: Mapping[str, Any], lower: str, upper: str) -> tuple[Any, Any] | None:
    start, end = metadata.get(lower), metadata.get(upper)
    start_present = start is not None and start != ""
    end_present = end is not None and end != ""
    if not start_present and not end_present:
        return None
    start_number = _range_number(start) if start_present else None
    end_number = _range_number(end) if end_present else None
    if (start_present and start_number is None) or (end_present and end_number is None):
        return None
    if start_number is not None and end_number is not None and start_number > end_number:
        return None
    # A partial live response stays partial; do not invent or mix boundaries.
    return (start if start_present else "", end if end_present else "")


def _confirmed_local_range(code, hint, definitions, knowledge) -> CloudRange:
    register = resolve_cloud_register(code, hint, definitions)
    if register is None:
        return CloudRange()
    unit = resolve_cloud_unit(code, hint, definition=definitions.get(str(register), {}))
    for source, entry in (("register", definitions.get(str(register), {})),
                          ("knowledge", knowledge.get(str(register), {}))):
        if not isinstance(entry, Mapping):
            continue
        bounds = entry.get("range")
        if not isinstance(bounds, Mapping):
            continue
        if bounds.get("confidence") != "confirmed" or bounds.get("representation") != "engineering" or not bounds.get("source"):
            continue
        # Do not silently combine physical ranges in different units.
        if unit and explicit_unit(bounds) and explicit_unit(bounds) != unit:
            continue
        values = _explicit_range(bounds, "min", "max")
        if values is not None and values[0] != "" and values[1] != "":
            return CloudRange(*values, source, True, explicit_unit(bounds))
    return CloudRange()


def resolve_cloud_range(
    code: str, hint: Mapping[str, Any], live: Mapping[str, Any] | None = None,
    *, definitions=None, knowledge=None,
) -> CloudRange:
    """Live bounds > reviewed structured local bounds > unconfirmed hint > empty."""
    values = _explicit_range(live or {}, "rangeStart", "rangeEnd")
    if values is not None:
        return CloudRange(*values, "live", True, explicit_unit(live))
    definitions = definitions if definitions is not None else current_register_definitions()
    knowledge = knowledge if knowledge is not None else current_register_knowledge()
    local = _confirmed_local_range(code, hint, definitions, knowledge)
    live_unit = explicit_unit(live)
    if local.source != "unknown":
        if live_unit and local.unit != live_unit:
            return CloudRange()
        return local
    if live_unit and explicit_unit(hint) != live_unit:
        return CloudRange()
    values = _explicit_range(hint, "rangeStart", "rangeEnd")
    return CloudRange(*values, "hint", False, explicit_unit(hint)) if values is not None else CloudRange()


def audit_cloud_ranges(hints: Mapping[str, Mapping[str, Any]], definitions=None, knowledge=None) -> dict[str, Any]:
    """Compare only explicit, reviewed bounds in the same engineering units."""
    definitions = definitions if definitions is not None else current_register_definitions()
    knowledge = knowledge if knowledge is not None else current_register_knowledge()
    checked = 0
    local_ranges = 0
    conflicts = []
    missing_local_range = []
    unverified_static_ranges = []
    for code, hint in hints.items():
        register = resolve_cloud_register(code, hint, definitions)
        if register is None:
            continue
        checked += 1
        local = _confirmed_local_range(code, hint, definitions, knowledge)
        values = _explicit_range(hint, "rangeStart", "rangeEnd")
        if local.source == "unknown":
            missing_local_range.append(code)
            if values is not None:
                unverified_static_ranges.append(code)
            continue
        local_ranges += 1
        if values is not None and any(
            value != "" and _range_number(value) != _range_number(bound)
            for value, bound in zip(values, (local.minimum, local.maximum))
        ):
            conflicts.append({"code": code, "register": register,
                              "hint_range": list(values),
                              "local_range": [local.minimum, local.maximum],
                              "source": local.source})
    return {"checked": checked, "local_ranges": local_ranges, "conflicts": conflicts,
            "missing_local_range": missing_local_range,
            "unverified_static_ranges": unverified_static_ranges}
