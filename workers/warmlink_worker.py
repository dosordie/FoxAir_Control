# -*- coding: utf-8 -*-
"""Warmlink/LTE Worker-Hilfslogik fuer FoxAir / Phnix Control.

Fix31 Refactor 2:
Die Init-Lese-Sequenz fuer den Warmlink/LTE-Pfad liegt hier als eigener
Controller. Der eigentliche Socket-/ReaderWorker bleibt unverändert im
Hauptmodul, aber Ablauf, Timing und Pending-Handling fuer "Alle bekannten
Register lesen" sind nicht mehr im GUI-Code verstreut.
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer


WARMLINK_INIT_BLOCKS: list[tuple[int, int, str]] = [
    (1001, 90, "Init Extra Paketkopf/Block 1001/0x03E9"),
    (1018, 73, "Init V1.3 Paket 1 Nutzdaten 1018/0x03FA"),
    (1091, 90, "Init Extra Paketkopf/Block 1091/0x0443"),
    (1101, 80, "Init V1.3 Paket 2 Nutzdaten 1101/0x044D"),
    (1181, 90, "Init Extra Paketkopf/Block 1181/0x049D"),
    (1191, 80, "Init V1.3 Paket 3 Nutzdaten 1191/0x04A7"),
    (1271, 90, "Init Parameterblock 1271/0x04F7"),
    (1361, 90, "Init Extra-Block 1361/0x0551"),
    (1451, 90, "Init Extra-Block 1451/0x05AB"),
    (1541, 90, "Init Extra-Block 1541/0x0605"),
    (2001, 90, "Init Statusblock 2001/0x07D1"),
    (2091, 90, "Init Statusblock 2091/0x082B"),
]


class WarmlinkInitReadController:
    """Sequenzieller Controller fuer 'Alle bekannten Register lesen' am Warmlink-Bus.

    Anders als der alte GUI-Pfad sendet dieser Controller nicht stur nach fester
    Pause den naechsten Block, sondern wartet auf Antwort oder Timeout. Dadurch
    koennen spaete Antworten, z.B. 1541/2001/2091, nicht mehr so leicht dem
    falschen Pending-Read zugeordnet werden.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.active = False
        self.queue: list[tuple[int, int, str, int, int]] = []
        self.retry_items: list[tuple[int, int, str, int, int]] = []
        self.current: tuple[int, int, str, int, int] | None = None
        self.timeout_s = 6.0
        self.pause_ms = 900
        self.waiting_since = 0.0

    def start(self, slave_addr: int, pause_ms: int = 900) -> None:
        owner = self.owner
        if self.active:
            owner._log("WARMLINK-INIT läuft bereits; zweiter Start wird ignoriert.")
            return
        self.pause_ms = max(400, int(pause_ms))
        self.timeout_s = max(4.0, float(self.pause_ms) / 1000.0 + 5.0)
        self.queue = [(addr, qty, label, int(slave_addr), 0) for addr, qty, label in WARMLINK_INIT_BLOCKS]
        self.retry_items = []
        self.current = None
        self.waiting_since = 0.0
        self.active = True

        owner.init_read_active = True
        owner.init_display_packet_mode = False
        owner.init_waiting_for_display_packet = False
        try:
            owner.init_read_btn.setEnabled(False)
            owner.init_read_btn.setText("Init läuft ...")
        except Exception:
            pass

        text = ", ".join(f"{addr}/{qty}" for addr, qty, _ in WARMLINK_INIT_BLOCKS)
        owner._log(
            f"WARMLINK-INIT gestartet: {len(WARMLINK_INIT_BLOCKS)} Blöcke, "
            f"Pause {self.pause_ms} ms / {self.pause_ms/1000:.1f} s, Timeout {self.timeout_s:.1f} s: {text}"
        )
        QTimer.singleShot(50, self.step)

    def _finish(self, message: str) -> None:
        owner = self.owner
        self.active = False
        self.current = None
        owner.init_read_active = False
        owner.init_display_packet_mode = False
        owner.init_waiting_for_display_packet = False
        try:
            if hasattr(owner, "_update_init_read_button_state"):
                owner._update_init_read_button_state()
            else:
                owner.init_read_btn.setEnabled(True)
                owner.init_read_btn.setText("Alle bekannten Register lesen")
        except Exception:
            pass
        owner._log(message)

    def notify_response(self, addr: int, quantity: int, slave_addr: int) -> None:
        if not self.active or self.current is None:
            return
        cur_addr, cur_qty, _label, cur_slave, _retry = self.current
        if int(addr) == int(cur_addr) and int(quantity) == int(cur_qty) and int(slave_addr) == int(cur_slave):
            self.current = None
            QTimer.singleShot(max(200, self.pause_ms), self.step)

    def step(self) -> None:
        owner = self.owner
        if not self.active:
            return
        if not getattr(owner, "connected", False) or not getattr(owner, "worker", None):
            self._finish("WARMLINK-INIT abgebrochen: keine aktive Verbindung.")
            return

        now = time.monotonic()
        if self.current is not None:
            age = now - self.waiting_since
            if age < self.timeout_s:
                QTimer.singleShot(250, self.step)
                return
            addr, qty, label, slave, retry = self.current
            # Passendes Pending aus der Hauptliste entfernen, damit ein spaeter Nachzuegler
            # nicht den naechsten Block faelschlich klaut.
            try:
                owner.pending_read_requests = [
                    r for r in owner.pending_read_requests
                    if not (
                        int(r.get("slave_addr", -1)) == int(slave)
                        and int(r.get("addr", -1)) == int(addr)
                        and int(r.get("quantity", -1)) == int(qty)
                        and str(r.get("label", "")) == str(label)
                    )
                ]
            except Exception:
                pass
            owner._log(
                f"WARMLINK-INIT TIMEOUT nach {self.timeout_s:.1f}s: "
                f"Unit 0x{int(slave):02X}, start={int(addr)}/0x{int(addr):04X}, qty={int(qty)}, retry={int(retry)}; nächster Block."
            )
            if int(retry) < 1:
                self.retry_items.append((addr, qty, label + " RETRY", slave, int(retry) + 1))
            self.current = None

        if not self.queue:
            if self.retry_items:
                retry_count = len(self.retry_items)
                self.queue = list(self.retry_items)
                self.retry_items = []
                owner._log(f"WARMLINK-INIT: starte Retry-Runde fuer {retry_count} Timeout-Block/Blöcke.")
                QTimer.singleShot(max(300, self.pause_ms), self.step)
                return
            self._finish("WARMLINK-INIT fertig / alle Blöcke inkl. Retry angefordert.")
            return

        addr, qty, label, slave, retry = self.queue.pop(0)
        total_left = len(self.queue)
        self.current = (addr, qty, label, slave, retry)
        self.waiting_since = time.monotonic()
        owner._log(f"WARMLINK-INIT Block: {label} ({addr}/{qty}), retry={retry}, verbleibend danach: {total_left}")
        owner.send_read_request(int(addr), int(qty), slave_addr=int(slave), label=str(label), delay_ms=0)
        QTimer.singleShot(250, self.step)
