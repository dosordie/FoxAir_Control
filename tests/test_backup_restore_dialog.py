import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

qt_widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
QApplication = qt_widgets.QApplication
QWidget = qt_widgets.QWidget

from core.foxair_phnix_core import RegisterInfo
from dialogs.backup_restore_dialog import BackupRestoreDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.regmap = {
            1015: RegisterInfo("Sprachauswahl", "RAW", {1: "Deutsch"}, None),
            1018: RegisterInfo("Autostart", "DIGI1", {1: "Ein"}, None),
        }
        self.latest_regs = {1015: SimpleNamespace(raw_value=1)}

    def _unit_for_register(self, _reg_no):
        return ""


def test_backup_and_restore_previews_use_central_formatter(qapp):
    main_window = MainWindowStub()
    dialog = BackupRestoreDialog(main_window)

    dialog.refresh_backup_preview()

    assert dialog.backup_table.rowCount() == 1
    assert dialog.backup_table.item(0, 4).text() == "1 = Deutsch"

    dialog.loaded_backup = {
        "registers": [
            {"reg": 1015, "raw_value": 0},
            {"reg": 1011, "raw_value": 1},
        ],
    }
    dialog.refresh_restore_table()

    assert dialog.restore_table.rowCount() == 2
    assert dialog.restore_table.item(0, 5).text() == "1 = Deutsch"
    assert [item[0] for item in dialog._restore_items("changed")] == [1015]
    dialog.close()
    main_window.close()
