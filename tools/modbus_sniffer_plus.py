#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import socket
from typing import Optional, Tuple, Dict, Any, List

# ---------------- CRC ----------------
def modbus_crc(buf: bytes) -> int:
    crc = 0xFFFF
    for b in buf:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

def check_crc(frame: bytes) -> bool:
    if len(frame) < 4:
        return False
    calc = modbus_crc(frame[:-2])
    lo = frame[-2]
    hi = frame[-1]
    expect = (hi << 8) | lo
    return calc == expect

# -------------- utils ---------------
def emit(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False), flush=True)

def emit_raw(note: str, data: bytes) -> None:
    emit({"proto":"ModbusRTU","type":"raw","note":note,"len":len(data),"hex":data.hex()})

def mk_addr_list(start: int, regs: List[int]) -> List[Dict[str, int]]:
    return [{"address": start+i, "value": v} for i, v in enumerate(regs)]

def parse_u16s(data: bytes) -> List[int]:
    return [ (data[i]<<8) | data[i+1] for i in range(0, len(data), 2) ]

# ---------- decoders (strict head) ----------
def decode_fc3_4_response_head(buf: bytes, unit: int, func: int) -> Optional[Tuple[Dict[str,Any], int]]:
    # need at least addr, func, byteCount, crc -> 5 bytes minimum
    if len(buf) < 5:
        return None
    byte_count = buf[2]
    total = 5 + byte_count  # includes CRC
    if len(buf) < total:
        return None
    frame = buf[:total]
    if not check_crc(frame):
        return None
    payload = frame[3:3+byte_count]
    if byte_count % 2 != 0:
        return None
    regs = parse_u16s(payload)
    obj = {
        "proto":"ModbusRTU","addr":unit,"func":func,"type":"response",
        "len": total, "crcOk": True, "hex": frame.hex(),
        "byteCount": byte_count, "registers": regs
    }
    return obj, total

def decode_fc3_4_request_head(buf: bytes, unit: int, func: int) -> Optional[Tuple[Dict[str,Any], int]]:
    # fixed 8 bytes incl CRC
    if len(buf) < 8:
        return None
    frame = buf[:8]
    if not check_crc(frame):
        return None
    start_addr = (buf[2]<<8) | buf[3]
    qty = (buf[4]<<8) | buf[5]
    obj = {
        "proto":"ModbusRTU","addr":unit,"func":func,"type":"request",
        "len": 8, "crcOk": True, "hex": frame.hex(),
        "startAddr": start_addr, "qty": qty
    }
    return obj, 8

def decode_fc6_request_head(buf: bytes, unit: int) -> Optional[Tuple[Dict[str,Any], int]]:
    if len(buf) < 8:
        return None
    frame = buf[:8]
    if not check_crc(frame):
        return None
    addr = (buf[2]<<8) | buf[3]
    value = (buf[4]<<8) | buf[5]
    return ({
        "proto":"ModbusRTU","addr":unit,"func":6,"type":"request",
        "len":8,"crcOk":True,"hex":frame.hex(),
        "address":addr,"value":value
    }, 8)

def decode_fc6_response_head(buf: bytes, unit: int) -> Optional[Tuple[Dict[str,Any], int]]:
    if len(buf) < 8:
        return None
    frame = buf[:8]
    if not check_crc(frame):
        return None
    addr = (buf[2]<<8) | buf[3]
    value = (buf[4]<<8) | buf[5]
    return ({
        "proto":"ModbusRTU","addr":unit,"func":6,"type":"response",
        "len":8,"crcOk":True,"hex":frame.hex(),
        "address":addr,"value":value
    }, 8)

def decode_fc16_request_head(buf: bytes, unit: int) -> Optional[Tuple[Dict[str,Any], int]]:
    if len(buf) < 7:  # until qty
        return None
    start_addr = (buf[2]<<8) | buf[3]
    qty       = (buf[4]<<8) | buf[5]
    if len(buf) < 7:  # need byteCount
        return None
    byte_count = buf[6]
    if byte_count != qty*2:
        # Wenn noch zu kurz, nicht verwerfen – erst später entscheiden.
        if len(buf) < 9:  # nicht genug, um CRC zu prüfen
            return None
    total = 9 + byte_count   # incl CRC
    if len(buf) < total:
        return None
    frame = buf[:total]
    if not check_crc(frame):
        return None
    payload = buf[7:7+byte_count]
    regs = parse_u16s(payload)
    return ({
        "proto":"ModbusRTU","addr":unit,"func":16,"type":"request",
        "len": total,"crcOk":True,"hex":frame.hex(),
        "startAddr":start_addr,"qty":qty,
        "byteCount":byte_count,"registers":regs,
        "addressed": mk_addr_list(start_addr, regs)
    }, total)

def decode_fc16_response_head(buf: bytes, unit: int) -> Optional[Tuple[Dict[str,Any], int]]:
    if len(buf) < 8:
        return None
    frame = buf[:8]
    if not check_crc(frame):
        return None
    start_addr = (buf[2]<<8) | buf[3]
    qty        = (buf[4]<<8) | buf[5]
    return ({
        "proto":"ModbusRTU","addr":unit,"func":16,"type":"response",
        "len":8,"crcOk":True,"hex":frame.hex(),
        "startAddr":start_addr,"qty":qty
    }, 8)

def decode_from_head(buf: bytes,
                     last_req: Dict[Tuple[int,int], Dict[str,Any]]
                    ) -> Optional[Tuple[Dict[str,Any], int]]:
    if len(buf) < 4:
        return None
    unit = buf[0]
    func = buf[1]

    # FC3/4: zuerst Response versuchen, dann Request
    if func in (3,4):
        r = decode_fc3_4_response_head(buf, unit, func)
        if r:
            obj, flen = r
            # Korrelation: startAddr/qty vom letzten Request gleicher (addr,func)
            req = last_req.get((unit, func))
            if req and req.get("type") == "request":
                obj["startAddr"] = req.get("startAddr")
                obj["qty"]       = req.get("qty")
                if "registers" in obj and isinstance(obj["registers"], list) and isinstance(obj.get("startAddr"), int):
                    obj["addressed"] = mk_addr_list(obj["startAddr"], obj["registers"])
            return obj, flen

        r = decode_fc3_4_request_head(buf, unit, func)
        if r:
            obj, flen = r
            # Für Response-Korrelation ablegen
            last_req[(unit, func)] = obj
            return obj, flen

    elif func == 6:
        r = decode_fc6_response_head(buf, unit)
        if r:
            return r
        r = decode_fc6_request_head(buf, unit)
        if r:
            return r

    elif func == 16:
        r = decode_fc16_response_head(buf, unit)
        if r:
            return r
        r = decode_fc16_request_head(buf, unit)
        if r:
            obj, flen = r
            last_req[(unit, 3)]  = {"addr":unit,"func":3, "startAddr":obj["startAddr"], "qty":obj["qty"], "type":"request"}
            last_req[(unit, 4)]  = {"addr":unit,"func":4, "startAddr":obj["startAddr"], "qty":obj["qty"], "type":"request"}
            last_req[(unit,16)]  = {"addr":unit,"func":16,"startAddr":obj["startAddr"], "qty":obj["qty"], "type":"request"}
            return obj, flen

    # nichts Decodierbares am Kopf
    return None

# -------------- Filter --------------
def frame_matches_watch(watch_set: set, obj: Dict[str, Any]) -> bool:
    if not watch_set:
        return True
    if "addressed" in obj and isinstance(obj["addressed"], list):
        return any(it.get("address") in watch_set for it in obj["addressed"])
    if obj.get("func") == 6 and "address" in obj:
        return obj["address"] in watch_set
    if "startAddr" in obj and "qty" in obj and isinstance(obj["startAddr"], int) and isinstance(obj["qty"], int):
        s = obj["startAddr"]; q = obj["qty"]
        return any(a in watch_set for a in range(s, s+q))
    return False

def frame_matches_value(value_only: Optional[int], obj: Dict[str, Any]) -> bool:
    if value_only is None:
        return True
    if "value" in obj and isinstance(obj["value"], int) and obj["value"] == value_only:
        return True
    if "addressed" in obj and any(it.get("value") == value_only for it in obj["addressed"]):
        return True
    if "registers" in obj and any(v == value_only for v in obj["registers"]):
        return True
    return False

# --------------- Main ---------------
def main():
    ap = argparse.ArgumentParser(description="Robuster Modbus-RTU Sniffer über TCP (ser2net/socat)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2001)
    ap.add_argument("--recv-chunk", dest="recv_chunk", type=int, default=2048)
    ap.add_argument("--watch", default="", help="Kommagetrennte Register (z.B. 1011,1205)")
    ap.add_argument("--value-only", dest="value_only", type=int, default=None, help="Nur Frames mit diesem Wert")
    ap.add_argument("--hits-only", dest="hits_only", action="store_true", help="Nur Filtertreffer ausgeben")
    ap.add_argument("--dump-raw", dest="dump_raw", action="store_true", help="Rohbytes dumpen, wenn gar kein Frame erkannt wurde")
    ap.add_argument("--raw-chunk", dest="raw_chunk", type=int, default=64)
    args = ap.parse_args()

    watch_regs = set()
    if args.watch.strip():
        for token in args.watch.replace(";", ",").split(","):
            token = token.strip()
            if token:
                try: watch_regs.add(int(token))
                except ValueError: pass

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((args.host, args.port))
    s.settimeout(0.1)

    buf = bytearray()
    last_req: Dict[Tuple[int,int], Dict[str,Any]] = {}

    MAX_FRAME_LEN = 300  # Sicherheitslimit für Desync-Recovery

    while True:
        got_any = False
        try:
            chunk = s.recv(args.recv_chunk)
            if chunk:
                buf.extend(chunk)
                got_any = True
        except socket.timeout:
            pass
        except KeyboardInterrupt:
            break

        produced = 0
        # Immer NUR vom Anfang dekodieren; angefangene Frames bleiben liegen
        while True:
            if len(buf) < 4:
                break
            res = decode_from_head(bytes(buf), last_req)
            if res:
                obj, flen = res
                # Filter
                hit = frame_matches_watch(watch_regs, obj) and frame_matches_value(args.value_only, obj)
                if args.hits_only:
                    if hit: emit(obj)
                else:
                    emit(obj)
                del buf[:flen]
                produced += 1
                continue

            # nicht decodierbar – zwei Fälle:
            # (1) zu kurz -> warten
            # (2) offensichtlich kaputt -> ein Byte verwerfen (Desync)
            # Heuristik: wenn Puffer groß ist, wirf 1 Byte
            if len(buf) > MAX_FRAME_LEN:
                # optional: Rohdump eines kleinen Stücks
                if args.dump_raw:
                    emit_raw("desyncDrop", bytes(buf[:32]))
                del buf[:1]
                continue
            # zu klein für sichere Entscheidung -> warten auf mehr Bytes
            break

        if got_any and produced == 0 and args.dump_raw and len(buf) > 0:
            n = min(len(buf), args.raw_chunk)
            emit_raw("noFrameFromChunk", bytes(buf[:n]))

if __name__ == "__main__":
    main()
