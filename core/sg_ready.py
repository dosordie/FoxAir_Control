from __future__ import annotations


CLASSIC_VIRTUAL_STAGES = (
    ("Mode 1 / Schlafmodus", 1),
    ("Mode 2 / Normal / wenig PV", 2),
    ("Mode 3 / mittel PV", 3),
    ("Mode 4 / High PV", 4),
)
PV_THREE_STAGE_OPTIONS = (
    ("Low PV – Begrenzung über SG03 (1336)", 1),
    ("Neutral / Normalbetrieb – keine SG-Anpassung", 2),
    ("High PV – SG05/SG06 Anhebung, SG07 Absenkung", 3),
)


def virtual_stage_options(sg_mode: int) -> tuple[tuple[str, int], ...]:
    """Return the firmware-specific choices exposed through virtual register 8801."""
    return PV_THREE_STAGE_OPTIONS if int(sg_mode) == 7 else CLASSIC_VIRTUAL_STAGES


def sg_status_description(sg_mode: int, status: int) -> str:
    """Describe effective register 2133 without applying the app's contact-bit view."""
    if int(sg_mode) == 7:
        return {
            1: "Low PV – Begrenzung über SG03 (1336)",
            2: "Neutral / Normalbetrieb – keine SG-Anpassung",
            3: "High PV – SG05/SG06 Anhebung, SG07 Absenkung",
        }.get(int(status), "unbekannte dreistufige PV-Stufe")
    return {
        0: "WP aus oder SG deaktiviert",
        1: "SG Mode 1 / Schlafmodus",
        2: "SG Mode 2 / wenig PV",
        3: "SG Mode 3 / mittel PV",
        4: "SG Mode 4 / High PV",
    }.get(int(status), "unbekannt / nicht interpretiert")
