"""Cloud helper package."""

from __future__ import annotations


def _ensure_warmlink_compat() -> None:
    """Provide compatibility aliases for generated WarmLink mapping files."""
    try:
        from cloud import warmlink_codes
    except Exception:
        return

    if not hasattr(warmlink_codes, "WARMLINK_CLOUD_WRITE_TEST_CODES"):
        warmlink_codes.WARMLINK_CLOUD_WRITE_TEST_CODES = {
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

    if not hasattr(warmlink_codes, "cloud_modbus_register"):
        if hasattr(warmlink_codes, "code_modbus_register"):
            warmlink_codes.cloud_modbus_register = warmlink_codes.code_modbus_register
        else:
            def _cloud_modbus_register(code: str):
                hint = warmlink_codes.cloud_hint(code) if hasattr(warmlink_codes, "cloud_hint") else {}
                try:
                    return int(hint.get("modbus_register")) if hint.get("modbus_register") not in (None, "") else None
                except Exception:
                    return None
            warmlink_codes.cloud_modbus_register = _cloud_modbus_register


_ensure_warmlink_compat()
