# -*- coding: utf-8 -*-
"""Display-Bus Hilfslogik fuer FoxAir / Phnix Control.

Fix29 Refactor 1:
Die funktionierende Display-INIT-Logik aus dem Dual-Bus-Logger liegt hier als
kleiner Controller. Ziel ist eine klare Trennung: Display-Bus ist kein normaler
Master/Slave-Modbus-Pfad, sondern ein laufender HMI-Bus, auf dem wir passiv
mithoeren und nur gezielt aktive 0x03-WP-Paketreads einschieben.
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer


# Bekannte aktive WP-Paketbloecke auf dem Display-Bus.
# Unit 0x03 ist bisher die einzige bestaetigte Unit fuer diese aktiven Reads.
# 1001 bleibt absichtlich zuletzt, weil dieser Block am empfindlichsten auf
# Kollisionen mit dem normalen Display-Zyklus reagiert.
DISPLAY_KNOWN_PACKET_READS: list[tuple[int, int, int, str, int]] = [
    (0x03, 1091, 90, "Alle bekannten Display WP-Paketblock 0x03 1091/0x0443", 0),
    (0x03, 1181, 90, "Alle bekannten Display WP-Paketblock 0x03 1181/0x049D", 0),
    (0x03, 1271, 90, "Alle bekannten Display WP-Paketblock 0x03 1271/0x04F7", 0),
    (0x03, 1361, 90, "Alle bekannten Display WP-Paketblock 0x03 1361/0x0551", 0),
    (0x03, 1001, 90, "Alle bekannten Display WP-Paketblock 0x03 1001/0x03E9", 0),
]


class DisplayKnownReadController:
    """Sequenzieller Controller fuer 'Alle bekannten Register lesen' am Display-Bus.

    Der Controller arbeitet bewusst mit dem bestehenden DualBusLoggerDialog als
    Owner, damit Fix29 eine reine Struktur-/Wartbarkeitsänderung bleibt. Die
    Runtime-Objekte (ReaderWorker, Pending-Listen, Logging, Start/Stop) bleiben
    unverändert; nur die Ablaufsteuerung ist aus foxair_phnix_control.py
    herausgelöst.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def _status_text(self) -> str:
        owner = self.owner
        ok_items = list(getattr(owner, "display_known_init_ok_items", []) or [])
        timeout_items = list(getattr(owner, "display_known_init_timeout_items", []) or [])
        fail_items = list(getattr(owner, "display_known_init_fail_items", []) or [])
        total = len(DISPLAY_KNOWN_PACKET_READS)
        done = len({int(x[1]) for x in ok_items})
        return f"Display-Init: {done}/{total} OK, Timeout {len(timeout_items)}, ungültig {len(fail_items)}"

    def _update_button_status(self) -> None:
        main_window = getattr(self.owner, "main_window", None)
        if main_window is None:
            return
        try:
            main_window.init_read_btn.setText(self._status_text())
        except Exception:
            pass

    def start(self, pause_ms: int = 900) -> None:
        owner = self.owner
        if bool(getattr(owner, "display_known_init_active", False)):
            owner._log("DISPLAY-INIT via DisplayWorker läuft bereits; zweiter Start wird ignoriert.")
            return
        pause_ms = max(700, int(pause_ms))
        main_window = getattr(owner, "main_window", None)
        if main_window is not None:
            try:
                main_window.init_read_btn.setEnabled(False)
                main_window.init_read_btn.setText("Display-Init läuft ...")
            except Exception:
                pass
        owner.display_known_init_pause_ms = pause_ms
        # Fix32: Fix31-Buslueckenlogik wieder entschaerft.
        # Die reine Idle-Wartezeit hat die aktiven 0x03/10xx-Reads oft genau
        # kurz vor den naechsten Display-Zyklus geschoben; dadurch kamen nur
        # Timeouts. Zurueck zum bewaehrten Fix30-Verhalten: senden und dann
        # konsequent auf Antwort/Timeout warten.
        owner.display_known_init_timeout_s = max(7.0, float(pause_ms) / 1000.0 + 6.2)
        owner.display_known_init_bus_idle_ms = 0.0
        owner.display_known_init_retry_items = []
        owner.display_known_init_queue = list(DISPLAY_KNOWN_PACKET_READS)
        owner.display_known_init_active = True
        owner.display_known_init_ok_items = []
        owner.display_known_init_timeout_items = []
        owner.display_known_init_fail_items = []
        owner.display_packet_scan_cb.setChecked(False)
        self._update_button_status()

        # Alte Einmal-Init-Pendings entfernen, damit keine falsche Zuordnung bleibt.
        owner.display_pending_reads = [
            item for item in owner.display_pending_reads
            if str(item.get("active_scan_kind", "")) != "display_init_button"
        ]
        owner._log(
            "DISPLAY-INIT via DisplayWorker gestartet: "
            "bekannte erfolgreiche Paketreads 0x03/1091,1181,1271,1361,1001; "
            f"Pause {pause_ms} ms, Timeout {owner.display_known_init_timeout_s:.1f} s, ein Retry fuer Timeouts."
        )
        if not owner.display_worker:
            owner._log("DISPLAY-INIT via DisplayWorker: Display-Worker läuft noch nicht, starte Display-Verbindung.")
            # Fix33: start(display_only=True) initialisiert ausschliesslich den Display-Reader.
            # Der Warmlink-Bus wird hier bewusst NICHT geoeffnet; DualLogger bleibt getrennt.
            owner.start(display_only=True)
            QTimer.singleShot(1200, self.step)
        else:
            QTimer.singleShot(80, self.step)

    def _finish(self, message: str) -> None:
        owner = self.owner
        ok_items = list(getattr(owner, "display_known_init_ok_items", []) or [])
        timeout_items = list(getattr(owner, "display_known_init_timeout_items", []) or [])
        fail_items = list(getattr(owner, "display_known_init_fail_items", []) or [])
        total = len(DISPLAY_KNOWN_PACKET_READS)
        ok_addrs = sorted({int(x[1]) for x in ok_items})
        timeout_addrs = sorted({int(x[1]) for x in timeout_items})
        fail_addrs = sorted({int(x[1]) for x in fail_items})
        owner._log(
            "DISPLAY-INIT Ergebnis: "
            f"{len(ok_addrs)}/{total} Paketblock/Bloecke erfolgreich. "
            f"OK={ok_addrs or '-'}, Timeout={timeout_addrs or '-'}, ungueltig={fail_addrs or '-'}; "
            "aktive Display-Init-Paketreads werden in V0.2.38 fix2 bei gueltigem WP-Paketkopf wieder ins Hauptfenster übernommen."
        )
        owner.display_known_init_active = False
        main_window = getattr(owner, "main_window", None)
        if main_window is not None:
            try:
                main_window.init_read_btn.setEnabled(True)
                main_window.init_read_btn.setText("Alle bekannten Register lesen")
                if bool(getattr(main_window, "display_aux_takeover_active", False)):
                    main_window.connected = True
                    main_window.status_label.setText("DisplayWorker aktiv")
                    main_window.connect_btn.setEnabled(False)
                    main_window.disconnect_btn.setEnabled(True)
            except Exception:
                pass
        try:
            if main_window is not None and hasattr(main_window, "_update_init_read_button_state"):
                main_window._update_init_read_button_state()
        except Exception:
            pass
        owner._log(message)

    def step(self) -> None:
        owner = self.owner
        if owner._stopping or not getattr(owner, "display_known_init_active", False):
            return
        if not owner.display_worker:
            self._finish("DISPLAY-INIT via DisplayWorker abgebrochen: Display-Worker nicht verfügbar.")
            return

        now = time.monotonic()
        idx, item = owner._find_pending_read(owner.display_pending_reads, "display_init_button")
        if item is not None:
            age = now - float(item.get("queued_at", now))
            timeout_s = float(getattr(owner, "display_known_init_timeout_s", 7.0))
            if age < timeout_s:
                QTimer.singleShot(300, self.step)
                return
            try:
                owner.display_pending_reads.pop(idx)  # type: ignore[arg-type]
            except Exception:
                pass
            retry_no = int(item.get("retry_no", 0) or 0)
            owner._log(
                f"DISPLAY-INIT via DisplayWorker TIMEOUT nach {timeout_s:.1f}s: "
                f"Unit 0x{int(item.get('slave', 0)):02X}, "
                f"start={int(item.get('addr', 0))}/0x{int(item.get('addr', 0)):04X}, "
                f"qty={int(item.get('qty', 0))}, retry={retry_no}; nächster Block."
            )
            try:
                timeout_items = list(getattr(owner, "display_known_init_timeout_items", []) or [])
                timeout_items.append((int(item.get("slave", 0)), int(item.get("addr", 0)), int(item.get("qty", 0)), retry_no))
                owner.display_known_init_timeout_items = timeout_items
                self._update_button_status()
            except Exception:
                pass
            # Ein Retry am Ende ist sinnvoll, weil die Reads mit zyklischem Display-Traffic
            # kollidieren können. Jeder Timeout-Block bekommt genau einen zweiten Versuch.
            if retry_no < 1:
                retry_item = (
                    int(item.get("slave", 0)),
                    int(item.get("addr", 0)),
                    int(item.get("qty", 0)),
                    str(item.get("label", "Display WP-Paketblock Retry")) + " RETRY",
                    retry_no + 1,
                )
                retry_items = list(getattr(owner, "display_known_init_retry_items", []) or [])
                retry_items.append(retry_item)
                owner.display_known_init_retry_items = retry_items

        queue = list(getattr(owner, "display_known_init_queue", []) or [])
        if not queue:
            retry_items = list(getattr(owner, "display_known_init_retry_items", []) or [])
            if retry_items:
                owner.display_known_init_retry_items = []
                owner.display_known_init_queue = retry_items
                owner._log(
                    "DISPLAY-INIT via DisplayWorker: starte Retry-Runde fuer "
                    f"{len(retry_items)} Timeout-Block/Blöcke am Ende."
                )
                QTimer.singleShot(max(500, int(getattr(owner, "display_known_init_pause_ms", 900))), self.step)
                return
            self._finish("DISPLAY-INIT via DisplayWorker fertig / alle bekannten Blöcke inkl. Retry angefordert.")
            return

        slave, addr, qty, label, retry_no = queue.pop(0)

        owner.display_known_init_queue = queue
        owner.display_pending_reads.append({
            "slave": int(slave),
            "addr": int(addr),
            "qty": int(qty),
            "label": str(label),
            "map": "warmlink",
            "packet_test": True,
            "active_scan_kind": "display_init_button",
            "queued_at": now,
            "retry_no": int(retry_no),
        })
        owner.display_worker.enqueue_read(int(addr), int(qty), slave_addr=int(slave), post_delay_ms=0)
        owner._log(
            f"DISPLAY-INIT via DisplayWorker gesendet: Unit 0x{int(slave):02X}, "
            f"start={int(addr)}/0x{int(addr):04X}, qty={int(qty)}, "
            f"retry={int(retry_no)}, verbleibend={len(queue)}"
        )
        self._update_button_status()
        # Jetzt wirklich auf passende Antwort warten; Timeout/Weiter wird oben behandelt.
        QTimer.singleShot(250, self.step)
