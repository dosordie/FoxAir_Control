"""Cloud helper package."""

from __future__ import annotations


def _ensure_warmlink_write_test_codes() -> None:
    """Provide optional write-test code metadata for generated mapping files.

    Some generated versions of cloud.warmlink_codes do not include the optional
    WARMLINK_CLOUD_WRITE_TEST_CODES constant. Older UI code imports it directly,
    so add a safe fallback before those imports happen.
    """
    try:
        from cloud import warmlink_codes
    except Exception:
        return
    if hasattr(warmlink_codes, "WARMLINK_CLOUD_WRITE_TEST_CODES"):
        return
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


_ensure_warmlink_write_test_codes()
