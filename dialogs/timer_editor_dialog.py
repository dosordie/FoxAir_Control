from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR, hexdump


def encode_hhmm(hour: int, minute: int) -> int:
    """Timer-Zeit nach bisheriger Beobachtung: High-Byte=Stunde, Low-Byte=Minute."""
    if not 0 <= hour <= 23:
        raise ValueError("Stunde außerhalb 0..23")
    if not 0 <= minute <= 59:
        raise ValueError("Minute außerhalb 0..59")
    return ((hour & 0xFF) << 8) | (minute & 0xFF)

def decode_hhmm(value: int) -> tuple[int, int]:
    return (value >> 8) & 0xFF, value & 0xFF

class TimerEditorDialog(QDialog):
    """Editor für Timer 1..6.

    Registerschema laut Display-Firmware/ASM:
    Timer n: base = 1281 + (n-1)*7
      +0 Ein-Zeit, +1 Aus-Zeit, +2 WW, +3 HZ, +4 Kühlen, +5 Modus, +6 max. Leistung
    Bitmasken: 1323=Timer1+2, 1324=Timer3+4, 1325=Timer5+6.
    """
    TIMER_REGS = set(range(1281, 1326))
    CAPABILITY_REGS = {1021, 1028}  # H05 Kühlen vorhanden, H28 WW vorhanden
    DAY_BITS = [
        ("Mo", 0x01),
        ("Di", 0x02),
        ("Mi", 0x04),
        ("Do", 0x08),
        ("Fr", 0x10),
        ("Sa", 0x20),
        ("So", 0x40),
    ]
    ACTIVE_BIT = 0x80
    MODE_ITEMS = [
        ("Warmwasser / Code 0", 0),
        ("Heizen / Code 1", 1),
        ("Kühlen / Code 2", 2),
        ("Warmwasser + Heizen / Code 3", 3),
        ("Warmwasser + Kühlen / Code 4", 4),
        ("keinen Modus ändern / Code 9", 9),
    ]

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self.fields: dict[int, dict[str, Any]] = {}
        self.setWindowTitle("Timer 1-6 Editor")
        self.setMinimumWidth(720)
        self.setMinimumHeight(560)
        self._build_ui()
        self.load_from_live_values()

    def _timer_base(self, timer_no: int) -> int:
        return 1281 + (timer_no - 1) * 7

    def _timer_bit_reg(self, timer_no: int) -> int:
        return 1323 + ((timer_no - 1) // 2)

    def _timer_uses_high_byte(self, timer_no: int) -> bool:
        return (timer_no % 2) == 0

    def _build_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Timer 1-6 werden live aus bekannten Registern aktualisiert. "
            "Wenn du gerade ein Feld bearbeitest, wird dieses Feld nicht überschrieben. "
            "Geschrieben wird standardmäßig nur der aktuell geöffnete Timer-Tab."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        # Timer-Editor nutzt die Standard-WP-Adresse. Die Busadresse bleibt bewusst
        # aus der Oberfläche raus, weil sie im Normalbetrieb nicht geändert wird.
        self.bus_edit = QLineEdit(f"0x{DEFAULT_BUS_ADDR:02X}")
        self.bus_edit.setVisible(False)
        self.auto_update_cb = QCheckBox("live aktualisieren")
        self.auto_update_cb.setChecked(True)
        self.status_label = QLabel("Bereit.")
        self.status_label.setMinimumWidth(220)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666;")
        top.addWidget(self.auto_update_cb)
        top.addStretch(1)
        top.addWidget(self.status_label)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        for timer_no in range(1, 7):
            self._add_timer_tab(timer_no)
        self.capability_label = QLabel("")
        self.capability_label.setWordWrap(True)
        layout.addWidget(self.capability_label)
        self._apply_capability_hints()

        bottom = QHBoxLayout()
        self.timer_delay_ms = QSpinBox()
        self.timer_delay_ms.setRange(0, 10000)
        self.timer_delay_ms.setSingleStep(100)
        self.timer_delay_ms.setValue(1200)
        self.timer_delay_ms.setSuffix(" ms")
        self.timer_delay_ms.setToolTip("Pause zwischen den einzelnen Registerwrites.")
        bottom.addWidget(QLabel("Pause zwischen Writes:"))
        bottom.addWidget(self.timer_delay_ms)
        bottom.addStretch(1)
        layout.addLayout(bottom)

        button_layout = QHBoxLayout()
        self.load_btn = QPushButton("Aus Live-Werten laden")
        self.read_btn = QPushButton("Alle Timer von WP lesen")
        self.send_btn = QPushButton("Aktiven Timer schreiben")
        self.send_all_btn = QPushButton("Alle 6 schreiben")
        self.close_btn = QPushButton("Schließen")
        self.load_btn.clicked.connect(self.load_from_live_values)
        self.read_btn.clicked.connect(self.read_from_wp)
        self.send_btn.clicked.connect(self.send_values)
        self.send_all_btn.clicked.connect(self.send_all_values)
        self.close_btn.clicked.connect(self.close)
        for w in (self.load_btn, self.read_btn, self.send_btn, self.send_all_btn):
            button_layout.addWidget(w)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)


    def set_write_status(self, text: str) -> None:
        self.status_label.setText(str(text))

    def _add_timer_tab(self, timer_no: int):
        widget = QWidget()
        form = QFormLayout(widget)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        base = self._timer_base(timer_no)
        bit_reg = self._timer_bit_reg(timer_no)
        high = self._timer_uses_high_byte(timer_no)
        byte_label = "High-Byte" if high else "Low-Byte"

        on_hour = QSpinBox(); on_hour.setRange(0, 23)
        on_min = QSpinBox(); on_min.setRange(0, 59)
        on_layout = QHBoxLayout(); on_layout.addWidget(on_hour); on_layout.addWidget(QLabel(":")); on_layout.addWidget(on_min); on_layout.addStretch(1)

        off_hour = QSpinBox(); off_hour.setRange(0, 23)
        off_min = QSpinBox(); off_min.setRange(0, 59)
        off_layout = QHBoxLayout(); off_layout.addWidget(off_hour); off_layout.addWidget(QLabel(":")); off_layout.addWidget(off_min); off_layout.addStretch(1)

        ww_temp = QDoubleSpinBox(); ww_temp.setRange(-50.0, 95.0); ww_temp.setDecimals(1); ww_temp.setSingleStep(0.5); ww_temp.setSuffix(" °C")
        heat_temp = QDoubleSpinBox(); heat_temp.setRange(-50.0, 95.0); heat_temp.setDecimals(1); heat_temp.setSingleStep(0.5); heat_temp.setSuffix(" °C")
        cool_temp = QDoubleSpinBox(); cool_temp.setRange(-50.0, 95.0); cool_temp.setDecimals(1); cool_temp.setSingleStep(0.5); cool_temp.setSuffix(" °C")

        power_kw = QDoubleSpinBox(); power_kw.setRange(0.0, 20.0); power_kw.setDecimals(1); power_kw.setSingleStep(0.1); power_kw.setSuffix(" kW")
        power_raw = QSpinBox(); power_raw.setRange(0, 0xFFFF)
        power_layout = QHBoxLayout(); power_layout.addWidget(power_kw); power_layout.addWidget(QLabel("Raw:")); power_layout.addWidget(power_raw); power_layout.addStretch(1)

        active_cb = QCheckBox("Timer aktiv")
        day_raw = QSpinBox(); day_raw.setRange(0, 0xFFFF)
        day_raw.setToolTip(f"Register {bit_reg}: {byte_label} = Timer {timer_no}, anderes Byte wird erhalten.")
        day_layout = QVBoxLayout()
        day_top = QHBoxLayout(); day_top.addWidget(active_cb); day_top.addWidget(QLabel(f"Reg {bit_reg}, {byte_label}, Raw:")); day_top.addWidget(day_raw); day_top.addStretch(1)
        day_layout.addLayout(day_top)
        checks = []
        day_bits_layout = QHBoxLayout()
        for label, bit in self.DAY_BITS:
            cb = QCheckBox(label)
            cb.setProperty("day_bit", bit)
            checks.append(cb)
            day_bits_layout.addWidget(cb)
        day_bits_layout.addStretch(1)
        day_layout.addLayout(day_bits_layout)

        mode_combo = QComboBox()
        mode_combo.addItem("Raw-Code verwenden", -1)
        for text, code in self.MODE_ITEMS:
            mode_combo.addItem(text, code)
        mode_raw = QSpinBox(); mode_raw.setRange(0, 0xFFFF)
        mode_layout = QHBoxLayout(); mode_layout.addWidget(mode_combo, 1); mode_layout.addWidget(QLabel("Raw:")); mode_layout.addWidget(mode_raw)

        form.addRow(f"Ein ({base}):", on_layout)
        form.addRow(f"Aus ({base + 1}):", off_layout)
        form.addRow(f"WW Ziel ({base + 2}):", ww_temp)
        form.addRow(f"HZ Ziel ({base + 3}):", heat_temp)
        form.addRow(f"Kühlen Ziel ({base + 4}):", cool_temp)
        form.addRow(f"Max. Leistung ({base + 6}):", power_layout)
        form.addRow(f"Tage/Aktiv ({bit_reg}):", day_layout)
        form.addRow(f"Modus ({base + 5}):", mode_layout)

        fld = {
            "base": base,
            "bit_reg": bit_reg,
            "byte_high": high,
            "on_hour": on_hour, "on_min": on_min,
            "off_hour": off_hour, "off_min": off_min,
            "ww_temp": ww_temp, "heat_temp": heat_temp, "cool_temp": cool_temp,
            "power_kw": power_kw, "power_raw": power_raw,
            "active_cb": active_cb, "day_raw": day_raw, "day_checks": checks,
            "mode_combo": mode_combo, "mode_raw": mode_raw,
        }
        self.fields[timer_no] = fld

        power_kw.valueChanged.connect(lambda _=None, t=timer_no: self._power_kw_changed(t))
        power_raw.valueChanged.connect(lambda _=None, t=timer_no: self._power_raw_changed(t))
        active_cb.stateChanged.connect(lambda _=None, t=timer_no: self._day_controls_changed(t))
        day_raw.valueChanged.connect(lambda value, t=timer_no: self._day_raw_changed(t, int(value)))
        for cb in checks:
            cb.stateChanged.connect(lambda _=None, t=timer_no: self._day_controls_changed(t))
        mode_combo.currentIndexChanged.connect(lambda _=None, t=timer_no: self._mode_combo_changed(t))
        mode_raw.valueChanged.connect(lambda value, t=timer_no: self._mode_raw_changed(t, int(value)))

        self.tabs.addTab(widget, f"Timer {timer_no}")

    def _current_timer_no(self) -> int:
        return max(1, min(6, self.tabs.currentIndex() + 1))

    def _has_focus(self, *widgets: QWidget) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        for widget in widgets:
            if focus is widget or widget.isAncestorOf(focus):
                return True
        return False

    def _set_spin_value(self, widget, value, force: bool = False):
        if not force and self._has_focus(widget):
            return
        if isinstance(widget, QDoubleSpinBox):
            if abs(float(widget.value()) - float(value)) > 0.0001:
                widget.setValue(float(value))
        else:
            if int(widget.value()) != int(value):
                widget.setValue(int(value))

    def _set_time_widgets(self, hour_widget: QSpinBox, min_widget: QSpinBox, raw_value: int, force: bool = False):
        if not force and self._has_focus(hour_widget, min_widget):
            return
        hour, minute = decode_hhmm(raw_value)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            self._set_spin_value(hour_widget, hour, force=True)
            self._set_spin_value(min_widget, minute, force=True)

    def _power_kw_changed(self, timer_no: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        self._programmatic = True
        try:
            fld["power_raw"].setValue(int(round(float(fld["power_kw"].value()) * 10.0)) & 0xFFFF)
        finally:
            self._programmatic = False

    def _power_raw_changed(self, timer_no: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        self._programmatic = True
        try:
            fld["power_kw"].setValue(int(fld["power_raw"].value()) / 10.0)
        finally:
            self._programmatic = False

    def _timer_day_byte_from_controls(self, timer_no: int) -> int:
        fld = self.fields[timer_no]
        raw = self.ACTIVE_BIT if fld["active_cb"].isChecked() else 0
        for cb in fld["day_checks"]:
            if cb.isChecked():
                raw |= int(cb.property("day_bit"))
        return raw & 0x00FF

    def _set_day_controls_from_byte(self, timer_no: int, byte_value: int):
        fld = self.fields[timer_no]
        fld["active_cb"].setChecked(bool(byte_value & self.ACTIVE_BIT))
        for cb in fld["day_checks"]:
            cb.setChecked(bool(byte_value & int(cb.property("day_bit"))))

    def _day_controls_changed(self, timer_no: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        current_pair = int(fld["day_raw"].value()) & 0xFFFF
        byte = self._timer_day_byte_from_controls(timer_no)
        if fld["byte_high"]:
            raw = (current_pair & 0x00FF) | (byte << 8)
        else:
            raw = (current_pair & 0xFF00) | byte
        self._programmatic = True
        try:
            fld["day_raw"].setValue(raw & 0xFFFF)
        finally:
            self._programmatic = False

    def _day_raw_changed(self, timer_no: int, value: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        byte = ((int(value) >> 8) & 0xFF) if fld["byte_high"] else (int(value) & 0xFF)
        self._programmatic = True
        try:
            self._set_day_controls_from_byte(timer_no, byte)
        finally:
            self._programmatic = False

    def _mode_combo_changed(self, timer_no: int):
        fld = self.fields[timer_no]
        data = fld["mode_combo"].currentData()
        if data is not None and int(data) >= 0 and fld["mode_raw"].value() != int(data):
            fld["mode_raw"].setValue(int(data))

    def _mode_raw_changed(self, timer_no: int, value: int):
        fld = self.fields[timer_no]
        for idx in range(fld["mode_combo"].count()):
            data = fld["mode_combo"].itemData(idx)
            if data is not None and int(data) == int(value):
                fld["mode_combo"].setCurrentIndex(idx)
                return
        fld["mode_combo"].setCurrentIndex(0)

    def _capability_values(self) -> tuple[bool, bool]:
        cool_reg = self.main_window.latest_regs.get(1021)
        ww_reg = self.main_window.latest_regs.get(1028)
        cooling = True if cool_reg is None else bool(int(cool_reg.raw_value))
        dhw = True if ww_reg is None else bool(int(ww_reg.raw_value))
        return cooling, dhw

    def _set_combo_item_enabled(self, combo: QComboBox, index: int, enabled: bool):
        item = combo.model().item(index) if combo.model() is not None else None
        if item is not None:
            item.setEnabled(enabled)

    def _apply_capability_hints(self):
        cooling, dhw = self._capability_values()
        text = f"Ausstattung erkannt: Kühlen={'ja' if cooling else 'nein/unbekannt deaktiviert'}, WW={'ja' if dhw else 'nein/unbekannt deaktiviert'}"
        if not cooling or not dhw:
            text += " — nicht passende Modus-Auswahlen sind ausgegraut."
        if hasattr(self, "capability_label"):
            self.capability_label.setText(text)
        for fld in self.fields.values():
            combo = fld["mode_combo"]
            for idx in range(combo.count()):
                code = combo.itemData(idx)
                enabled = True
                if code is not None and int(code) >= 0:
                    code = int(code)
                    needs_ww = code in (0, 3, 4)
                    needs_cooling = code in (2, 4)
                    if needs_ww and not dhw:
                        enabled = False
                    if needs_cooling and not cooling:
                        enabled = False
                self._set_combo_item_enabled(combo, idx, enabled)

    def load_from_live_values(self):
        for reg_no in sorted(self.TIMER_REGS | self.CAPABILITY_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg, force=True)
        self._apply_capability_hints()
        # V0.2.41 fix5: Wenn noch kein 1271ff-/Timer-Livewert geladen ist,
        # keine scheinbar sinnvollen Fantasie-Defaults mehr setzen. Leere
        # Timerfelder bleiben konsequent 0, damit ein zu früh geöffnetes Popup
        # nicht 15:00/19:00/55°C/45°C/7°C in den Dialog übernimmt.
        self._programmatic = True
        try:
            for timer_no, fld in self.fields.items():
                base = fld["base"]
                if self.main_window.latest_regs.get(base) is None:
                    self._set_time_widgets(fld["on_hour"], fld["on_min"], encode_hhmm(0, 0), force=True)
                if self.main_window.latest_regs.get(base + 1) is None:
                    self._set_time_widgets(fld["off_hour"], fld["off_min"], encode_hhmm(0, 0), force=True)
                if self.main_window.latest_regs.get(base + 2) is None:
                    fld["ww_temp"].setValue(0.0)
                if self.main_window.latest_regs.get(base + 3) is None:
                    fld["heat_temp"].setValue(0.0)
                if self.main_window.latest_regs.get(base + 4) is None:
                    fld["cool_temp"].setValue(0.0)
                if self.main_window.latest_regs.get(base + 5) is None:
                    fld["mode_raw"].setValue(0)
                    self._mode_raw_changed(timer_no, 0)
                if self.main_window.latest_regs.get(base + 6) is None:
                    fld["power_raw"].setValue(0)
                    fld["power_kw"].setValue(0.0)
                bit_reg = fld["bit_reg"]
                if self.main_window.latest_regs.get(bit_reg) is None:
                    fld["day_raw"].setValue(0)
                    self._set_day_controls_from_byte(timer_no, 0)
        finally:
            self._programmatic = False

    def update_from_live_register(self, reg, force: bool = False):
        reg_no = int(reg.reg)
        if reg_no not in self.TIMER_REGS and reg_no not in self.CAPABILITY_REGS:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        if reg_no in self.CAPABILITY_REGS:
            self._apply_capability_hints()
            return
        raw = int(reg.raw_value) & 0xFFFF
        self._programmatic = True
        try:
            if 1281 <= reg_no <= 1322:
                timer_no = ((reg_no - 1281) // 7) + 1
                offset = (reg_no - 1281) % 7
                fld = self.fields.get(timer_no)
                if not fld:
                    return
                if offset == 0:
                    self._set_time_widgets(fld["on_hour"], fld["on_min"], raw, force=force)
                elif offset == 1:
                    self._set_time_widgets(fld["off_hour"], fld["off_min"], raw, force=force)
                elif offset == 2:
                    self._set_spin_value(fld["ww_temp"], raw / 10.0, force=force)
                elif offset == 3:
                    self._set_spin_value(fld["heat_temp"], raw / 10.0, force=force)
                elif offset == 4:
                    self._set_spin_value(fld["cool_temp"], raw / 10.0, force=force)
                elif offset == 5:
                    self._set_spin_value(fld["mode_raw"], raw, force=force)
                    self._mode_raw_changed(timer_no, raw)
                elif offset == 6:
                    if force or not self._has_focus(fld["power_kw"], fld["power_raw"]):
                        fld["power_raw"].setValue(raw)
                        fld["power_kw"].setValue(raw / 10.0)
            elif 1323 <= reg_no <= 1325:
                first_timer = 1 + (reg_no - 1323) * 2
                for timer_no in (first_timer, first_timer + 1):
                    fld = self.fields.get(timer_no)
                    if not fld:
                        continue
                    if not (force or not self._has_focus(fld["active_cb"], fld["day_raw"], *fld["day_checks"])):
                        continue
                    fld["day_raw"].setValue(raw)
                    byte = ((raw >> 8) & 0xFF) if fld["byte_high"] else (raw & 0xFF)
                    self._set_day_controls_from_byte(timer_no, byte)
        finally:
            self._programmatic = False

    def silent_timer_values(self) -> list[tuple[int, int, str]]:
        return [
            (1244, 1 if self.silent_start_enable_cb.isChecked() else 0, "Silentmodus Start aktiv"),
            (1245, int(self.silent_start_hour.value()) & 0xFFFF, "Silentmodus Start Stunde"),
            (1246, int(self.silent_start_min.value()) & 0xFFFF, "Silentmodus Start Minute"),
            (1247, 1 if self.silent_stop_enable_cb.isChecked() else 0, "Silentmodus Stop aktiv"),
            (1248, int(self.silent_stop_hour.value()) & 0xFFFF, "Silentmodus Stop Stunde"),
            (1249, int(self.silent_stop_min.value()) & 0xFFFF, "Silentmodus Stop Minute"),
        ]

    def timer_values(self, timer_no: Optional[int] = None) -> list[tuple[int, int, str]]:
        if timer_no is None:
            timer_no = self._current_timer_no()
        fld = self.fields[timer_no]
        base = fld["base"]
        bit_reg = fld["bit_reg"]
        return [
            (base, encode_hhmm(int(fld["on_hour"].value()), int(fld["on_min"].value())), f"Timer {timer_no} Ein"),
            (base + 1, encode_hhmm(int(fld["off_hour"].value()), int(fld["off_min"].value())), f"Timer {timer_no} Aus"),
            (base + 2, int(round(float(fld["ww_temp"].value()) * 10.0)) & 0xFFFF, f"Timer {timer_no} WW Zieltemperatur"),
            (base + 3, int(round(float(fld["heat_temp"].value()) * 10.0)) & 0xFFFF, f"Timer {timer_no} HZ Zieltemperatur"),
            (base + 4, int(round(float(fld["cool_temp"].value()) * 10.0)) & 0xFFFF, f"Timer {timer_no} Kuehlen Zieltemperatur"),
            (base + 6, int(fld["power_raw"].value()) & 0xFFFF, f"Timer {timer_no} max. Leistung"),
            (bit_reg, int(fld["day_raw"].value()) & 0xFFFF, f"Timer {timer_no} Aktiv/Tage + Partner-Byte erhalten"),
            (base + 5, int(fld["mode_raw"].value()) & 0xFFFF, f"Timer {timer_no} Modus-Code"),
        ]

    def _pair_raw_from_controls(self, first_timer_no: int) -> int:
        low = self._timer_day_byte_from_controls(first_timer_no)
        high = self._timer_day_byte_from_controls(first_timer_no + 1)
        return ((high & 0xFF) << 8) | (low & 0xFF)

    def all_timer_values(self) -> list[tuple[int, int, str]]:
        out: list[tuple[int, int, str]] = []
        for timer_no in range(1, 7):
            for addr, value, label in self.timer_values(timer_no):
                if addr not in (1323, 1324, 1325):
                    out.append((addr, value, label))
        for first_timer, reg_no in ((1, 1323), (3, 1324), (5, 1325)):
            out.append((reg_no, self._pair_raw_from_controls(first_timer), f"Timer {first_timer}+{first_timer+1} Aktiv/Tage"))
        return out

    def _dry_run_lines(self, values: list[tuple[int, int, str]], slave_addr: int) -> list[str]:
        # PRIVATE fix53: Im Display-Bus nutzen Timer-/SG-/Popup-Mehrfachwrites
        # denselben Bedienwertpfad wie normale Display-Parameterwrites. Der Dry-Run
        # soll deshalb nicht mehr faelschlich direkte 12xx/13xx-FC06-Frames anzeigen.
        helper = getattr(self.main_window, "_timer_write_preview_lines", None)
        if callable(helper):
            return helper(values, slave_addr)
        lines = []
        for addr, value, label in values:
            frame, wire_addr, wire_slave, note, fc_text = self.main_window._build_write_frame_for_backend(addr, value, slave_addr)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")
        return lines

    def show_dry_run(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            lines = self._dry_run_lines(self.timer_values(), slave_addr)
            self.main_window._log("TIMER Dry-Run aktiver Tab:\n" + "\n".join(lines))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def show_dry_run_all(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            lines = self._dry_run_lines(self.all_timer_values(), slave_addr)
            self.main_window._log("TIMER Dry-Run alle 6:\n" + "\n".join(lines))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    TIMER_READ_LABEL = "Timer Bereich 1281-1325"

    def read_from_wp(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.status_label.setText("Lese Betriebsart Timer 1281-1325 ...")
            self.main_window.send_read_request(1281, 45, slave_addr=slave_addr, label=self.TIMER_READ_LABEL)
            self.main_window._log("TIMER Lesen angefordert. Offenes Timerfenster aktualisiert sich bei eintreffenden Werten automatisch.")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Leseanforderung", str(exc))

    def on_timer_read_response(self, label: str, start_addr: int, quantity: int):
        if label == self.TIMER_READ_LABEL and int(start_addr) == 1281 and int(quantity) == 45:
            self.status_label.setText("Betriebsart Timer erfolgreich gelesen.")

    def show_timer_read_timeout(self, label: str, start_addr: int, quantity: int):
        if label == self.TIMER_READ_LABEL and int(start_addr) == 1281 and int(quantity) == 45:
            self.status_label.setText("Betriebsart Timer Timeout. Vorhandene Live-Werte bleiben erhalten.")

    def send_values(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            timer_no = self._current_timer_no()
            self.main_window.send_timer_values(slave_addr, self.timer_values(timer_no), int(self.timer_delay_ms.value()), title=f"Timer {timer_no}")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def send_all_values(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.send_timer_values(slave_addr, self.all_timer_values(), int(self.timer_delay_ms.value()), title="Alle Timer 1-6")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

class SilentTimerDialog(QDialog):
    TIMER_REGS = set(range(1244, 1250))

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Silentmodus Timer")
        self.setMinimumWidth(520)
        self.setMinimumHeight(280)
        self._build_ui()
        self.load_from_live_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("Silentmodus Timer: Start und Stop können getrennt aktiviert werden. Register 1244-1249.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.status_label = QLabel("Bereit.")
        self.status_label.setMinimumWidth(220)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

        form = QFormLayout()
        self.start_enable_cb = QCheckBox("Start aktiv")
        self.stop_enable_cb = QCheckBox("Stop aktiv")
        self.start_hour = QSpinBox(); self.start_hour.setRange(0, 23)
        self.start_min = QSpinBox(); self.start_min.setRange(0, 59)
        self.stop_hour = QSpinBox(); self.stop_hour.setRange(0, 23)
        self.stop_min = QSpinBox(); self.stop_min.setRange(0, 59)
        start_time = QHBoxLayout(); start_time.addWidget(self.start_hour); start_time.addWidget(QLabel(":")); start_time.addWidget(self.start_min); start_time.addStretch(1)
        stop_time = QHBoxLayout(); stop_time.addWidget(self.stop_hour); stop_time.addWidget(QLabel(":")); stop_time.addWidget(self.stop_min); stop_time.addStretch(1)
        form.addRow("Ein aktiv (1244):", self.start_enable_cb)
        form.addRow("Ein Zeit (1245/1246):", start_time)
        form.addRow("Aus aktiv (1247):", self.stop_enable_cb)
        form.addRow("Aus Zeit (1248/1249):", stop_time)
        layout.addLayout(form)

        bottom = QHBoxLayout()
        self.timer_delay_ms = QSpinBox(); self.timer_delay_ms.setRange(0, 10000); self.timer_delay_ms.setValue(1200); self.timer_delay_ms.setSuffix(" ms")
        bottom.addWidget(QLabel("Pause zwischen Writes:")); bottom.addWidget(self.timer_delay_ms); bottom.addStretch(1)
        layout.addLayout(bottom)

        buttons = QHBoxLayout()
        self.load_btn = QPushButton("Aus Live-Werten laden")
        self.read_btn = QPushButton("von WP lesen")
        self.dry_btn = QPushButton("Dry-Run")
        self.send_btn = QPushButton("schreiben")
        self.close_btn = QPushButton("Schließen")
        self.load_btn.clicked.connect(self.load_from_live_values)
        self.read_btn.clicked.connect(self.read_from_wp)
        self.dry_btn.clicked.connect(self.show_dry_run)
        self.send_btn.clicked.connect(self.send_values)
        self.close_btn.clicked.connect(self.close)
        for w in (self.load_btn, self.read_btn, self.dry_btn, self.send_btn):
            buttons.addWidget(w)
        buttons.addStretch(1); buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def set_write_status(self, text: str) -> None:
        self.status_label.setText(str(text))

    def load_from_live_values(self):
        for reg_no in sorted(self.TIMER_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg)

    def update_from_live_register(self, reg):
        reg_no = int(reg.reg)
        raw = int(reg.raw_value) & 0xFFFF
        if reg_no == 1244:
            self.start_enable_cb.setChecked(bool(raw))
        elif reg_no == 1245:
            self.start_hour.setValue(max(0, min(23, raw)))
        elif reg_no == 1246:
            self.start_min.setValue(max(0, min(59, raw)))
        elif reg_no == 1247:
            self.stop_enable_cb.setChecked(bool(raw))
        elif reg_no == 1248:
            self.stop_hour.setValue(max(0, min(23, raw)))
        elif reg_no == 1249:
            self.stop_min.setValue(max(0, min(59, raw)))

    def timer_values(self) -> list[tuple[int, int, str]]:
        return [
            (1244, 1 if self.start_enable_cb.isChecked() else 0, "Silentmodus Start aktiv"),
            (1245, int(self.start_hour.value()) & 0xFFFF, "Silentmodus Start Stunde"),
            (1246, int(self.start_min.value()) & 0xFFFF, "Silentmodus Start Minute"),
            (1247, 1 if self.stop_enable_cb.isChecked() else 0, "Silentmodus Stop aktiv"),
            (1248, int(self.stop_hour.value()) & 0xFFFF, "Silentmodus Stop Stunde"),
            (1249, int(self.stop_min.value()) & 0xFFFF, "Silentmodus Stop Minute"),
        ]

    def _dry_run_lines(self) -> list[str]:
        lines = []
        for addr, value, label in self.timer_values():
            frame, wire_addr, wire_slave, note, fc_text = self.main_window._build_write_frame_for_backend(addr, value, DEFAULT_BUS_ADDR)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")
        return lines

    def show_dry_run(self):
        self.main_window._log("SILENT TIMER Dry-Run:\n" + "\n".join(self._dry_run_lines()))

    def read_from_wp(self):
        self.main_window.send_read_request(1244, 6, slave_addr=DEFAULT_BUS_ADDR, label="Silentmodus Timer 1244-1249")
        self.main_window._log("Silentmodus Timer Lesen angefordert.")

    def send_values(self):
        self.main_window.send_timer_values(DEFAULT_BUS_ADDR, self.timer_values(), int(self.timer_delay_ms.value()), title="Silentmodus Timer")
