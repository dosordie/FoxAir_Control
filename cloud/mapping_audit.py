"""Read-only catalog audit; runtime support requires actual scan rows."""

from collections import defaultdict

from cloud.register_resolver import (
    current_register_definitions, resolve_cloud_projection_register, resolve_cloud_register,
)
from cloud.warmlink_codes import (
    WARMLINK_644_DISCOVERY_CODES, WARMLINK_CLOUD_CODE_HINTS, merged_cloud_metadata,
)


def audit_cloud_mappings(rows=None, *, hints=None, register_defs=None, discovery_codes=None):
    """Compare discovery, reviewed hints and current MAIN definitions.

    ``rows`` optionally supplies normalized rows from one current scan. Static
    app knowledge or a historical GL9 test never asserts runtime support.
    Confirmed mapping errors fail the audit; unmapped codes and aliases are
    reported separately and never acquire a guessed register.
    """
    hints = WARMLINK_CLOUD_CODE_HINTS if hints is None else hints
    definitions = current_register_definitions() if register_defs is None else register_defs
    discovery = set(WARMLINK_644_DISCOVERY_CODES if discovery_codes is None else discovery_codes)
    live = {str(row["code"]): row for row in rows or [] if row.get("code")}
    codes = sorted(discovery | set(hints) | set(live))
    entries, errors, aliases = [], [], defaultdict(list)
    for code in codes:
        hint = hints.get(code, {})
        strict = resolve_cloud_register(code, hint, definitions)
        projection = resolve_cloud_projection_register(code, hint, definitions)
        declared = hint.get("modbus_register")
        confirmed = str(hint.get("confidence", "")).lower() == "confirmed"
        if confirmed and declared is not None:
            if str(declared) not in definitions:
                errors.append({"code": code, "error": "target_missing", "register": declared})
            if strict is None:
                errors.append({"code": code, "error": "confirmed_mapping_unresolved"})
            elif strict != declared:
                errors.append({"code": code, "error": "hint_target_mismatch",
                               "hint_register": declared, "resolved_register": strict})
            if projection != strict:
                errors.append({"code": code, "error": "projection_resolver_mismatch"})
        if strict is not None:
            aliases[strict].append(code)
        row = live.get(code, {})
        supported = row.get("supported") if isinstance(row.get("supported"), bool) else None
        deliberate = bool(hint.get("mapping_intentionally_absent"))
        entries.append({
            "code": code, "known": code in discovery or code in hints,
            "discovery": code in discovery,
            "app_known": bool(merged_cloud_metadata(code).get("app_known")),
            "hint_known": bool(hint), "supported": supported,
            "gl9_tested_supported": hint.get("gl9_tested_supported"),
            "confirmed_mapped": strict is not None, "main_register": strict,
            "projection_register": projection,
            "mapping_intentionally_absent": deliberate,
            "mapping_missing": strict is None and not deliberate,
        })
    return {
        "counts": {
            "known": sum(entry["known"] for entry in entries),
            "app_known": sum(entry["app_known"] for entry in entries),
            "discovery": len(discovery),
            "confirmed_mapped": sum(entry["confirmed_mapped"] for entry in entries),
            "confirmed_main_registers": len(aliases),
            "mapping_missing": sum(entry["mapping_missing"] for entry in entries),
            "mapping_intentionally_absent": sum(entry["mapping_intentionally_absent"] for entry in entries),
            "supported": None if rows is None else sum(entry["supported"] is True for entry in entries),
            "supported_unmapped": None if rows is None else sum(
                entry["supported"] is True and not entry["confirmed_mapped"] for entry in entries),
        },
        "errors": errors,
        "aliases": [{"main_register": register, "codes": values}
                    for register, values in sorted(aliases.items()) if len(values) > 1],
        "codes": entries,
    }
