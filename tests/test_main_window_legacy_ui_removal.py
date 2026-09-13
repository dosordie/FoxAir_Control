from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (ROOT / "foxair_phnix_control.py").read_text(encoding="utf-8")


def test_register_double_click_uses_existing_quick_write_path():
    assert "itemDoubleClicked.connect(self.open_register_quick_write_from_table_item)" in MAIN_SOURCE
    handler = MAIN_SOURCE.split("def open_register_quick_write_from_table_item", 1)[1].split("\n    def ", 1)[0]
    context_handler = MAIN_SOURCE.split("def open_register_context_menu", 1)[1].split("\n    def ", 1)[0]
    assert "self._register_and_bus_from_table_row(item.row())" in handler
    assert "self._register_and_bus_from_table_row(item.row())" in context_handler
    assert "self.open_register_quick_write(reg_no, slave_addr)" in handler


def test_table_row_helper_falls_back_to_default_bus_address():
    helper = MAIN_SOURCE.split("def _register_and_bus_from_table_row", 1)[1].split("\n    def ", 1)[0]
    assert "except Exception:" in helper
    assert "slave_addr = DEFAULT_BUS_ADDR" in helper


def test_persistent_value_cache_and_legacy_raw_writer_are_removed():
    forbidden = (
        "Werte-Cache",
        "save_value_cache",
        "load_value_cache",
        "cache_load_on_start",
        "Raw in Datei (nc/bin)",
        "on_raw_file_checkbox_changed",
        "foxair_phnix_raw_",
    )
    for marker in forbidden:
        assert marker not in MAIN_SOURCE


def test_long_term_capture_path_remains_connected_to_rx_and_tx():
    assert "cap.capture_rx(chunk)" in MAIN_SOURCE
    assert "cap.capture_tx(chunk)" in MAIN_SOURCE
    assert "WarmlinkRawCapture(" in MAIN_SOURCE
