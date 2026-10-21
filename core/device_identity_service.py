"""Asynchronous, narrowly scoped identity service state machine (issue #115)."""
from __future__ import annotations

import math
import time
from PySide6.QtCore import QObject, Signal, Slot, Qt

from core.device_identity import (
    SLAVE, READ_START, READ_QUANTITY, WRITE_START, identity_access_error,
    validate_wifi_identity, decode_wifi_identity, build_identity_write_payload,
    decode_identity_read_response, validate_identity_write_ack, verify_identity_readback,
    create_identity_backup, update_identity_backup, load_identity_backup, mask_wifi_identity,
)


class DeviceIdentityService(QObject):
    changed = Signal()
    TIMEOUT = 8.0

    def __init__(self, owner, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.owner, self.clock = owner, clock
        self.state, self.status = "idle", "Bereit"
        self.words = None
        self.target = ""
        self.payload = None
        self.preparation_revision = 0
        self.worker = None
        self.token = None
        self.deadline = None
        self.backup_path = None
        self.backup = None
        self.ack_ok = False
        self.immediate_ok = None
        self.reserve_ok = None
        self.persistence_ok = None
        self.persist_after = None
        self.written_worker = None
        self.disconnect_seen = False
        self.reconnected = False
        self._authorized_transport = False
        backend_selector = getattr(owner, "backend_combo", None)
        if backend_selector is not None:
            backend_selector.currentIndexChanged.connect(self._transport_changed)

    @property
    def busy(self):
        return self.state in {"reading", "preparing", "prewrite", "writing", "readback", "persistence"}

    @property
    def wait_seconds(self):
        return max(0, math.ceil(self.persist_after - self.clock())) if self.persist_after else 0

    def _set(self, state, status):
        self.state, self.status = state, status
        self.changed.emit()

    def _transport_changed(self):
        self._authorized_transport = not identity_access_error(self.owner)
        if self.token and not self._authorized_transport:
            self.fail("Transport geändert; Serviceablauf abgebrochen.")

    def _io_guard(self):
        # This final TX barrier executes in the I/O thread: no Qt widget reads.
        return (self._authorized_transport and
                self.owner.settings.get("show_engineering_parameters") is True and
                self.owner.connected and self.owner.worker is self.worker)

    def _guard(self):
        return not identity_access_error(self.owner) and self.owner._active_io_worker() is self.worker

    def _begin(self):
        error = identity_access_error(self.owner)
        if error:
            self._set("blocked", error)
            return False
        if self.wait_seconds:
            self.status = "Vor Neustart/Ausschalten noch mindestens 60 Sekunden ab Rückleseprüfung warten."
            self.changed.emit()
            return False
        if self.token:
            if self._guard():
                return True
            self.fail("Verbindung oder Engineering-Freischaltung geändert.")
            return False
        scheduler = getattr(self.owner, "warmlink_read_scheduler", None)
        if (getattr(self.owner, "pending_read_requests", []) or
                (scheduler and (scheduler.active or scheduler.queue or scheduler.resume_at > self.clock()))):
            self._set("blocked", "Bus beschäftigt; laufende Abfragen erst abschließen lassen.")
            return False
        self.worker = self.owner._active_io_worker()
        self._authorized_transport = True
        self.token = self.worker.begin_identity_service(self._io_guard)
        if not self.token:
            self.worker = None
            self._set("blocked", "Bus beschäftigt oder Senden gesperrt; später erneut vorbereiten.")
            return False
        self.worker.identity_event.connect(self._event, Qt.QueuedConnection)
        self.deadline = self.clock() + self.TIMEOUT
        return True

    def _release(self, abort=False):
        worker, token = self.worker, self.token
        self.token = None
        self.deadline = None
        if worker is not None and token:
            try:
                worker.identity_event.disconnect(self._event)
                worker.end_identity_service(token, abort=abort)
            except RuntimeError:  # The connection's worker may already have been deleted.
                pass
        self.worker = None

    def _read(self, state):
        self._set(state, "Frische FC03-Abfrage: Slave 0x63, 2001–2008")
        self.deadline = self.clock() + self.TIMEOUT
        if not self.worker.enqueue_read(READ_START, READ_QUANTITY, slave_addr=SLAVE, identity_token=self.token):
            self.fail("FC03 konnte nicht sicher vorgemerkt werden.")
            return False
        return True

    def read_current(self):
        if self.busy or not self._begin():
            return False
        return self._read("reading")

    def prepare(self, target):
        if self.busy or not validate_wifi_identity(target):
            self.status = "Ungültige ID; erforderlich: WF und zehn ASCII-Ziffern."
            self.changed.emit()
            return False
        if not self._begin():
            return False
        self.target, self.payload = target, None
        self.ack_ok, self.immediate_ok, self.reserve_ok, self.persistence_ok = False, None, None, None
        return self._read("preparing")

    def invalidate_preparation(self):
        if self.state == "prepared":
            self._release()
            self.payload = None
            self._set("idle", "Eingabe geändert; Änderung erneut vorbereiten.")

    def write(self, confirmation):
        if identity_access_error(self.owner):
            self.fail(identity_access_error(self.owner))
            return False
        if self.state != "prepared" or confirmation != self.target or not validate_wifi_identity(self.target):
            return False
        if not self._begin():
            return False
        # A second fresh read is mandatory even after a long confirmation pause.
        return self._read("prewrite")

    @Slot(str, str, object)
    def _event(self, token, kind, data):
        if token != self.token:
            return
        if not self._guard():
            self.fail("Transport oder Engineering-Freischaltung geändert; kein weiteres Schreiben.")
            return
        if kind == "error":
            self.fail("Service-Übertragung fehlgeschlagen; kein automatischer Wiederholungsversuch.")
        elif kind == "sent":
            self.deadline = self.clock() + self.TIMEOUT
            if data == "write_block":
                self.status = "FC10 gesendet; ACK und Rückleseprüfung stehen aus."
                self.changed.emit()
        elif kind == "ack" and self.state == "writing":
            if not validate_identity_write_ack(data):
                self.fail("FC10-ACK bestätigt nicht exakt Slave 0x63 / 7001 / 10.")
                return
            self.ack_ok = True
            self.backup["write_ack"] = True
            self._read("readback")
        elif kind == "read" and self.state in {"reading", "preparing", "prewrite", "readback", "persistence"}:
            try:
                words = decode_identity_read_response(data)
            except ValueError:
                self.fail("Keine vollständige, gültige frische Antwort für 2001–2008.")
                return
            phase = self.state
            previous = self.words
            self.words = words
            if phase == "reading":
                self._release()
                self._set("idle", "Aktuelle Mainboard-ID frisch gelesen.")
            elif phase in {"preparing", "prewrite"}:
                self.payload = build_identity_write_payload(self.target, *words[6:])
                if phase == "preparing" or words != previous:
                    self.preparation_revision += 1
                    self.deadline = None
                    self._set("prepared", "Payload bereit. Ziel-ID zur Bestätigung erneut eingeben." if phase == "preparing"
                              else "Werte haben sich geändert. Neues Payload prüfen und Ziel-ID erneut bestätigen.")
                    return
                # Back up the just-read authoritative block before the one write.
                try:
                    self.backup_path, self.backup = create_identity_backup(self.owner.user_data_dir, words, self.target)
                except (OSError, ValueError):
                    self.fail("Lokales sensibles Backup konnte nicht sicher gespeichert werden; kein Schreiben.")
                    return
                if not self._guard():
                    self.fail("Freischaltung oder Verbindung geändert; kein Schreiben.")
                    return
                self._set("writing", "FC10 vorgemerkt; noch keine Änderung bestätigt.")
                self.deadline = self.clock() + self.TIMEOUT
                if not self.worker.enqueue_write_block(WRITE_START, self.payload, slave_addr=SLAVE, identity_token=self.token):
                    self.fail("FC10 konnte nicht sicher vorgemerkt werden.")
            elif phase in {"readback", "persistence"}:
                valid = verify_identity_readback(words, self.backup["expected_id"], self.backup["reserved"])
                field = "immediate_readback" if phase == "readback" else "persistence_readback"
                self.backup[field] = {"ok": valid, "raw_2001_2008": words,
                                      "timestamp_monotonic": self.clock()}
                if phase == "readback":
                    self.reserve_ok = words[6:] == self.backup["reserved"]
                    self.immediate_ok = valid
                    # Even a failed RAM comparison may have written EEPROM data.
                    self.persist_after = self.clock() + 60
                    self.written_worker = self.worker
                    self.disconnect_seen = self.reconnected = False
                else:
                    self.persistence_ok = valid
                try:
                    update_identity_backup(self.backup_path, self.backup)
                except OSError:
                    self.fail("Prüfergebnis konnte nicht gespeichert werden; Backup vor Ort kontrollieren.")
                    return
                if not valid:
                    self.fail("Rückleseprüfung fehlgeschlagen: ID oder Reservewörter abweichend. Kein Retry.")
                    return
                self._release()
                if phase == "readback":
                    self.owner._log("Identity-Service: Änderung im RAM bestätigt: " + mask_wifi_identity(self.target))
                    self._set("ram_confirmed", "Änderung im Mainboard-RAM bestätigt. EEPROM-Persistenz noch ungeprüft.")
                else:
                    self._set("persisted", "Persistenz nach Neustart bestätigt (Neustart durch Benutzer bestätigt).")

    def verify_after_restart(self, restart_confirmed=False):
        # A reconnect alone does not prove a mainboard restart.
        if (self.busy or not self.backup or self.immediate_ok is not True or self.wait_seconds
                or not self.reconnected or restart_confirmed is not True or not self._begin()):
            return False
        self.backup["restart_confirmed_by_user"] = True
        return self._read("persistence")

    def restore_backup(self, path):
        if self.busy or identity_access_error(self.owner):
            return False
        try:
            record = load_identity_backup(path)
        except (OSError, ValueError, TypeError, KeyError):
            self.status = "Kein gültiges sensibles Identity-Backup mit wiederherstellbarer ID."
            self.changed.emit()
            return False
        # Only take the old ID; the old reserved words are NEVER used for writes.
        return self.prepare(record["old_id"])

    def tick(self):
        if self.token:
            if not self._guard():
                self.fail("Verbindung oder Engineering-Freischaltung verloren.")
            elif self.deadline is not None and self.clock() >= self.deadline:
                self.fail("Zeitüberschreitung; Verbindung zum Schutz vor verspäteten Antworten schließen. Kein Retry.")
        if self.written_worker is not None:
            current = self.owner._active_io_worker()
            if current is not self.written_worker:
                self.disconnect_seen = True
            if self.disconnect_seen and current is not None and current is not self.written_worker:
                self.reconnected = True

    def fail(self, message):
        if self.backup and self.state in {"writing", "readback", "persistence"}:
            self.backup["error"] = message
            try:
                update_identity_backup(self.backup_path, self.backup)
            except OSError:
                pass
        # A sent write with no valid readback is an uncertain outcome, never a retry.
        if self.state in {"writing", "readback"}:
            self.persist_after = self.clock() + 60
        self._release(abort=True)
        self.payload = None
        self._set("failed", message)

    def close(self):
        self._release(abort=self.busy)
