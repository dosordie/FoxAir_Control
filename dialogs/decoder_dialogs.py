from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR, decode_contact_bits
from ui.paths import resource_path
from ui.theme import APP_ICON_FILE

FLASH_CHANGED_ROW_MS = 2000
FLASH_CHANGED_ROW_COLOR = QColor(255, 255, 130)
FLASH_CHANGED_ROW_FADE_STEPS = [
    (0, QColor(255, 255, 130)),
    (850, QColor(255, 255, 185)),
]


def app_icon() -> QIcon:
    return QIcon(resource_path(APP_ICON_FILE, __file__))


class ContactDecoderDialog(QDialog):
    def __init__(self, parent: "MainWindow", value: Optional[int]):
        super().__init__(parent)
        self.main_window = parent
        self._last_value: Optional[int] = None
        self._flash_tokens: dict[int, int] = {}
        self._flash_colors: dict[int, QColor] = {}
        self.setWindowTitle("Kontaktdecoder Register 2034 / 0x07F2")
        self.resize(1030, 560)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.value_label = QLabel("2034: --")
        self.status_label = QLabel("Bereit.")
        self.status_label.setStyleSheet("color: #666;")
        self.poll_cb = QCheckBox("poll aktiv")
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 3600)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" s")
        self.read_now_btn = QPushButton("jetzt lesen")
        top.addWidget(self.value_label, 1)
        top.addWidget(self.status_label)
        top.addWidget(self.poll_cb)
        top.addWidget(QLabel("Intervall:"))
        top.addWidget(self.poll_interval_spin)
        top.addWidget(self.read_now_btn)
        layout.addLayout(top)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_once)
        self.poll_cb.stateChanged.connect(lambda _=None: self._apply_poll_state())
        self.poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_poll_state())
        self.read_now_btn.clicked.connect(self.poll_once)

        self.table = QTableWidget(16, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalHeaderLabels(["Bit", "Roh", "Name", "Status", "Bedeutung"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.set_value(value)

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        self.status_label.setText("Lese Register 2034 ...")
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2034, 1, slave_addr=slave_addr, label="Kontaktdecoder 2034")

    def _contact_status_for_bit(self, bit: int, bit_value: int) -> str:
        for row_bit, row_bit_value, _name, state, _meaning in decode_contact_bits(1 << bit if bit_value else 0):
            if row_bit == bit and row_bit_value == bit_value:
                return state
        return "Ein" if bit_value else "Aus"

    def _contact_row_color(self, bit: int, bit_value: int, value_known: bool, state: Optional[str] = None) -> QColor:
        if bit in self._flash_tokens:
            return self._flash_colors.get(bit, FLASH_CHANGED_ROW_COLOR)
        if not value_known:
            return QColor(245, 245, 245)
        status = state if state is not None else self._contact_status_for_bit(bit, bit_value)
        return QColor(220, 255, 220) if status == "Ein" else QColor(245, 245, 245)

    def _apply_contact_row_background(self, bit: int, bit_value: int, value_known: bool, state: Optional[str] = None) -> None:
        color = self._contact_row_color(bit, bit_value, value_known, state)
        for col in range(self.table.columnCount()):
            item = self.table.item(bit, col)
            if item is not None:
                item.setBackground(color)

    def _flash_contact_bit_row(self, bit: int, bit_value: int) -> None:
        token = self._flash_tokens.get(bit, 0) + 1
        self._flash_tokens[bit] = token

        def apply_flash_step(color: QColor) -> None:
            if self._flash_tokens.get(bit) != token:
                return
            self._flash_colors[bit] = color
            current = self._last_value
            current_bit = ((int(current) >> bit) & 1) if current is not None else bit_value
            self._apply_contact_row_background(bit, current_bit, current is not None)

        for delay_ms, color in FLASH_CHANGED_ROW_FADE_STEPS:
            QTimer.singleShot(delay_ms, lambda c=color: apply_flash_step(c))

        def clear_flash() -> None:
            if self._flash_tokens.get(bit) != token:
                return
            self._flash_tokens.pop(bit, None)
            self._flash_colors.pop(bit, None)
            current = self._last_value
            current_bit = ((int(current) >> bit) & 1) if current is not None else bit_value
            self._apply_contact_row_background(bit, current_bit, current is not None)
        QTimer.singleShot(FLASH_CHANGED_ROW_MS, clear_flash)

    def set_value(self, value: Optional[int]):
        old_value = self._last_value
        changed_bits: set[int] = set()
        if value is not None and old_value is not None:
            diff = (int(old_value) ^ int(value)) & 0xFFFF
            changed_bits = {bit for bit in range(16) if diff & (1 << bit)}
        self._last_value = value
        if value is None:
            self.value_label.setText("2034: --")
            self.status_label.setText("Noch nicht gelesen.")
            rows = decode_contact_bits(0)
            for bit, _bit_value, name, _state, meaning in rows:
                display_name = name if name else f"Bit {bit} / unbekannt"
                vals = [str(bit), "--", display_name, "--", meaning]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setBackground(QColor(245, 245, 245))
                    self.table.setItem(bit, col, item)
            return

        self.value_label.setText(f"2034: {value} / 0x{value:04X} / bin={value:016b}")
        self.status_label.setText("Erfolgreich gelesen." if not changed_bits else f"Erfolgreich gelesen, {len(changed_bits)} Bit(s) geändert.")
        rows = decode_contact_bits(value)
        for bit, bit_value, name, state, meaning in rows:
            display_name = name if name else f"Bit {bit} / unbekannt"
            vals = [str(bit), str(bit_value), display_name, state, meaning]
            for col, val in enumerate(vals):
                item = self.table.item(bit, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(bit, col, item)
                item.setText(val)
                item.setBackground(self._contact_row_color(bit, bit_value, True, state))
            if bit in changed_bits:
                self._flash_contact_bit_row(bit, bit_value)


class LoadOutputDecoderDialog(QDialog):
    """Decoder fuer Register 2019 / 0x07E3 Lastausgaenge."""

    def __init__(self, parent: "MainWindow", value: Optional[int]):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Lastausgangdecoder Register 2019 / 0x07E3")
        self.setWindowIcon(app_icon())
        self.resize(1030, 560)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.value_label = QLabel("2019: --")
        self.poll_cb = QCheckBox("poll aktiv")
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 3600)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" s")
        self.read_now_btn = QPushButton("jetzt lesen")
        top.addWidget(self.value_label, 1)
        top.addWidget(self.poll_cb)
        top.addWidget(QLabel("Intervall:"))
        top.addWidget(self.poll_interval_spin)
        top.addWidget(self.read_now_btn)
        layout.addLayout(top)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_once)
        self.poll_cb.stateChanged.connect(lambda _=None: self._apply_poll_state())
        self.poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_poll_state())
        self.read_now_btn.clicked.connect(self.poll_once)

        self.table = QTableWidget(16, 4)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalHeaderLabels(["Bit", "Wert", "Ausgang", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 62)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 68)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.set_value(value)

    def _bit_map(self) -> dict[int, str]:
        info = self.main_window.regmap.get(2019)
        return dict(info.bit_map or {}) if info is not None else {}

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2019, 1, slave_addr=slave_addr, label="Lastausgang 2019")

    def set_value(self, value: Optional[int]):
        bit_map = self._bit_map()
        if value is None:
            self.value_label.setText("2019: --")
            raw = 0
        else:
            raw = int(value) & 0xFFFF
            active = [str(bit) for bit in range(16) if raw & (1 << bit)]
            active_text = ",".join(active) if active else "keine"
            self.value_label.setText(f"2019: {raw} / 0x{raw:04X} / Bits EIN: {active_text}")

        for bit in range(16):
            bit_value = 1 if (raw & (1 << bit)) else 0
            name = bit_map.get(bit, "Reserviert / unbekannt")
            status = "EIN" if bit_value else "AUS"
            vals = [str(bit), "--" if value is None else str(bit_value), name, "--" if value is None else status]
            for col, val in enumerate(vals):
                item = self.table.item(bit, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(bit, col, item)
                item.setText(val)
                item.setToolTip(val)
                item.setBackground(QColor(220, 255, 220) if bit_value and value is not None else QColor(245, 245, 245))


class FaultDecoderDialog(QDialog):
    """Klartextanzeige fuer Fehlerbits und Sammelstoerung."""

    FAULT_REGS = [2085, 2086, 2087, 2088, 2089, 2090, 2081, 2082, 2083]
    FAULT_TITLES = {
        2085: "Fehler 1",
        2086: "Fehler 2",
        2087: "Fehler 3",
        2088: "Fehler 4",
        2089: "Fehler 5",
        2090: "Fehler 6",
        2081: "Fehler 7",
        2082: "Fehler 8",
        2083: "Fehler 9",
    }

    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Störungen / Fehlerdecoder")
        self.setWindowIcon(app_icon())
        self.resize(1120, 620)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.status_label = QLabel("Sammelstörung: --")
        self.poll_cb = QCheckBox("poll aktiv")
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 3600)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" s")
        self.read_now_btn = QPushButton("jetzt lesen")
        top.addWidget(self.status_label, 1)
        top.addWidget(self.poll_cb)
        top.addWidget(QLabel("Intervall:"))
        top.addWidget(self.poll_interval_spin)
        top.addWidget(self.read_now_btn)
        layout.addLayout(top)

        self.info_label = QLabel("Alarm-Ausgang: Register 2019 Bit 10. Fehlerklartexte aus Fehlerregistern 2081–2090.")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalHeaderLabels(["Register", "Fehler", "Bit", "Raw", "Klartext"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 78)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 86)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 48)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 92)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_once)
        self.poll_cb.stateChanged.connect(lambda _=None: self._apply_poll_state())
        self.poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_poll_state())
        self.read_now_btn.clicked.connect(self.poll_once)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.refresh()

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2019, 1, slave_addr=slave_addr, label="Störung: Lastausgang 2019")
        self.main_window.send_read_request(2081, 10, slave_addr=slave_addr, label="Störung: Fehlerregister 2081-2090")

    def _fault_rows(self) -> list[tuple[int, str, int, int, str]]:
        rows: list[tuple[int, str, int, int, str]] = []
        for reg_no in self.FAULT_REGS:
            raw = self.main_window.last_values.get(reg_no)
            if raw is None:
                continue
            raw_i = int(raw) & 0xFFFF
            if raw_i == 0:
                continue
            info = self.main_window.regmap.get(reg_no)
            bit_map = dict(info.bit_map or {}) if info is not None else {}
            for bit in range(16):
                if raw_i & (1 << bit):
                    text = bit_map.get(bit, "Fehlerbit aktiv, Klartext noch unbekannt")
                    rows.append((reg_no, self.FAULT_TITLES.get(reg_no, f"Fehler {reg_no}"), bit, raw_i, text))
        return rows

    def refresh(self):
        load_raw = self.main_window.last_values.get(2019)
        alarm_active = bool((int(load_raw) & (1 << 10))) if load_raw is not None else False
        if load_raw is None:
            self.status_label.setText("Sammelstörung: unbekannt (2019 noch nicht gelesen)")
            self.status_label.setStyleSheet("font-weight: bold;")
        elif alarm_active:
            self.status_label.setText(f"Sammelstörung: AKTIV  |  2019=0x{int(load_raw)&0xFFFF:04X}, Bit 10 = 1")
            self.status_label.setStyleSheet("font-weight: bold; color: white; background-color: #b00020; padding: 4px;")
        else:
            self.status_label.setText(f"Sammelstörung: aus  |  2019=0x{int(load_raw)&0xFFFF:04X}, Bit 10 = 0")
            self.status_label.setStyleSheet("font-weight: bold; color: #006000; padding: 4px;")

        rows = self._fault_rows()
        if not rows:
            self.table.setRowCount(1)
            vals = ["--", "--", "--", "--", "Keine aktiven Fehlerbits in den bekannten Fehlerregistern." if load_raw is not None else "Noch keine Fehlerregister gelesen."]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setBackground(QColor(245, 245, 245))
                self.table.setItem(0, col, item)
            return

        self.table.setRowCount(len(rows))
        for row, (reg_no, title, bit, raw_i, text) in enumerate(rows):
            vals = [str(reg_no), title, str(bit), f"0x{raw_i:04X}", text]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col in (0, 2, 3):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setToolTip(val)
                item.setBackground(QColor(255, 230, 230))
                self.table.setItem(row, col, item)

