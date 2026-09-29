from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.bus_address_info import display_bus_address_info
from ui.paths import resource_path
from ui.theme import APP_ICON_FILE


def app_icon() -> QIcon:
    return QIcon(resource_path(APP_ICON_FILE, __file__))



class BusAddressDialog(QDialog):
    """Popup fuer gesehene Bus-Adressen."""

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Gesehene Bus-Adressen")
        self.setWindowIcon(app_icon())
        self.resize(1040, 380)
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Interner FoxAir-Boardbus: USART3 / RS485 / 4800 Baud / 8N1. "
            "Das Mainboard arbeitet als Master; Requests adressieren den internen Teilnehmer, "
            "0x00 wird für Broadcasts verwendet.\n\n"
            "Der Warmlink/LTE-Bus ist davon getrennt: USART1 / RS485 / 9600 Baud. "
            "Dort arbeitet das Mainboard als Slave 0x63."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Bus", "Rolle", "Typische Frames", "Übernahme/Hinweis",
            "Frames", "CRC OK", "CRC BAD", "Letzter Frame"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        for col in (4, 5, 6, 7):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        btns = QHBoxLayout()
        self.refresh_btn = QPushButton("aktualisieren")
        self.close_btn = QPushButton("Schließen")
        btns.addWidget(self.refresh_btn)
        btns.addStretch(1)
        btns.addWidget(self.close_btn)
        layout.addLayout(btns)
        self.refresh_btn.clicked.connect(self.refresh)
        self.close_btn.clicked.connect(self.close)
        self.refresh()

    def refresh(self):
        stats = getattr(self.main_window, "bus_stats", {})
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(stats))
        for row, addr in enumerate(sorted(stats)):
            st = stats[addr]
            role, typical, hint = display_bus_address_info(int(addr))
            values = [
                f"0x{addr:02X}", role, typical, hint,
                str(st.get("frames", 0)), str(st.get("crc_ok", 0)),
                str(st.get("crc_bad", 0)), str(st.get("last_frame", "")),
            ]
            for col, text in enumerate(values):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(text)
                if col in (0, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setSortingEnabled(True)
