#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import socket
import struct
import time
try:
    import serial  # type: ignore
except Exception:  # pyserial optional, nur fuer COM-Port Transport
    serial = None
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_BUS_ADDR = 0x63
MODBUS_FUNC_READ_HOLDING = 0x03
MODBUS_FUNC_WRITE_SINGLE = 0x06
MODBUS_FUNC_WRITE_MULTIPLE = 0x10
SUPPORTED_FUNCTIONS = {MODBUS_FUNC_READ_HOLDING, MODBUS_FUNC_WRITE_SINGLE, MODBUS_FUNC_WRITE_MULTIPLE}
INCOMPLETE = object()
IAC = 0xFF

# bekannte Warmlink/WP-Blockframes. Struktur ist im Kern Modbus-FC16:
# addr 10 start qty byte_count data crc
# Bei den grossen Paketen ist qty=90 und byte_count=0xB4.
WORD_LEN_TYPES = {
    0x03E9,  # 1001 (neuere Display-FW)
    0x0443,  # 1091 (neuere Display-FW)
    0x049D,  # 1181 (neuere Display-FW)
    0x03FA,  # 1018 (Legacy V1.3 Paket 1)
    0x044D,  # 1101 (Legacy V1.3 Paket 2)
    0x04A7,  # 1191 (Legacy V1.3 Paket 3)
    0x04F7,  # 1271
    0x0551,  # 1361
    0x05AB,  # 1451 (neuere Display-FW)
    0x0605,  # 1541 (neuere Display-FW)
    0x05B5,  # 1461/Legacy optionaler Testblock V1.3
    0x060F,  # 1551/Legacy optionaler Testblock V1.3
    0x07D1,  # 2001
    0x082B,  # 2091
}

CONTACT_BIT_MAP_2034 = {
    0: ("S01 Hochdruckschalter", "0=ein / 1=aus"),
    1: ("S02 Niederdruckschalter", "0=ein / 1=aus"),
    2: ("S03 Wasserflussschalter", "0=ein / 1=aus"),
    3: ("S04 Überhitzungsschalter elektrischer Heizer", "0=ein / 1=aus"),
    4: ("S05 Fern-AN/AUS", "0=ein / 1=aus"),
    5: ("S06 Fernheizung/Kühlung", "0=ein / 1=aus"),
    6: ("S07 Warmwasserschalter", "0=ein / 1=aus"),
    7: ("S08 Reserviert / unbekannt", ""),
    8: ("S09 Reserviert / unbekannt", ""),
    9: ("S10 Heizen/Kühlen AN/AUS", "0=ein / 1=aus"),
    10: ("S11 Reserviert / unbekannt", ""),
    11: ("S12 Reserviert / unbekannt", ""),
    12: ("SG Kontakt 1", "DWIN 14.bin Seite 238, Maske 0x1000; 0=AUS / 1=EIN"),
    13: ("SG Kontakt 2", "DWIN 14.bin Seite 237/238, Maske 0x2000; 0=AUS / 1=EIN"),
    14: ("S15 Reserviert / unbekannt", ""),
    15: ("S16 Reserviert / unbekannt", ""),
}


def s16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def hexdump(data: bytes, max_len: int = 128) -> str:
    if max_len == -1:
        max_len = len(data)
    out = data[:max_len].hex(" ")
    if len(data) > max_len:
        out += f" ... (+{len(data) - max_len}B)"
    return out


def ascii_preview(data: bytes, max_len: int = 128) -> str:
    if max_len == -1:
        max_len = len(data)
    chunk = data[:max_len]
    out = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    if len(data) > max_len:
        out += f"...(+{len(data) - max_len}B)"
    return out


def hex_ascii_line(data: bytes, max_len: int = -1) -> str:
    return f"{hexdump(data, max_len)}    |{ascii_preview(data, max_len)}|"


def u16be_words(data: bytes) -> List[int]:
    cut = len(data) - (len(data) % 2)
    if cut <= 0:
        return []
    return list(struct.unpack(">" + "H" * (cut // 2), data[:cut]))


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def crc_bytes_le(data_without_crc: bytes) -> bytes:
    return crc16_modbus(data_without_crc).to_bytes(2, "little")


def crc_check_frame(raw: bytes) -> Tuple[bool, int, int]:
    if len(raw) < 4:
        return False, 0, 0
    got = int.from_bytes(raw[-2:], "little")
    calc = crc16_modbus(raw[:-2])
    return got == calc, got, calc


def build_write_frame(addr: int, value: int, slave_addr: int = DEFAULT_BUS_ADDR) -> bytes:
    if not 0 <= addr <= 0xFFFF:
        raise ValueError("Adresse außerhalb 0..65535")
    if not 0 <= value <= 0xFFFF:
        raise ValueError("Wert außerhalb 0..65535")
    if not is_possible_bus_addr(slave_addr):
        raise ValueError("Bus-Adresse außerhalb 1..247")

    frame_wo_crc = bytes([
        slave_addr, 0x10,
        (addr >> 8) & 0xFF, addr & 0xFF,
        0x00, 0x01,
        0x02,
        (value >> 8) & 0xFF, value & 0xFF,
    ])
    return frame_wo_crc + crc_bytes_le(frame_wo_crc)



def build_write_single_frame(addr: int, value: int, slave_addr: int = DEFAULT_BUS_ADDR) -> bytes:
    """Standard Modbus FC06: Write Single Register."""
    if not 0 <= addr <= 0xFFFF:
        raise ValueError("Adresse außerhalb 0..65535")
    if not 0 <= value <= 0xFFFF:
        raise ValueError("Wert außerhalb 0..65535")
    if not is_possible_bus_addr(slave_addr):
        raise ValueError("Bus-Adresse außerhalb 1..247")

    frame_wo_crc = bytes([
        slave_addr, 0x06,
        (addr >> 8) & 0xFF, addr & 0xFF,
        (value >> 8) & 0xFF, value & 0xFF,
    ])
    return frame_wo_crc + crc_bytes_le(frame_wo_crc)

def build_write_multiple_one_frame(addr: int, value: int, slave_addr: int = DEFAULT_BUS_ADDR) -> bytes:
    """Alias fuer bisherigen Warmlink/FC16 Einzelregister-Write."""
    return build_write_frame(addr, value, slave_addr=slave_addr)


def build_read_frame(addr: int, quantity: int = 1, slave_addr: int = DEFAULT_BUS_ADDR) -> bytes:
    if not 0 <= addr <= 0xFFFF:
        raise ValueError("Adresse außerhalb 0..65535")
    if not 1 <= quantity <= 125:
        raise ValueError("Anzahl außerhalb 1..125")
    if not is_possible_bus_addr(slave_addr):
        raise ValueError("Bus-Adresse außerhalb 1..247")

    frame_wo_crc = bytes([
        slave_addr, 0x03,
        (addr >> 8) & 0xFF, addr & 0xFF,
        (quantity >> 8) & 0xFF, quantity & 0xFF,
    ])
    return frame_wo_crc + crc_bytes_le(frame_wo_crc)

@dataclass
class RegisterInfo:
    name: str = ""
    dtype: str = "RAW"
    value_map: Optional[Dict[int, str]] = None
    bit_map: Optional[Dict[int, str]] = None


@dataclass
class DecodedRegister:
    slave_addr: int
    reg: int
    index: int
    frame_type: int
    raw_value: int
    signed_value: int
    display_value: str
    name: str
    dtype: str
    timestamp: float


@dataclass
class DecodedFrame:
    slave_addr: int
    func: int
    typ: int
    length_field: int
    payload: bytes
    trailer: bytes
    raw: bytes
    mode: str
    registers: List[DecodedRegister]
    crc_ok: bool
    crc_got: int
    crc_calc: int


class RegisterMap:
    def __init__(self, path: str):
        self.path = path
        self.items: Dict[int, RegisterInfo] = {}
        self.load(path)

    def load(self, path: str):
        self.items = {}
        if not path or not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            raw: Dict[str, Any] = json.load(f)
        for key, value in raw.items():
            reg = int(key, 0)
            if isinstance(value, list) and len(value) >= 2:
                self.items[reg] = RegisterInfo(str(value[0]), str(value[1]), None, None)
            elif isinstance(value, dict):
                
                raw_map = value.get("value_map") or value.get("values") or None
                value_map = None
                if isinstance(raw_map, dict):
                    value_map = {}
                    for mk, mv in raw_map.items():
                        try:
                            mi = int(mk, 0) if isinstance(mk, str) else int(mk)
                            value_map[mi] = str(mv)
                        except Exception:
                            pass
                raw_bit_map = value.get("bit_map") or value.get("bits") or None
                bit_map = None
                if isinstance(raw_bit_map, dict):
                    bit_map = {}
                    for mk, mv in raw_bit_map.items():
                        try:
                            mi = int(mk, 0) if isinstance(mk, str) else int(mk)
                            bit_map[mi] = str(mv)
                        except Exception:
                            pass
                self.items[reg] = RegisterInfo(str(value.get("name", "")), str(value.get("type", "RAW")), value_map, bit_map)
            else:
                self.items[reg] = RegisterInfo(str(value), "RAW")

    def get(self, reg: int) -> RegisterInfo:
        return self.items.get(reg, RegisterInfo())

    def __len__(self) -> int:
        return len(self.items)


def _decode_hhmm_value(raw_value: int) -> str:
    hour = (raw_value >> 8) & 0xFF
    minute = raw_value & 0xFF
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return f"ungültig {raw_value} / 0x{raw_value:04X}"


def _decode_timer_bit_byte(byte_value: int) -> str:
    days = []
    for name, bit in (("Mo", 1), ("Di", 2), ("Mi", 4), ("Do", 8), ("Fr", 16), ("Sa", 32), ("So", 64)):
        if byte_value & bit:
            days.append(name)
    state = "aktiv" if byte_value & 0x80 else "inaktiv"
    day_text = "+".join(days) if days else "keine Tage"
    return f"{state}, {day_text}"



def _decode_bit_map(raw_value: int, bit_map: Optional[Dict[int, str]]) -> str:
    if not bit_map:
        return str(s16(raw_value))
    hits = []
    for bit in sorted(bit_map):
        if 0 <= bit <= 15 and (raw_value & (1 << bit)):
            hits.append(f"B{bit}: {bit_map[bit]}")
    if not hits:
        return "0"
    return f"0x{raw_value:04X}: " + "; ".join(hits)

def format_value_by_type(raw_value: int, dtype: str, value_map: Optional[Dict[int, str]] = None, bit_map: Optional[Dict[int, str]] = None) -> str:
    signed = s16(raw_value)
    dtype = (dtype or "RAW").upper()
    if value_map and raw_value in value_map:
        return f"{raw_value} = {value_map[raw_value]}"
    if value_map and signed in value_map:
        return f"{signed} = {value_map[signed]}"
    if bit_map or dtype in ("FAULT_BITS", "BITFIELD"):
        return _decode_bit_map(raw_value, bit_map)
    if dtype in ("TEMP", "TEMP1"):
        return f"{signed / 10.0:.1f} °C"
    if dtype in ("TEMP05", "TEMP_0_5", "STEP_0_5C"):
        return f"{signed / 2.0:.1f} °C"
    if dtype in ("TIME_HHMM", "HHMM"):
        return _decode_hhmm_value(raw_value)
    if dtype in ("POWER_KW_X10", "KW_X10"):
        return f"{signed / 10.0:.1f} kW"
    if dtype in ("BAR_X10", "PRESSURE_BAR_X10"):
        return f"{signed / 10.0:.1f} bar"
    if dtype in ("AMP_X2", "CURRENT_A_X2"):
        return f"{signed / 2.0:.1f} A"
    if dtype in ("FLOW_M3H_X100", "FLOW_X100"):
        return f"{signed / 100.0:.1f} m³/h"
    if dtype in ("FLOW_M3H_X10", "FLOW_X10"):
        return f"{signed / 10.0:.1f} m³/h"
    if dtype in ("COP_X100", "COP100"):
        return f"{signed / 100.0:.2f}"
    if dtype in ("MINUTES", "MIN"):
        return f"{signed} min"
    if dtype in ("SECONDS", "SEC"):
        return f"{signed} s"
    if dtype in ("HOURS", "HOUR"):
        return f"{signed} h"
    if dtype in ("DAYS", "DAY"):
        return f"{signed} days"
    if dtype in ("HZ", "FREQUENCY_HZ"):
        return f"{signed} Hz"
    if dtype in ("STEPS_N", "EEV_STEPS", "STEPS"):
        return f"{signed} N"
    if dtype in ("PERCENT", "PCT"):
        return f"{signed} %"
    if dtype in ("TIMER_BITPAIR", "DAYPAIR"):
        low = raw_value & 0xFF
        high = (raw_value >> 8) & 0xFF
        return f"low: {_decode_timer_bit_byte(low)} | high: {_decode_timer_bit_byte(high)}"
    if dtype in ("TIMER_MODE", "MODE_0_4", "SG_MODE", "RUN_MODE"):
        return f"{signed}"
    if dtype in ("DIGI5",):
        return f"{signed / 10.0:.1f}"
    if dtype == "DIGI6":
        return f"{signed / 1000.0:.3f}"
    if dtype == "DIGI19":
        return f"{signed / 100.0:.2f}"
    if dtype == "DIGI4":
        return f"{signed / 5.0:.1f}"
    if dtype == "DIGI1":
        return f"{signed}"
    if dtype == "DIGI9":
        return f"{signed} raw / evtl. {signed / 10.0:.1f}"
    return str(signed)


def is_possible_bus_addr(value: int) -> bool:
    # Modbus-RTU normale Slave-Adressen: 1..247.
    # 0 ist Broadcast. Auf dem Display-Bus werden die grossen zyklischen
    # Hauptdatenbloecke als FC16-Broadcast (Unit 0x00) gesendet; die muessen
    # fuer den Passiv-Logger sichtbar bleiben.
    # Warmlink nutzt hier bisher 0x63, wir lassen aber bewusst alle gueltigen
    # Adressen zu, damit andere Teilnehmer/Warmlink-Frames sichtbar werden.
    return 0 <= value <= 247


def is_frame_header_at(buf: bytearray, pos: int) -> bool:
    return (
        0 <= pos < len(buf) - 1
        and is_possible_bus_addr(buf[pos])
        and buf[pos + 1] in SUPPORTED_FUNCTIONS
    )


def next_frame_pos(buf: bytearray, start: int) -> int:
    # Suche nach beliebiger Bus-Adresse + unterstütztem Funktionscode.
    # Der simple Byte-Scan ist hier absichtlich robuster als find(0x10),
    # weil inzwischen auch FC03 auftaucht.
    for j in range(max(0, start + 1), len(buf) - 1):
        if is_frame_header_at(buf, j):
            return j
    return -1


def _ret(slave_addr: int, func: int, typ: int, length_field: int, payload: bytes,
         trailer: bytes, raw: bytes, j: int, end_frame: int, mode: str):
    return slave_addr, func, typ, length_field, payload, trailer, raw, j, end_frame, mode


def parse_frame_at(buf: bytearray, j: int, max_words: int = 512):
    n = len(buf)
    if n - j < 2:
        return INCOMPLETE
    slave_addr = buf[j]
    func = buf[j + 1]
    if not is_possible_bus_addr(slave_addr) or func not in SUPPORTED_FUNCTIONS:
        return None

    if func == MODBUS_FUNC_READ_HOLDING:
        # FC03 Request:  addr 03 start_hi start_lo qty_hi qty_lo crc_lo crc_hi
        # FC03 Response: addr 03 byte_count data... crc_lo crc_hi
        # Wichtig: Requests mit Startadresse 0x05xx sehen sonst wie eine
        # unvollstaendige Response mit byte_count=0x05 aus. Deshalb zuerst
        # das feste 8-Byte-Request-Format per CRC pruefen.
        if n - j >= 8:
            raw8 = bytes(buf[j:j + 8])
            if crc_check_frame(raw8)[0]:
                typ = struct.unpack_from(">H", raw8, 2)[0]
                quantity = struct.unpack_from(">H", raw8, 4)[0]
                if 1 <= quantity <= max_words:
                    payload = raw8[2:6]
                    trailer = raw8[6:8]
                    return _ret(slave_addr, func, typ, quantity, payload, trailer, raw8, j, j + 8, "read-request")

        if n - j < 5:
            return INCOMPLETE

        byte_count = buf[j + 2]
        if 0 < byte_count <= max_words * 2:
            end_frame = j + 3 + byte_count + 2
            if n < end_frame:
                return INCOMPLETE
            raw = bytes(buf[j:end_frame])
            if crc_check_frame(raw)[0]:
                payload = raw[3:3 + byte_count]
                trailer = raw[-2:]
                return _ret(slave_addr, func, 0, byte_count, payload, trailer, raw, j, end_frame, "read-response")

        if n - j < 8:
            return INCOMPLETE
        return None

    if func == MODBUS_FUNC_WRITE_SINGLE:
        # FC06 Request und Response haben identisches 8-Byte-Format:
        # addr 06 register value crc
        if n - j < 8:
            return INCOMPLETE
        raw8 = bytes(buf[j:j + 8])
        if crc_check_frame(raw8)[0]:
            typ = struct.unpack_from(">H", raw8, 2)[0]
            payload = raw8[4:6]
            trailer = raw8[6:8]
            return _ret(slave_addr, func, typ, 1, payload, trailer, raw8, j, j + 8, "write-single")
        return None

    if func != MODBUS_FUNC_WRITE_MULTIPLE:
        return None

    if n - j < 6:
        return INCOMPLETE

    typ = struct.unpack_from(">H", buf, j + 2)[0]
    quantity = struct.unpack_from(">H", buf, j + 4)[0]

    if quantity > max_words:
        return None

    # FC16 Request: addr 10 start qty byte_count data crc
    # Das deckt kurze Einzelwrites UND die grossen 90-Wort-Statusframes ab.
    if n - j >= 7:
        byte_count = buf[j + 6]
        if quantity > 0 and byte_count == quantity * 2 and byte_count <= max_words * 2:
            end_frame = j + 7 + byte_count + 2
            if n < end_frame:
                return INCOMPLETE
            raw = bytes(buf[j:end_frame])
            if not crc_check_frame(raw)[0]:
                # Meist kein echtes Frame, sondern z. B. eingebettetes "02 10 ..." im Payload.
                return None
            payload = raw[6:7 + byte_count]  # Bytecount + Daten
            trailer = raw[-2:]
            if quantity >= 16 and (typ in WORD_LEN_TYPES or byte_count == 0xB4):
                mode = "word-frame"
            elif quantity == 1:
                mode = "short-write"
            else:
                mode = "write-request"
            return _ret(slave_addr, func, typ, quantity, payload, trailer, raw, j, end_frame, mode)

    # FC16 Response/ACK: addr 10 start qty crc
    if n - j < 8:
        return INCOMPLETE
    raw8 = bytes(buf[j:j + 8])
    if crc_check_frame(raw8)[0]:
        payload = b""
        trailer = raw8[6:8]
        return _ret(slave_addr, func, typ, quantity, payload, trailer, raw8, j, j + 8, "write-response")

    return None


def find_frames(buf: bytearray, max_len: int = 512):
    frames = []
    i = 0
    saw_incomplete_frame = False

    while True:
        j = next_frame_pos(buf, i - 1)
        if j < 0:
            break

        parsed = parse_frame_at(buf, j, max_len)

        if parsed is INCOMPLETE:
            # TCP darf Modbus-Frames beliebig zerstueckeln.
            # Den gesamten angefangenen Frame behalten und beim naechsten recv()
            # fortsetzen. Nicht in eingebettete Marker wie "02 10 07 D1" resyncen.
            if j > 0:
                del buf[:j]
            saw_incomplete_frame = True
            break

        if parsed is None:
            i = j + 1
            continue

        frames.append(parsed)
        i = parsed[8]

    if frames:
        del buf[:frames[-1][8]]
    elif saw_incomplete_frame:
        pass
    else:
        # Kein sicherer Frame-Anfang gefunden: nur kleines Resync-Fenster behalten.
        keep_from = max(0, len(buf) - 32)
        if keep_from > 0:
            del buf[:keep_from]

    return frames


def word_frame_words(payload: bytes, length_field: int) -> Tuple[Optional[int], List[int]]:
    if not payload:
        return None, []
    prefix = payload[0]
    data = payload[1:1 + length_field * 2]
    return prefix, u16be_words(data)


def write_request_words(payload: bytes, quantity: int) -> Tuple[Optional[int], List[int]]:
    if not payload:
        return None, []
    byte_count = payload[0]
    data = payload[1:1 + byte_count]
    return byte_count, u16be_words(data[:quantity * 2])


def generic_payload_words(payload: bytes) -> List[int]:
    return u16be_words(payload)


def extract_register_blocks(typ: int, length_field: int, payload: bytes, mode: str):
    blocks = []
    if mode == "word-frame":
        prefix, words = word_frame_words(payload, length_field)
        meta = bytes([prefix]) if prefix is not None else b""
        blocks.append((typ, typ, 7, meta, words, "word-frame"))
        return blocks

    if mode in ("short-write", "write-request"):
        byte_count, words = write_request_words(payload, length_field)
        meta = bytes([byte_count]) if byte_count is not None else b""
        blocks.append((typ, typ, 7, meta, words, mode))
        return blocks

    if mode == "write-single":
        words = u16be_words(payload)
        blocks.append((typ, typ, 4, b"", words, mode))
        return blocks

    if mode == "read-response":
        # Ohne vorherige Request-Zuordnung ist die Startadresse nicht sicher bekannt.
        return blocks

    pos = 0
    while True:
        idx = payload.find(b"\x02\x10", pos)
        if idx < 0:
            break
        if idx + 8 > len(payload):
            break
        block_type = struct.unpack_from(">H", payload, idx + 2)[0]
        meta = payload[idx + 4:idx + 8]
        data = payload[idx + 8:]
        words = u16be_words(data)
        if words and 0x0001 <= block_type <= 0x6FFF:
            blocks.append((block_type, block_type, idx, meta, words, "marker-scan"))
        pos = idx + 2
    return blocks


def decode_frame(parsed, regmap: RegisterMap) -> DecodedFrame:
    slave_addr, func, typ, length_field, payload, trailer, raw, _start, _end, mode = parsed
    crc_ok, crc_got, crc_calc = crc_check_frame(raw)
    registers: List[DecodedRegister] = []
    ts = time.time()

    for block_type, base, _offset, _meta, words, _note in extract_register_blocks(typ, length_field, payload, mode):
        for idx, raw_value in enumerate(words):
            reg = base + idx
            info = regmap.get(reg)
            registers.append(DecodedRegister(
                slave_addr=slave_addr,
                reg=reg,
                index=idx,
                frame_type=block_type,
                raw_value=raw_value,
                signed_value=s16(raw_value),
                display_value=format_value_by_type(raw_value, info.dtype, info.value_map, info.bit_map),
                name=info.name,
                dtype=info.dtype,
                timestamp=ts,
            ))

    return DecodedFrame(
        slave_addr=slave_addr,
        func=func,
        typ=typ,
        length_field=length_field,
        payload=payload,
        trailer=trailer,
        raw=raw,
        mode=mode,
        registers=registers,
        crc_ok=crc_ok,
        crc_got=crc_got,
        crc_calc=crc_calc,
    )


def numeric_value_by_type(raw_value: int, dtype: str) -> float:
    signed = s16(raw_value)
    dtype = (dtype or "RAW").upper()
    if dtype in ("TEMP", "TEMP1"):
        return signed / 10.0
    if dtype in ("TEMP05", "TEMP_0_5", "STEP_0_5C"):
        return signed / 2.0
    if dtype in ("DIGI5", "POWER_KW_X10", "KW_X10", "BAR_X10", "PRESSURE_BAR_X10", "FLOW_M3H_X10", "FLOW_X10"):
        return signed / 10.0
    if dtype in ("FLOW_M3H_X100", "FLOW_X100", "COP_X100", "COP100"):
        return signed / 100.0
    if dtype in ("AMP_X2", "CURRENT_A_X2"):
        return signed / 2.0
    if dtype == "DIGI6":
        return signed / 1000.0
    if dtype == "DIGI19":
        return signed / 100.0
    if dtype == "DIGI4":
        return signed / 5.0
    return float(signed)


def decode_read_response_registers(frame: DecodedFrame, start_reg: int, regmap: RegisterMap) -> List[DecodedRegister]:
    words = u16be_words(frame.payload)
    ts = time.time()
    regs: List[DecodedRegister] = []
    for idx, raw_value in enumerate(words):
        reg_no = start_reg + idx
        info = regmap.get(reg_no)
        regs.append(DecodedRegister(
            slave_addr=frame.slave_addr,
            reg=reg_no,
            index=idx,
            frame_type=start_reg,
            raw_value=raw_value,
            signed_value=s16(raw_value),
            display_value=format_value_by_type(raw_value, info.dtype, info.value_map, info.bit_map),
            name=info.name,
            dtype=info.dtype,
            timestamp=ts,
        ))
    return regs


def get_write_value(payload: bytes) -> Optional[int]:
    if payload and payload[0] == 0x02 and len(payload) >= 3:
        return (payload[1] << 8) | payload[2]
    return None


def decode_contact_bits(value: int) -> List[Tuple[int, int, str, str, str]]:
    rows = []
    for bit in range(16):
        bit_value = (value >> bit) & 1
        name, meaning = CONTACT_BIT_MAP_2034.get(bit, (f"Bit{bit}", ""))
        if meaning:
            meaning_upper = meaning.upper()
            if "0=AUS" in meaning_upper and "1=EIN" in meaning_upper:
                state = "EIN/aktiv" if bit_value == 1 else "AUS/inaktiv"
            else:
                state = "ein/aktiv" if bit_value == 0 else "aus/inaktiv"
        else:
            state = "0 / LOW" if bit_value == 0 else "1 / HIGH"
            meaning = "reserviert / Bedeutung unbekannt"
        rows.append((bit, bit_value, name, state, meaning))
    return rows


def guess_device_name(slave_addr: int, crc_ok: bool = True) -> str:
    if slave_addr == 0x00:
        return "Modbus-Broadcast/System-Adresse 0x00; WP-Paket-Broadcast 2001ff/2091ff, keine normale Read-Antwort erwartet"
    if slave_addr == DEFAULT_BUS_ADDR:
        return "Wärmepumpe / Regler 0x63"
    if slave_addr == 0x01:
        return "Display/HMI-Bus: vermutlich WP-Hauptplatine/Kopf; Live-/Status 1999/2099ff"
    if slave_addr == 0x02:
        if not crc_ok:
            return "wahrscheinlich eingebetteter Marker / Resync, kein echtes Gerät"
        return "Display/HMI-Bus: DWIN/HMI-Pfad 0x02; 3001ff/Parameterpakete, Rolle unklar"
    if slave_addr == 0x03:
        return "Display/HMI-Bus: vermutlich Display/DWIN-HMI; Parameterpakete 1001ff und DWIN 3001ff"
    if slave_addr == 0x04:
        return "Display/HMI-Bus: interner Teilnehmer 0x04; fragt 1011ff, evtl. Leistungs-/Hydraulikpfad"
    if slave_addr == 0x05:
        return "Display/HMI-Bus: interner Teilnehmer 0x05; liest 2000ff/schreibt 1001ff, evtl. Leistungselektronik"
    if slave_addr == 0x06:
        return "Display/HMI-Bus: Testadresse 0x06, bisher keine gesicherte Rolle"
    if 1 <= slave_addr <= 247:
        return "unbekannter Modbus-Teilnehmer"
    return "ungültige Modbus-Adresse"


class WarmlinkSocketClient:
    def __init__(self, host: str, port: int, timeout: float = 1.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10.0)
        self.sock.settimeout(self.timeout)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    def is_connected(self) -> bool:
        return self.sock is not None

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def recv(self, size: int = 4096) -> bytes:
        if not self.sock:
            raise RuntimeError("Nicht verbunden")
        return self.sock.recv(size)

    def send(self, data: bytes):
        if not self.sock:
            raise RuntimeError("Nicht verbunden")
        self.sock.sendall(data)


class ModbusSerialClient:
    """Einfacher Modbus-RTU Byte-Transport ueber lokalen COM-Port.

    Erwartet bereits fertig gebaute RTU-Frames inkl. CRC. Damit koennen Warmlink,
    Standard-Modbus und Display-Modbus denselben Frame-Builder nutzen.
    """
    def __init__(self, port: str, baudrate: int = 9600, parity: str = "N", bytesize: int = 8, stopbits: float = 1.0, timeout: float = 0.5):
        self.port = port
        self.baudrate = int(baudrate)
        self.parity = str(parity or "N").upper()[0]
        self.bytesize = int(bytesize)
        self.stopbits = float(stopbits)
        self.timeout = timeout
        self.ser = None

    def connect(self):
        if serial is None:
            raise RuntimeError("pyserial ist nicht installiert. Bitte 'pip install pyserial' ausfuehren.")
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
            write_timeout=2.0,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False,
        )

    def is_connected(self) -> bool:
        return self.ser is not None and bool(getattr(self.ser, "is_open", False))

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def recv(self, size: int = 4096) -> bytes:
        if not self.ser:
            raise RuntimeError("Nicht verbunden")
        data = self.ser.read(size)
        if not data:
            raise socket.timeout()
        return data

    def send(self, data: bytes):
        if not self.ser:
            raise RuntimeError("Nicht verbunden")
        self.ser.write(data)
        self.ser.flush()

