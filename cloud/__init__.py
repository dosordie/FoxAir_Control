"""Cloud helper package."""

from __future__ import annotations


def _ensure_warmlink_compat() -> None:
    """Provide compatibility aliases for generated WarmLink mapping files."""
    try:
        from cloud import warmlink_codes
    except Exception:
        return

    def _cloud_hint(code: str):
        hints = getattr(warmlink_codes, "WARMLINK_CLOUD_CODE_HINTS", {})
        return hints.get(str(code), {}) if isinstance(hints, dict) else {}

    if not hasattr(warmlink_codes, "cloud_hint"):
        warmlink_codes.cloud_hint = _cloud_hint

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

    if not hasattr(warmlink_codes, "code_display_name"):
        def _code_display_name(code: str) -> str:
            return str(warmlink_codes.cloud_hint(code).get("name") or code)
        warmlink_codes.code_display_name = _code_display_name

    if not hasattr(warmlink_codes, "code_unit"):
        def _code_unit(code: str) -> str:
            return str(warmlink_codes.cloud_hint(code).get("unit") or "")
        warmlink_codes.code_unit = _code_unit

    if not hasattr(warmlink_codes, "code_confidence"):
        def _code_confidence(code: str) -> str:
            return str(warmlink_codes.cloud_hint(code).get("confidence") or "")
        warmlink_codes.code_confidence = _code_confidence

    if not hasattr(warmlink_codes, "code_modbus_register"):
        def _code_modbus_register(code: str):
            hint = warmlink_codes.cloud_hint(code)
            try:
                return int(hint.get("modbus_register")) if hint.get("modbus_register") not in (None, "") else None
            except Exception:
                return None
        warmlink_codes.code_modbus_register = _code_modbus_register

    if not hasattr(warmlink_codes, "cloud_modbus_register"):
        warmlink_codes.cloud_modbus_register = warmlink_codes.code_modbus_register


_ensure_warmlink_compat()
