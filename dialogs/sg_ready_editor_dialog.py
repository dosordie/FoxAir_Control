from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR, s16

FLASH_CHANGED_ROW_MS = 2000


class SGReadyEditorDialog(QDialog):
    SG_REGS = set(range(1334, 1342)) | {2133}
    READ_LABEL_VALUES = "SG Ready 1334-1341"
    READ_LABEL_STATUS = "SG Status 2133"

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self._sg_status_read_pending = False
        self._sg_read_generation = 0
        self._last_raw_values: dict[int, int] = {}
        self._flash_tokens: dict[int, int] = {}
        self.setWindowTitle("SG Ready Editor")
        self.setMinimumWidth(620)
        self._build_ui()
        self.load_from_live_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("SG Ready Register 1334-1341 plus read-only aktiver SG-Modus 2133. SG01: Aus / 1 Kontakt / 2 Kontakte. Kontaktstatus wird sofort über Register 2034 angezeigt. Der aktive SG-Modus in Register 2133 kann zeitverzögert umschalten. SG Kontakt 1: Klemme 1–2 / AI-DI16 / Fernschalter. SG Kontakt 2: Klemme 7–8 / DIN_1 / Heat/Cool On/Off / PV-Kontakt. Live-Update überschreibt keine gerade bearbeiteten Felder. Der Lese-/Schreibstatus wird global angezeigt.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        layout.addLayout(form)
        status_row = QHBoxLayout()
        self.status_label = QLabel("Bereit.")
        self.status_label.setMinimumWidth(220)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666;")
        self.auto_update_cb = QCheckBox("live aktualisieren")
        self.auto_update_cb.setChecked(True)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.auto_update_cb)
        form.addRow("Status:", status_row)

        self.sg_mode_combo = QComboBox()
        self.sg_mode_combo.addItem("Aus", 0)
        self.sg_mode_combo.addItem("1 Kontakt", 1)
        self.sg_mode_combo.addItem("2 Kontakte", 2)
        form.addRow("SG Ready Auswahl (1334):", self.sg_mode_combo)

        self.raw_spins: dict[int, QSpinBox] = {}
        for reg_no, label in [
            (1335, "SG02 Schlafmodus Zeit"),
            (1336, "SG03 Mode 2 Leistung / wenig PV (RAW / 10 kW)"),
            (1337, "SG04 Mode 3 Leistung / mittel PV (RAW / 10 kW)"),
            (1341, "SG08 E-Heizer / Zusatzfunktion bei Mode 4"),
        ]:
            spin = QSpinBox(); spin.setRange(0, 0xFFFF)
            self.raw_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.temp_spins: dict[int, QDoubleSpinBox] = {}
        for reg_no, label in [
            (1338, "SG05 Mode 4 WW-Sollwertanhebung"),
            (1339, "SG06 Mode 4 HZ-Sollwertanhebung"),
            (1340, "SG07 Mode 4 Kühlen-Sollwertanhebung"),
        ]:
            spin = QDoubleSpinBox(); spin.setRange(-50.0, 25.0); spin.setDecimals(1); spin.setSingleStep(0.5); spin.setSuffix(" °C")
            self.temp_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.sg_status_label = QLabel("--")
        self.sg_status_label.setToolTip("Read-only: Register 2133 / aktiver SG-Modus. 0=WP aus oder SG deaktiviert, 1=SG Mode 1 / Schlafmodus, 2=SG Mode 2 / wenig PV, 3=SG Mode 3 / mittel PV, 4=SG Mode 4 / High PV. Kontaktstatus wird sofort über Register 2034 angezeigt; Register 2133 kann zeitverzögert umschalten.")
        form.addRow("Aktiver SG-Modus (2133, read-only):", self.sg_status_label)

        self.delay_ms = QSpinBox(); self.delay_ms.setRange(0, 10000); self.delay_ms.setValue(500); self.delay_ms.setSingleStep(100); self.delay_ms.setSuffix(" ms")
        form.addRow("Pause zwischen Writes:", self.delay_ms)

        buttons = QHBoxLayout()
        self.load_btn = QPushButton("Aus Live-Werten laden")
        self.read_btn = QPushButton("Von WP lesen")
        self.send_btn = QPushButton("Schreiben")
        self.close_btn = QPushButton("Schließen")
        self.load_btn.clicked.connect(self.load_from_live_values)
        self.read_btn.clicked.connect(self.read_from_wp)
        self.send_btn.clicked.connect(self.send_values)
        self.close_btn.clicked.connect(self.close)
        for b in (self.load_btn, self.read_btn, self.send_btn):
            buttons.addWidget(b)
        buttons.addStretch(1); buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def _has_focus(self, *widgets: QWidget) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        return any(focus is w or w.isAncestorOf(focus) for w in widgets)

    def load_from_live_values(self):
        for reg_no in sorted(self.SG_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg, force=True)

    def set_write_status(self, text: str) -> None:
        self.status_label.setText(str(text))

    def _widget_for_reg(self, reg_no: int) -> Optional[QWidget]:
        if reg_no == 1334:
            return self.sg_mode_combo
        if reg_no in self.raw_spins:
            return self.raw_spins[reg_no]
        if reg_no in self.temp_spins:
            return self.temp_spins[reg_no]
        if reg_no == 2133:
            return self.sg_status_label
        return None

    def _flash_sg_widget(self, reg_no: int) -> None:
        widget = self._widget_for_reg(reg_no)
        if widget is None:
            return
        token = self._flash_tokens.get(reg_no, 0) + 1
        self._flash_tokens[reg_no] = token
        old_style = widget.property("_foxair_normal_style")
        if old_style is None:
            widget.setProperty("_foxair_normal_style", widget.styleSheet())
        widget.setStyleSheet("background-color: #ffff82;")
        def clear_flash() -> None:
            if self._flash_tokens.get(reg_no) != token:
                return
            self._flash_tokens.pop(reg_no, None)
            widget.setStyleSheet(str(widget.property("_foxair_normal_style") or ""))
            widget.setProperty("_foxair_normal_style", None)
        QTimer.singleShot(FLASH_CHANGED_ROW_MS, clear_flash)

    def update_from_live_register(self, reg, force: bool = False):
        reg_no = int(reg.reg)
        if reg_no not in self.SG_REGS:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        raw = int(reg.raw_value) & 0xFFFF
        old_raw = self._last_raw_values.get(reg_no)
        should_flash = old_raw is not None and old_raw != raw
        self._programmatic = True
        try:
            if reg_no == 1334:
                if force or not self._has_focus(self.sg_mode_combo):
                    idx = self.sg_mode_combo.findData(raw)
                    if idx >= 0:
                        self.sg_mode_combo.setCurrentIndex(idx)
            elif reg_no in self.raw_spins:
                spin = self.raw_spins[reg_no]
                if force or not self._has_focus(spin):
                    spin.setValue(raw)
            elif reg_no in self.temp_spins:
                spin = self.temp_spins[reg_no]
                if force or not self._has_focus(spin):
                    spin.setValue(s16(raw) / 10.0)
            elif reg_no == 2133:
                label = {0: "WP aus oder SG deaktiviert", 1: "SG Mode 1 / Schlafmodus", 2: "SG Mode 2 / wenig PV", 3: "SG Mode 3 / mittel PV", 4: "SG Mode 4 / High PV"}.get(raw, "unbekannt / nicht interpretiert")
                self.sg_status_label.setText(f"{raw} - {label}")
                self._sg_status_read_pending = False
                self.status_label.setText("SG Ready / SG Status erfolgreich gelesen.")
        finally:
            self._programmatic = False
        if should_flash:
            self._flash_sg_widget(reg_no)
        self._last_raw_values[reg_no] = raw

    def show_sg_status_timeout(self):
        self._sg_status_read_pending = False
        self.sg_status_label.setText("Timeout / keine Antwort")
        self.status_label.setText("SG Status Timeout / keine Antwort.")

    def sg_values(self) -> list[tuple[int, int, str]]:
        values = [(1334, int(self.sg_mode_combo.currentData()) & 0xFFFF, "SG Ready Auswahl")]
        for reg_no in (1335, 1336, 1337):
            values.append((reg_no, int(self.raw_spins[reg_no].value()) & 0xFFFF, f"SG Register {reg_no}"))
        for reg_no, label in ((1338, "SG05 WW-Anhebung"), (1339, "SG06 HZ-Anhebung"), (1340, "SG07 Kuehlen-Anhebung")):
            values.append((reg_no, int(round(float(self.temp_spins[reg_no].value()) * 10.0)) & 0xFFFF, label))
        values.append((1341, int(self.raw_spins[1341].value()) & 0xFFFF, "SG08 E-Heizer / Zusatzfunktion bei Mode 4"))
        return values

    def read_from_wp(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.remove_pending_read_requests_by_label(
                {self.READ_LABEL_VALUES, self.READ_LABEL_STATUS},
                log_prefix="SG Ready Editor",
            )
            self._sg_read_generation += 1
            generation = self._sg_read_generation
            self._sg_status_read_pending = False
            self.status_label.setText("Lese SG Ready Werte ...")
            self.main_window.send_read_request(1334, 8, slave_addr=slave_addr, label=self.READ_LABEL_VALUES)
            QTimer.singleShot(0, lambda: self._send_status_read_after_values(slave_addr, generation))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige SG-Leseanforderung", str(exc))

    def _send_status_read_after_values(self, slave_addr: int, generation: int):
        if not self.isVisible() or generation != self._sg_read_generation:
            return
        if self.main_window.has_pending_read_request(self.READ_LABEL_VALUES, slave_addr=slave_addr):
            QTimer.singleShot(250, lambda: self._send_status_read_after_values(slave_addr, generation))
            return
        try:
            self.main_window.remove_pending_read_requests_by_label(
                {self.READ_LABEL_STATUS},
                log_prefix="SG Ready Editor",
            )
            self.status_label.setText("SG Ready Werte gelesen. Lese SG Status ...")
            self.sg_status_label.setText("wird gelesen ...")
            self._sg_status_read_pending = True
            self.main_window.send_read_request(2133, 1, slave_addr=slave_addr, label=self.READ_LABEL_STATUS)
        except Exception as exc:
            self._sg_status_read_pending = False
            QMessageBox.warning(self, "Ungültige SG-Status-Leseanforderung", str(exc))

    def send_values(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.status_label.setText("Schreibe SG Ready Werte ...")
            self.main_window.send_timer_values(slave_addr, self.sg_values(), int(self.delay_ms.value()), title="SG Ready")
            self.status_label.setText("SG Ready Schreiben gesendet.")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige SG-Werte", str(exc))
