from __future__ import annotations

import json, os, queue, threading, time, datetime, math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

DEFAULT_CAPTURE_SETTINGS = {
    "enabled": False,
    "directory": "warmlink_captures",
    "capture_rx": True,
    "capture_tx": True,
    "write_events": True,
    "idle_rotation_minutes": 5,
    "max_file_size_mb": 1024,
    "max_total_size_mb": 10240,
    "retention_days": 14,
    "anomaly_detection": True,
    "poll_2104": False,
    "poll_2104_interval_min": 60,
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


def parse_modbus(data: bytes) -> dict[str, Any]:
    ev: dict[str, Any] = {"parser": "partial"}
    if len(data) < 2:
        return ev
    fc = data[1]
    ev["function"] = f"0x{fc:02X}"
    try:
        if fc == 0x03 and len(data) >= 8:
            ev.update({"parser": "modbus_read", "addr": int.from_bytes(data[2:4], "big"), "qty": int.from_bytes(data[4:6], "big")})
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
    def start(self, baseline: Any = None):
        if self.thread: return
        if baseline is not None: self.note_register_2104(baseline, str(baseline), baseline=True)
        self.stop_evt.clear(); self.status.active = True; self._open_segment(force=True)
        self.thread = threading.Thread(target=self._run, name="WarmlinkRawCapture", daemon=True); self.thread.start(); self.log_cb("Warmlink Capture: gestartet")
    def stop(self, reason: str = "gestoppt"):
        self.stop_evt.set(); self.status.active = False; self._put(("event", {"event":"capture_stopped","reason":reason}))
        self.log_cb(f"Warmlink Capture: {reason}")
    def capture_rx(self, b: bytes): self._put(("rx", bytes(b)))
    def capture_tx(self, b: bytes): self._put(("tx", bytes(b)))
    def force_new_segment(self): self._put(("rotate", {}))
    def get_status(self) -> CaptureStatus:
        with self.lock: return CaptureStatus(**self.status.__dict__)
    def _put(self, item):
        if not self.status.active and item[0] not in ("event",): return
        try: self.q.put_nowait(item)
        except queue.Full:
            with self.lock: self.status.drops += 1
    def _run(self):
        while not self.stop_evt.is_set() or not self.q.empty():
            try: kind, payload = self.q.get(timeout=0.5)
            except queue.Empty: self._periodic(); continue
            try:
                if kind in ("rx","tx"): self._write_chunk(kind, payload)
                elif kind == "event": self._write_event(payload)
                elif kind == "rotate": self._open_segment(force=True)
                self._periodic()
            except Exception as exc:
                with self.lock: self.status.error = str(exc); self.status.active = False
                self.log_cb(f"Warmlink Capture: Schreibfehler: {exc}"); self.stop_evt.set()
        self._close_files()
    def _dir(self) -> Path:
        p = Path(str(self.cfg.get("directory") or "warmlink_captures"));
        if not p.is_absolute(): p = Path(self.base_dir)/p
        p.mkdir(parents=True, exist_ok=True); return p
    def _open_segment(self, force=False):
        self._close_files(); d=self._dir(); today=datetime.date.today().isoformat()
        if today != self.segment_date: self.segment_date=today; self.segment_no=0
        self.segment_no += 1; prefix=f"warmlink_capture_{today}_{self.segment_no:03d}"; self.offsets={"rx":0,"tx":0}
        self.rx=open(d/(prefix+".rx.bin"),"ab") if self.cfg.get("capture_rx",True) else None
        self.tx=open(d/(prefix+".tx.bin"),"ab") if self.cfg.get("capture_tx",True) else None
        self.events=open(d/(prefix+".events.jsonl"),"a",encoding="utf-8") if self.cfg.get("write_events",True) else None
        self.summary_path=str(d/(prefix+".summary.txt")); Path(self.summary_path).write_text("Warmlink RAW Capture Segment\nFirmware update suspected: no\n", encoding="utf-8")
        self.active_paths={str(x) for x in (getattr(self.rx,'name',None),getattr(self.tx,'name',None),getattr(self.events,'name',None),self.summary_path) if x}
        with self.lock: self.status.segment=prefix; self.status.rx_size=0; self.status.tx_size=0
        self.log_cb(f"Warmlink Capture: neues Segment {prefix}")
    def _close_files(self):
        for f in (self.rx,self.tx,self.events):
            if f:
                try: f.flush(); os.fsync(f.fileno()); f.close()
                except Exception: pass
        self.rx=self.tx=self.events=None
    def _write_chunk(self, direction, data: bytes):
        now=time.monotonic(); self.last_data_mono=now; f = self.rx if direction=="rx" else self.tx
        if f: f.write(data)
        off=self.offsets[direction]; self.offsets[direction]+=len(data)
        ev={"ts":utc_iso(),"mono_s":now,"dir":direction,"offset":off,"len":len(data),"hex_head":data[:32].hex()}
        ev.update(parse_modbus(data)); self._write_event(ev)
        with self.lock:
            if direction=="rx": self.status.rx_size=self.offsets["rx"]; self.status.last_rx=ev["ts"]
            else: self.status.tx_size=self.offsets["tx"]; self.status.last_tx=ev["ts"]
        self._anomaly(direction, data, ev, now)
    def _write_event(self, ev: dict[str,Any]):
        if self.events: self.events.write(json.dumps(ev, ensure_ascii=False, separators=(",",":"))+"\n")
    def _anomaly(self, direction, data, ev, now):
        if not self.cfg.get("anomaly_detection", True): return
        arr = self.recent_rx if direction=="rx" else self.recent_tx; arr.append((now,len(data))); del arr[:max(0,len(arr)-200)]
        rx_bytes=sum(n for t,n in self.recent_rx if now-t<=10); tx_bytes=sum(n for t,n in self.recent_tx if now-t<=10)
        kind=None
        if direction=="rx" and rx_bytes>50*1024: kind="large_rx_burst"
        if ev.get("function") and ev.get("function") not in {"0x03","0x06","0x10"}: kind="unknown_function"
        if ev.get("function")=="0x10":
            self.fc16_window.append((now, int(ev.get("addr",-1)), int(ev.get("qty",0)), len(data))); self.fc16_window=[x for x in self.fc16_window if now-x[0]<=60]
            if len(self.fc16_window)>=20 or sum(x[3] for x in self.fc16_window)>50*1024: kind="firmware_like_fc16_sequence"
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
