"""Session-local WarmLink snapshots and mapping-based polling groups."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cloud.register_resolver import resolve_cloud_register
from cloud.warmlink_codes import cloud_hint


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
    validated: bool = False
    candidates: list[str] = field(default_factory=list)
    supported_codes: list[str] = field(default_factory=list)
    live_codes: list[str] = field(default_factory=list)
    static_codes: list[str] = field(default_factory=list)
    other_codes: list[str] = field(default_factory=list)
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    scanned: bool = False

    def reusable(self, username, device_code, token):
        return bool(token and self.validated and self.devices and self.username == username
                    and self.device_code == device_code)

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

    def classify(self, candidates):
        self.candidates = list(candidates)
        self.supported_codes = [code for code in candidates if self.rows.get(code, {}).get("supported")]
        groups = classify_cloud_codes(self.supported_codes)
        self.live_codes, self.static_codes, self.other_codes = (
            groups["live"], groups["static"], groups["other"])
        self.scanned = True
