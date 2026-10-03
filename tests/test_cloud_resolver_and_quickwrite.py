import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cloud.register_resolver import resolve_cloud_register
from cloud.warmlink_codes import cloud_hint, cloud_modbus_register


@pytest.mark.parametrize(("code", "register"), [
    ("R02", 1158), ("Power", 1011), ("Mode", 1012), ("T35", 2057),
    ("InputCurrent1", 2029), ("2029", 2029), ("code_version", 2104),
    ("MainBoard Version", 2105), ("Z21", None), ("H45", None),
])
def test_cloud_register_resolver(code, register):
    assert cloud_modbus_register(code) == register


def test_confirmed_local_code_follows_current_register_map():
    hint = {"confidence": "confirmed", "local_code": "R02", "modbus_register": 9999}
    definitions = {"4321": {"code": "R02"}, "9999": {"code": "OLD"}}
    assert resolve_cloud_register("R02", hint, definitions) == 4321


def test_candidate_and_ambiguous_codes_do_not_resolve():
    assert resolve_cloud_register("KG1", {"confidence": "candidate", "local_code": "KG1"}, {"100": {"code": "KG1"}}) is None
    assert resolve_cloud_register("R02", {"confidence": "confirmed", "local_code": "R02"}, {"1": {"code": "R02"}, "2": {"code": "R02"}}) is None


def test_cloud_engineering_values_are_not_locally_rescaled():
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)
    for code, value, expected in [
        ("T38", "26", "26 °C"),
        ("InputCurrent1", "3.4", "3.4 A"),
        ("code_version", "3.5", "3.5"),
        ("compensate_offset", "44.0", "44.0 °C"),
    ]:
        fake_window = SimpleNamespace(regmap=SimpleNamespace(get=lambda _reg: None))
        display = app.MainWindow._cloud_display_text(fake_window, code, value)
        reg = app.DecodedRegister(0xC1, 1, 0, 0xC10D, 0, 0, display, "", "", 0)
        assert app.MainWindow._display_value_for_main_table(SimpleNamespace(), reg) == expected


def _quickwrite_window(qt_widgets, connected, cloud_only=False, reg_no=1011):
    app_module = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)

    class FakeWindow(qt_widgets.QWidget):
        def __init__(self):
            super().__init__()
            self.regmap = SimpleNamespace(get=lambda _reg: SimpleNamespace(name="Power", dtype="DIGI1", value_map={}, bit_map={}))
            self.register_defs = {}
            self.latest_regs = {}
            self.last_values = {}
        def current_device_model(self): return ""
        def _write_scale_hint(self, _reg): return ""
        def cloud_code_for_register(self, reg, require_write_allowed=False):
            if reg not in (1011, 2029): return None
            if require_write_allowed and reg == 2029: return None
            return "Power" if reg == 1011 else "InputCurrent1"
        def is_cloud_connected(self): return connected
        def _is_cloud_only_register(self, _reg): return cloud_only
        def _display_write_input_for_register(self, _reg, raw): return str(raw)
        def read_cloud_register(self, _reg): pass
        def open_cloud_write_for_register(self, _reg): pass

    return app_module.RegisterQuickWriteDialog(FakeWindow(), reg_no, 0xC1 if cloud_only else 0x63)


def test_quickwrite_buttons_and_connection_visibility():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    application = qt_widgets.QApplication.instance() or qt_widgets.QApplication([])
    disconnected = _quickwrite_window(qt_widgets, False)
    assert [disconnected.read_btn.text(), disconnected.write_btn.text(), disconnected.close_btn.text()] == ["Lesen", "Schreiben", "Schließen"]
    assert disconnected.cloud_read_btn.isHidden()
    assert disconnected.cloud_write_btn.isHidden()
    connected = _quickwrite_window(qt_widgets, True)
    assert not connected.cloud_read_btn.isHidden()
    assert not connected.cloud_write_btn.isHidden()
    read_only = _quickwrite_window(qt_widgets, True, reg_no=2029)
    assert not read_only.cloud_read_btn.isHidden()
    assert read_only.cloud_write_btn.isHidden()
    cloud_only = _quickwrite_window(qt_widgets, True, cloud_only=True)
    assert not cloud_only.read_btn.isEnabled()
    assert not cloud_only.write_btn.isEnabled()
    assert application is not None



def test_cloud_connection_state_refreshes_open_quickwrite_dialogs():
    app_module = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)

    calls = []
    dialog = SimpleNamespace(
        isVisible=lambda: True,
        update_cloud_actions=lambda: calls.append("updated"),
    )
    window = SimpleNamespace(
        cloud_session_authenticated=False,
        cloud_session_device_code="",
        register_write_dialogs={(0x63, 1011): dialog},
    )

    app_module.MainWindow.set_cloud_connection_state(window, True, "device-1")
    assert window.cloud_session_authenticated is True
    assert window.cloud_session_device_code == "device-1"
    assert calls == ["updated"]

    app_module.MainWindow.set_cloud_connection_state(window, False)
    assert window.cloud_session_authenticated is False
    assert window.cloud_session_device_code == ""
    assert calls == ["updated", "updated"]


def test_cloud_dialog_accepts_confirmed_explicit_alias_without_local_code():
    cloud_dialog_module = pytest.importorskip("dialogs.cloud_dialog", exc_type=ImportError)

    fake = SimpleNamespace(
        main_window=SimpleNamespace(
            _validated_cloud_modbus_register=lambda _code, _hint: (1011, "", "")
        )
    )
    status = cloud_dialog_module.WarmLinkCloudDialog._mapping_status(fake, "Power")
    assert status["mapping_status"] == "OK"
    assert status["modbus_register"] == "1011"
