# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import socket
from datetime import datetime
from typing import Any, Callable, Optional

DEFAULT_UDP_DIAGNOSTIC_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "host": "127.0.0.1",
    "port": 8766,
    "send_register_changes": True,
    "send_raw_bus": False,
}

MAX_UDP_DATAGRAM_BYTES = 8 * 1024


def udp_diagnostic_defaults(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_UDP_DIAGNOSTIC_SETTINGS)
    if isinstance(settings, dict):
        cfg.update(settings)
    cfg["enabled"] = bool(cfg.get("enabled", False))
    cfg["host"] = str(cfg.get("host") or "127.0.0.1").strip() or "127.0.0.1"
    try:
        cfg["port"] = max(1, min(65535, int(cfg.get("port", 8766) or 8766)))
    except Exception:
        cfg["port"] = 8766
    cfg["send_register_changes"] = bool(cfg.get("send_register_changes", True))
    cfg["send_raw_bus"] = bool(cfg.get("send_raw_bus", False))
    return cfg


def local_iso_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class UdpDiagnosticSender:
    """Small best-effort UDP diagnostic sender; never raises on send failures."""

    def __init__(
        self,
        settings: dict[str, Any] | None = None,
        *,
        socket_factory: Callable[[int, int], socket.socket] = socket.socket,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._socket_factory = socket_factory
        self._logger = logger
        self._sock: Any = None
        self._error_logged = False
        self.configure(settings or {})

    def configure(self, settings: dict[str, Any] | None) -> None:
        old_target = getattr(self, "target", None)
        self.settings = udp_diagnostic_defaults(settings)
        self.enabled = bool(self.settings["enabled"])
        self.host = str(self.settings["host"])
        self.port = int(self.settings["port"])
        self.allow_register_changes = bool(self.settings["send_register_changes"])
        self.allow_raw_bus = bool(self.settings["send_raw_bus"])
        self.target = (self.host, self.port)
        if old_target is not None and old_target != self.target:
            self.close()

    def close(self) -> None:
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    def _socket(self):
        if self._sock is None:
            self._sock = self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        return self._sock

    def send(self, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(data) > MAX_UDP_DATAGRAM_BYTES:
                payload = dict(payload)
                payload["truncated"] = True
                if payload.get("event") == "raw_bus" and isinstance(payload.get("hex"), str):
                    keep = max(0, MAX_UDP_DATAGRAM_BYTES - 512)
                    payload["hex"] = payload["hex"][:keep].rstrip()
                data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")[:MAX_UDP_DATAGRAM_BYTES]
            self._socket().sendto(data, self.target)
        except Exception as exc:
            if self._logger is not None and not self._error_logged:
                self._error_logged = True
                try:
                    self._logger(f"UDP-Diagnose Sendefehler ignoriert: {exc}")
                except Exception:
                    pass

    def send_register_change(self, *, backend: str, reg: int, raw: int, old_raw: int | None = None, value: str | None = None, name: str | None = None) -> None:
        if not (self.enabled and self.allow_register_changes):
            return
        payload: dict[str, Any] = {
            "event": "register_change",
            "ts": local_iso_timestamp(),
            "backend": str(backend or ""),
            "reg": int(reg),
            "raw": int(raw) & 0xFFFF,
            "hex": f"0x{int(raw) & 0xFFFF:04X}",
        }
        if old_raw is not None:
            payload["old_raw"] = int(old_raw) & 0xFFFF
        if value:
            payload["value"] = str(value)
        if name:
            payload["name"] = str(name)
        self.send(payload)

    def send_raw_bus(self, *, backend: str, direction: str, data: bytes | bytearray) -> None:
        if not (self.enabled and self.allow_raw_bus):
            return
        raw = bytes(data or b"")
        hex_text = " ".join(f"{b:02X}" for b in raw)
        payload: dict[str, Any] = {
            "event": "raw_bus",
            "ts": local_iso_timestamp(),
            "backend": str(backend or ""),
            "direction": "tx" if str(direction).lower() == "tx" else "rx",
            "hex": hex_text,
        }
        self.send(payload)
