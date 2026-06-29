from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR
from ui.paths import resource_path
from ui.theme import APP_ICON_FILE


def app_icon() -> QIcon:
    return QIcon(resource_path(APP_ICON_FILE, __file__))


def display_bus_address_info(addr: int) -> tuple[str, str, str]:
    """Lesbare Displaybus-Rollen fuer das Popup 'Gesehene Bus-Adressen'."""
    addr = int(addr)
    if addr == 0x00:
        return (
            "Broadcast / WP-Livewerte",
            "FC16 2001/90 und 2091/90",
            "wird als echter WP-Livebereich übernommen",
        )
    if addr == 0x01:
        return (
            "WP-/Kopf-/Power-Modul-Rohstatus",
            "FC16 1999/16, FC03 2099/51",
            "2099/51 virtuell 91099-91149; 91105~2062 AC-Spannung, 91108~2043 DC-Bus",
        )
    if addr == 0x02:
        return (
            "DWIN/HMI-Pfad unklar",
            "FC03 3001/21 Requests gesehen",
            "bisher Diagnose, keine stabile Übernahme",
        )
    if addr == 0x03:
        return (
            "Display / DWIN-Speicher",
            "FC03 3001/21, Parameterpakete 1001ff, Writes 23xx",
            "3001-3021 sichtbar; Bedienwerte laufen über 23xx",
        )
    if addr == 0x04:
        return (
            "interner Teilnehmer/Ziel",
            "FC03 1011/14 Requests",
            "nicht übernehmen, solange Bereich mit 10xx kollidiert",
        )
    if addr == 0x05:
        return (
            "interner Teilnehmer",
            "FC03 2000/90, FC16 1001/90 Nullblock",
            "Null-/Fremdblock gesperrt, überschreibt keine WP-Werte",
        )
    if addr == DEFAULT_BUS_ADDR:
        return (
            "Warmlink/WP",
            "normaler Warmlink-Modbus",
            "Standard-WP-Adresse außerhalb Displaybus",
        )
    return ("unbekannt", "noch keine feste Zuordnung", "nur beobachten")


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
            "Hinweis: In Modbus-RTU-Requests ist die Adresse die Zieladresse. "
            "Die Rollen unten beschreiben die bisher beobachteten Frames/Erkenntnisse."
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

