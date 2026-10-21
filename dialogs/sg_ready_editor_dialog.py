from __future__ import annotations

from typing import Optional
import time

from cloud.snapshot_request import CloudSnapshotRequest
from core.control_transport import TRANSPORT_NAMES
from core.foxair_phnix_core import numeric_value_by_type

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR, s16
from core.sg_ready import (
    SG_MODE_OPTIONS, sg_status_description, uses_virtual_sg_input, virtual_stage_options,
)

FLASH_CHANGED_ROW_MS = 2000

class SGReadyEditorDialog(QDialog):
    CLOUD_CODES = tuple(f"SG{i:02}" for i in range(1, 9)) + ("SG Status",)
    SG_REGS = set(range(1334, 1342)) | {2133, 8801}
    READ_LABEL_VALUES = "SG Ready 1334-1341"
    READ_LABEL_STATUS = "SG Status 2133"
    READ_LABEL_VIRTUAL = "SG virtueller Eingang 8801"

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self._dirty = set()
        self._edit_versions = {}
        self._pending_write_versions = {}
        self._pending_write_raw = {}
        self._control_identity = main_window.control_context()
        self.cloud_request = None
        self.finished.connect(lambda *_args: self._cancel_cloud_read())
        self.cloud_read_timer = QTimer(self)
        self.cloud_read_timer.setSingleShot(True)
        self.cloud_read_timer.timeout.connect(self._cloud_timeout)
        self._sg_status_read_pending = False
        self._sg_read_generation = 0
        self._last_raw_values: dict[int, int] = {}
        self._flash_tokens: dict[int, int] = {}
        self.setWindowTitle("SG Ready Editor")
        self.setMinimumWidth(620)
        self._build_ui()
        self.load_from_live_values()
        self.connection_changed()
        self.initial_read_timer = QTimer(self)
        self.initial_read_timer.setSingleShot(True)
        self.initial_read_timer.timeout.connect(self._autoload_cloud)
        self.initial_read_timer.start(250)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("SG01: klassische SG-Ready-Familie 1/2/3, AI Saving 4 und erweiterte SG/PV-Familie 5/6/7 mit Low / Neutral / High. Modus 5 erreicht Neutral/High über einen Kontakt, Modus 6 alle drei Stufen über zwei Kontakte, Modus 7 über 8801. Register 8801 ist nur am direkten User-/Mainboard-Modbus bestätigt. Live-Updates überschreiben keine gerade bearbeiteten Felder.")
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
        for label, value in SG_MODE_OPTIONS:
            self.sg_mode_combo.addItem(label, value)
        self.sg_mode_combo.currentIndexChanged.connect(self._update_virtual_stage_choices)
        form.addRow("SG Ready Auswahl (1334):", self.sg_mode_combo)

        self.virtual_sg_combo = QComboBox()
        self._update_virtual_stage_choices()
        form.addRow("Virtueller SG-Modus (8801, nur direkt):", self.virtual_sg_combo)

        self.raw_spins: dict[int, QSpinBox] = {}
        self.power_spins: dict[int, QDoubleSpinBox] = {}
        for reg_no, label in [
            (1335, "SG02 – Schlaf-/Sperrzeit klassischer Mode 1"),
            (1336, "SG03 – Low-PV / klassische Mode-2-Leistungsgrenze"),
            (1337, "SG04 – klassische Mode-3-/Medium-PV-Leistung"),
        ]:
            if reg_no in (1336, 1337):
                spin = QDoubleSpinBox()
                spin.setRange(0, 6553.5); spin.setDecimals(1); spin.setSingleStep(0.1); spin.setSuffix(" kW")
                self.power_spins[reg_no] = spin
            else:
                spin = QSpinBox(); spin.setRange(0, 0xFFFF)
                self.raw_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.temp_spins: dict[int, QDoubleSpinBox] = {}
        for reg_no, label in [
            (1338, "SG05 – High-PV WW-Sollwertanhebung"),
            (1339, "SG06 – High-PV Heiz-Sollwertanhebung"),
            (1340, "SG07 – High-PV Kühl-Sollwertänderung"),
        ]:
            spin = QDoubleSpinBox(); spin.setRange(-50.0, 25.0); spin.setDecimals(1); spin.setSingleStep(0.5); spin.setSuffix(" °C")
            self.temp_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.sg08_combo = QComboBox()
        self.sg08_combo.addItem("Aus", 0)
        self.sg08_combo.addItem("Ein", 1)
        form.addRow("SG08 – High-PV E-Heizer / Zusatzfunktion (1341):", self.sg08_combo)

        self.sg_status_label = QLabel("--")
        self.sg_status_label.setToolTip("Read-only: Register 2133 zeigt im klassischen Pfad den aktiven SG-Modus. Bei SG01=7 entspricht 1=Low PV, 2=Neutral und 3=High PV.")
        form.addRow("Aktiver SG-Modus (2133, read-only):", self.sg_status_label)

        for reg_no in sorted(self.SG_REGS - {2133}):
            widget = self._widget_for_reg(reg_no)
            signal = widget.currentIndexChanged if isinstance(widget, QComboBox) else widget.valueChanged
            signal.connect(lambda _value, r=reg_no: self._mark_dirty(r))

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

    def _update_virtual_stage_choices(self, _index: int = -1) -> None:
        previous = self.virtual_sg_combo.currentData() if hasattr(self, "virtual_sg_combo") else None
        if not hasattr(self, "virtual_sg_combo"):
            return
        self.virtual_sg_combo.blockSignals(True)
        self.virtual_sg_combo.clear()
        for label, value in virtual_stage_options(int(self.sg_mode_combo.currentData())):
            self.virtual_sg_combo.addItem(label, value)
        index = self.virtual_sg_combo.findData(previous)
        self.virtual_sg_combo.setCurrentIndex(index if index >= 0 else 0)
        self.virtual_sg_combo.blockSignals(False)
        mode = int(self.sg_mode_combo.currentData())
        backend_key = self.main_window.control_transport()
        direct_modbus = backend_key == "standard_modbus"
        self.virtual_sg_combo.setEnabled(uses_virtual_sg_input(mode, backend_key))
        if not direct_modbus:
            tooltip = "Register 8801 ist über Cloud, Warmlink/LTE und Display-Modbus nicht bestätigt und gesperrt."
        elif mode == 3:
            tooltip = (
                "Klassischer virtueller SG-Ready-Pfad:\n1 Schlaf\n2 wenig PV / Normal\n"
                "3 mittel PV\n4 High PV"
            )
        elif mode == 7:
            tooltip = "Erweiterter SG/PV-Pfad:\n1 Low PV\n2 Neutral\n3 High PV"
        elif mode == 4:
            tooltip = "AI Saving / Remote Energy Control.\n8801 wird in diesem Modus nicht als SG-Stufeneingang verwendet."
        elif mode == 5:
            tooltip = ("Erweiterter SG/PV-Pfad über einen physischen Kontakt:\nNeutral / High PV.\n"
                       "Firmwareseitig bestätigt, noch nicht live verifiziert.")
        elif mode == 6:
            tooltip = ("Erweiterter SG/PV-Pfad über zwei physische Kontakte:\nLow PV / Neutral / High PV.\n"
                       "Firmwareseitig bestätigt, noch nicht live verifiziert.")
        else:
            tooltip = "Dieser SG01-Modus verwendet physische Kontakte und nicht Register 8801."
        self.virtual_sg_combo.setToolTip(tooltip)
        if 2133 in self._last_raw_values:
            status = self._last_raw_values[2133]
            self.sg_status_label.setText(
                f"{status} - {sg_status_description(int(self.sg_mode_combo.currentData()), status)}"
            )

    def _has_focus(self, *widgets: QWidget) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        return any(focus is w or w.isAncestorOf(focus) for w in widgets)

    def load_from_live_values(self):
        self._dirty.clear()
        for reg_no in sorted(self.SG_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if self.main_window.control_transport() == "cloud":
                self.update_from_cloud_register(reg_no, force=True)
            elif reg is not None:
                self.update_from_live_register(reg, force=True)

    def set_write_status(self, text: str) -> None:
        self.status_label.setText(str(text))

    def _widget_for_reg(self, reg_no: int) -> Optional[QWidget]:
        if reg_no == 1334:
            return self.sg_mode_combo
        if reg_no == 8801:
            return self.virtual_sg_combo
        if reg_no == 1341:
            return self.sg08_combo
        if reg_no in self.raw_spins:
            return self.raw_spins[reg_no]
        if reg_no in getattr(self, "power_spins", {}):
            return self.power_spins[reg_no]
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
        QTimer.singleShot(FLASH_CHANGED_ROW_MS, widget, clear_flash)

    def update_from_live_register(self, reg, force: bool = False):
        reg_no = int(reg.reg)
        if reg_no not in self.SG_REGS:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        if self.main_window.control_transport() == "cloud":
            return
        raw = int(reg.raw_value) & 0xFFFF
        if self._pending_write_raw.get(reg_no) == raw:
            self.write_readback_confirmed(reg_no)
        self._apply_raw(reg_no, raw, force)

    def _apply_raw(self, reg_no, raw, force=False):
        old_raw = self._last_raw_values.get(reg_no)
        should_flash = old_raw is not None and old_raw != raw
        self._programmatic = True
        try:
            if reg_no == 1334:
                if force or (reg_no not in self._dirty and not self._has_focus(self.sg_mode_combo)):
                    idx = self.sg_mode_combo.findData(raw)
                    if idx >= 0:
                        self.sg_mode_combo.setCurrentIndex(idx)
            elif reg_no in (8801, 1341):
                combo = self.virtual_sg_combo if reg_no == 8801 else self.sg08_combo
                if force or (reg_no not in self._dirty and not self._has_focus(combo)):
                    index = combo.findData(raw)
                    if index >= 0 or reg_no == 1341:
                        combo.setCurrentIndex(index)
            elif reg_no in self.raw_spins:
                spin = self.raw_spins[reg_no]
                if force or (reg_no not in self._dirty and not self._has_focus(spin)):
                    spin.setValue(raw)
            elif reg_no in self.power_spins:
                spin = self.power_spins[reg_no]
                if force or (reg_no not in self._dirty and not self._has_focus(spin)):
                    spin.setValue(raw / 10.0)
            elif reg_no in self.temp_spins:
                spin = self.temp_spins[reg_no]
                if force or (reg_no not in self._dirty and not self._has_focus(spin)):
                    spin.setValue(s16(raw) / 10.0)
            elif reg_no == 2133:
                label = sg_status_description(int(self.sg_mode_combo.currentData()), raw)
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
        for reg_no in (1335,):
            values.append((reg_no, int(self.raw_spins[reg_no].value()) & 0xFFFF, f"SG Register {reg_no}"))
        for reg_no, spin in self.power_spins.items():
            values.append((reg_no, round(spin.value() * 10), f"SG Register {reg_no}"))
        for reg_no, label in ((1338, "SG05 WW-Anhebung"), (1339, "SG06 HZ-Anhebung"), (1340, "SG07 High-PV Kühl-Sollwertänderung")):
            values.append((reg_no, int(round(float(self.temp_spins[reg_no].value()) * 10.0)) & 0xFFFF, label))
        values.append((1341, int(self.sg08_combo.currentData()) & 0xFFFF, "SG08 High-PV E-Heizer / Zusatzfunktion"))
        if uses_virtual_sg_input(
                int(self.sg_mode_combo.currentData()), self.main_window.control_transport()):
            values.append((8801, int(self.virtual_sg_combo.currentData()) & 0xFFFF, "Virtueller SG-Modus (nur direkter Modbus)"))
        return values

    def _autoload_cloud(self):
        if self.isVisible() and self.main_window.control_transport() == "cloud":
            if self.main_window._control_cloud_busy():
                self.initial_read_timer.start(250)
                return
            self.read_from_wp()

    def read_from_wp(self):
        if not self.isVisible():
            return
        self.initial_read_timer.stop()
        try:
            context = self.main_window.control_context()
            capability = self.main_window.control_can_read(*range(1334, 1342), 2133)
            if not capability:
                self.set_write_status(capability.reason)
                return
            if context.transport == "cloud":
                if self.cloud_request is not None:
                    return
                owner = self.main_window
                owner._sg_cloud_generation = getattr(owner, "_sg_cloud_generation", 0) + 1
                self.cloud_request = CloudSnapshotRequest(owner._sg_cloud_generation, self.CLOUD_CODES,
                    time.monotonic() + 60, context.username, context.device_code, purpose="sg_ready")
                self.cloud_read_timer.start(60000)
                self.set_write_status("Lese SG Ready über Cloud …")
                error = owner.control_request_snapshot(self.cloud_request)
                if error:
                    self.cloud_read_finished(self.cloud_request.cycle_id, [], error)
                return
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.remove_pending_read_requests_by_label(
                {self.READ_LABEL_VALUES, self.READ_LABEL_STATUS, self.READ_LABEL_VIRTUAL},
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
            if uses_virtual_sg_input(
                    int(self.sg_mode_combo.currentData()), self.main_window.control_transport()):
                QTimer.singleShot(0, lambda: self._send_virtual_read_after_status(slave_addr, generation))
        except Exception as exc:
            self._sg_status_read_pending = False
            QMessageBox.warning(self, "Ungültige SG-Status-Leseanforderung", str(exc))

    def _send_virtual_read_after_status(self, slave_addr: int, generation: int):
        if not self.isVisible() or generation != self._sg_read_generation:
            return
        if self.main_window.has_pending_read_request(self.READ_LABEL_STATUS, slave_addr=slave_addr):
            QTimer.singleShot(250, lambda: self._send_virtual_read_after_status(slave_addr, generation))
            return
        self.status_label.setText("SG Status gelesen. Lese virtuellen SG-Modus 8801 ...")
        self.main_window.send_read_request(8801, 1, slave_addr=slave_addr, label=self.READ_LABEL_VIRTUAL)

    def _mark_dirty(self, register):
        if not self._programmatic:
            self._dirty.add(register)
            self._edit_versions[register] = self._edit_versions.get(register, 0) + 1

    def write_readback_confirmed(self, register):
        version = self._pending_write_versions.pop(register, None)
        self._pending_write_raw.pop(register, None)
        if version is not None and version == self._edit_versions.get(register, 0):
            self._dirty.discard(register)

    def update_from_cloud_register(self, reg_no, force=False):
        if self.main_window.control_transport() != "cloud" or reg_no not in self.SG_REGS - {8801}:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        value = self.main_window.register_value_sources(reg_no).cloud_engineering
        if value is None:
            return
        scale = 10 if reg_no in {1336, 1337, 1338, 1339, 1340} else 1
        self._apply_raw(reg_no, round(float(value) * scale) & 0xFFFF, force)

    def connection_changed(self):
        context = self.main_window.control_context()
        if context != self._control_identity:
            self._cancel_cloud_read()
            self._dirty.clear()
            self._pending_write_versions.clear()
            self._pending_write_raw.clear()
            self._last_raw_values.clear()
            self._programmatic = True
            self.sg_mode_combo.setCurrentIndex(0)
            self.sg08_combo.setCurrentIndex(0)
            for spin in (*self.raw_spins.values(), *self.power_spins.values(), *self.temp_spins.values()):
                spin.setValue(0)
            self.sg_status_label.setText("--")
            self._programmatic = False
            self._control_identity = context
            self.load_from_live_values()
        self._update_virtual_stage_choices()
        self.read_btn.setEnabled(bool(self.main_window.control_can_read(*range(1334, 1342), 2133)))
        self.send_btn.setEnabled(bool(self.main_window.control_can_write(*range(1334, 1342))))

    def _cancel_cloud_read(self):
        self.cloud_read_timer.stop()
        if self.cloud_request:
            self.cloud_request.cancelled.set()
        self.cloud_request = None

    def _cloud_timeout(self):
        self._cancel_cloud_read()
        self.set_write_status("SG Ready Cloud: Timeout / keine frische Antwort.")
        self.connection_changed()

    def cloud_read_finished(self, cycle_id, rows, error):
        request = self.cloud_request
        if request is None or request.cycle_id != cycle_id:
            return
        context = self.main_window.control_context()
        if not self.isVisible() or context != self._control_identity or context.transport != "cloud":
            self.connection_changed()
            return
        if request.expired():
            self._cloud_timeout()
            return
        fresh = [r for r in rows if r.get("code") in request.codes and r.get("supported")
                 and r.get("value") is not None and not any(r.get(f) for f in ("stale", "cached", "currentEmpty"))]
        self._cancel_cloud_read()
        if not error:
            self.main_window.apply_cloud_rows_to_main(fresh)
        self.set_write_status(f"SG Ready Cloud: {len(fresh)}/{len(request.codes)} Werte" + (f" · {error}" if error else ""))
        self.connection_changed()

    def send_values(self):
        try:
            owner = self.main_window
            context = owner.control_context()
            changed = [(r, raw, label) for r, raw, label in self.sg_values()
                       if r in self._dirty and self._last_raw_values.get(r) != raw]
            # Configure dependent limits first. Activate the new source last;
            # disabling SG is deliberately the first operation.
            changed.sort(key=lambda item: (-1 if item[0] == 1334 and item[1] == 0
                                            else 2 if item[0] == 8801 else 1 if item[0] == 1334 else 0))
            if not changed:
                self.set_write_status("Keine geänderten SG-Parameter.")
                return
            capability = owner.control_can_write(*(r for r, _, _ in changed))
            if not capability:
                self.set_write_status(capability.reason)
                return
            text = "Geänderte SG-Parameter schreiben?\nTransport: " + TRANSPORT_NAMES[context.transport]
            if owner.control_requires_write_confirmation() and QMessageBox.question(self, "SG Ready schreiben", text,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
            writes = tuple((r, raw, numeric_value_by_type(raw, owner.regmap.get(r).dtype)) for r, raw, _ in changed)
            self._pending_write_versions = {r: self._edit_versions.get(r, 0) for r, _, _ in writes}
            self._pending_write_raw = {r: raw for r, raw, _ in writes}
            error = owner.control_write_registers(writes, "SG Ready", expected_context=context)
            self.set_write_status(error or "SG Ready Schreiben eingeplant; Bestätigung steht aus.")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige SG-Werte", str(exc))

    def closeEvent(self, event):
        self.initial_read_timer.stop()
        self._sg_read_generation += 1
        self._cancel_cloud_read()
        super().closeEvent(event)
