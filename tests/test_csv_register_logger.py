import csv
import os
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtCore import QObject

from cloud.register_resolver import current_register_definitions
from core.csv_register_logger import (
    CSV_HEADER, LIVE_REGISTERS, CsvRegisterLogger, cloud_engineering_snapshot,
    csv_number, local_engineering_value, logger_cloud_mappings,
)
from core.csv_logger_controller import CsvLoggerController
from core.foxair_phnix_core import DecodedRegister, RegisterMap
from core.settings_manager import ensure_defaults
from dialogs.csv_logger_dialog import CsvLoggerDialog
from test_cloud_single_read_and_values import application


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.reader(file, delimiter=";"))


def reg(number, raw=453, dtype="TEMP1", timestamp=None):
    return DecodedRegister(0x63, number, 0, 2001, raw, raw, "not parsed", "", dtype,
                           time.time() if timestamp is None else timestamp)


@pytest.mark.parametrize("initial", ["new", "empty", "compatible"])
def test_header_once_append_utf8_and_ninety_numeric_columns(tmp_path, initial):
    path = tmp_path / "values.csv"
    if initial == "empty":
        path.touch()
    elif initial == "compatible":
        with path.open("w", encoding="utf-8", newline="") as file:
            csv.writer(file, delimiter=";").writerow(CSV_HEADER)
    writer = CsvRegisterLogger()
    writer.open(path)
    writer.append("first", "cloud", "Gerät Küche", {2048: 45.3, 2034: 4096, 2001: 0})
    writer.close()
    writer.open(path)
    writer.append("second", "standard_modbus", "GL9", {2090: 17})
    writer.close()
    rows = read_csv(path)
    assert rows[0] == list(CSV_HEADER)
    assert rows[0][3:] == [f"R{n}" for n in range(2001, 2091)]
    assert len(rows) == 3 and all(len(row) == 93 for row in rows)
    assert rows[1][2] == "Gerät Küche" and rows[1][3] == "0"
    assert rows[1][rows[0].index("R2048")] == "45.3"
    assert rows[1][rows[0].index("R2034")] == "4096"
    assert rows[1][rows[0].index("R2078")] == ""
    assert rows[2][-1] == "17" and rows[2][rows[0].index("R2048")] == ""
    assert "°C" not in path.read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("header", ["timestamp,source,device,R2001", "wrong;header", "\n"])
def test_incompatible_file_is_not_modified(tmp_path, header):
    path = tmp_path / "wrong.csv"
    path.write_text(header, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        CsvRegisterLogger().open(path)
    assert path.read_bytes() == before


def test_compatible_header_without_final_newline(tmp_path):
    path = tmp_path / "header.csv"
    path.write_text(";".join(CSV_HEADER), encoding="utf-8")
    writer = CsvRegisterLogger()
    writer.open(path)
    writer.append("now", "cloud", "GL9", {})
    writer.close()
    assert len(read_csv(path)) == 2


@pytest.mark.parametrize("value", [None, "cached text", float("nan"), float("inf"), float("-inf")])
def test_non_numeric_and_nonfinite_values_remain_empty(value):
    assert csv_number(value) == ""


def test_local_engineering_uses_existing_decoder_and_unsigned_bit_words():
    regmap = RegisterMap(str(Path(__file__).parents[1] / "data/foxair_phnix_registers.json"))
    assert local_engineering_value(reg(2048), regmap) == 45.3
    assert local_engineering_value(reg(2048, 0xFFF6), regmap) == -1
    assert local_engineering_value(reg(2034, 0xFFFF, "BITFIELD"), regmap) == 65535
    assert local_engineering_value(reg(2048, 1234, "DIGI5"), regmap) == 123.4


def test_only_current_confirmed_catalogue_cloud_codes_and_no_guessed_faults():
    mappings = logger_cloud_mappings()
    assert mappings["T04"] == 2048 and mappings["S01~S10"] == 2034
    assert mappings["2014"] == 2014  # actual reviewed alias, not generated from addresses
    assert all(2001 <= n <= 2090 for n in mappings.values())
    assert "2078" not in mappings and "R02" not in mappings and "F23" not in mappings
    assert not {f"Fault{n}" for n in range(1, 11)}.intersection(mappings)
    assert not set(range(2081, 2091)).intersection(mappings.values())
    custom = {"2078": {"code": "T04"}, "2081": {"code": "Fault1"}}
    assert logger_cloud_mappings(custom) == {"T04": 2078}


def test_cloud_snapshot_uses_only_fresh_response_and_keeps_engineering_scale():
    definitions = current_register_definitions()
    mappings = logger_cloud_mappings(definitions)
    rows = [
        {"code": "T04", "value": "45.3", "supported": True},
        {"code": "S01~S10", "value": "1000000000000000", "dataType": "BINARY", "supported": True},
        {"code": "T03", "value": 88, "supported": True, "stale": True},
        {"code": "T05", "value": 88, "supported": True, "cached": True},
        {"code": "T01", "value": 88, "supported": False},
        {"code": "T02", "value": 88, "supported": True, "currentEmpty": True},
        {"code": "R02", "value": 55, "supported": True},
        {"code": "Fault1", "value": 17, "supported": True},
    ]
    snapshot = cloud_engineering_snapshot(rows, mappings, definitions)
    assert snapshot == {2048: 45.3, 2034: 32768}


class LoggerOwner(QObject):
    def __init__(self, backend="warmlink_raw", connected=True, cloud=True):
        super().__init__()
        self.backend, self.connected, self.cloud = backend, connected, cloud
        self.io_worker = object()
        self.cloud_session_device_code = "device"
        self.settings = {"warmlink_cloud": {"username": "user"}, "csv_logger": {"interval_s": 30}}
        self.cloud_session = SimpleNamespace(devices=[{"deviceCode": "device", "deviceNickName": "GL9 Küche"}])
        self.register_defs = current_register_definitions()
        self.regmap = RegisterMap(str(Path(__file__).parents[1] / "data/foxair_phnix_registers.json"))
        self.pending_read_requests, self.local_calls, self.cloud_calls, self.logs = [], [], [], []
        self.csv_logger_controller = CsvLoggerController(self)
        self.saved = 0
        self.capture = False
        self.unit = 0x63
        self.user_data_dir = "."

    def current_backend_key(self): return self.backend
    def current_device_model(self): return "GL9"
    def _active_io_worker(self): return self.io_worker if self.connected else None
    def is_cloud_connected(self): return self.cloud and bool(self.cloud_session_device_code)
    def _wire_slave_addr(self, _requested): return self.unit
    def _is_firmware_capture_mode(self): return self.capture
    def _log(self, text, **kwargs): self.logs.append((text, kwargs))
    def _save_settings(self, **kwargs): self.saved += 1
    def request_csv_cloud_snapshot(self, request): self.cloud_calls.append(request)
    def send_read_request(self, start, qty, **kwargs):
        request = {"addr": start, "quantity": qty, **kwargs}
        self.local_calls.append(request)
        return request


@pytest.mark.parametrize("backend", ["standard_modbus", "warmlink_raw"])
def test_local_priority_and_exact_read_per_interval_with_async_fresh_snapshot(application, tmp_path, backend):
    owner = LoggerOwner(backend)
    logger = owner.csv_logger_controller
    path = tmp_path / "local.csv"
    logger.start(path, 30)
    assert owner.local_calls[0]["addr"] == 2001 and owner.local_calls[0]["quantity"] == 90
    assert owner.cloud_calls == [] and len(read_csv(path)) == 1
    logger.interval_timer.timeout.emit()  # pending cycle cannot issue a concurrent read
    assert len(owner.local_calls) == 1
    fresh = [reg(n, n, "UINT16") for n in LIVE_REGISTERS]
    logger.local_response(logger.local_request, fresh)
    assert len(read_csv(path)) == 2 and logger.last_success
    logger.interval_timer.timeout.emit()
    assert len(owner.local_calls) == 2
    logger.stop()
    assert owner.connected and owner.io_worker is not None and owner.cloud


def test_partial_timeout_excludes_old_generation_and_cached_values(application, tmp_path):
    owner = LoggerOwner()
    logger = owner.csv_logger_controller
    path = tmp_path / "partial.csv"
    logger.start(path, 5)
    old_request = dict(logger.local_request)
    logger.local_response(old_request, [reg(2048)])  # same fields, different request identity
    assert logger.snapshot == {}
    logger.local_response(logger.local_request, [reg(2048, timestamp=logger.started_wall - 1), reg(2034, 4096, "BITFIELD")])
    assert logger.snapshot == {2034: 4096} and len(read_csv(path)) == 1
    logger.cycle_timeout()
    rows = read_csv(path)
    assert rows[1][rows[0].index("R2034")] == "4096"
    assert rows[1][rows[0].index("R2048")] == "" and not logger.last_success
    logger.interval_timer.timeout.emit()
    logger.cycle_timeout()
    assert all(value == "" for value in read_csv(path)[2][3:])
    assert logger.running  # a lost cycle does not stop the logger
    logger.stop()


def test_old_pending_qty90_is_not_relabelled_or_joined(application, tmp_path):
    owner = LoggerOwner()
    old = {"addr": 2001, "quantity": 90, "label": "background"}
    owner.pending_read_requests.append(old)
    logger = owner.csv_logger_controller
    logger.start(tmp_path / "pending.csv", 30)
    assert owner.local_calls == []
    logger.local_response(old, [reg(n) for n in LIVE_REGISTERS])
    assert logger.snapshot == {}
    owner.pending_read_requests.clear()
    logger.local_wait_timer.timeout.emit()
    assert len(owner.local_calls) == 1 and logger.local_request is owner.local_calls[0]
    logger.stop()


@pytest.mark.parametrize("loss", ["disconnect", "worker", "backend", "unit"])
def test_local_source_is_fixed_and_loss_never_switches_to_cloud(application, tmp_path, loss):
    owner = LoggerOwner()
    logger = owner.csv_logger_controller
    logger.start(tmp_path / "loss.csv", 30)
    if loss == "disconnect": owner.connected = False
    if loss == "worker": owner.io_worker = object()
    if loss == "backend": owner.backend = "standard_modbus"
    if loss == "unit": owner.unit = 1
    logger.source_changed()
    assert not logger.running and logger.source == "warmlink_raw" and owner.cloud_calls == []
    logger.interval_timer.timeout.emit()
    assert len(owner.local_calls) == 1


def test_cloud_source_and_own_interval_use_only_response_of_matching_cycle(application, tmp_path):
    owner = LoggerOwner(connected=False)
    logger = owner.csv_logger_controller
    path = tmp_path / "cloud.csv"
    logger.start(path, 60)
    request = owner.cloud_calls[-1]
    assert request.username == "user" and request.device_code == "device"
    assert request.codes == tuple(logger_cloud_mappings()) and owner.local_calls == []
    logger.cloud_response(request.cycle_id + 1, [{"code": "T04", "supported": True, "value": 99}])
    assert len(read_csv(path)) == 1
    logger.cloud_response(request.cycle_id, [{"code": "T04", "supported": True, "value": 45.3}])
    assert len(read_csv(path)) == 2
    assert not any(not kwargs.get("level") for text, kwargs in owner.logs if "Snapshot teilweise" in text)
    owner.connected = True  # connecting locally does not silently change an ongoing Cloud recording
    logger.interval_timer.timeout.emit()
    assert len(owner.cloud_calls) == 2 and owner.local_calls == []
    logger.cloud_response(request.cycle_id, [{"code": "T04", "supported": True, "value": 99}])
    logger.cloud_response(owner.cloud_calls[-1].cycle_id, [{"code": "T04", "supported": False, "value": None}])
    rows = read_csv(path)
    assert rows[1][rows[0].index("R2048")] == "45.3"
    assert rows[2][rows[0].index("R2048")] == ""
    logger.stop()
    assert owner.cloud and owner.cloud_calls[-1].cancelled.is_set()


@pytest.mark.parametrize("loss", ["auth", "device", "account"])
def test_cloud_loss_or_device_change_stops_without_source_fallback(application, tmp_path, loss):
    owner = LoggerOwner(connected=False)
    logger = owner.csv_logger_controller
    logger.start(tmp_path / "cloudloss.csv", 30)
    request = owner.cloud_calls[-1]
    if loss == "auth": owner.cloud = False
    if loss == "device": owner.cloud_session_device_code = "other"
    if loss == "account": owner.settings["warmlink_cloud"]["username"] = "other"
    owner.connected = True
    logger.source_changed()
    assert not logger.running and logger.source == "cloud" and owner.local_calls == []
    assert request.cancelled.is_set()


@pytest.mark.parametrize("mode", ["no_connection", "display", "capture"])
def test_start_validation_does_not_create_a_file_or_request(application, tmp_path, mode):
    owner = LoggerOwner()
    if mode == "no_connection": owner.connected = owner.cloud = False
    if mode == "display": owner.backend = "display_modbus"
    if mode == "capture": owner.capture = True
    path = tmp_path / "invalid.csv"
    with pytest.raises(ValueError):
        owner.csv_logger_controller.start(path, 30)
    assert not path.exists() and owner.local_calls == owner.cloud_calls == []


def test_stop_cancels_only_recording_and_ignores_late_response(application, tmp_path):
    owner = LoggerOwner(connected=False)
    logger = owner.csv_logger_controller
    path = tmp_path / "stop.csv"
    logger.start(path, 30)
    request = owner.cloud_calls[-1]
    logger.stop()
    assert not logger.interval_timer.isActive() and logger.writer.file is None
    logger.cloud_response(request.cycle_id, [{"code": "T04", "value": 12, "supported": True}])
    assert len(read_csv(path)) == 1 and owner.cloud


def test_disk_error_stops_recording_without_closing_transport(application, tmp_path, monkeypatch):
    owner = LoggerOwner()
    logger = owner.csv_logger_controller
    logger.start(tmp_path / "disk.csv", 30)
    monkeypatch.setattr(logger.writer, "append", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    logger.cycle_timeout()
    assert not logger.running and logger.writer.file is None and owner.connected
    assert "disk full" in logger.status


def test_logger_settings_default_bounds_and_no_autostart():
    assert ensure_defaults({})["csv_logger"] == {"interval_s": 30, "last_directory": ""}
    for given, expected in [(1, 5), (5000, 3600), ("broken", 30)]:
        assert ensure_defaults({"csv_logger": {"interval_s": given}})["csv_logger"]["interval_s"] == expected


def test_dialog_persists_interval_and_closing_stops_only_logger(application, tmp_path):
    # QDialog needs a QWidget parent; reuse a small actual GUI test window.
    from test_cloud_polling import DialogWindow
    window = DialogWindow()
    window.connected = False
    window.cloud_session_device_code = "device"
    window.csv_logger_controller = CsvLoggerController(window)
    window.cloud_write_thread = None
    window.request_csv_cloud_snapshot = lambda request: None
    dialog = CsvLoggerDialog(window)
    assert not window.csv_logger_controller.running
    dialog.interval_spin.setValue(60)
    path = tmp_path / "ui.csv"
    dialog.path_edit.setText(str(path))
    dialog.start_button.click()
    assert window.csv_logger_controller.running and not dialog.start_button.isEnabled()
    assert window.settings["csv_logger"]["interval_s"] == 60
    assert window.settings["csv_logger"]["last_directory"] == str(tmp_path)
    dialog.stop_button.click()
    assert not window.csv_logger_controller.running and window.is_cloud_connected()
    dialog.close()
