from __future__ import annotations


SG_MODE_OPTIONS = (
    ("Aus", 0),
    ("Klassisch: 1 Kontakt", 1),
    ("Klassisch: 2 Kontakte", 2),
    ("Klassisch: Modbus 8801 / 4 Zustände", 3),
    ("AI Saving / Remote Energy Control", 4),
    ("SG/PV erweitert: 1 Kontakt (Neutral / High)", 5),
    ("SG/PV erweitert: 2 Kontakte (Low / Neutral / High)", 6),
    ("SG/PV erweitert: Modbus 8801 (Low / Neutral / High)", 7),
)

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
    mode = int(sg_mode)
    if mode == 3:
        return CLASSIC_VIRTUAL_STAGES
    if mode == 7:
        return PV_THREE_STAGE_OPTIONS
    return ()


def uses_virtual_sg_input(sg_mode: int, backend_key: str) -> bool:
    """Return whether register 8801 is usable for this SG01/backend combination."""
    return str(backend_key) == "standard_modbus" and int(sg_mode) in (3, 7)


def sg_status_description(sg_mode: int, status: int) -> str:
    """Describe effective register 2133 without applying the app's contact-bit view."""
    mode = int(sg_mode)
    if mode == 7:
        return {
            1: "Low PV – Begrenzung über SG03 (1336)",
            2: "Neutral / Normalbetrieb – keine SG-Anpassung",
            3: "High PV – SG05/SG06 Anhebung, SG07 Absenkung",
        }.get(int(status), "unbekannte dreistufige PV-Stufe")
    if mode in (5, 6):
        return f"Status RAW {int(status)} – erweiterter physischer SG/PV-Pfad"
    if mode == 4:
        return f"Status RAW {int(status)} – AI Saving / Remote Energy Control"
    return {
        0: "WP Aus / SG Ready Aus",
        1: "SG Mode 1 / Schlafmodus",
        2: "SG Mode 2 / wenig PV",
        3: "SG Mode 3 / mittel PV",
        4: "SG Mode 4 / High PV",
    }.get(int(status), "unbekannt / nicht interpretiert")
