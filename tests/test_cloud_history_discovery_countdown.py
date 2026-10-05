"""Cloud history, session lifetime, discovery isolation and worker-owned timing."""
import time
from copy import deepcopy

import pytest
from PySide6.QtCore import QEventLoop, QTimer

import foxair_phnix_control as gui
from cloud.known_devices import merge_device_sources
from cloud.polling import CloudSession, CloudTimingState
from cloud.warmlink_api import WarmLinkCloudError, normalize_house_devices
from cloud.warmlink_codes import cloud_modbus_register
from core.foxair_phnix_core import DecodedRegister
from dialogs.cloud_dialog import WarmLinkCloudDialog
from dialogs.cloud_table_helpers import device_table_value
from workers import warmlink_cloud_worker as workers
from test_cloud_single_read_and_values import CloudWindow, application, cloud_row
from test_cloud_polling import DialogWindow, fake_api, poll_worker, run_cycles, success


def test_cloud_only_history_uses_engineering_values_and_shared_flash(application, monkeypatch):
    window = CloudWindow()
    flashes = []
    monkeypatch.setattr(window, "flash_register_row", flashes.append)
    register = cloud_modbus_register("T04")
    window.apply_cloud_rows_to_main([cloud_row(8.4, "T04")])
    row = window.table_rows[register]
    assert window.register_table.item(row, 5).text() == "--"
    assert window.register_table.item(row, 12).text() == "--"
    assert flashes == []
    window.apply_cloud_rows_to_main([cloud_row(8.7, "T04")])
    assert window.register_table.item(row, 7).text() == "8.7 °C"
    assert window.register_table.item(row, 5).text() == "8.4 °C"
    assert window.register_table.item(row, 12).text() == "8.4 °C"
    assert flashes == [register]
    assert window.cloud_change_highlights == {register}
    assert window.previous_value_texts == {} and window.last_values == {}
    assert window.register_change_highlights == set()


def test_identical_numeric_values_timestamps_stale_and_metadata_do_not_flash(application, monkeypatch):
    window = CloudWindow()
    flashes = []
    monkeypatch.setattr(window, "flash_register_row", flashes.append)
    register = cloud_modbus_register("T04")
    window.apply_cloud_rows_to_main([cloud_row(8.4, "T04")])
    for value, metadata in [("8.40", {"lastFetch": "later"}), (8.4, {"stale": True}),
                            (8.4, {"stale": False, "rangeStart": 0, "rangeEnd": 100}),
                            (8.4, {"unit": "K"})]:
        window.apply_cloud_rows_to_main([cloud_row(value, "T04", **metadata)])
    assert flashes == []
    assert register not in window.cloud_previous_value_by_reg
    assert window.register_table.item(window.table_rows[register], 12).text() == "--"
    window.apply_cloud_rows_to_main([cloud_row(8.7, "T04", unit="K")])
    previous = window.cloud_previous_value_by_reg[register]
    window.apply_cloud_rows_to_main([cloud_row(8.7, "T04", lastFetch="newer")])
    assert flashes == [register] and window.cloud_previous_value_by_reg[register] == previous


def test_local_and_cloud_histories_stay_separate_even_after_cloud_only_promotion(application, monkeypatch):
    window = CloudWindow()
    flashes = []
    monkeypatch.setattr(window, "flash_register_row", flashes.append)
    register = cloud_modbus_register("R02")
    window.apply_cloud_rows_to_main([cloud_row(55)])
    window.apply_cloud_rows_to_main([cloud_row(54)])
    # A real local read takes ownership of the normal history column.
    local = DecodedRegister(0x63, register, 0, 3, 550, 550, "55 °C", "R02", "TEMP1", time.time())
    window._upsert_register_row(local, changed=False)
    window.last_values[register] = 550
    window.previous_value_texts[register] = "530 / 0x0212"
    window._upsert_register_row(local, changed=False)
    local_text = window.register_table.item(window.table_rows[register], 7).text()
    window.apply_cloud_rows_to_main([cloud_row(52)])
    row = window.table_rows[register]
    assert window.register_table.item(row, 5).text() == "530 / 0x0212"
    assert window.register_table.item(row, 12).text() == "54 °C"
    assert window.register_table.item(row, 7).text() == local_text
    assert window.latest_regs[register] is local and window.last_values[register] == 550
    assert window.register_change_highlights == set()


@pytest.mark.parametrize("path", ["single", "main_write", "dialog_write", "static_reload"])
def test_all_cloud_readback_paths_update_history(application, monkeypatch, path):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    window.warmlink_cloud_dialog = dialog
    flashes = []
    monkeypatch.setattr(window, "flash_register_row", flashes.append)
    register = cloud_modbus_register("R02")
    dialog._on_data([cloud_row(55)])
    window.cloud_read_reg_no = register
    if path == "single":
        window._on_cloud_read_data("R02", [cloud_row(54)])
    elif path == "main_write":
        window._on_cloud_write_result("R02", {"isReusltSuc": True, "readback": cloud_row(54)})
    elif path == "dialog_write":
        dialog._on_command_result({"isReusltSuc": True, "readback": cloud_row(54)})
    else:
        dialog._on_data([cloud_row(54)])  # The static worker emits this same data signal.
    assert window.cloud_previous_value_by_reg[register] == "55 °C"
    assert window.cloud_overlay_by_reg[register]["value"] == "54 °C"
    assert window.cloud_session.rows["R02"]["value"] == 54
    assert flashes == [register]  # Main/dialog cache updates cannot double-flash.
    dialog.close()


def test_session_devices_selection_and_cache_survive_actual_dialog_close_and_reopen(application, monkeypatch):
    window = DialogWindow()
    def forbidden(*args, **kwargs):
        pytest.fail("Opening a cached dialog must not make requests")
    monkeypatch.setattr(workers, "WarmLinkCloudApi", forbidden)
    window.cloud_session = CloudSession(username="user", device_code="device", devices=[
        {"deviceCode": "other", "deviceNickName": "Other", "discoverySource": "house"},
        {"deviceCode": "device", "deviceNickName": "Selected", "discoverySource": "deviceList + House"}], validated=True,
        scanned=True, candidates=["R02", "T04"], supported_codes=["R02", "T04"],
        static_codes=["R02"], live_codes=["T04"], rows={"R02": cloud_row(55)})
    window.open_warmlink_cloud_dialog()
    first = window.warmlink_cloud_dialog
    first._on_token_updated("memory-token")
    first._on_credentials_loaded("user", "memory-password")
    first.device_combo.setCurrentIndex(first.device_combo.findData("device"))
    session = first.session
    first.close()
    assert window.warmlink_cloud_dialog is None
    window.open_warmlink_cloud_dialog()
    second = window.warmlink_cloud_dialog
    assert second is not first and second.session is session
    assert second.device_combo.count() == 2 and second._selected_device_code() == "device"
    assert second.devices[1]["discoverySource"] == "deviceList + House"
    assert second.data_rows == [cloud_row(55)]
    assert second.session.static_codes == ["R02"] and second.session.live_codes == ["T04"]
    assert second._initial_token_for_user("user") == "memory-token"
    assert second._password() == "memory-password"
    assert second.cloud_thread is None and second.cloud_worker is None
    assert "devices" not in window.settings["warmlink_cloud"]
    second.close()


def test_discovery_only_never_reads_values_status_or_faults_and_preserves_same_device_cache(fake_api):
    first = poll_worker(poll_once=True)
    first.run()
    cached = deepcopy(first.session)
    worker = poll_worker(poll_once=True, discovery_only=True, session=cached)
    updates, timings = [], []
    worker.data.connect(updates.append)
    worker.timing_updated.connect(timings.append)
    worker.run()
    assert fake_api.created[-1].calls == ["devices", "houses", ("house", "house-a"), ("house", "house-b")]
    assert updates == [] and worker.session.rows == cached.rows
    assert worker.session.scanned and worker.session.static_codes == cached.static_codes
    assert worker.session.device_code == "device"
    assert "DISCOVERY" in [state.phase for state in timings] and timings[-1].phase == "IDLE"


def test_discovery_without_selection_finds_two_devices_without_selecting_and_scanning_first(fake_api, monkeypatch):
    monkeypatch.setattr(fake_api, "get_devices", lambda api: api.calls.append("devices") or success([
        {"deviceCode": "A"}, {"deviceCode": "B"}]))
    worker = workers.WarmLinkCloudWorker("user", "password", ["R02", "T04"],
        discovery_only=True, initial_token="token")
    worker.run()
    calls = fake_api.created[-1].calls
    assert not any(isinstance(call, tuple) and call[0] == "read" for call in calls)
    assert "status" not in calls and worker.session.rows == {} and not worker.session.scanned
    assert worker.session.devices[0]["deviceCode"] == "A"


def test_rediscover_button_starts_only_discovery_mode(application, monkeypatch):
    dialog = WarmLinkCloudDialog(DialogWindow())
    starts = []
    monkeypatch.setattr(dialog, "_start_worker", lambda *args, **kwargs: starts.append(kwargs))
    dialog.rediscover_btn.click()
    assert starts == [{"discovery_only": True}]
    dialog.close()


def test_device_merge_keeps_authoritative_zero_false_and_fills_only_gaps():
    merged = merge_device_sources([
        {"deviceCode": "X", "deviceNickName": "Main", "dtuSoftwareVer": "1.2.3",
         "isFault": False, "dtuSignalIntensity": 0, "model": "", "custModel": None},
    ], [
        {"deviceCode": "X", "deviceNickName": "House", "houseName": "Zuhause", "isShared": False,
         "isFault": True, "dtuSignalIntensity": 99, "model": "GL9", "custModel": "PHNIX"},
    ], ["X", "manual"])
    assert merged[0] == {"deviceCode": "X", "deviceNickName": "Main", "dtuSoftwareVer": "1.2.3",
        "isFault": False, "dtuSignalIntensity": 0, "model": "GL9", "custModel": "PHNIX",
        "houseName": "Zuhause", "isShared": False, "discoverySource": "deviceList + House"}
    assert merged[1] == {"deviceCode": "manual", "discoverySource": "manual"}


def test_full_device_table_keeps_unknown_fields_and_unmasked_ids(application):
    dialog = WarmLinkCloudDialog(DialogWindow())
    dialog._on_devices([{"deviceCode": "device", "deviceId": "short", "deviceName": "Shared",
        "isShared": True, "isFault": False, "houseName": "Zuhause", "roomId": "R", "areaId": "A",
        "houseRoleType": "1", "productKey": "P", "faultState": 0, "dtuIccid": "123456", "sn": "SN123",
        "discoverySource": "deviceList + House", "deviceSecret": "do-not-show", "MAC": "new-field"}])
    columns = [dialog.device_table.horizontalHeaderItem(i).text() for i in range(dialog.device_table.columnCount())]
    assert columns[:len(dialog.DEVICE_COLUMNS)] == dialog.DEVICE_COLUMNS
    assert columns[len(dialog.DEVICE_COLUMNS):] == sorted(set(columns) - set(dialog.DEVICE_COLUMNS))
    values = {key: dialog.device_table.item(0, i).text() for i, key in enumerate(columns)}
    assert values["isFault"] == "False" and values["faultState"] == "0"
    assert values["dtuSignalIntensity"] == "—"
    assert values["deviceId"] == "short" and values["deviceCode"] == "device"
    assert values["sn"] == "SN123" and values["dtuIccid"] == "123456"
    assert values["houseRoleType"] == "1" and values["productKey"] == "P"
    assert values["MAC"] == "new-field" and "deviceSecret" not in values
    assert not hasattr(dialog, "device_details_table") and not hasattr(dialog, "ids_cb")
    assert device_table_value({"v": ""}, "v", set()) == ""
    assert device_table_value({"v": 0}, "v", set()) == "0"
    assert device_table_value({"v": False}, "v", set()) == "False"
    dialog.close()


def test_sparse_house_metadata_does_not_invent_fields():
    device = normalize_house_devices(success({"data": [{"houseRelDeviceList": [{"deviceCode": "X", "isShared": False}]}]}))[0]
    assert device == {"deviceCode": "X", "isShared": False}


def test_worker_timing_starts_full_interval_at_completion_and_static_reload_keeps_deadline(fake_api, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(workers.time, "monotonic", lambda: now[0])
    original = fake_api.get_data_by_code_batched
    def read(api, *args, **kwargs):
        now[0] += 4
        return original(api, *args, **kwargs)
    monkeypatch.setattr(fake_api, "get_data_by_code_batched", read)
    worker = poll_worker(interval_s=30)
    timings, sleeps = [], []
    worker.timing_updated.connect(timings.append)
    def wait(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 1:
            now[0] += 2
            worker.request_static_reload()
            return False
        return True
    worker._sleep_interruptible = wait
    worker.run()
    waits = [state for state in timings if state.phase == "POLL_WAIT"]
    assert waits[0].deadline == 134 and waits[0].duration == 30 and sleeps[0] == 30
    assert waits[1].deadline == 134 and sleeps[1] == 24
    assert [state.phase for state in timings].count("STATIC_RELOAD") == 2
    assert timings[-1].phase == "IDLE" and not timings[-1].polling_active


def test_worker_retry_deadline_and_running_states(fake_api, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(workers.time, "monotonic", lambda: now[0])
    first = poll_worker(poll_once=True)
    first.run()
    fake_api.failures = [WarmLinkCloudError("timeout"), None]
    worker = poll_worker(session=first.session)
    states = []
    worker.timing_updated.connect(states.append)
    run_cycles(worker)
    retry = next(state for state in states if state.phase == "RETRY")
    assert retry.deadline == 105 and retry.duration == 5
    assert "POLL_RUNNING" in [state.phase for state in states]
    assert "POLL_WAIT" in [state.phase for state in states]


def test_countdown_timer_only_renders_worker_state_and_never_requests(application, monkeypatch):
    window = CloudWindow()
    now = [100.0]
    monkeypatch.setattr(gui.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(workers, "WarmLinkCloudApi", lambda *args, **kwargs: pytest.fail("Countdown made a request"))
    state = CloudTimingState("POLL_WAIT", deadline=130.0, duration=30.0, polling_active=True)
    window.set_cloud_timing_state(state)
    assert window.cloud_progress_bar.value() == 30000 and window.cloud_countdown_timer.isActive()
    for second in range(1, 31):
        now[0] = 100 + second
        window.cloud_countdown_timer.timeout.emit()
        assert window.cloud_progress_bar.value() == (30 - second) * 1000
        assert window.cloud_timing_state is state and state.deadline == 130
    for phase in ("INITIAL_SCAN", "STATIC_RELOAD", "POLL_RUNNING", "DISCOVERY"):
        window.set_cloud_timing_state(CloudTimingState(phase, done=3, total=10))
        assert window.cloud_progress_bar.property("cloudPhase") == phase
        assert window.cloud_progress_bar.maximum() == 10 and window.cloud_progress_bar.value() == 3
        assert not window.cloud_countdown_timer.isActive()
    window.set_cloud_timing_state(CloudTimingState("DISCOVERY"))
    assert window.cloud_progress_bar.maximum() == 0
    window.set_cloud_timing_state(CloudTimingState("RETRY", deadline=135, duration=5))
    assert window.cloud_progress_bar.property("cloudPhase") == "RETRY" and window.cloud_progress_bar.value() == 5000
    window.set_cloud_timing_state(CloudTimingState())
    assert window.cloud_progress_bar.isHidden() and not window.cloud_countdown_timer.isActive()


def test_existing_local_row_retains_modbus_history_while_cloud_changes(application, monkeypatch):
    window = CloudWindow()
    monkeypatch.setattr(window, "flash_register_row", lambda *_args: None)
    register = cloud_modbus_register("T04")
    local = DecodedRegister(0x63, register, 0, 3, 83, 83, "8.3 °C", "T04", "TEMP1", time.time())
    window.previous_value_texts[register] = "82 / 0x0052"
    window.last_values[register] = 83
    window._upsert_register_row(local, changed=False)
    window.apply_cloud_rows_to_main([cloud_row(8.4, "T04")])
    window.apply_cloud_rows_to_main([cloud_row(8.7, "T04")])
    assert window.previous_value_texts[register] == "82 / 0x0052"
    assert window.register_table.item(window.table_rows[register], 5).text() == "82 / 0x0052"
    assert window.cloud_previous_value_by_reg[register] == "8.4 °C"
    assert window.last_values[register] == 83 and window.latest_regs[register] is local


def test_discovery_retains_nonfirst_selection_without_scan_and_replaces_missing_selection(fake_api, monkeypatch):
    monkeypatch.setattr(fake_api, "get_devices", lambda api: success([
        {"deviceCode": "A"}, {"deviceCode": "B"}]))
    for selected, expected in [("B", "B"), ("removed", "A")]:
        worker = workers.WarmLinkCloudWorker("user", "password", ["R02", "T04"],
            device_code=selected, discovery_only=True, initial_token="token")
        worker.run()
        assert worker.session.device_code == expected
        assert worker.session.rows == {} and not worker.session.scanned
        assert "status" not in fake_api.created[-1].calls
        assert not any(isinstance(call, tuple) and call[0] == "read" for call in fake_api.created[-1].calls)


def test_discovery_new_selection_drops_previous_device_values_without_reading(application):
    window = DialogWindow()
    dialog = WarmLinkCloudDialog(window)
    dialog.session = CloudSession(username="user", device_code="device", scanned=True)
    dialog._on_data([cloud_row(55)])
    dialog._on_session_updated(CloudSession(username="user", device_code="new", validated=True,
        devices=[{"deviceCode": "new"}]))
    dialog._on_devices([{"deviceCode": "new"}])
    assert dialog._selected_device_code() == "new"
    assert dialog.data_rows == [] and dialog.session.rows == {}
    assert window.cloud_last_rows == [] and window.cloud_overlay_by_reg == {}
    assert window.latest_regs == {}
    dialog.close()


def test_cloud_flash_reuses_animation_without_modbus_change_state(application):
    window = CloudWindow()
    register = cloud_modbus_register("T04")
    window.apply_cloud_rows_to_main([cloud_row(8.4, "T04")])
    window.apply_cloud_rows_to_main([cloud_row(8.7, "T04")])
    assert register in window.register_flash_tokens
    assert register in window.cloud_change_highlights
    assert register not in window.register_change_highlights
    window.cloud_countdown_timer.stop()


def test_type_metadata_change_without_payload_change_does_not_flash(application, monkeypatch):
    window = CloudWindow()
    flashes = []
    monkeypatch.setattr(window, "flash_register_row", flashes.append)
    window.apply_cloud_rows_to_main([cloud_row("0101", "T04", dataType="FLOAT")])
    window.apply_cloud_rows_to_main([cloud_row("0101", "T04", dataType="BINARY")])
    assert flashes == [] and window.cloud_previous_value_by_reg == {}


def test_house_area_and_room_duplicates_fill_missing_metadata_without_overwriting_zero_false():
    devices = normalize_house_devices(success({"data": [{"areaId": "area", "houseRelDeviceList": [
        {"deviceCode": "X", "isFault": False, "dtuSignalIntensity": 0}], "roomInfoResultList": [
        {"roomId": "room", "houseRelDeviceList": [{"deviceCode": "X", "deviceName": "Shared",
            "isFault": True, "dtuSignalIntensity": 99}]}]}]}), {"id": "house", "houseName": "", "roleType": "1"})
    assert len(devices) == 1
    assert devices[0]["roomId"] == "room" and devices[0]["deviceName"] == "Shared"
    assert devices[0]["isFault"] is False and devices[0]["dtuSignalIntensity"] == 0
    assert devices[0]["houseName"] == ""
