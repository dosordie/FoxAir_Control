from __future__ import annotations

from core.foxair_phnix_core import DEFAULT_BUS_ADDR


def display_bus_address_info(addr: int) -> tuple[str, str, str]:
    """Documented roles on the internal board bus and separate Warmlink bus."""
    addr = int(addr)
    if addr == 0x00:
        return (
            "Mainboard-Broadcast / WP-Live- und Statuswerte",
            "Mainboard-Broadcast 2001–2090 und 2091–2180",
            "Broadcast auf dem internen Boardbus",
        )
    if addr == 0x01:
        return (
            "Verdichter-/Leistungs-/Inverterboard (+ Fan-Driver bei H33)",
            "FC10 1999ff Sollwerte; FC03 2099ff Telemetrie",
            "interner Boardbus-Teilnehmer",
        )
    if addr == 0x02:
        return (
            "Optionaler zweiter HMI-/Controller-Kanal",
            "keine weiteren Frames bestätigt",
            "optionaler interner Kanal",
        )
    if addr == 0x03:
        return (
            "DWIN-/Wire-Controller / Hauptdisplay",
            "FC03 3001/21",
            "Hauptdisplay / DWIN",
        )
    if addr == 0x04:
        return (
            "Separater Fan-Driver-Pfad",
            "wird vom Mainboard gepollt",
            "bei integriertem Fan-Driver ggf. ohne separate Antwort",
        )
    if addr == 0x05:
        return (
            "Hydraulik-/Erweiterungsmodul",
            "FC03 2000ff lesen; FC10 1001ff schreiben",
            "interner Boardbus-Teilnehmer",
        )
    if addr == 0x61:
        return (
            "Alternatives Hydraulikmodul bei H30=3",
            "alternative Variante von 0x05",
            "interner Boardbus-Teilnehmer",
        )
    if addr == DEFAULT_BUS_ADDR:
        return (
            "Wärmepumpen-Mainboard als Slave",
            "Warmlink/LTE-Service-Modbus, Slave 0x63",
            "separater USART1-/9600-Baud-Bus; nicht der interne Boardbus",
        )
    return ("unbekannt", "noch keine feste Zuordnung", "nur beobachten")
