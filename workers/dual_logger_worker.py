# -*- coding: utf-8 -*-
"""Dual-Logger Worker/Coordinator.

Kapselt bewusst nur die Verbindungs-/Thread-Verwaltung fuer den echten
Dual-Bus-Logger. Die Auswertung/Korrelation bleibt vorerst im Dialog, damit der
Fix klein und risikoarm bleibt. Wichtig ist die saubere Trennung:

- DisplayWorker: nur Display-Bus/Display-Init
- WarmlinkWorker: nur Warmlink-Init/Warmlink-Betrieb
- StandardModbusWorker: nur Standard-Modbus
- DualLoggerWorkerController: nur wenn das Dual-Logger-Fenster bewusst gestartet wird
"""

from __future__ import annotations

from typing import Any, Optional, Type

from PySide6.QtCore import QObject, QThread


class DualLoggerWorkerController(QObject):
    """Startet/stoppt die zwei ReaderWorker des echten Dual-Logger-Fensters.

    Der Controller bekommt den Dialog als Owner. Dadurch kann er weiter die dort
    vorhandenen UI-Felder und Callbacks nutzen, ohne die Parser-/Korrelationslogik
    zu duplizieren. Das ist absichtlich ein erster Refactor-Schritt: die Bus-
    Besitzverhältnisse sind jetzt zentral getrennt; die restliche Diagnose-Logik
    kann spaeter in kleineren Schritten folgen.
    """

    def __init__(self, owner: Any, reader_worker_cls: Type[QObject]):
        super().__init__(owner)
        self.owner = owner
        self.reader_worker_cls = reader_worker_cls
        self.display_thread: Optional[QThread] = None
        self.display_worker: Optional[QObject] = None
        self.warmlink_thread: Optional[QThread] = None
        self.warmlink_worker: Optional[QObject] = None

    def start_display_worker(self, backend_label: str) -> None:
        if self.display_thread is not None:
            return
        o = self.owner
        self.display_thread = QThread(o)
        self.display_worker = self.reader_worker_cls(
            o.display_host_edit.text().strip(),
            int(o.display_port_spin.value()),
            o.main_window.display_regmap,
            backend_label=backend_label,
            transport="tcp",
            write_single=False,
        )
        self.display_worker.moveToThread(self.display_thread)
        self.display_thread.started.connect(self.display_worker.run)
        self.display_worker.connected.connect(lambda: o._log("Display-Bus verbunden."))
        self.display_worker.disconnected.connect(lambda: o._log("Display-Bus getrennt."))
        self.display_worker.error.connect(lambda e: o._log(f"Display Fehler: {e}"))
        self.display_worker.log.connect(lambda t: o._log(f"Display Worker: {t}"))
        self.display_worker.raw_chunk.connect(o.on_display_raw_chunk)
        self.display_worker.frame_decoded.connect(o.on_display_frame)
        self.display_worker.disconnected.connect(self.display_thread.quit)
        self.display_worker.disconnected.connect(self.display_worker.deleteLater)
        self.display_thread.finished.connect(self.display_thread.deleteLater)
        self.display_thread.finished.connect(self._clear_display_refs)
        self.display_thread.start()
        self._sync_owner_refs()

    def start_warmlink_worker(self, backend_label: str) -> None:
        if self.warmlink_thread is not None:
            return
        o = self.owner
        self.warmlink_thread = QThread(o)
        self.warmlink_worker = self.reader_worker_cls(
            o.warmlink_host_edit.text().strip(),
            int(o.warmlink_port_spin.value()),
            o.main_window.regmap,
            backend_label=backend_label,
            transport="tcp",
            write_single=False,
        )
        self.warmlink_worker.moveToThread(self.warmlink_thread)
        self.warmlink_thread.started.connect(self.warmlink_worker.run)
        self.warmlink_worker.connected.connect(lambda: o._log("Warmlink-Bus verbunden."))
        self.warmlink_worker.disconnected.connect(lambda: o._log("Warmlink-Bus getrennt."))
        self.warmlink_worker.error.connect(lambda e: o._log(f"Warmlink Fehler: {e}"))
        self.warmlink_worker.log.connect(lambda t: o._log(f"Warmlink Worker: {t}"))
        self.warmlink_worker.frame_decoded.connect(o.on_warmlink_frame)
        self.warmlink_worker.disconnected.connect(self.warmlink_thread.quit)
        self.warmlink_worker.disconnected.connect(self.warmlink_worker.deleteLater)
        self.warmlink_thread.finished.connect(self.warmlink_thread.deleteLater)
        self.warmlink_thread.finished.connect(self._clear_warmlink_refs)
        self.warmlink_thread.start()
        self._sync_owner_refs()

    def stop(self) -> None:
        if self.display_worker is not None:
            try:
                self.display_worker.stop()
            except Exception:
                pass
        if self.warmlink_worker is not None:
            try:
                self.warmlink_worker.stop()
            except Exception:
                pass

    def _clear_display_refs(self) -> None:
        self.display_thread = None
        self.display_worker = None
        self._sync_owner_refs()

    def _clear_warmlink_refs(self) -> None:
        self.warmlink_thread = None
        self.warmlink_worker = None
        self._sync_owner_refs()

    def _sync_owner_refs(self) -> None:
        # Kompatibilitaet: Der alte Dialog-Code greift noch auf diese Attribute zu.
        self.owner.display_thread = self.display_thread
        self.owner.display_worker = self.display_worker
        self.owner.warmlink_thread = self.warmlink_thread
        self.owner.warmlink_worker = self.warmlink_worker
