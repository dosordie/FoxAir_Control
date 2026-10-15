from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from core.foxair_phnix_core import (
    DEFAULT_BUS_ADDR, bitfield_states, decode_contact_bits, decode_system_io_status_2146,
    format_bitfield_details, format_value_by_type, s16,
)
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
        self.status_label.setText("Lese Lastausgänge ...")
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2019, 1, slave_addr=slave_addr, label="Lastausgang 2019")

    def show_read_timeout(self):
        self.status_label.setText("Timeout / keine Antwort.")

    def set_value(self, value: Optional[int], status_text: Optional[str] = None):
        if status_text is not None:
            self.status_label.setText(status_text)
        elif value is not None:
            self.status_label.setText("Live-Wert aktualisiert.")
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


class SystemIOStatusDecoderDialog(QDialog):
    """MAIN status groups sharing the formatter and scheduled read path."""

    READ_LABEL = "System-/I/O-Status 2146-2147"
    DIAGNOSTIC_GROUPS = (
        (2139, "Frequenzbegrenzungen"), (2152, "EMS / Remote"),
        (2109, "Parameteränderungen"), (2080, "Inverterstatus"),
    )
    STATUS_REGISTERS = frozenset((2146, 2147, *(reg for reg, _ in DIAGNOSTIC_GROUPS)))
    READ_LABELS = frozenset((READ_LABEL, *(f"System-/I/O-Status {reg}" for reg, _ in DIAGNOSTIC_GROUPS)))

    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.main_window = parent
        self._value_2146: Optional[int] = None
        self._value_2147: Optional[int] = None
        self._diagnostic_values = {}
        self._read_status = {}
        self._source_slave = self._selected_slave()
        self.setWindowTitle("System-/I/O-Status und Registerdiagnose")
        self.setWindowIcon(app_icon())
        self.resize(1040, 470)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.value_label = QLabel("2146: --")
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

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        io_page = QWidget()
        io_layout = QVBoxLayout(io_page)
        self.tabs.addTab(io_page, "System / I/O 2146–2147")
        self.info_label = QLabel(
            "2146 ist ein System-/I/O-Statuswort, kein Temperaturwert. "
            "Die praktische Ansicht blendet feste Basisbits aus; der volle Rohwert bleibt oben sichtbar."
        )
        self.info_label.setWordWrap(True)
        io_layout.addWidget(self.info_label)

        self.table = QTableWidget(6, 4)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setHorizontalHeaderLabels(["Status", "Quelle", "Zustand", "Bedeutung"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        io_layout.addWidget(self.table, 1)

        self.diagnostic_tables = {}
        self.diagnostic_summaries = {}
        for reg_no, title in self.DIAGNOSTIC_GROUPS:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            summary = QLabel("–")
            summary.setWordWrap(True)
            page_layout.addWidget(summary)
            description = QLabel("Gesetzte Statusbits belegen nicht automatisch eine aktuell messbare Regelauswirkung. Details im Tooltip.")
            description.setToolTip(self.main_window.register_defs.get(str(reg_no), {}).get("description", ""))
            description.setWordWrap(True)
            page_layout.addWidget(description)
            table = QTableWidget(16, 4)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            table.setHorizontalHeaderLabels(["Bit / Maske", "Zustand", "Status", "Bedeutung"])
            for col in range(3):
                table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
            page_layout.addWidget(table, 1)
            self.tabs.addTab(page, f"{title} {reg_no}")
            self.diagnostic_tables[reg_no] = table
            self.diagnostic_summaries[reg_no] = summary
            self._refresh_diagnostic_group(reg_no)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_once)
        self.poll_cb.stateChanged.connect(lambda _=None: self._apply_poll_state())
        self.poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_poll_state())
        self.read_now_btn.clicked.connect(self.poll_once)
        self.tabs.currentChanged.connect(self._show_current_group)
        self.finished.connect(lambda _=None: self.poll_timer.stop())

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.set_values(None, None)
        # Only a local MAIN word from the selected bus may seed this dialog.
        # Cloud projections never carry a local Modbus raw word.
        for reg_no in self.STATUS_REGISTERS:
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg)
        self._show_current_group()

    def _selected_slave(self):
        try:
            return self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except (AttributeError, TypeError, ValueError):
            return DEFAULT_BUS_ADDR

    def _current_group(self):
        index = self.tabs.currentIndex()
        return 2146 if index == 0 else self.DIAGNOSTIC_GROUPS[index - 1][0]

    def _show_current_group(self, _index=None):
        group = self._current_group()
        if group == 2146:
            self.set_values(self._value_2146, self._value_2147)
        else:
            raw = self._diagnostic_values.get(group)
            info = self.main_window.regmap.get(group)
            self.value_label.setText(f"{group}: " + format_bitfield_details(raw, info).split("\n")[0])
        self.status_label.setText(self._read_status.get(group, "Bereit. Nur lokale MAIN-Werte."))

    def _refresh_diagnostic_group(self, reg_no):
        raw = self._diagnostic_values.get(reg_no)
        info = self.main_window.regmap.get(reg_no)
        self.diagnostic_summaries[reg_no].setText(format_value_by_type(raw, info.dtype, bit_map=info.bit_map, compact=True))
        table = self.diagnostic_tables[reg_no]
        for row, (bit, label, description, active) in enumerate(bitfield_states(raw, info.bit_map, info.bit_descriptions)):
            values = [f"B{bit} / 0x{1 << bit:04X}", "–" if active is None else "gesetzt" if active else "aus", label, description]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setBackground(QColor(220, 240, 255) if active else QColor(245, 245, 245))
                table.setItem(row, col, item)

    def clear_values(self, status_text="Werte geleert."):
        self._value_2146 = self._value_2147 = None
        self._diagnostic_values.clear()
        self._read_status = {reg: status_text for reg in self.STATUS_REGISTERS}
        self.set_values(None, None)
        for reg, _title in self.DIAGNOSTIC_GROUPS:
            self._refresh_diagnostic_group(reg)
        self._show_current_group()

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        slave_addr = self._selected_slave()
        if slave_addr != self._source_slave:
            self._source_slave = slave_addr
            self.clear_values("Bus gewechselt; noch keine neuen Werte.")
        group = self._current_group()
        self._read_status[group] = f"Lese MAIN:{group} ..."
        self._show_current_group()
        if group == 2146:
            self.main_window.send_read_request(2146, 2, slave_addr=slave_addr, label=self.READ_LABEL)
        else:
            self.main_window.send_read_request(group, 1, slave_addr=slave_addr, label=f"System-/I/O-Status {group}")

    def _group_for_label(self, label):
        return 2146 if label == self.READ_LABEL else int(label.rsplit(" ", 1)[-1])

    def show_read_timeout(self, label=READ_LABEL):
        self._read_status[self._group_for_label(label)] = "Timeout / keine Antwort; letzter Wert bleibt sichtbar."
        self._show_current_group()

    def show_read_response(self, label, registers):
        accepted = any([self.update_from_live_register(reg) for reg in registers])
        if accepted:
            self._read_status[self._group_for_label(label)] = "Erfolgreich gelesen."
            self._show_current_group()

    def update_from_live_register(self, reg):
        if getattr(reg, "value_source", "modbus") != "modbus":
            return False
        wire_slave = self._source_slave
        if hasattr(self.main_window, "_wire_slave_addr"):
            wire_slave = self.main_window._wire_slave_addr(wire_slave)
        if reg.slave_addr != wire_slave:
            is_main_broadcast = (
                reg.slave_addr == 0 and reg.frame_type in (2001, 2091)
                and self.main_window.current_backend_key() == "display_modbus"
            )
            if not is_main_broadcast:
                return False
        reg_no = int(reg.reg)
        if reg_no == 2146:
            self._value_2146 = int(reg.raw_value) & 0xFFFF
        elif reg_no == 2147:
            self._value_2147 = s16(int(reg.raw_value) & 0xFFFF)
        elif reg_no in self.diagnostic_tables:
            self._diagnostic_values[reg_no] = int(reg.raw_value) & 0xFFFF
            self._refresh_diagnostic_group(reg_no)
        else:
            return False
        self._read_status[2146 if reg_no == 2147 else reg_no] = "Lokaler Live-Wert aktualisiert."
        self._show_current_group()
        return True

    def set_values(self, value_2146: Optional[int], value_2147: Optional[int], status_text: Optional[str] = None):
        if value_2146 is not None:
            self._value_2146 = int(value_2146) & 0xFFFF
        elif self._value_2146 is None:
            self._value_2146 = None

        if value_2147 is not None:
            self._value_2147 = s16(int(value_2147) & 0xFFFF)
        elif self._value_2147 is None:
            self._value_2147 = None

        if status_text:
            self.status_label.setText(status_text)

        if self._value_2146 is None:
            self.value_label.setText("2146: --")
            decoded = decode_system_io_status_2146(0)
            known = False
        else:
            raw = self._value_2146
            self.value_label.setText(f"2146: {raw} / 0x{raw:04X} / bin={raw:016b}")
            decoded = decode_system_io_status_2146(raw)
            known = True

        def bit_state(bit: int, on_text: str = "AKTIV", off_text: str = "aus") -> str:
            if not known:
                return "--"
            return on_text if (int(decoded["raw"]) & (1 << bit)) else off_text

        s10_state = "--" if not known else str(decoded["s10_state"])
        hyd2050 = "--" if self._value_2147 is None else str(self._value_2147)
        rows = [
            (
                "Heiz-/Sommerabschaltung",
                "2146 Bit 4",
                bit_state(4),
                "Runtime-State aus MAIN:1464/1465; für den normalen Betrieb direkt nutzbar.",
            ),
            (
                "S10-Hardwaresteuerung",
                "2146 Bit 6",
                s10_state,
                "H07=2 / S10 'Heizen/Kühlen AN/AUS'; nicht mit allgemeinem Heizbetrieb verwechseln.",
            ),
            (
                "Service-/Engineering-Qualifizierung",
                "2146 Bit 8",
                bit_state(8, "AKTIV – S10 gesperrt", "frei"),
                "ENG:A:5036-Qualifizierung; 120 Scheduler-Ticks = 60 s. Währenddessen ist S10 gesperrt; zusätzlich nutzt die Firmware einen Abtau-Sonderpfad mit ENG:A:5035-Handshake.",
            ),
            (
                "HYD61 Statusbit",
                "2146 Bit 1 / HYD61:2049 Bit1",
                bit_state(1, "1", "0"),
                "Bei H30=3 externes Hydraulikmodul-Bit; Hersteller-Klartextname noch offen.",
            ),
            (
                "HYD61 Nachbarwert",
                "2147 / HYD61:2050",
                hyd2050,
                "Signed Rohwert aus Unit 0x61; physikalische Semantik/Einheit noch offen.",
            ),
            (
                "V3.5 Capability-Kennbit",
                "2146 Bit 9",
                bit_state(9, "gesetzt", "nicht gesetzt"),
                "In V3.5 fest gesetzt; nur Signaturhinweis, keine alleinige Firmware-Versionserkennung.",
            ),
        ]

        for row, vals in enumerate(rows):
            active = known and row in (0, 1, 2) and (
                (row == 0 and bool(decoded["summer_shutdown"]))
                or (row == 1 and bool(decoded["s10_control_active"]))
                or (row == 2 and bool(decoded["io_qualification_inhibit"]))
            )
            for col, val in enumerate(vals):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(str(val))
                item.setToolTip(str(val))
                item.setBackground(QColor(220, 255, 220) if active else QColor(245, 245, 245))


class FaultDecoderDialog(QDialog):
    """Klartextanzeige fuer Fehlerbits und Sammelstoerung."""

    FAULT_REGS = [2085, 2086, 2087, 2088, 2089, 2090, 2081, 2082, 2083, 2084]
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
        2084: "Fehler 10",
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
        self.read_status_label = QLabel("Bereit.")
        self.read_status_label.setStyleSheet("color: #666;")
        self.poll_cb = QCheckBox("poll aktiv")
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 3600)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" s")
        self.read_now_btn = QPushButton("jetzt lesen")
        top.addWidget(self.status_label, 1)
        top.addWidget(self.read_status_label)
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
        self.refresh(update_status=False)

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        self.read_status_label.setText("Lese Störungen ...")
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
                raw = self.main_window.cloud_overlay_by_reg.get(reg_no, {}).get("raw")
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

    def show_read_timeout(self):
        self.read_status_label.setText("Timeout / keine Antwort.")

    def show_read_success(self):
        self.read_status_label.setText("Störungen erfolgreich gelesen.")
        self.refresh(update_status=False)

    def refresh(self, update_status: bool = True):
        if update_status:
            self.read_status_label.setText("Live-Wert aktualisiert.")
        load_raw = self.main_window.last_values.get(2019)
        if load_raw is None:
            load_raw = self.main_window.cloud_overlay_by_reg.get(2019, {}).get("raw")
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
