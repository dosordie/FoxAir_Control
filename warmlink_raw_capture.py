from __future__ import annotations

import json, os, queue, threading, time, datetime, math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

DEFAULT_CAPTURE_SETTINGS = {
    "enabled": False,
    "directory": "captures",
    "capture_rx": True,
    "capture_tx": True,
    "write_events": True,
    "idle_rotation_minutes": 5,
    "max_file_size_mb": 1024,
    "max_total_size_mb": 10240,
    "retention_days": 14,
    "anomaly_detection": True,
}

@dataclass
class CaptureStatus:
    active: bool = False
    segment: str = "--"
    rx_size: int = 0
    tx_size: int = 0
    last_rx: str = "--"
    last_tx: str = "--"
    anomalies: int = 0
    drops: int = 0
    error: str = ""


def utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


KNOWN_BUS_ADDRS = {0x63}
KNOWN_FUNCTIONS = {0x03, 0x06, 0x10}
NORMAL_FC16_BLOCKS = {
    (0x0443, 90),
    (0x07D1, 90),
    (0x082B, 90),
}


def parse_modbus(data: bytes, expected_unit_id: Optional[int] = None) -> dict[str, Any]:
    """Conservatively classify a TCP chunk without assuming frame alignment."""
    ev: dict[str, Any] = {"parser": "partial" if len(data) < 4 else "chunk"}
    addrs = set(KNOWN_BUS_ADDRS)
    if expected_unit_id is not None:
        try:
            addrs.add(int(expected_unit_id) & 0xFF)
        except Exception:
            pass
    if len(data) < 2:
        return ev
    if data[0] not in addrs:
        return ev
    fc = data[1]
    if fc not in KNOWN_FUNCTIONS:
        ev.update({"parser": "frame_start", "function": f"0x{fc:02X}", "bus": data[0]})
        return ev
    ev.update({"parser": "frame_start", "function": f"0x{fc:02X}", "bus": data[0]})
    try:
        if fc == 0x03 and len(data) >= 8:
            ev.update({"parser": "frame", "addr": int.from_bytes(data[2:4], "big"), "qty": int.from_bytes(data[4:6], "big")})
        elif fc in (0x06, 0x10) and len(data) >= 8:
            ev.update({"parser": "frame", "frame_type": f"0x{int.from_bytes(data[2:4], 'big'):04X}", "addr": int.from_bytes(data[2:4], "big"), "qty": int.from_bytes(data[4:6], "big")})
    except Exception:
        ev["parser"] = "partial"
    return ev

class WarmlinkRawCapture:
    def __init__(self, settings: dict[str, Any], base_dir: str, log_cb: Optional[Callable[[str], None]] = None):
        cfg = dict(DEFAULT_CAPTURE_SETTINGS); cfg.update(settings or {})
        self.cfg = cfg; self.base_dir = base_dir; self.log_cb = log_cb or (lambda _m: None)
        self.q: queue.Queue = queue.Queue(maxsize=2000); self.thread: Optional[threading.Thread] = None; self.stop_evt = threading.Event()
        self.lock = threading.Lock(); self.status = CaptureStatus(); self.segment_date = ""; self.segment_no = 0
        self.rx = self.tx = self.events = None; self.summary_path = ""; self.active_paths: set[str] = set(); self.offsets = {"rx":0,"tx":0}
        self.last_data_mono = 0.0; self.last_flush = 0.0; self.recent_rx: list[tuple[float,int]] = []; self.recent_tx: list[tuple[float,int]] = []; self.last_prune = 0.0
        self.fc16_window: list[tuple[float,int,int,int]] = []; self.firmware_baseline: Optional[tuple[int,str]] = None; self.firmware_changed = False
        self._drop_event_pending = False; self._last_drop_event_total = 0
        self._continuation: dict[str, Any] = {"dir": None, "remaining": 0, "addr": None, "qty": None}
        self._frame_index_buffers: dict[str, dict[str, Any]] = {
            "rx": {"offset": 0, "data": bytearray()},
            "tx": {"offset": 0, "data": bytearray()},
        }
    def start(self, baseline: Any = None):
        if self.thread: return
        if baseline is not None: self.note_register_2104(baseline, str(baseline), baseline=True)
        self.stop_evt.clear(); self.status.active = True; self._open_segment(force=True)
        self.thread = threading.Thread(target=self._run, name="WarmlinkRawCapture", daemon=True); self.thread.start(); self.log_cb("Warmlink Capture: gestartet")
    def stop(self, reason: str = "gestoppt", join: bool = False, timeout: float = 3.0):
        self.stop_evt.set(); self.status.active = False; self._put(("event", {"event":"capture_stopped","reason":reason,"ts":utc_iso()}))
        self.log_cb(f"Warmlink Capture: {reason}")
        if join and self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=max(0.0, float(timeout)))
    def capture_rx(self, b: bytes): self._put(("rx", bytes(b)))
    def capture_tx(self, b: bytes): self._put(("tx", bytes(b)))
    def force_new_segment(self): self._put(("rotate", {}))
    def get_status(self) -> CaptureStatus:
        with self.lock: return CaptureStatus(**self.status.__dict__)
    def _put(self, item):
        if not self.status.active and item[0] not in ("event",): return
        try:
            if self._drop_event_pending and item[0] != "drop_event":
                drops = int(self.status.drops)
                try:
                    self.q.put_nowait(("drop_event", {"ts": utc_iso(), "event": "capture_drop", "drops_total": drops, "note": "Capture queue full; raw bytes may be incomplete"}))
                    self._drop_event_pending = False
                    self._last_drop_event_total = drops
                except queue.Full:
                    pass
            self.q.put_nowait(item)
        except queue.Full:
            with self.lock: self.status.drops += 1
            self._drop_event_pending = True
    def _run(self):
        while not self.stop_evt.is_set() or not self.q.empty():
            try: kind, payload = self.q.get(timeout=0.5)
            except queue.Empty: self._periodic(); continue
            try:
                if kind in ("rx","tx"): self._write_chunk(kind, payload)
                elif kind in ("event", "drop_event"): self._write_event(payload)
                elif kind == "rotate": self._open_segment(force=True)
                self._periodic()
            except Exception as exc:
                with self.lock: self.status.error = str(exc); self.status.active = False
                self.log_cb(f"Warmlink Capture: Schreibfehler: {exc}"); self.stop_evt.set()
        self._close_files()
    def _dir(self) -> Path:
        p = Path(str(self.cfg.get("directory") or DEFAULT_CAPTURE_SETTINGS["directory"]));
        if not p.is_absolute(): p = Path(self.base_dir)/p
        p.mkdir(parents=True, exist_ok=True); return p
    def _open_segment(self, force=False):
        self._close_files(); d=self._dir(); today=datetime.date.today().isoformat()
        if today != self.segment_date: self.segment_date=today; self.segment_no=0
        prefix, segment_no = self._next_free_segment_prefix(d, today, self.segment_no + 1)
        self.segment_no = segment_no
        self.offsets={"rx":0,"tx":0}
        self._reset_frame_index_buffers()
        self.rx=open(d/(prefix+".rx.bin"),"xb") if self.cfg.get("capture_rx",True) else None
        self.tx=open(d/(prefix+".tx.bin"),"xb") if self.cfg.get("capture_tx",True) else None
        self.events=open(d/(prefix+".events.jsonl"),"x",encoding="utf-8") if self.cfg.get("write_events",True) else None
        self.summary_path=str(d/(prefix+".summary.txt"))
        with open(self.summary_path, "x", encoding="utf-8") as summary:
            summary.write("Warmlink RAW Capture Segment\nFirmware update suspected: no\n")
        self.active_paths={str(x) for x in (getattr(self.rx,'name',None),getattr(self.tx,'name',None),getattr(self.events,'name',None),self.summary_path) if x}
        with self.lock: self.status.segment=prefix; self.status.rx_size=0; self.status.tx_size=0
        self.log_cb(f"Warmlink Capture: neues Segment {prefix}")

    @staticmethod
    def _segment_prefix_exists(directory: Path, prefix: str) -> bool:
        suffixes = (".rx.bin", ".tx.bin", ".events.jsonl", ".summary.txt", ".UPDATE_DETECTED.txt")
        return any((directory / (prefix + suffix)).exists() for suffix in suffixes)

    def _next_free_segment_prefix(self, directory: Path, today: str, start_no: int) -> tuple[str, int]:
        segment_no = max(1, int(start_no))
        while True:
            prefix = f"warmlink_capture_{today}_{segment_no:03d}"
            if not self._segment_prefix_exists(directory, prefix):
                return prefix, segment_no
            segment_no += 1

    def _reset_frame_index_buffers(self):
        for state in self._frame_index_buffers.values():
            state["offset"] = 0
            state["data"].clear()
    def _close_files(self):
        for f in (self.rx,self.tx,self.events):
            if f:
                try: f.flush(); os.fsync(f.fileno()); f.close()
                except Exception: pass
        if self.summary_path:
            try:
                with open(self.summary_path, "a", encoding="utf-8") as f:
                    f.write(f"Drops total: {int(self.status.drops)}\n")
                    if int(self.status.drops) > 0:
                        f.write("Capture complete: no (queue drops occurred)\n")
            except Exception:
                pass
        self.rx=self.tx=self.events=None
    def _write_chunk(self, direction, data: bytes):
        now=time.monotonic(); self.last_data_mono=now; f = self.rx if direction=="rx" else self.tx
        if f: f.write(data)
        off=self.offsets[direction]; self.offsets[direction]+=len(data)
        ev={"ts":utc_iso(),"mono_s":now,"dir":direction,"offset":off,"len":len(data),"hex_head":data[:32].hex()}
        ev.update(self._parse_capture_chunk(direction, data)); self._write_event(ev)
        self._index_complete_frames(direction, off, data)
        with self.lock:
            if direction=="rx": self.status.rx_size=self.offsets["rx"]; self.status.last_rx=ev["ts"]
            else: self.status.tx_size=self.offsets["tx"]; self.status.last_tx=ev["ts"]
        self._anomaly(direction, data, ev, now)
    def _expected_unit_id(self) -> Optional[int]:
        try:
            return int(self.cfg.get("unit_id")) if self.cfg.get("unit_id") is not None else None
        except Exception:
            return None
    def _parse_capture_chunk(self, direction: str, data: bytes) -> dict[str, Any]:
        cont = self._continuation
        parsed = parse_modbus(data, self._expected_unit_id())
        if cont.get("remaining", 0) > 0 and cont.get("dir") == direction and parsed.get("parser") != "frame":
            remaining = max(0, int(cont.get("remaining", 0)) - len(data))
            out = {"parser": "continuation", "continuation_addr": cont.get("addr"), "continuation_qty": cont.get("qty"), "continuation_remaining": remaining}
            cont["remaining"] = remaining
            return out
        if parsed.get("function") == "0x10" and parsed.get("parser") == "frame":
            qty = int(parsed.get("qty", 0)); addr = int(parsed.get("addr", -1))
            expected = 1 + 1 + 2 + 2 + 1 + (qty * 2) + 2 if qty > 0 and len(data) >= 7 and data[6] == (qty * 2) & 0xFF else 0
            if expected and len(data) < expected:
                cont.update({"dir": direction, "remaining": expected - len(data), "addr": addr, "qty": qty})
                parsed["parser"] = "frame_start"
                parsed["expected_len"] = expected
                parsed["continuation_remaining"] = expected - len(data)
        return parsed

    def _index_complete_frames(self, direction: str, offset: int, data: bytes):
        buf_state = self._frame_index_buffers[direction]
        buf = buf_state["data"]
        if not buf:
            buf_state["offset"] = offset
        elif int(buf_state["offset"]) + len(buf) != offset:
            buf.clear()
            buf_state["offset"] = offset
        buf.extend(data)
        while True:
            found = self._find_complete_frame(bytes(buf))
            if found is None:
                if len(buf) > 4096:
                    drop = len(buf) - 512
                    del buf[:drop]
                    buf_state["offset"] = int(buf_state["offset"]) + drop
                return
            start, frame, meta = found
            if start:
                del buf[:start]
                buf_state["offset"] = int(buf_state["offset"]) + start
            frame_start = int(buf_state["offset"])
            self._write_frame_complete_event(direction, frame_start, frame, meta)
            del buf[:len(frame)]
            buf_state["offset"] = frame_start + len(frame)

    def _find_complete_frame(self, data: bytes) -> Optional[tuple[int, bytes, dict[str, Any]]]:
        addrs = set(KNOWN_BUS_ADDRS)
        unit = self._expected_unit_id()
        if unit is not None:
            addrs.add(unit & 0xFF)
        for start in range(len(data)):
            if data[start] not in addrs or start + 4 > len(data):
                continue
            fc = data[start + 1]
            if fc not in KNOWN_FUNCTIONS:
                continue
            tail = data[start:]
            candidates: list[tuple[int, dict[str, Any]]] = []
            if fc == 0x03:
                if len(tail) >= 3:
                    bc = tail[2]
                    if bc % 2 == 0 and 5 + bc <= 260:
                        candidates.append((5 + bc, {"byte_count": bc, "payload_rel": 3, "payload_len": bc, "qty": bc // 2}))
                candidates.append((8, {"addr": int.from_bytes(tail[2:4], "big") if len(tail) >= 6 else None, "qty": int.from_bytes(tail[4:6], "big") if len(tail) >= 6 else None}))
            elif fc == 0x06:
                candidates.append((8, {"addr": int.from_bytes(tail[2:4], "big") if len(tail) >= 6 else None, "qty": 1}))
            elif fc == 0x10:
                if len(tail) >= 7:
                    bc = tail[6]
                    if bc % 2 == 0 and bc > 0 and 9 + bc <= 260:
                        candidates.append((9 + bc, {"addr": int.from_bytes(tail[2:4], "big"), "qty": int.from_bytes(tail[4:6], "big"), "byte_count": bc, "payload_rel": 7, "payload_len": bc}))
                candidates.append((8, {"addr": int.from_bytes(tail[2:4], "big") if len(tail) >= 6 else None, "qty": int.from_bytes(tail[4:6], "big") if len(tail) >= 6 else None}))
            for length, meta in candidates:
                if len(tail) < length:
                    continue
                frame = tail[:length]
                if self._modbus_crc_ok(frame):
                    meta.update({"bus": frame[0], "function": f"0x{fc:02X}", "crc": int.from_bytes(frame[-2:], "little"), "crc_ok": True})
                    return start, frame, meta
        return None

    @staticmethod
    def _modbus_crc_ok(frame: bytes) -> bool:
        if len(frame) < 4:
            return False
        crc = 0xFFFF
        for b in frame[:-2]:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc == int.from_bytes(frame[-2:], "little")

    def _write_frame_complete_event(self, direction: str, offset_start: int, frame: bytes, meta: dict[str, Any]):
        ev = {
            "ts": utc_iso(),
            "event": "frame_complete",
            "dir": direction,
            "file": os.path.basename(getattr(self.rx if direction == "rx" else self.tx, "name", "")),
            "offset_start": offset_start,
            "offset_end": offset_start + len(frame),
            "len": len(frame),
            "bus": meta.get("bus"),
            "function": meta.get("function"),
            "crc_ok": bool(meta.get("crc_ok")),
            "crc": f"0x{int(meta.get('crc', 0)):04X}",
        }
        for key in ("addr", "qty", "byte_count"):
            if meta.get(key) is not None:
                ev[key] = meta.get(key)
        if meta.get("payload_rel") is not None:
            ev["payload_offset"] = offset_start + int(meta.get("payload_rel", 0))
            ev["payload_len"] = int(meta.get("payload_len", 0))
        self._write_event(ev)
    def _write_event(self, ev: dict[str,Any]):
        if self.events: self.events.write(json.dumps(ev, ensure_ascii=False, separators=(",",":"))+"\n")
    def _anomaly(self, direction, data, ev, now):
        if not self.cfg.get("anomaly_detection", True): return
        arr = self.recent_rx if direction=="rx" else self.recent_tx; arr.append((now,len(data))); del arr[:max(0,len(arr)-200)]
        rx_bytes=sum(n for t,n in self.recent_rx if now-t<=10); tx_bytes=sum(n for t,n in self.recent_tx if now-t<=10)
        kind=None
        if direction=="rx" and rx_bytes>50*1024: kind="large_rx_burst"
        if ev.get("parser") == "frame_start" and ev.get("function") and ev.get("function") not in {"0x03","0x06","0x10"} and len(data) >= 4 and ev.get("bus") in KNOWN_BUS_ADDRS:
            kind="unknown_function"
        if ev.get("function")=="0x10":
            self.fc16_window.append((now, int(ev.get("addr",-1)), int(ev.get("qty",0)), len(data))); self.fc16_window=[x for x in self.fc16_window if now-x[0]<=60]
            normal = (int(ev.get("addr",-1)), int(ev.get("qty",0))) in NORMAL_FC16_BLOCKS
            unknown_addrs = {x[1] for x in self.fc16_window if (x[1], x[2]) not in NORMAL_FC16_BLOCKS}
            fc16_bytes = sum(x[3] for x in self.fc16_window)
            if (unknown_addrs and (len(self.fc16_window) >= 20 or fc16_bytes > 50*1024)) or fc16_bytes > 200*1024 or (self.firmware_changed and len(self.fc16_window) >= 10 and not normal):
                kind="firmware_like_fc16_sequence"
        if kind: self._mark_anomaly(kind, now, rx_bytes, tx_bytes, ev)
    def _mark_anomaly(self, kind, now, rx_bytes, tx_bytes, ev):
        with self.lock: self.status.anomalies += 1
        addrs=[x[1] for x in self.fc16_window if x[1]>=0]
        out={"ts":utc_iso(),"event":"anomaly","kind":kind,"window_s":10,"totalbytes":rx_bytes+tx_bytes,"rx_tx_ratio": (rx_bytes / tx_bytes if tx_bytes else None),"function":ev.get("function"),"first_addr":min(addrs) if addrs else ev.get("addr"),"last_addr":max(addrs) if addrs else ev.get("addr"),"frame_count":len(self.fc16_window),"reconnect_after":False,"note":"Ungewoehnliche Warmlink/Modbus-Aktivitaet, moegliche Sonderuebertragung"}
        self._write_event(out); self.log_cb(f"Warmlink Capture: Anomalie erkannt: {kind} bytes={rx_bytes+tx_bytes}")
    def note_register_2104(self, raw: Any, display: str, baseline=False):
        try: raw_i=int(raw)
        except Exception: raw_i=0
        if self.firmware_baseline is None or baseline:
            self.firmware_baseline=(raw_i, str(display)); self._put(("event", {"ts":utc_iso(),"event":"firmware_version_seen","reg":2104,"raw":raw_i,"display":str(display)})); return
        old_raw, old_disp = self.firmware_baseline
        if old_raw != raw_i or old_disp != str(display):
            ev={"ts":utc_iso(),"event":"firmware_version_changed","reg":2104,"old_raw":old_raw,"new_raw":raw_i,"old_display":old_disp,"new_display":str(display),"increased": raw_i>old_raw,"note":"Hauptsoftwareversion hat sich geaendert; Firmwareupdate vermutlich abgeschlossen oder gestartet"}
            self.firmware_baseline=(raw_i,str(display)); self.firmware_changed=True
            self._put(("event", ev))
            if raw_i > old_raw:
                self._put(("event", {**ev, "event": "firmware_version_increased"}))
            try:
                with open(self.summary_path,"a",encoding="utf-8") as f: f.write(f"Firmware update suspected: yes\nMain software version old: {old_disp}\nMain software version new: {display}\nTime of change: {ev['ts']}\n")
                Path(self.summary_path.replace(".summary.txt", ".UPDATE_DETECTED.txt")).write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception: pass
            with self.lock: self.status.anomalies += 1
            self.log_cb(f"Warmlink Capture: Hauptsoftwareversion 2104 geändert: {old_disp} -> {display}")
    def _periodic(self):
        now=time.monotonic()
        if now-self.last_flush>10:
            for f in (self.rx,self.tx,self.events):
                if f: f.flush()
            self.last_flush=now
        max_size=int(self.cfg.get("max_file_size_mb",1024))*1024*1024
        if max(self.offsets.values() or [0]) >= max_size: self._open_segment(force=True)
        today=datetime.date.today().isoformat()
        idle_min=float(self.cfg.get("idle_rotation_minutes",5) or 5)
        if self.segment_date and today != self.segment_date and (self.last_data_mono <= 0 or now-self.last_data_mono >= idle_min*60):
            self._open_segment(force=True)
        if now-self.last_prune > 300:
            self._prune_old_segments(); self.last_prune=now

    def _prune_old_segments(self):
        d=self._dir(); now=time.time(); retention=float(self.cfg.get("retention_days",14) or 14)*86400
        files=[p for p in d.glob("warmlink_capture_*") if str(p) not in self.active_paths and p.is_file()]
        for p in sorted(files, key=lambda x: x.stat().st_mtime):
            try:
                if now-p.stat().st_mtime > retention: p.unlink()
            except Exception: pass
        max_total=int(self.cfg.get("max_total_size_mb",10240))*1024*1024
        files=[p for p in d.glob("warmlink_capture_*") if str(p) not in self.active_paths and p.is_file()]
        total=sum(p.stat().st_size for p in files if p.exists()) + sum(os.path.getsize(p) for p in self.active_paths if p and os.path.exists(p))
        for p in sorted(files, key=lambda x: x.stat().st_mtime):
            if total <= max_total: break
            try:
                sz=p.stat().st_size; p.unlink(); total-=sz
            except Exception: pass
        if total > max_total:
            self._write_event({"ts":utc_iso(),"event":"storage_limit_reached","limit_bytes":max_total,"total_bytes":total})
            self.log_cb("Warmlink Capture: Speicherlimit erreicht, Capture wird gestoppt")
            self.stop_evt.set(); self.status.active=False
