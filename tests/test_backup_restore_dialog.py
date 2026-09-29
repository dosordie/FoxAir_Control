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

    def _communication_summary_text(self):
        return "test"

    def current_backend_key(self):
        return "test"

    def current_device_model(self):
        return "test"


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


def test_unknown_package_slot_is_backed_up_and_restored_bit_exactly(qapp):
    main_window = MainWindowStub()
    unknown_reg = 1089
    main_window.latest_regs[1018] = SimpleNamespace(raw_value=1)
    main_window.latest_regs[unknown_reg] = SimpleNamespace(raw_value=0xFFFF)
    dialog = BackupRestoreDialog(main_window)

    assert 1018 in dialog.backup_registers()
    assert unknown_reg in dialog.backup_registers()
    assert not ({1011, 1012, 1013, 1014, 1016} & set(dialog.backup_registers()))
    assert all(
        not (start <= reg <= end)
        for reg in dialog.backup_registers()
        for start, end in dialog.READ_ONLY_BLOCK_HEADER_RANGES
    )

    data = dialog._build_backup_data()
    unknown = next(item for item in data["registers"] if item["reg"] == unknown_reg)
    assert unknown["raw_value"] == 0xFFFF
    assert unknown["dtype"] == "RAW"
    assert "legacy/reserve" in unknown["name"]

    dialog.loaded_backup = {
        "registers": [
            unknown,
            {"reg": 1091, "raw_value": 0x1234},  # Paketkopf
            {"reg": 2001, "raw_value": 0x5678},  # außerhalb der Allowlist
        ]
    }
    assert dialog._restore_items("changed") == [
        (unknown_reg, 0xFFFF, "")
    ]
    dialog.close()
    main_window.close()
