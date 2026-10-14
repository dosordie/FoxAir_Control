"""Strict, testable PHNIX identity service helpers (issue #115)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid

from core.device_info import decode_wifi_id
from core.foxair_phnix_core import crc16_modbus

SLAVE = 0x63
READ_START = 2001
READ_QUANTITY = 8
WRITE_START = 7001
WRITE_QUANTITY = 10
WARNING = ("Die Mainboard-Kommunikations-ID wird dauerhaft geändert.\n"
           "Eine falsche ID kann Hersteller-Service-, Diagnose- oder Cloudfunktionen beeinflussen.")
TRANSPORT_WARNING = "Diese Servicefunktion ist nur über den Warmlink-/LTE-Bus (Slave 0x63) verfügbar."


def validate_wifi_identity(text: str) -> bool:
    return isinstance(text, str) and re.fullmatch(r"WF[0-9]{10}", text) is not None


def checked_words(words, count):
    try:
        values = list(words)
    except TypeError as exc:
        raise ValueError("Keine gültigen Registerwörter") from exc
    if len(values) != count or any(type(v) is not int or not 0 <= v <= 0xFFFF for v in values):
        raise ValueError("Unvollständige oder ungültige Registerwörter")
    return values


def decode_wifi_identity(words):
    values = checked_words(words, READ_QUANTITY)
    return decode_wifi_id(values)


def encode_wifi_identity(text):
    if not validate_wifi_identity(text):
        raise ValueError("Die ID muss exakt WF und zehn ASCII-Ziffern enthalten")
    raw = text.encode("ascii")
    return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, 12, 2)]


def build_identity_write_payload(new_id, reserved_2007, reserved_2008):
    reserve = checked_words([reserved_2007, reserved_2008], 2)
    return [0x00AA, 0x005A, *encode_wifi_identity(new_id), *reserve]


def mask_wifi_identity(text):
    return text[:4] + "******" + text[-2:] if validate_wifi_identity(text) else "[ID maskiert]"


def valid_crc(raw):
    return len(raw) >= 5 and crc16_modbus(raw[:-2]) == int.from_bytes(raw[-2:], "little")


def validate_identity_write_ack(raw):
    raw = bytes(raw)
    return (len(raw) == 8 and raw[:6] == bytes.fromhex("63 10 1b 59 00 0a") and valid_crc(raw))


def decode_identity_read_response(raw):
    raw = bytes(raw)
    if len(raw) != 21 or raw[:3] != bytes([SLAVE, 0x03, 16]) or not valid_crc(raw):
        raise ValueError("Keine vollständige FC03-Antwort für Slave 0x63 / acht Wörter")
    return [int.from_bytes(raw[i:i + 2], "big") for i in range(3, 19, 2)]


def verify_identity_readback(words, expected_id, reserved):
    values = checked_words(words, READ_QUANTITY)
    return values == [*encode_wifi_identity(expected_id), *checked_words(reserved, 2)]


def identity_access_error(owner):
    if owner.settings.get("show_engineering_parameters") is not True:
        return "Engineering-Parameter anzeigen muss für diese Servicefunktion eingeschaltet sein."
    if (owner.current_backend_key() != "warmlink_raw" or owner._active_io_worker() is None
            or owner._wire_slave_addr(SLAVE) != SLAVE):
        return TRANSPORT_WARNING
    return ""


def create_identity_backup(user_data_dir, words, new_id):
    values = checked_words(words, 8)
    encode_wifi_identity(new_id)
    record = {"schema": 1, "sensitive": True,
              "timestamp": datetime.now(timezone.utc).isoformat(), "transport": "warmlink_raw",
              "slave": SLAVE, "raw_2001_2008": values, "old_id": decode_wifi_identity(values),
              "expected_id": new_id, "reserved": values[6:],
              "immediate_readback": None, "persistence_readback": None}
    directory = Path(user_data_dir) / "device_identity_backups"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex + ".json")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    return path, record


def update_identity_backup(path, record):
    # Atomic replacement also retains restrictive permissions on POSIX.
    temporary = Path(str(path) + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_identity_backup(path):
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("Kein gültiges Identity-Service-Backup")
    if record.get("schema") != 1 or record.get("transport") != "warmlink_raw" or record.get("slave") != SLAVE:
        raise ValueError("Kein gültiges Identity-Service-Backup")
    words = checked_words(record.get("raw_2001_2008", []), 8)
    if not validate_wifi_identity(record.get("old_id")) or decode_wifi_identity(words) != record["old_id"]:
        raise ValueError("Backup enthält keine gültige alte ID")
    if record.get("reserved") != words[6:]:
        raise ValueError("Inkonsistentes Identity-Service-Backup")
    encode_wifi_identity(record.get("expected_id"))
    return record
