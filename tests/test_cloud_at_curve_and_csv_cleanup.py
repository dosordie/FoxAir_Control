import csv
import re
import time

import pytest

from cloud.register_resolver import current_register_definitions
from cloud.snapshot_request import CloudSnapshotRequest
from cloud.warmlink_codes import WARMLINK_644_DISCOVERY_CODES, cloud_hint, cloud_modbus_register
from core.at_compensation import AT_CLOUD_READ_CODES, AT_READ_BLOCKS
from core.csv_register_logger import CSV_HEADER, LEGACY_CSV_HEADER, CsvRegisterLogger, cloud_engineering_snapshot, logger_cloud_mappings
from core.foxair_phnix_core import DecodedRegister
from dialogs.cloud_dialog import WarmLinkCloudDialog
from workers import warmlink_cloud_worker as workers
from test_cloud_polling import fake_api, poll_worker
from test_cloud_app_heartbeat import scanned_session
from test_cloud_single_read_and_values import cloud_row
from test_csv_register_logger import LoggerOwner, read_csv, application
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window


@pytest.mark.parametrize(("code", "register"), [
    ("CP1-1", 1250), ("CP1-2", 1251), ("CP1-3", 1252), ("compensate_offset", 1235),
    ("CP1-5", 1253), ("CP1-6", 1254), ("CP1-7", 1255),
])
def test_zone1_curve_uses_confirmed_firmware_points_without_cloud_write_grants(code, register):
    assert code in WARMLINK_644_DISCOVERY_CODES
    assert cloud_modbus_register(code) == register
    assert cloud_hint(code)["confidence"] == "confirmed"
    assert cloud_hint(code)["write_allowed"] is False


def test_middle_alias_and_zone2_have_no_invented_projection():
    for code in ["CP1-4", *(f"CP2-{n}" for n in range(1, 8)), "Zone 2 Curve Offset"]:
        assert code in WARMLINK_644_DISCOVERY_CODES
        assert cloud_modbus_register(code) is None
        assert "modbus_register" not in cloud_hint(code)
        assert not cloud_hint(code)["write_allowed"]
    assert cloud_modbus_register("compensate_offset") == 1235


def test_family_full_scan_reads_all_fourteen_curve_codes_and_classifies_only_confirmed_points(fake_api):
    worker = workers.WarmLinkCloudWorker("user", "password", WARMLINK_644_DISCOVERY_CODES,
        device_code="device", initial_token="token", session=scanned_session(), poll_once=True, full_scan=True)
    worker.run()
    reads = [call[1] for call in fake_api.created[0].calls if isinstance(call, tuple) and call[0] == "read"]
    assert len(reads) == 1
    assert set(f"CP{zone}-{n}" for zone in (1, 2) for n in range(1, 8)) <= set(reads[0])
    assert "CP1-1" in worker.session.static_codes and "CP1-4" in worker.session.other_codes
    assert "CP2-1" in worker.session.other_codes and "Fault8" in worker.session.live_codes


@pytest.mark.parametrize(("value", "expected"), [(512, 512), (512.0, 512), ("512", 512), ("0000001000000000", 512), (10, 10), (-1, 65535)])
def test_csv_fault_numbers_are_unsigned_raw_words_without_scaling(value, expected, tmp_path):
    snapshot = cloud_engineering_snapshot([cloud_row(value, "Fault8")], logger_cloud_mappings(), current_register_definitions())
    assert snapshot == {2088: expected}
    path = tmp_path / "fault.csv"
    writer = CsvRegisterLogger()
    writer.open(path)
    writer.append("now", "cloud", "GL9", snapshot)
    writer.close()
    assert read_csv(path)[1][list(CSV_HEADER).index("2088")] == str(expected)
    assert read_csv(path)[1][list(CSV_HEADER).index("2087")] == ""


@pytest.mark.parametrize("flag", ["stale", "cached", "currentEmpty"])
def test_csv_never_reuses_cached_faults(flag):
    assert cloud_engineering_snapshot([cloud_row(512, "Fault8", **{flag: True})], logger_cloud_mappings(), current_register_definitions()) == {}


def test_legacy_header_and_old_iso_row_remain_intact_when_appending(tmp_path):
    path = tmp_path / "legacy.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(LEGACY_CSV_HEADER)
        writer.writerow(["2026-10-06T10:29:18+02:00", "cloud", "GL9", *("" for _ in range(90))])
    before = path.read_bytes()
    logger = CsvRegisterLogger()
    logger.open(path)
    logger.append("2026-10-06 11:00:00", "cloud", "GL9", {2088: 512})
    logger.close()
    assert path.read_bytes().startswith(before)
    assert len(read_csv(path)) == 3
    assert read_csv(path)[0] == list(LEGACY_CSV_HEADER)


def test_controller_writes_excel_timestamp_and_new_header(application, tmp_path):
    owner = LoggerOwner(connected=False)
    logger = owner.csv_logger_controller
    path = tmp_path / "timestamp.csv"
    logger.start(path, 30)
    logger.cloud_response(logger.active_cycle, [cloud_row(512, "Fault8")])
    logger.stop()
    rows = read_csv(path)
    assert rows[0][3:] == [str(n) for n in range(2001, 2091)]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", rows[1][0])
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def cloud_only(window):
    window.connected, window.worker = False, None
    window.settings["warmlink_cloud"].update(username="user", selected_device_code="device", save_token=False)
    window.cloud_credentials_cache = {"token": "token", "token_user": "user", "password": "password",
                                     "password_user": "user", "session_password": "password"}
    window.cloud_session = scanned_session()
    window.set_cloud_connection_state(True, "device")


def open_at(window):
    window.open_at_compensation()
    dialog = window.at_comp_dialog
    dialog.initial_read_timer.stop()
    return dialog


@pytest.mark.parametrize("backend", ["warmlink_raw", "display_modbus"])
def test_cloud_only_at_displays_engineering_values_and_receives_live_updates_without_fake_local_words(window, monkeypatch, backend):
    cloud_only(window)
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend))
    window.backend_combo.blockSignals(False)
    monkeypatch.setattr(window, "_display_wait_for_param_blocks_before_popup", lambda *a, **kw: pytest.fail("No Display fake for Cloud-only"))
    monkeypatch.setattr(window, "send_read_request", lambda *a, **kw: pytest.fail("No local Cloud-only read"))
    window.apply_cloud_rows_to_main([cloud_row(2, "H36"), cloud_row(1.5, "compensate_slope"), cloud_row(44.3, "compensate_offset"),
                                    cloud_row(54.2, "CP1-1"), cloud_row(-5.4, "T04"), cloud_row(41.2, "2014")])
    dialog = open_at(window)
    assert dialog.mode_combo.currentData() == 2
    assert dialog.slope_spin.value() == 1.5 and dialog.offset_spin.value() == 44.3
    assert dialog._seven_spins()[0].value() == 54.2 and dialog._seven_spins()[3].value() == 44.3
    assert dialog._temp(2048) == -5.4 and dialog._temp(2014) == 41.2
    assert window.last_values == {}
    assert window.register_value_sources(1250).local_raw is None
    assert window.latest_regs[1250].value_source == "cloud"
    window.apply_cloud_rows_to_main([cloud_row(48.6, "CP1-1"), cloud_row(99, "CP1-4")])
    assert dialog._seven_spins()[0].value() == 48.6 and dialog._seven_spins()[3].value() == 44.3
    assert "CP1-4" not in {info["code"] for info in window.cloud_overlay_by_reg.values()}
    dialog.close()


def test_at_local_values_and_transport_keep_priority_and_local_writes(window, monkeypatch):
    window.apply_cloud_rows_to_main([cloud_row(54.2, "CP1-1")])
    local = DecodedRegister(0x63, 1250, 0, 3, 453, 453, "45.3 °C", "", "TEMP1", time.time())
    window.latest_regs[1250], window.last_values[1250] = local, 453
    dialog = open_at(window)
    assert dialog._seven_spins()[0].value() == 45.3
    reads, writes = [], []
    monkeypatch.setattr(window, "send_read_request", lambda addr, qty, **kw: reads.append((addr, qty)))
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda req: pytest.fail("Local takes priority"))
    dialog.read_from_wp()
    assert reads == list(AT_READ_BLOCKS)
    monkeypatch.setattr(window, "send_register_write", lambda *args, **kw: writes.append(args))
    monkeypatch.setattr("foxair_phnix_control.ask_yes_no", lambda *a, **kw: True)
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData(2))
    assert dialog.write_seven_btn.isEnabled()
    dialog.write_seven_points()
    assert [item[0] for item in writes] == [1250, 1251, 1252, 1235, 1253, 1254, 1255]
    assert window.latest_regs[1250] is local and window.last_values[1250] == 453
    dialog.close()


def test_at_cloud_only_guard_blocks_all_local_writes_and_updates_on_disconnect(window, monkeypatch):
    cloud_only(window)
    dialog = open_at(window)
    monkeypatch.setattr(window, "send_register_write", lambda *a, **kw: pytest.fail("Cloud-only must never write locally"))
    monkeypatch.setattr("foxair_phnix_control.ask_yes_no", lambda *a, **kw: pytest.fail("No unavailable write confirmation"))
    for mode in (0, 1, 2):
        dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData(mode))
        assert not any(btn.isEnabled() for btn in (dialog.write_mode_btn, dialog.write_linear_btn, dialog.write_seven_btn))
        dialog.write_mode(); dialog.write_linear_params(); dialog.write_seven_points()
    window.set_cloud_connection_state(False)
    assert not dialog.write_mode_btn.isEnabled()
    dialog.close()


@pytest.mark.parametrize("loss", ["close", "timeout", "device"])
def test_at_targeted_read_is_cycle_bound_cancelled_and_never_accepts_late_response(window, monkeypatch, loss):
    cloud_only(window)
    reads = []
    monkeypatch.setattr(window, "request_cloud_snapshot", lambda req: reads.append(req))
    dialog = open_at(window)
    dialog.read_from_wp(); dialog.read_from_wp()
    assert len(reads) == 1 and reads[0].codes == AT_CLOUD_READ_CODES
    req = reads[0]
    dialog.cloud_read_finished(req.cycle_id + 1, [cloud_row(55, "CP1-1")], "")
    assert 1250 not in window.cloud_overlay_by_reg
    if loss == "close":
        dialog.close()
    elif loss == "timeout":
        dialog._cloud_read_timeout()
    else:
        window.set_cloud_connection_state(True, "other-device")
    assert req.cancelled.is_set()
    dialog.cloud_read_finished(req.cycle_id, [cloud_row(55, "CP1-1")], "")
    assert 1250 not in window.cloud_overlay_by_reg
    dialog.close()


def test_targeted_curve_request_is_serialized_and_routed_separately_from_csv(fake_api):
    worker = poll_worker(session=scanned_session(), poll_once=True,
        logger_request=CloudSnapshotRequest(1, AT_CLOUD_READ_CODES, time.monotonic() + 60, "user", "device", purpose="at_compensation"))
    targeted, csv_results = [], []
    worker.targeted_snapshot.connect(lambda *args: targeted.append(args))
    worker.logger_snapshot.connect(lambda *args: csv_results.append(args))
    worker.run()
    assert len(fake_api.created) == 1
    assert fake_api.created[0].calls == ["heartbeat", ("read", list(AT_CLOUD_READ_CODES))]
    assert targeted[0][0:2] == ("at_compensation", 1) and not targeted[0][3]
    assert not csv_results


def test_at_and_csv_can_share_cycle_number_and_one_worker_without_cross_routing(fake_api):
    worker = poll_worker(session=scanned_session(), poll_once=True,
        logger_request=CloudSnapshotRequest(1, AT_CLOUD_READ_CODES, time.monotonic() + 60, "user", "device", purpose="at_compensation"))
    worker.request_logger_snapshot(CloudSnapshotRequest(1, ("T04", "Fault8"), time.monotonic() + 60, "user", "device"))
    targeted, csv_results = [], []
    worker.targeted_snapshot.connect(lambda *args: targeted.append(args))
    worker.logger_snapshot.connect(lambda *args: csv_results.append(args))
    worker.run()
    assert len(fake_api.created) == 1
    assert fake_api.created[0].calls == ["heartbeat", ("read", list(AT_CLOUD_READ_CODES)), "heartbeat", ("read", ["T04", "Fault8"])]
    assert len(targeted) == len(csv_results) == 1
    assert targeted[0][1] == csv_results[0][0] == 1
    assert {row["code"] for row in csv_results[0][1]} == {"T04", "Fault8"}


@pytest.mark.parametrize("polling", [False, True])
def test_at_targeted_read_uses_real_existing_cloud_dialog_worker_without_full_scan(window, fake_api, monkeypatch, polling):
    cloud_only(window)
    monkeypatch.setattr(workers, "load_cloud_credentials", lambda user, pw, token, **kw: (pw, token))
    cloud = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    cloud.codes_edit.setPlainText("\n".join(window.cloud_session.candidates))
    monkeypatch.setattr(window, "send_read_request", lambda *a, **kw: pytest.fail("No local read"))
    existing_worker = None
    try:
        if polling:
            cloud._start_worker(False)
            wait_for(lambda: fake_api.created and "status" in fake_api.created[0].calls)
            existing_worker = cloud.cloud_worker
        dialog = open_at(window)
        dialog.read_from_wp()
        if polling:
            assert cloud.cloud_worker is existing_worker
        wait_for(lambda: dialog.cloud_request is None)
        assert 1250 in window.cloud_overlay_by_reg and window.register_value_sources(1250).cloud_engineering is not None
        assert window.last_values == {}
        reads = [call[1] for call in fake_api.created[0].calls if isinstance(call, tuple) and call[0] == "read"]
        assert reads == ([["T04"]] if polling else []) + [list(AT_CLOUD_READ_CODES)]
        assert len(fake_api.created) == 1
        dialog.close()
        if polling:
            assert cloud.cloud_worker is existing_worker and not existing_worker._stop_event.is_set()
    finally:
        if window.at_comp_dialog is not None:
            window.at_comp_dialog.close()
        cloud.stop_worker()
        wait_for(lambda: cloud.cloud_thread is None)
