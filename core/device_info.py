"""Pure decoders and state for the asynchronous PHNIX device-info cycle."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
import time
from typing import Optional, Sequence


DEVICE_INFO_BLOCK_STARTS = (1001, 1091, 1181, 1271, 1361, 1451, 2001, 2091)
C37B_STATUS = {
    3: "Datenphase und erste MD5-/Stagingprüfung erfolgreich; Abschluss/Promotion läuft noch",
    4: "Daten-/Staging-/MD5- beziehungsweise Push-Fehler",
    5: "Mainboard-OTA/Promotion erfolgreich abgeschlossen",
    6: "Mainboard-Upgrade/Promotion fehlgeschlagen",
    7: "C544-Geräte-/Versionsinformation vom LTE-Modem verarbeitet und quittiert",
}


class DeviceInfoCycleState(str, Enum):
    IDLE = "Bereit"
    TRIGGER_SENT = "Geräteinfo angefordert"
    STARTUP_SEEN = "Startup-/UART-Handshake erkannt"
    PRODUCT_KEY_SEEN = "ProductKey empfangen"
    BLOCKS_RECEIVING = "Datenblöcke werden empfangen"
    BLOCKS_COMPLETE = "Datenblöcke vollständig"
    WAITING_FOR_C544 = "Warte auf Hardware-/Softwareinformation"
    C544_RECEIVED = "Hardware-/Softwareinformation empfangen"
    CONFIRMED = "Versionsinformation bestätigt"
    PARTIAL_TIMEOUT = "Teilweise abgeschlossen; Versionsinformation nicht empfangen"


@dataclass(frozen=True)
class ProductKeyResult:
    value: Optional[str]
    raw: bytes
    error: Optional[str] = None


@dataclass
class DeviceInfoSnapshot:
    state: DeviceInfoCycleState = DeviceInfoCycleState.IDLE
    triggered: bool = False
    startup_seen: bool = False
    product_key: Optional[str] = None
    product_key_error: Optional[str] = None
    product_key_raw: bytes = b""
    wifi_id: Optional[str] = None
    code_date: Optional[str] = None
    production_date: Optional[str] = None
    block_starts: set[int] = field(default_factory=set)
    service_ssid: Optional[int] = None
    hardware_code: Optional[str] = None
    hardware_version: Optional[str] = None
    software_code: Optional[str] = None
    internal_version: Optional[str] = None
    firmware_version: Optional[str] = None
    ack_status: Optional[int] = None
    last_update: Optional[float] = None
    cycle_started: Optional[float] = None

    @property
    def block_count(self) -> int:
        return len(self.block_starts)

    @property
    def running(self) -> bool:
        return self.state not in {DeviceInfoCycleState.IDLE, DeviceInfoCycleState.CONFIRMED,
                                  DeviceInfoCycleState.PARTIAL_TIMEOUT}


def words_to_bytes(words: Sequence[int]) -> bytes:
    return b"".join((int(word) & 0xFFFF).to_bytes(2, "big") for word in words)


def decode_wifi_id(words: Sequence[int]) -> Optional[str]:
    raw = words_to_bytes(words[:6])
    if len(raw) != 12 or not all(32 <= byte <= 126 for byte in raw):
        return None
    return raw.decode("ascii")


def decode_wifi_id_date(value: str) -> tuple[Optional[str], Optional[str]]:
    """Return YYMMDD and German date only for the known, structurally valid format."""
    if not re.fullmatch(r"WF\d{10}", value or ""):
        return None, None
    code = value[2:8]
    try:
        parsed = datetime.strptime(code, "%y%m%d")
    except ValueError:
        return code, None
    return code, parsed.strftime("%d.%m.%Y")


def decode_product_key(words: Sequence[int]) -> ProductKeyResult:
    raw = words_to_bytes(words[:16])
    value_raw = raw.split(b"\0", 1)[0]
    if not value_raw:
        return ProductKeyResult("", raw)
    if not all(32 <= byte <= 126 for byte in value_raw):
        return ProductKeyResult(None, raw, "ProductKey enthält ungültige Nicht-ASCII-Bytes")
    return ProductKeyResult(value_raw.decode("ascii"), raw)


def readable_firmware_version(code: str) -> str:
    match = re.fullmatch(r"00(\d)(\d)", code or "")
    return f"V{match.group(1)}.{match.group(2)}" if match else code


def decode_c544(words: Sequence[int]) -> dict[str, object]:
    if len(words) != 13:
        raise ValueError("C544 benötigt exakt 13 Register")
    def ascii_field(start: int, count: int) -> str:
        raw = words_to_bytes(words[start:start + count])
        if not all(byte == 0 or 32 <= byte <= 126 for byte in raw):
            raise ValueError("C544 enthält ungültige Nicht-ASCII-Bytes")
        return raw.split(b"\0", 1)[0].decode("ascii").rstrip()
    internal = ascii_field(11, 2)
    return {"service_ssid": int(words[0]) & 0xFFFF, "hardware_code": ascii_field(1, 4),
            "hardware_version": ascii_field(5, 2), "software_code": ascii_field(7, 4),
            "internal_version": internal, "firmware_version": readable_firmware_version(internal)}


def decode_c37b(words: Sequence[int]) -> dict[str, object]:
    if len(words) != 2:
        raise ValueError("C37B benötigt exakt zwei Register")
    status = int(words[1]) & 0xFFFF
    return {"service_ssid": int(words[0]) & 0xFFFF, "status": status,
            "meaning": C37B_STATUS.get(status, "Unbekannter Quittungsstatus")}


def fc16_data_words(raw: bytes) -> Optional[tuple[int, list[int]]]:
    """Return data words; an eight-byte FC16 write ACK intentionally returns None."""
    if len(raw) == 8 or len(raw) < 9 or raw[1] != 0x10:
        return None
    addr, qty, byte_count = int.from_bytes(raw[2:4], "big"), int.from_bytes(raw[4:6], "big"), raw[6]
    if byte_count != qty * 2 or len(raw) != byte_count + 9:
        return None
    payload = raw[7:7 + byte_count]
    return addr, [int.from_bytes(payload[i:i + 2], "big") for i in range(0, len(payload), 2)]


class DeviceInfoTracker:
    TIMEOUT_SECONDS = 180.0

    def __init__(self) -> None:
        self.snapshot = DeviceInfoSnapshot()

    def start(self, now: Optional[float] = None) -> None:
        self.snapshot.state = DeviceInfoCycleState.TRIGGER_SENT
        self.snapshot.triggered = True
        self.snapshot.startup_seen = False
        self.snapshot.block_starts.clear()
        self.snapshot.cycle_started = time.time() if now is None else now
        self.snapshot.last_update = self.snapshot.cycle_started

    def hydrate_cache(self, values: dict[int, int]) -> bool:
        """Populate fields from an existing register cache without simulating a cycle."""
        changed = False
        if all(reg in values for reg in range(2001, 2007)):
            value = decode_wifi_id([values[reg] for reg in range(2001, 2007)])
            if value:
                self.snapshot.wifi_id = value
                self.snapshot.code_date, self.snapshot.production_date = decode_wifi_id_date(value)
                changed = True
        if all(reg in values for reg in range(200, 216)):
            result = decode_product_key([values[reg] for reg in range(200, 216)])
            self.snapshot.product_key, self.snapshot.product_key_raw = result.value, result.raw
            self.snapshot.product_key_error, changed = result.error, True
        if all(reg in values for reg in range(50500, 50513)):
            for key, value in decode_c544([values[reg] for reg in range(50500, 50513)]).items():
                setattr(self.snapshot, key, value)
            changed = True
        if all(reg in values for reg in range(50043, 50045)):
            ack = decode_c37b([values[50043], values[50044]])
            self.snapshot.service_ssid, self.snapshot.ack_status = int(ack["service_ssid"]), int(ack["status"])
            changed = True
        if changed and self.snapshot.last_update is None:
            self.snapshot.last_update = time.time()
        return changed

    def feed_read_request(self, addr: int) -> None:
        if self.snapshot.running and int(addr) == 6:
            self.snapshot.startup_seen = True
            self.snapshot.state = DeviceInfoCycleState.STARTUP_SEEN
            self.snapshot.last_update = time.time()

    def feed_fc16(self, raw: bytes) -> bool:
        parsed = fc16_data_words(raw)
        if parsed is None:
            return False
        addr, words = parsed
        changed = False
        if addr == 200 and len(words) == 16:
            result = decode_product_key(words)
            self.snapshot.product_key, self.snapshot.product_key_raw = result.value, result.raw
            self.snapshot.product_key_error = result.error
            if self.snapshot.running:
                self.snapshot.state = DeviceInfoCycleState.PRODUCT_KEY_SEEN
            changed = True
        elif addr in DEVICE_INFO_BLOCK_STARTS and len(words) == 90:
            if self.snapshot.running:
                self.snapshot.block_starts.add(addr)
                self.snapshot.state = (DeviceInfoCycleState.WAITING_FOR_C544 if self.snapshot.block_count == 8
                                       else DeviceInfoCycleState.BLOCKS_RECEIVING)
            if addr == 2001:
                self.snapshot.wifi_id = decode_wifi_id(words)
                if self.snapshot.wifi_id:
                    self.snapshot.code_date, self.snapshot.production_date = decode_wifi_id_date(self.snapshot.wifi_id)
            changed = True
        elif addr == 50500 and len(words) == 13:
            for key, value in decode_c544(words).items():
                setattr(self.snapshot, key, value)
            if self.snapshot.running:
                self.snapshot.state = DeviceInfoCycleState.C544_RECEIVED
            changed = True
        elif addr == 50043 and len(words) == 2:
            result = decode_c37b(words)
            self.snapshot.service_ssid = int(result["service_ssid"])
            self.snapshot.ack_status = int(result["status"])
            if self.snapshot.running and self.snapshot.ack_status == 7:
                self.snapshot.state = DeviceInfoCycleState.CONFIRMED
            changed = True
        if changed:
            self.snapshot.last_update = time.time()
        return changed

    def check_timeout(self, now: Optional[float] = None) -> bool:
        current = time.time() if now is None else now
        if self.snapshot.running and self.snapshot.cycle_started is not None and current - self.snapshot.cycle_started >= self.TIMEOUT_SECONDS:
            self.snapshot.state = DeviceInfoCycleState.PARTIAL_TIMEOUT
            self.snapshot.last_update = current
            return True
        return False
