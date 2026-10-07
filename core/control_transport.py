"""Pure control routing and capabilities; I/O stays in MainWindow."""
from dataclasses import dataclass
from typing import Any


LOCAL_TRANSPORTS = frozenset({"standard_modbus", "warmlink_raw", "display_modbus"})
TRANSPORT_NAMES = {
    "standard_modbus": "Standard-Modbus", "warmlink_raw": "Warmlink-Modbus",
    "display_modbus": "Display-Modbus", "cloud": "WarmLink Cloud", "none": "nicht verbunden",
}


def select_control_transport(local_connected, local_backend, cloud_connected):
    # An unsupported local backend must never fall through to Cloud.
    if local_connected:
        return local_backend if local_backend in LOCAL_TRANSPORTS else "none"
    return "cloud" if cloud_connected else "none"


@dataclass(frozen=True)
class ControlContext:
    transport: str
    local_worker: Any = None
    username: str = ""
    device_code: str = ""


@dataclass(frozen=True)
class ControlCapability:
    available: bool
    reason: str = ""

    def __bool__(self):
        return self.available


def register_control_capability(context, registers, code_for_register, *, write=False,
                                capture=False, busy=False):
    if capture:
        return ControlCapability(False, "Firmware-Capture aktiv – aktive Steuerbefehle sind gesperrt.")
    if context.transport in LOCAL_TRANSPORTS:
        return ControlCapability(context.local_worker is not None,
                                 "" if context.local_worker is not None else
                                 "Aktion über die aktuelle lokale Verbindung nicht verfügbar.")
    if context.transport != "cloud":
        return ControlCapability(False, "Keine Steuerverbindung verfügbar.")
    if not context.username or not context.device_code:
        return ControlCapability(False, "Keine gültige Cloud-Geräteauswahl verfügbar.")
    for register in registers:
        if code_for_register(register, require_write_allowed=write) is None:
            action = "Schreiben" if write else "Lesen"
            return ControlCapability(False, f"Cloud-{action} für Register {register} ist noch nicht bestätigt.")
    if busy:
        return ControlCapability(False, "Ein Cloudauftrag läuft; bitte danach erneut versuchen.")
    return ControlCapability(True)
