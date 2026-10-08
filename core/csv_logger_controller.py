"""GUI-thread CSV scheduling; reads use the owner's existing local/Cloud paths."""
from __future__ import annotations

from datetime import datetime
import time

from PySide6.QtCore import QObject, QTimer, Signal

from cloud.logger_snapshot import CloudLoggerSnapshotRequest
from core.foxair_phnix_core import DEFAULT_BUS_ADDR
from core.csv_register_logger import (
    CsvRegisterLogger, LIVE_REGISTERS, cloud_engineering_snapshot,
    local_engineering_value, logger_cloud_mappings, csv_number,
)

SOURCE_NAMES = {"standard_modbus": "Standard-Modbus", "warmlink_raw": "Warmlink-Modbus", "cloud": "WarmLink Cloud"}


class CsvLoggerController(QObject):
    changed = Signal()

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.writer = CsvRegisterLogger()
        self.running = False
        self.source = ""
        self.device = ""
        self.identity = None
        self.status = "Bereit"
        self.last_success = ""
        self.cycle_id = 0
        self.active_cycle = None
        self.local_request = None
        self.cloud_request = None
        self.snapshot = {}
        self.interval_timer = QTimer(self)
        self.interval_timer.timeout.connect(self.begin_cycle)
        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.cycle_timeout)
        self.local_wait_timer = QTimer(self)
        self.local_wait_timer.setInterval(100)
        self.local_wait_timer.timeout.connect(self._request_local)

    def available_source(self):
        owner = self.owner
        if getattr(owner, "connected", False):
            backend = owner.current_backend_key()
            if backend not in ("standard_modbus", "warmlink_raw"):
                raise ValueError("CSV Logger ist für Display-Modbus derzeit nicht verfügbar; der direkte Liveblock-Read ist nicht bestätigt.")
            if owner._active_io_worker() is None:
                raise ValueError("Keine aktive lokale Geräteverbindung.")
            return backend, owner._active_io_worker()
        if owner.is_cloud_connected():
            cfg = owner.settings.get("warmlink_cloud", {})
            return "cloud", (str(cfg.get("username") or "").strip(), owner.cloud_session_device_code)
        raise ValueError("Keine lokale oder gültige WarmLink-Cloud-Verbindung mit ausgewähltem Gerät.")

    def _source_matches(self):
        owner = self.owner
        if owner._is_firmware_capture_mode():
            return False
        if self.source == "cloud":
            cfg = owner.settings.get("warmlink_cloud", {})
            return owner.is_cloud_connected() and self.identity == (
                str(cfg.get("username") or "").strip(), owner.cloud_session_device_code)
        return (getattr(owner, "connected", False) and owner.current_backend_key() == self.source
                and owner._active_io_worker() is self.identity and owner._wire_slave_addr(DEFAULT_BUS_ADDR) == self.unit_id)

    def start(self, path, interval_s):
        if self.running:
            raise ValueError("CSV Logger läuft bereits.")
        if not str(path).strip():
            raise ValueError("Bitte eine CSV-Datei wählen.")
        if not 5 <= int(interval_s) <= 3600:
            raise ValueError("Logging-Intervall muss zwischen 5 und 3600 Sekunden liegen.")
        if self.owner._is_firmware_capture_mode():
            raise ValueError("Firmware-Capture aktiv – aktive Logger-Abfragen sind gesperrt.")
        source, identity = self.available_source()
        if source == "cloud":
            mappings = logger_cloud_mappings(self.owner.register_defs)
            if not mappings:
                raise ValueError("Keine bestätigten Cloudcodes für Register 2001–2090 vorhanden.")
            self.mappings = mappings
            devices = self.owner.cloud_session.devices
            device = next((dev for dev in devices if dev.get("deviceCode") == identity[1]), {})
            name = str(device.get("deviceNickName") or device.get("deviceName") or device.get("model") or identity[1])
        else:
            self.unit_id = self.owner._wire_slave_addr(DEFAULT_BUS_ADDR)
            name = self.owner.current_device_model() or "PHNIX"
        self.writer.open(path)
        self.source, self.identity, self.device = source, identity, name
        self.last_success = ""
        self.running = True
        self.status = "Gestartet"
        self.owner._log(f"CSV Logger gestartet: Quelle={SOURCE_NAMES[source]}, Intervall={interval_s} s, Datei={path}")
        self.interval_timer.start(int(interval_s) * 1000)
        self.begin_cycle()

    def stop(self, status="Gestoppt"):
        was_running = self.running
        self.running = False
        self.interval_timer.stop()
        self._cancel_cycle()
        try:
            self.writer.close()
        except OSError as exc:
            status = f"Dateifehler: {exc}"
        self.status = status
        if was_running:
            self.owner._log(f"CSV Logger gestoppt: {self.writer.rows_written} Datensätze geschrieben")
        self.changed.emit()

    def _cancel_cycle(self):
        self.timeout_timer.stop()
        self.local_wait_timer.stop()
        if self.cloud_request is not None:
            self.cloud_request.cancelled.set()
        if self.local_request is not None:
            scheduler = getattr(self.owner, "warmlink_read_scheduler", None)
            if scheduler is not None:
                scheduler.cancel_labels({self.local_request.get("label", "")})
        self.active_cycle = self.local_request = self.cloud_request = None

    def source_changed(self):
        if not self.running:
            self.changed.emit()
            return
        if self.running and not self._source_matches():
            if self.active_cycle is not None:
                self._finish_cycle("Verbindung verloren", check_source=False)
            self.stop("Verbindung verloren – bitte stoppen/neu starten")

    def begin_cycle(self):
        if not self.running:
            return
        self.source_changed()
        if not self.running or self.active_cycle is not None:
            return  # A slow cycle never creates overlapping requests or a backlog.
        self.cycle_id += 1
        self.active_cycle = self.cycle_id
        self.started_at = time.monotonic()
        self.started_wall = time.time()
        self.snapshot = {}
        self.status = "Snapshot wird gelesen"
        self.timeout_timer.start(60000 if self.source == "cloud" else 15000)
        try:
            if self.source == "cloud":
                self.cloud_request = CloudLoggerSnapshotRequest(self.cycle_id, tuple(self.mappings),
                    self.started_at + 60, self.identity[0], self.identity[1])
                error = self.owner.request_csv_cloud_snapshot(self.cloud_request)
                if error:
                    self._finish_cycle(error)
            else:
                self.local_wait_timer.start()
                self._request_local()
        except Exception as exc:
            self._finish_cycle(str(exc))
        self.changed.emit()

    def _request_local(self):
        if not self.running or self.active_cycle is None or self.local_request is not None:
            return
        self.source_changed()
        if not self.running:
            return
        # Wait for old indistinguishable Qty90 reads. Do not join an older generation.
        if any(req.get("quantity") == 90 for req in getattr(self.owner, "pending_read_requests", [])):
            return
        scheduler = getattr(self.owner, "warmlink_read_scheduler", None)
        if scheduler and any(req.get("quantity") == 90 for _, _, req in scheduler.queue):
            return
        label = f"CSV Logger {self.active_cycle}"
        try:
            request = self.owner.send_read_request(2001, 90, slave_addr=self.unit_id, label=label, priority="background")
        except Exception as exc:
            self._finish_cycle(str(exc))
            return
        if request is not None and request.get("label") == label:
            self.local_request = request
            self.local_wait_timer.stop()

    def local_response(self, request, registers, received_at=None):
        if self.active_cycle is None or request is not self.local_request or self.source == "cloud":
            return
        if received_at is not None and received_at < self.started_at:
            return
        for register in registers:
            if register.reg in LIVE_REGISTERS and register.timestamp >= self.started_wall and getattr(register, "value_source", "local") != "cloud":
                value = local_engineering_value(register, self.owner.regmap)
                if csv_number(value) != "":
                    self.snapshot[register.reg] = value
        if len(self.snapshot) == 90:
            self._finish_cycle()
        else:
            self.status = f"Teilantwort: {len(self.snapshot)}/90 Werte · warte auf Timeout"
            self.changed.emit()

    def cloud_response(self, cycle_id, rows, error=""):
        if self.active_cycle != cycle_id or self.source != "cloud":
            return
        self.snapshot = cloud_engineering_snapshot(rows, self.mappings, self.owner.register_defs)
        self._finish_cycle(error)

    def cycle_timeout(self):
        if self.active_cycle is not None:
            self._finish_cycle("Timeout")

    def _finish_cycle(self, error="", *, check_source=True):
        if check_source and not self._source_matches():
            self.source_changed()
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = len(self.snapshot)
        try:
            self.writer.append(timestamp, self.source, self.device, self.snapshot)
        except (OSError, ValueError) as exc:
            self.stop(f"Dateifehler: {exc}")
            return
        self._cancel_cycle()
        self.status = f"{count}/90 Werte" + (f" · {error}" if error else "")
        if count and not error:
            self.last_success = timestamp
        if error or (self.source != "cloud" and count < 90):
            self.owner._log(f"CSV Logger: Snapshot teilweise, {count}/90 Werte" + (f" ({error})" if error else ""))
        else:
            self.owner._log(f"CSV Logger: Datensatz {self.writer.rows_written} geschrieben", level=7)
        self.changed.emit()
