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
from dialogs.parameter_settings_dialog import ParameterSettingsDialog


MAIN_MAP_PATH = ROOT / "data/foxair_phnix_registers.json"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = {}
        self.register_defs = json.loads(MAIN_MAP_PATH.read_text(encoding="utf-8"))
        self.regmap = RegisterMap(str(MAIN_MAP_PATH))
        self.latest_regs = {}
        self.last_values = {}
        self.saved = False

    def current_device_model(self):
        return "foxair_green_gl9_1"

    def _save_settings(self, **_kwargs):
        self.saved = True


def test_engineering_parameters_require_explicit_gui_switch(qapp):
    main_window = MainWindowStub()
    dialog = ParameterSettingsDialog(main_window)
    try:
        assert dialog.engineering_cb.text() == "Engineering anzeigen"
        assert dialog.engineering_cb.isChecked() is False
        assert "ENG" not in dialog.block_buttons

        dialog.engineering_cb.setChecked(True)

        assert "ENG" in dialog.block_buttons
        dialog._select_block("ENG")
        assert {item["reg"] for item in dialog._visible_items()} == {1430, 1492}
        assert main_window.settings["parameter_show_engineering"] is True
        assert main_window.saved is True
    finally:
        dialog.close()
        main_window.close()

