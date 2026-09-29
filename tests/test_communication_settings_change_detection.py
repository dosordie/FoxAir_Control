import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _apply_changes_method():
    """Compile the dialog logic without importing the Qt application module."""
    source_path = ROOT / "foxair_phnix_control.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    dialog = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CommunicationSettingsDialog"
    )
    method = next(
        node for node in dialog.body
        if isinstance(node, ast.FunctionDef) and node.name == "_apply_changes"
    )
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "DEFAULT_DEVICE_MODEL": "foxair_green_gl9_1",
        "QApplication": SimpleNamespace(instance=lambda: "application"),
        "apply_app_theme": MagicMock(),
        "udp_diagnostic_defaults": lambda value: dict(value),
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["_apply_changes"], namespace["apply_app_theme"]


class Widget:
    def __init__(self, value):
        self.data = value

    def currentData(self):
        return self.data

    def isChecked(self):
        return bool(self.data)

    def value(self):
        return self.data

    def text(self):
        return str(self.data)


def _dialog():
    method, apply_theme = _apply_changes_method()
    parameter_dialog = SimpleNamespace(close=MagicMock())
    main = SimpleNamespace(
        connected=False,
        settings={
            "theme": "system",
            "show_public_warning": True,
            "show_engineering_parameters": False,
        },
        autoconnect_cb=SimpleNamespace(setChecked=MagicMock()),
        raw_log_cb=SimpleNamespace(setChecked=MagicMock()),
        known_only_cb=SimpleNamespace(setChecked=MagicMock()),
        log_changes_only_cb=SimpleNamespace(setChecked=MagicMock()),
        init_pause_spin=SimpleNamespace(setValue=MagicMock()),
        public_warning_label=SimpleNamespace(setVisible=MagicMock()),
        parameter_dialog=parameter_dialog,
        rebuild_table_filter=MagicMock(),
        set_current_device_model=MagicMock(),
        apply_communication_settings=MagicMock(),
        _apply_live_poll_timer_state=MagicMock(),
        _update_dual_logger_button_visibility=MagicMock(),
        _refresh_search_highlights=MagicMock(),
        _save_settings=MagicMock(),
    )
    values = {
        "autoconnect_cb": False, "raw_log_cb": False, "known_only_cb": False,
        "log_changes_only_cb": False, "show_warning_cb": True, "theme_combo": "system",
        "update_asset_combo": "auto", "engineering_cb": False,
        "device_combo": "foxair_green_gl9_1", "auto_read_init_cb": False,
        "live_poll_cb": False, "live_poll_interval_spin": 30, "init_pause_spin": 500,
        "tab_auto_poll_cb": False, "tab_poll_interval_spin": 30,
        "udp_enabled_cb": False, "udp_host_edit": "127.0.0.1", "udp_port_spin": 8766,
        "udp_reg_cb": True, "udp_raw_cb": False, "display_dual_logger_cb": False,
        "backend_combo": "standard_modbus",
    }
    dialog = SimpleNamespace(main_window=main, **{name: Widget(value) for name, value in values.items()})
    dialog._initial_theme = "system"
    dialog._initial_device_model = "foxair_green_gl9_1"
    dialog._initial_show_engineering_parameters = False
    dialog._initial_show_public_warning = True
    dialog._initial_known_only = False
    dialog._initial_live_poll = (False, 30)
    dialog._initial_udp_diagnostic = {
        "enabled": False, "host": "127.0.0.1", "port": 8766,
        "send_register_changes": True, "send_raw_bus": False,
    }
    dialog._initial_show_dual_logger = False
    dialog._initial_communication = ("unchanged",)
    dialog._communication_fields_snapshot = lambda: ("unchanged",)
    dialog._save_current_fields_to_selected_backend = MagicMock()
    return method, apply_theme, dialog, main, parameter_dialog


def test_unchanged_ok_skips_expensive_actions_and_saves_once():
    method, apply_theme, dialog, main, parameter_dialog = _dialog()

    method(dialog)

    apply_theme.assert_not_called()
    main.rebuild_table_filter.assert_not_called()
    main._refresh_search_highlights.assert_not_called()
    main.set_current_device_model.assert_not_called()
    main.apply_communication_settings.assert_not_called()
    parameter_dialog.close.assert_not_called()
    main._save_settings.assert_called_once_with(sync_main_fields=False)


def test_changed_theme_is_applied_and_colors_refreshed_once():
    method, apply_theme, dialog, main, _ = _dialog()
    dialog.theme_combo.data = "dark"

    method(dialog)

    apply_theme.assert_called_once_with("application", "dark")
    main._refresh_search_highlights.assert_called_once_with()


@pytest.mark.parametrize("changed", [False, True])
def test_known_only_rebuilds_table_only_when_changed(changed):
    method, _, dialog, main, _ = _dialog()
    dialog.known_only_cb.data = changed

    method(dialog)

    assert main.rebuild_table_filter.call_count == int(changed)


@pytest.mark.parametrize("changed", [False, True])
def test_engineering_closes_parameter_dialog_only_when_changed(changed):
    method, _, dialog, _, parameter_dialog = _dialog()
    dialog.engineering_cb.data = changed

    method(dialog)

    assert parameter_dialog.close.call_count == int(changed)


def test_device_change_uses_non_saving_setter_and_rebuilds_parameter_content():
    method, _, dialog, main, parameter_dialog = _dialog()
    dialog.device_combo.data = "foxair_blue_bl8_1"

    method(dialog)

    main.set_current_device_model.assert_called_once_with("foxair_blue_bl8_1", save=False)
    parameter_dialog.close.assert_called_once_with()
    main._save_settings.assert_called_once_with(sync_main_fields=False)


def test_changed_communication_is_applied_without_an_intermediate_save():
    method, _, dialog, main, _ = _dialog()
    dialog._communication_fields_snapshot = lambda: ("changed",)

    method(dialog)

    dialog._save_current_fields_to_selected_backend.assert_called_once_with()
    main.apply_communication_settings.assert_called_once_with("standard_modbus", save=False)
    main._save_settings.assert_called_once_with(sync_main_fields=False)
