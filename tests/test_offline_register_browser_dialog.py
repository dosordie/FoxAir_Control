import json
import os
import sys
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

qt_widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
QApplication = qt_widgets.QApplication
QWidget = qt_widgets.QWidget

from core.foxair_phnix_core import RegisterMap
from dialogs.offline_register_browser_dialog import OfflineRegisterBrowserDialog


MAIN_MAP_PATH = ROOT / "data/foxair_phnix_registers.json"
DISPLAY_MAP_PATH = ROOT / "data/foxair_phnix_display_registers.json"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = {}
        self.register_defs = json.loads(MAIN_MAP_PATH.read_text(encoding="utf-8"))
        self.display_regmap = RegisterMap(str(DISPLAY_MAP_PATH))

    def current_device_model(self):
        return "foxair_green_gl9_1"

    def _save_settings(self, **_kwargs):
        pass


@pytest.fixture()
def browser(qapp):
    main_window = MainWindowStub()
    dialog = OfflineRegisterBrowserDialog(main_window)
    yield dialog
    dialog.close()
    main_window.close()


def _search(dialog, text, *, regex=False):
    dialog.regex_cb.setChecked(regex)
    dialog.search_edit.setText(text)
    return {item["reg"] for item in dialog._filtered_items()}


def test_wp_browser_collects_every_numeric_mapping_entry(browser):
    expected = {int(key) for key in browser.main_window.register_defs if str(key).isdigit()}

    assert browser.search_edit.text() == ""
    assert {item["reg"] for item in browser._filtered_items()} == expected


@pytest.mark.parametrize(
    ("query", "expected_reg"),
    [("8801", 8801), ("0x2261", 8801), ("2261", 8801), ("2133", 2133), ("H31", 1041)],
)
def test_wp_search_supports_addresses_hex_and_existing_codes(browser, query, expected_reg):
    assert expected_reg in _search(browser, query)


def test_wp_search_includes_note_and_shows_it_in_description(browser):
    # This phrase occurs in register 1022's note, but not in its other fields.
    assert 1022 in _search(browser, "Reverse-Engineering")
    item = next(item for item in browser._filtered_items() if item["reg"] == 1022)

    assert "Notiz:" in item["detail"]
    assert "Reverse-Engineering" in item["detail"]


def test_display_search_supports_decimal_and_hex_addresses(browser):
    browser.source_combo.setCurrentIndex(browser.source_combo.findData("display"))

    assert 3001 in _search(browser, "3001")
    assert 3001 in _search(browser, "0x0BB9")
    assert 3001 in _search(browser, "0BB9")


def test_regex_search_remains_available(browser):
    assert 1041 in _search(browser, r"^1041\s+0x411\s+411.*H31", regex=True)
