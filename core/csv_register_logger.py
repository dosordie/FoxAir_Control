"""Append-only CSV writer and engineering snapshots of PHNIX registers 2001–2090."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from cloud.register_resolver import resolve_cloud_register
from cloud.warmlink_codes import WARMLINK_644_DISCOVERY_CODES, cloud_hint
from cloud.warmlink_value_translator import translate_cloud_value
from core.foxair_phnix_core import numeric_value_by_type

LIVE_REGISTERS = tuple(range(2001, 2091))
CSV_HEADER = ("timestamp", "source", "device", *(f"R{reg}" for reg in LIVE_REGISTERS))


def csv_number(value):
    """Keep numeric cells finite and unit-free; unavailable values stay empty."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return str(int(value)) if value.is_integer() else str(value)
    return ""


def local_engineering_value(register, regmap):
    info = regmap.get(register.reg)
    dtype = str(register.dtype or info.dtype).upper()
    if dtype in {"BITFIELD", "FAULT_BITS", "UINT16", "UNSIGNED INT16"} or info.bit_map or info.value_map:
        return int(register.raw_value) & 0xFFFF
    return numeric_value_by_type(register.raw_value, dtype)


def logger_cloud_mappings(definitions=None):
    result = {}
    for code in WARMLINK_644_DISCOVERY_CODES:
        reg = resolve_cloud_register(code, cloud_hint(code), definitions)
        if reg in LIVE_REGISTERS:
            result[code] = reg
    return result


def cloud_engineering_snapshot(rows, mappings, definitions):
    """Use only this response, never a cached/merged Cloud overlay."""
    snapshot = {}
    for row in rows:
        code = str(row.get("code") or "")
        reg = mappings.get(code)
        if reg in snapshot or reg not in LIVE_REGISTERS or not row.get("supported") or any(
            row.get(flag) for flag in ("stale", "cached", "currentEmpty")
        ) or row.get("value") is None:
            continue
        value = translate_cloud_value(code, row["value"], definitions.get(str(reg), {}), cloud_hint(code), row).raw
        if csv_number(value) != "":
            snapshot[reg] = value
    return snapshot


class CsvRegisterLogger:
    """Single-owner file writer. Communication and timing belong to the controller."""
    def __init__(self):
        self.file = None
        self.writer = None
        self.rows_written = 0

    def open(self, path):
        self.close()
        path = Path(path).expanduser()
        if path.exists() and path.stat().st_size:
            with path.open("r", encoding="utf-8-sig", newline="") as existing:
                if next(csv.reader(existing, delimiter=";"), None) != list(CSV_HEADER):
                    raise ValueError("CSV-Header passt nicht zum Liveblock 2001–2090. Bitte eine andere Datei wählen.")
            # A compatible last row without a newline must not concatenate the next row.
            with path.open("rb") as existing:
                existing.seek(-1, 2)
                needs_newline = existing.read(1) not in (b"\n", b"\r")
        else:
            needs_newline = False
        new = not path.exists() or not path.stat().st_size
        try:
            self.file = path.open("a", encoding="utf-8-sig" if new else "utf-8", newline="")
            self.writer = csv.writer(self.file, delimiter=";")
            if needs_newline:
                self.file.write("\n")
            if new:
                self.writer.writerow(CSV_HEADER)
            self.file.flush()
            self.rows_written = 0
        except Exception:
            self.close()
            raise

    def append(self, timestamp, source, device, snapshot):
        if self.writer is None:
            raise ValueError("CSV-Datei ist nicht geöffnet.")
        self.writer.writerow([timestamp, source, device, *(csv_number(snapshot.get(reg)) for reg in LIVE_REGISTERS)])
        self.file.flush()
        self.rows_written += 1

    def close(self):
        file, self.file = self.file, None
        self.writer = None
        if file is not None:
            file.close()
