from __future__ import annotations

from cloud.cloud_write_helpers import SILENT_TIMER_CODES, SILENT_TIMER_LIMITS
from dialogs.targeted_cloud import TargetedCloudDialogMixin
from cloud.operating_timer import M_TIMER_CODES

from typing import Any, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox,
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

class TimerEditorDialog(TargetedCloudDialogMixin, QDialog):
    """Existing six-tab editor, with raw baselines and byte-level draft tracking."""
    CLOUD_REGISTERS = M_TIMER_CODES
    CLOUD_PURPOSE = 'operating_timer'
    TIMER_REGS = set(range(1281, 1326))
    CAPABILITY_REGS = {1021, 1028}
    LOCAL_WRITE_DELAY_MS = 1200
    TIMER_READ_LABEL = 'Timer Bereich 1281-1325'
    DAY_BITS = [('Mo', 1), ('Di', 2), ('Mi', 4), ('Do', 8), ('Fr', 16), ('Sa', 32), ('So', 64)]
    ACTIVE_BIT = 0x80
    MODE_ITEMS = [('Warmwasser', 0), ('Heizen', 1), ('Kühlen', 2),
                  ('Warmwasser + Heizen', 3), ('Warmwasser + Kühlen', 4),
                  ('keinen Modus ändern', 9)]

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self._baseline, self._pending = {}, {}
        self._dirty, self._dirty_days = set(), set()
        self.fields = {}
        self.setWindowTitle('Betriebsart Timer 1-6')
        self.setMinimumSize(720, 550)
        layout = QVBoxLayout(self)
        hint = QLabel('Zeiten, Wochentage und Zielwerte je Timer einstellen. Nur Änderungen werden geschrieben; offene Eingaben bleiben erhalten.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.status_label = QLabel('Noch keine aktuellen Timerwerte gelesen.')
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        for timer in range(1, 7):
            self._add_timer_tab(timer)
        self.capability_label = QLabel()
        self.capability_label.setWordWrap(True)
        layout.addWidget(self.capability_label)
        buttons = QHBoxLayout()
        self.read_btn = QPushButton('Neu lesen')
        self.send_btn = QPushButton('Aktiven Timer schreiben')
        self.send_all_btn = QPushButton('Alle 6 schreiben')
        self.close_btn = QPushButton('Schließen')
        for button, action in ((self.read_btn, self.read_from_wp), (self.send_btn, self.send_values),
                               (self.send_all_btn, self.send_all_values), (self.close_btn, self.close)):
            buttons.addWidget(button)
            button.clicked.connect(action)
        layout.addLayout(buttons)
        self.tabs.currentChanged.connect(self._update_cloud_actions)
        self._init_cloud_snapshot()
        self.load_from_live_values()
        self._render_values()

    def _timer_base(self, timer):
        return 1281 + (timer - 1) * 7

    def _timer_bit_reg(self, timer):
        return 1323 + (timer - 1) // 2

    def _timer_uses_high_byte(self, timer):
        return timer % 2 == 0

    def _current_timer_no(self):
        return self.tabs.currentIndex() + 1

    def _add_timer_tab(self, timer):
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        base, mask = self._timer_base(timer), self._timer_bit_reg(timer)
        f = {'base': base, 'bit_reg': mask, 'byte_high': self._timer_uses_high_byte(timer)}
        for kind, offset, label in (('on', 0, 'Startzeit:'), ('off', 1, 'Endzeit:')):
            row = QHBoxLayout()
            for suffix, maximum in (('hour', 23), ('min', 59)):
                spin = QSpinBox(); spin.setRange(0, maximum)
                spin.setToolTip(f'MAIN:{base + offset} · Stunde im High-Byte, Minute im Low-Byte')
                f[f'{kind}_{suffix}'] = spin
                if suffix == 'min': row.addWidget(QLabel(':'))
                row.addWidget(spin)
                spin.valueChanged.connect(lambda _v, r=base+offset: self._edited(r))
            row.addStretch(1)
            form.addRow(label, row)
        days = QVBoxLayout()
        f['active_cb'] = QCheckBox('Timer aktiv')
        f['active_cb'].setToolTip(f'MAIN:{mask} · Bit 7 im eigenen Timer-Byte')
        days.addWidget(f['active_cb'])
        f['active_cb'].toggled.connect(lambda _v, r=mask, t=timer: self._edited(r, t))
        row = QHBoxLayout()
        f['day_checks'] = []
        for label, bit in self.DAY_BITS:
            cb = QCheckBox(label); cb.setProperty('day_bit', bit)
            cb.toggled.connect(lambda _v, r=mask, t=timer: self._edited(r, t))
            row.addWidget(cb); f['day_checks'].append(cb)
        row.addStretch(1); days.addLayout(row)
        form.addRow('Aktivierung / Tage:', days)
        combo = f['mode_combo'] = QComboBox()
        combo.addItem('Nicht gelesen', None)
        for label, code in self.MODE_ITEMS: combo.addItem(label, code)
        combo.setToolTip(f'MAIN:{base+5} · bekannte Codes 0–4 und 9')
        combo.currentIndexChanged.connect(lambda _v, r=base+5: self._edited(r))
        form.addRow('Betriebsart:', combo)
        for key, offset, label, power in (('heat_temp', 3, 'Heiz-Zieltemperatur:', False),
                ('cool_temp', 4, 'Kühl-Zieltemperatur:', False),
                ('ww_temp', 2, 'Warmwasser-Zieltemperatur:', False),
                ('power_kw', 6, 'Maximale Leistung:', True)):
            spin = QDoubleSpinBox(); spin.setDecimals(1); spin.setSingleStep(0.1)
            spin.setRange(0 if power else -3276.8, 3276.7)
            spin.setSuffix(' kW' if power else ' °C')
            spin.setToolTip(f'MAIN:{base+offset} · 0,1-Schritte; technische int16-Darstellung, keine bestätigte Herstellergrenze')
            spin.valueChanged.connect(lambda _v, r=base+offset: self._edited(r))
            f[key] = spin; form.addRow(label, spin)
        f['known_label'] = QLabel('Nicht gelesen')
        form.addRow('', f['known_label'])
        self.fields[timer] = f
        self.tabs.addTab(page, f'Timer {timer}')

    def _required(self, timers):
        return {reg for t in timers for reg in (*range(self._timer_base(t), self._timer_base(t)+7), self._timer_bit_reg(t))}

    def _day_widgets(self, timer):
        f = self.fields[timer]
        return [f['active_cb'], *f['day_checks']]

    def _timer_day_byte_from_controls(self, timer):
        f = self.fields[timer]
        return (128 if f['active_cb'].isChecked() else 0) | sum(int(cb.property('day_bit')) for cb in f['day_checks'] if cb.isChecked())

    def _byte(self, timer, word):
        return (word >> (8 if self._timer_uses_high_byte(timer) else 0)) & 255

    def _pair(self, reg, timers):
        if reg not in self._baseline:
            raise ValueError(f'Tagesmaske {reg} / Partner-Byte nicht gelesen; zuerst neu lesen.')
        word = self._baseline[reg]
        for timer in timers:
            if self._timer_bit_reg(timer) == reg:
                shift = 8 if self._timer_uses_high_byte(timer) else 0
                word = (word & ~(255 << shift)) | (self._timer_day_byte_from_controls(timer) << shift)
        return word

    def _value(self, reg):
        timer, offset = (reg-1281)//7+1, (reg-1281)%7
        f = self.fields[timer]
        if offset in (0, 1):
            kind = 'on' if offset == 0 else 'off'
            return encode_hhmm(f[kind+'_hour'].value(), f[kind+'_min'].value())
        if offset == 5:
            value = f['mode_combo'].currentData()
            if value is None: raise ValueError('Betriebsart nicht gelesen')
            return int(value)
        key = {2: 'ww_temp', 3: 'heat_temp', 4: 'cool_temp', 6: 'power_kw'}[offset]
        return int(round(f[key].value()*10)) & 65535

    def _edited(self, reg, timer=None):
        if self._programmatic: return
        if timer is not None:
            desired = self._timer_day_byte_from_controls(timer)
            baseline = self._baseline.get(reg)
            different = baseline is None or desired != self._byte(timer, baseline)
            if reg in self._pending and desired != self._byte(timer, self._pending[reg]): different = True
            (self._dirty_days.add if different else self._dirty_days.discard)(timer)
        else:
            try: desired = self._value(reg)
            except ValueError: return
            different = desired != self._baseline.get(reg)
            if reg in self._pending and desired != self._pending[reg]: different = True
            (self._dirty.add if different else self._dirty.discard)(reg)
        self._update_cloud_actions()

    def _widgets(self, reg):
        f = self.fields[(reg-1281)//7+1]
        off = (reg-1281)%7
        if off in (0, 1):
            kind = 'on' if off == 0 else 'off'
            return [f[kind+'_hour'], f[kind+'_min']]
        return [f[{2: 'ww_temp', 3: 'heat_temp', 4: 'cool_temp', 5: 'mode_combo', 6: 'power_kw'}[off]]]

    def _render_values(self):
        from core.foxair_phnix_core import s16
        self._programmatic = True
        try:
            for reg in range(1281, 1323):
                widgets, raw = self._widgets(reg), self._baseline.get(reg)
                if reg in self._dirty: continue
                for w in widgets: w.setEnabled(raw is not None)
                if raw is None:
                    for w in widgets:
                        if isinstance(w, QComboBox): w.setCurrentIndex(0)
                        else:
                            w.setSpecialValueText('—'); w.setValue(w.minimum())
                    continue
                offset = (reg-1281)%7
                if offset == 5:
                    combo = widgets[0]
                    index = combo.findData(raw)
                    if index < 0:
                        combo.addItem(f'Unbekannter Code {raw}', raw)
                        index = combo.count()-1
                        combo.model().item(index).setEnabled(False)
                    combo.setCurrentIndex(index)
                else:
                    values = decode_hhmm(raw) if offset in (0, 1) else (s16(raw)/10,)
                    for w, value in zip(widgets, values):
                        w.setSpecialValueText('')
                        w.setValue(value)
                        # Refresh a valid zero after an unread/blank field.
                        w.lineEdit().setText(w.textFromValue(w.value()) + w.suffix())
            for timer, f in self.fields.items():
                raw = self._baseline.get(f['bit_reg'])
                if timer not in self._dirty_days:
                    for w in self._day_widgets(timer): w.setEnabled(raw is not None)
                    if raw is not None:
                        byte = self._byte(timer, raw)
                        f['active_cb'].setChecked(bool(byte & 128))
                        for cb in f['day_checks']: cb.setChecked(bool(byte & int(cb.property('day_bit'))))
                needed = self._required((timer,))
                count = len(needed & self._baseline.keys())
                f['known_label'].setText(f'{count}/8 Werte gelesen' + (' · Daten unvollständig' if count < 8 else ''))
        finally:
            self._programmatic = False
        self._apply_capability_hints()
        self._update_cloud_actions()

    def _apply_capability_hints(self):
        cooling = dhw = True
        if self.main_window.control_transport() != 'cloud':
            for reg, key in ((1021, 'cooling'), (1028, 'dhw')):
                value = self.main_window.latest_regs.get(reg)
                if value is not None and getattr(value, 'value_source', 'modbus') == 'modbus':
                    if key == 'cooling': cooling = bool(value.raw_value)
                    else: dhw = bool(value.raw_value)
        for f in self.fields.values():
            combo = f['mode_combo']
            for i in range(combo.count()):
                code = combo.itemData(i)
                valid = code in (0, 1, 2, 3, 4, 9)
                combo.model().item(i).setEnabled(valid and (dhw or code not in (0, 3, 4)) and (cooling or code not in (2, 4)))
        self.capability_label.setText('Ausstattung: Kühlen deaktiviert.' if not cooling else '')
        if not dhw: self.capability_label.setText(self.capability_label.text() + ' Warmwasser deaktiviert.')

    def _accept_values(self, values, *, replace=False):
        if replace: self._baseline = dict(values)
        else: self._baseline.update(values)
        for reg in tuple(self._dirty):
            if (self._baseline.get(reg) == self._value(reg)
                    and (reg not in self._pending or self._pending[reg] == self._value(reg))):
                self._dirty.discard(reg)
        for timer in tuple(self._dirty_days):
            raw = self._baseline.get(self._timer_bit_reg(timer))
            if (raw is not None and self._timer_day_byte_from_controls(timer) == self._byte(timer, raw)
                    and (self._timer_bit_reg(timer) not in self._pending
                         or self._timer_day_byte_from_controls(timer) == self._byte(timer, self._pending[self._timer_bit_reg(timer)]))):
                self._dirty_days.discard(timer)
        self._render_values()

    def _decode_cloud_row(self, row):
        from cloud.operating_timer import m_timer_word
        try: return m_timer_word(row['code'], row['value'], row)
        except (ValueError, TypeError): return None

    def _apply_cloud_snapshot(self, values):
        # A later manual fresh snapshot resolves an earlier ambiguous write.
        # Missing values remain open; snapshots cannot overtake an active write.
        if getattr(self.main_window, "cloud_write_thread", None) is None:
            for reg in values:
                self._pending.pop(reg, None)
        self._accept_values(values, replace=True)

    def _reset_cloud_source(self):
        self._baseline.clear(); self._pending.clear()
        self._dirty.clear(); self._dirty_days.clear()
        self._render_values()

    def connection_changed(self):
        previous = self._control_identity
        super().connection_changed()
        if previous != self._control_identity and self.isVisible() and self._control_identity.transport != 'cloud':
            self.initial_read_timer.start(250)
        self._update_cloud_actions()

    def _autoload_cloud(self):
        if self.main_window.control_transport() == 'cloud': super()._autoload_cloud()
        elif self.isVisible(): self.read_from_wp()

    def read_cloud_snapshot(self):
        super().read_cloud_snapshot()
        self._update_cloud_actions()

    def load_from_live_values(self, *, preserve_edits=True):
        if self.main_window.control_transport() == 'cloud': return
        if not preserve_edits: self._dirty.clear(); self._dirty_days.clear()
        for reg in sorted(self.TIMER_REGS):
            value = self.main_window.latest_regs.get(reg)
            if value is not None: self.update_from_live_register(value)

    def update_from_live_register(self, reg, force=False):
        from cloud.operating_timer import m_timer_word, m_timer_write_value
        if self.main_window.control_transport() == 'cloud' or getattr(reg, 'value_source', 'modbus') != 'modbus': return
        number = int(reg.reg)
        if number in self.CAPABILITY_REGS: self._apply_capability_hints(); return
        if number not in self.TIMER_REGS: return
        raw = reg.raw_value
        if not isinstance(raw, int) or not 0 <= raw <= 65535: return
        try:
            code = self.CLOUD_REGISTERS[number]
            # Unknown modes are valid read values, but never implicit new writes.
            if (number-1281)%7 != 5 or number >= 1323:
                m_timer_word(code, m_timer_write_value(code, raw))
        except ValueError:
            self._baseline.pop(number, None); self._render_values(); return
        self._accept_values({number: raw})
        if self._pending.get(number) == raw: self._pending.pop(number, None)

    def _update_cloud_actions(self, *_args):
        if not hasattr(self, 'send_btn'): return
        cloud = self.main_window.control_transport() == 'cloud'
        self.read_btn.setText('Cloud neu lesen' if cloud else 'Neu von WP lesen')
        allowed = bool(self.main_window.control_can_write()) and self.cloud_request is None
        for button, timers in ((self.send_btn, (self._current_timer_no(),)), (self.send_all_btn, tuple(range(1, 7)))):
            needed = self._required(timers)
            changed = bool(self._dirty & needed or self._dirty_days & set(timers))
            button.setEnabled(bool(allowed and needed <= self._baseline.keys() and changed))
            button.setToolTip('Nur Änderungen; alle benötigten Werte einschließlich Partner-Byte müssen gelesen sein.')

    def timer_values(self, timer_no=None):
        timer = timer_no or self._current_timer_no()
        return self._values_for((timer,))

    def all_timer_values(self):
        return self._values_for(tuple(range(1, 7)))

    def _values_for(self, timers):
        missing = self._required(timers) - self._baseline.keys()
        if missing: raise ValueError('Timerdaten / Partner-Byte unvollständig; zuerst frisch lesen: ' + ', '.join(map(str, sorted(missing))))
        out = [(reg, self._value(reg), f'Timer {t}') for t in timers for reg in range(self._timer_base(t), self._timer_base(t)+7)]
        out.extend((reg, self._pair(reg, timers), 'Timer Aktiv/Tage, Partner-Byte erhalten') for reg in sorted({self._timer_bit_reg(t) for t in timers}))
        return out

    def _send(self, timers):
        from cloud.operating_timer import m_timer_write_value
        self.connection_changed()
        if self.cloud_request is not None: self.status_label.setText('Lesen läuft; anschließend schreiben.'); return
        try:
            values = self._values_for(timers)
            writes = [(reg, raw, label) for reg, raw, label in values if raw != self._baseline[reg]]
            # Preflight every changed value before either local or Cloud I/O.
            for reg, raw, _label in writes: m_timer_write_value(self.CLOUD_REGISTERS[reg], raw)
            if not writes: self.status_label.setText('Keine geänderten Timerwerte.'); return
            if not self.main_window.control_can_write(*[reg for reg, _, _ in writes]):
                self.status_label.setText('Schreiben nicht verfügbar; Verbindung/Auftrag prüfen.'); return
            self._pending = {reg: raw for reg, raw, _ in writes}
            if self.main_window.control_transport() == 'cloud':
                baselines = {self.CLOUD_REGISTERS[reg]: self._baseline[reg] for reg in self._pending if reg >= 1323}
                error = self.main_window.control_write_registers([(reg, raw, None) for reg, raw, _ in writes],
                    'Betriebsart Timer Cloud', expected_context=self._control_identity, mask_baselines=baselines)
                self.status_label.setText(error or 'Cloud-Batch gesendet; frischen Readback abwarten …')
                if error: self._pending.clear()
            else:
                accepted = self.main_window.send_timer_values(DEFAULT_BUS_ADDR, writes, self.LOCAL_WRITE_DELAY_MS, title='Betriebsart Timer')
                if accepted is False: self._pending.clear()
        except (ValueError, RuntimeError) as exc:
            self.status_label.setText(str(exc))
        self._update_cloud_actions()

    def send_values(self): self._send((self._current_timer_no(),))
    def send_all_values(self): self._send(tuple(range(1, 7)))

    def set_write_status(self, text):
        self.status_label.setText(str(text)); self._update_cloud_actions()

    def write_readback_confirmed(self, register):
        if register in self._pending: self._accept_readback(register, self._pending[register])

    def write_readback_result(self, register, data):
        from dialogs.targeted_cloud import fresh_cloud_row
        row = data.get('readback') or {}
        if (self.isVisible() and self.main_window.control_context() == self._control_identity
                and data.get('readback_verified') and fresh_cloud_row(row)):
            raw = self._decode_cloud_row(row)
            if raw is not None: self._accept_readback(register, raw)

    def _accept_readback(self, reg, raw):
        if reg not in self._pending: return
        self._baseline[reg] = raw
        if self._pending[reg] == raw: self._pending.pop(reg, None)
        # Never repaint an editor from an older write result. Recompute drafts
        # against the verified state, including both bytes of a shared mask.
        if reg < 1323:
            (self._dirty.discard if self._value(reg) == raw else self._dirty.add)(reg)
        else:
            for t in range(1, 7):
                if self._timer_bit_reg(t) == reg:
                    (self._dirty_days.discard if self._timer_day_byte_from_controls(t) == self._byte(t, raw) else self._dirty_days.add)(t)
        self._update_cloud_actions()

    def read_from_wp(self):
        self.connection_changed()
        if self.main_window.control_transport() == 'cloud': self.read_cloud_snapshot(); return
        capability = self.main_window.control_can_read()
        if not capability: self.status_label.setText(capability.reason); return
        self.initial_read_timer.stop()
        self.status_label.setText('Lese Betriebsart Timer …')
        self.main_window.send_read_request(1281, 45, slave_addr=DEFAULT_BUS_ADDR, label=self.TIMER_READ_LABEL)

    def on_timer_read_response(self, label, start_addr, quantity):
        if label == self.TIMER_READ_LABEL and start_addr == 1281 and quantity == 45:
            self.status_label.setText(f'Betriebsart Timer: {len(self._baseline)}/45 Werte gelesen.')

    def show_timer_read_timeout(self, label, start_addr, quantity):
        if label == self.TIMER_READ_LABEL:
            self.status_label.setText('Betriebsart Timer Timeout; offene Änderungen bleiben erhalten.')


class SilentTimerDialog(TargetedCloudDialogMixin, QDialog):
    CLOUD_REGISTERS = SILENT_TIMER_CODES
    CLOUD_PURPOSE = "silent_timer"
    TIMER_REGS = set(range(1244, 1250))

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Silentmodus Timer")
        self.setMinimumWidth(520)
        self.setMinimumHeight(280)
        self._baseline = {}
        self._dirty = set()
        self._pending = {}
        self._programmatic = False
        self._build_ui()
        self._widgets = dict(zip(sorted(self.TIMER_REGS), (self.start_enable_cb, self.start_hour,
            self.start_min, self.stop_enable_cb, self.stop_hour, self.stop_min)))
        for register, widget in self._widgets.items():
            signal = widget.toggled if isinstance(widget, QCheckBox) else widget.valueChanged
            signal.connect(lambda _value, r=register: self._edited(r))
        self._init_cloud_snapshot()
        self.load_from_live_values()
        self._update_cloud_actions()

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
        self._update_cloud_actions()

    def load_from_live_values(self):
        if self.main_window.control_transport() == "cloud":
            self.read_cloud_snapshot()
            return
        for reg_no in sorted(self.TIMER_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg)

    def update_from_live_register(self, reg):
        if self.main_window.control_transport() == "cloud":
            return
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
        if self.main_window.control_transport() == "cloud":
            return [f"Cloud {self.CLOUD_REGISTERS[r]} = {v}" for r, v, _ in self.timer_values()
                    if r in self._dirty]
        lines = []
        for addr, value, label in self.timer_values():
            frame, wire_addr, wire_slave, note, fc_text = self.main_window._build_write_frame_for_backend(addr, value, DEFAULT_BUS_ADDR)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")
        return lines

    def show_dry_run(self):
        self.main_window._log("SILENT TIMER Dry-Run:\n" + "\n".join(self._dry_run_lines()))

    def read_from_wp(self):
        self.connection_changed()
        if self.main_window.control_transport() == "cloud":
            self.read_cloud_snapshot()
            return
        self.main_window.send_read_request(1244, 6, slave_addr=DEFAULT_BUS_ADDR, label="Silentmodus Timer 1244-1249")
        self.main_window._log("Silentmodus Timer Lesen angefordert.")

    def send_values(self):
        self.connection_changed()
        if self.main_window.control_transport() == "cloud":
            self._send_cloud_values()
            return
        self.main_window.send_timer_values(DEFAULT_BUS_ADDR, self.timer_values(), int(self.timer_delay_ms.value()), title="Silentmodus Timer")

    def _widget_value(self, register):
        widget = self._widgets[register]
        return int(widget.isChecked()) if isinstance(widget, QCheckBox) else widget.value()

    def _edited(self, register):
        if self._programmatic:
            return
        if self._widget_value(register) == self._baseline.get(register):
            self._dirty.discard(register)
        else:
            self._dirty.add(register)
        self._update_cloud_actions()

    def _validated_cloud_values(self, values):
        return {r: v for r, v in values.items() if v is not None
                and 0 <= v <= SILENT_TIMER_LIMITS[self.CLOUD_REGISTERS[r]]}

    def _apply_cloud_snapshot(self, values):
        # A partial fresh snapshot invalidates missing baselines, never edits.
        self._baseline = dict(values)
        self._programmatic = True
        try:
            for register, value in values.items():
                if register in self._dirty:
                    continue
                widget = self._widgets[register]
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                else:
                    widget.setValue(value)
        finally:
            self._programmatic = False
        for register in list(self._dirty):
            self._edited(register)
        self._update_cloud_actions()

    def _reset_cloud_source(self):
        self._baseline.clear()
        self._dirty.clear()
        self._pending.clear()
        self._programmatic = True
        try:
            for widget in self._widgets.values():
                if isinstance(widget, QCheckBox):
                    widget.setChecked(False)
                else:
                    widget.setValue(0)
        finally:
            self._programmatic = False

    def connection_changed(self):
        previous = self._control_identity
        super().connection_changed()
        if previous != self._control_identity and self._control_identity.transport != "cloud":
            self.load_from_live_values()
        self._update_cloud_actions()

    def _update_cloud_actions(self):
        cloud = self.main_window.control_transport() == "cloud"
        self.timer_delay_ms.setEnabled(not cloud)
        self.read_btn.setText("Cloud lesen" if cloud else "von WP lesen")
        self.load_btn.setText("Cloud neu laden" if cloud else "Aus Live-Werten laden")
        if cloud:
            capability = self.main_window.control_can_write(*self.TIMER_REGS)
            self.send_btn.setEnabled(bool(capability) and self.cloud_request is None
                                     and len(self._baseline) == 6 and bool(self._dirty))
            self.send_btn.setToolTip(capability.reason or "Alle sechs aktuellen Werte müssen geladen sein.")
        else:
            self.send_btn.setEnabled(True)

    def _send_cloud_values(self):
        if len(self._baseline) != 6 or self.cloud_request is not None:
            self.status_label.setText("Daten unvollständig; zuerst alle sechs Cloudwerte frisch lesen.")
            return
        values = [(r, v, v) for r, v, _ in self.timer_values() if r in self._dirty]
        if not values:
            self.status_label.setText("Keine geänderten Werte.")
            return
        self._pending = {r: v for r, v, _ in values}
        error = self.main_window.control_write_registers(values, "Silentmodus Timer",
            expected_context=self._control_identity)
        if error:
            self._pending.clear()
        self.status_label.setText(error or "Cloud-Batch gesendet; warte auf frischen Readback …")
        self._update_cloud_actions()

    def write_readback_confirmed(self, register):
        value = self._pending.pop(register, None)
        if value is None:
            return
        self._baseline[register] = value
        self._edited(register)
