"""Physical cloud metadata, independent of WarmLink transport data types."""

from __future__ import annotations

from typing import Any, Mapping

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
