"""Session-local WarmLink snapshots and mapping-based polling groups."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cloud.register_resolver import resolve_cloud_register
from cloud.warmlink_codes import cloud_hint


@dataclass(frozen=True)
class CloudTimingState:
    """Worker-owned monotonic schedule; the GUI only renders this snapshot."""
    phase: str = "IDLE"
    done: int = 0
    total: int = 0
    deadline: float | None = None
    duration: float = 0.0
    polling_active: bool = False


# Reviewed cloud-live fault words, explicitly polled independently of the
# candidate Modbus projection. This does not promote their mapping confidence.
RAW_FAULT_LIVE_CODES = frozenset({
    "Fault1", "Fault2", "Fault3", "Fault4", "Fault5",
    "Fault6", "Fault7", "Fault8", "Fault9", "Fault10",
})

def classify_cloud_codes(codes, definitions=None):
    groups = {"live": [], "static": [], "other": []}
    for code in dict.fromkeys(codes):
        register = resolve_cloud_register(code, cloud_hint(code), definitions)
        group = "live" if code in RAW_FAULT_LIVE_CODES or (register is not None and 2000 <= register <= 2999) else (
            "static" if register is not None and 1000 <= register <= 1999 else "other")
        groups[group].append(code)
    return groups


@dataclass
class CloudSession:
    username: str = ""
    device_code: str = ""
    devices: list[dict[str, Any]] = field(default_factory=list)
    devices_cached: bool = False
    validated: bool = False
    candidates: list[str] = field(default_factory=list)
    supported_codes: list[str] = field(default_factory=list)
    live_codes: list[str] = field(default_factory=list)
    static_codes: list[str] = field(default_factory=list)
    other_codes: list[str] = field(default_factory=list)
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    scanned: bool = False

    def reusable(self, username, device_code, token):
        account_matches = self.username == username and self.device_code == device_code
        device_exists = any(device.get("deviceCode") == device_code for device in self.devices)
        return bool(account_matches and device_exists and (self.devices_cached or (token and self.validated)))

    def merge(self, rows):
        for row in rows:
            code = str(row.get("code") or "")
            if not code:
                continue
            cached = self.rows.get(code, {})
            if not row.get("supported") and cached.get("supported"):
                row = {**cached, "stale": True, "cached": True, "currentEmpty": True}
            else:
                row = {**cached, **row}
            self.rows[code] = dict(row)

    def classify(self, candidates, fresh_rows=None):
        self.candidates = list(candidates)
        # A full scan rechecks support; retained stale values are not evidence of support.
        evidence = self.rows if fresh_rows is None else {row["code"]: row for row in fresh_rows}
        self.supported_codes = [code for code in candidates if evidence.get(code, {}).get("supported")]
        groups = classify_cloud_codes(self.supported_codes)
        self.live_codes, self.static_codes, self.other_codes = (
            groups["live"], groups["static"], groups["other"])
        self.scanned = True
