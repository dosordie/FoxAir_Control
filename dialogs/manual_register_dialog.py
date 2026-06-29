from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTextEdit, QVBoxLayout,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR, DecodedRegister, hexdump
from dialogs.dialog_helpers import app_icon


class ManualRegisterDialog(QDialog):
    """Kompaktes Popup fuer manuelles Lesen/Schreiben einzelner Register."""

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Register lesen / schreiben")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.bus_edit = QLineEdit(f"0x{DEFAULT_BUS_ADDR:02X}")
        self.addr_edit = QLineEdit(str(self._saved_int("last_register", 1334)))
        self.value_edit = QLineEdit("0")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 125)
        self.count_spin.setValue(self._saved_count())
        self.cyclic_read_cb = QCheckBox("Zyklisch abfragen")
        self.cyclic_interval_spin = QSpinBox()
        self.cyclic_interval_spin.setRange(1, 3600)
        self.cyclic_interval_spin.setValue(self._saved_cyclic_interval())
        self.cyclic_interval_spin.setSuffix(" s")
        self.cyclic_interval_spin.setToolTip("Abfragezeit fuer zyklisches FC03-Lesen in Sekunden.")
        self.cyclic_read_timer = QTimer(self)
        self.cyclic_read_timer.setSingleShot(False)
        form.addRow("Bus-Adresse:", self.bus_edit)
        form.addRow("Register-Adresse:", self.addr_edit)
        form.addRow("Raw-Wert:", self.value_edit)
        form.addRow("Lesen Anzahl:", self.count_spin)
        form.addRow(self.cyclic_read_cb)
        form.addRow("Abfragezeit:", self.cyclic_interval_spin)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.read_btn = QPushButton("FC03 lesen")
        self.send_btn = QPushButton("ECHT senden")
        self.send_btn.setEnabled(True)
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.send_btn)
        layout.addLayout(buttons)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setMinimumHeight(115)
        self.result_box.setPlaceholderText("Antwort der letzten FC03-Abfrage erscheint hier ...")
        layout.addWidget(self.result_box)

        self.read_btn.clicked.connect(self.read_registers)
        self.send_btn.clicked.connect(self.send_write_frame)
        self.addr_edit.editingFinished.connect(self._remember_current_register_if_valid)
        self.count_spin.valueChanged.connect(lambda _=None: self._remember_current_count())
        self.cyclic_read_cb.toggled.connect(self._cyclic_read_toggled)
        self.cyclic_interval_spin.valueChanged.connect(self._cyclic_interval_changed)
        self.cyclic_read_timer.timeout.connect(self._cyclic_read_tick)

    def _state(self) -> dict[str, Any]:
        state = self.main_window.settings.setdefault("manual_register_dialog", {})
        if not isinstance(state, dict):
            state = {}
            self.main_window.settings["manual_register_dialog"] = state
        return state

    def _saved_int(self, key: str, default: int) -> int:
        try:
            value = int(self._state().get(key, default))
            if 0 <= value <= 0xFFFF:
                return value
        except Exception:
            pass
        return int(default)

    def _saved_count(self) -> int:
        try:
            return min(125, max(1, int(self._state().get("last_read_count", 1) or 1)))
        except Exception:
            return 1

    def _saved_cyclic_interval(self) -> int:
        try:
            return min(3600, max(1, int(self._state().get("cyclic_read_interval_s", 10) or 10)))
        except Exception:
            return 10

    def _remember_register(self, addr: int, *, for_read: bool = False, for_write: bool = False) -> None:
        addr = int(addr)
        if not (0 <= addr <= 0xFFFF):
            raise ValueError("Register-Adresse außerhalb 0..65535")
        state = self._state()
        state["last_register"] = addr
        if for_read:
            state["last_read_register"] = addr
            state["last_read_count"] = int(self.count_spin.value())
        if for_write:
            state["last_write_register"] = addr
        self.main_window._save_settings(sync_main_fields=False)

    def _remember_current_register_if_valid(self) -> None:
        try:
            text = self.addr_edit.text().strip()
            if not text:
                return
            self._remember_register(self.main_window._parse_int_text(text))
        except Exception:
            return

    def _remember_current_count(self) -> None:
        state = self._state()
        state["last_read_count"] = int(self.count_spin.value())
        self.main_window._save_settings(sync_main_fields=False)

    def _remember_cyclic_interval(self) -> None:
        state = self._state()
        state["cyclic_read_interval_s"] = int(self.cyclic_interval_spin.value())
        self.main_window._save_settings(sync_main_fields=False)

    def _bus(self) -> int:
        return self.main_window._parse_int_text(self.bus_edit.text())

    def _addr(self) -> int:
        return self.main_window._parse_int_text(self.addr_edit.text())

    def _value(self) -> int:
        return self.main_window._parse_int_text(self.value_edit.text()) & 0xFFFF

    def set_address(self, reg_no: int, slave_addr: int = DEFAULT_BUS_ADDR):
        self.addr_edit.setText(str(int(reg_no)))
        self.bus_edit.setText(f"0x{int(slave_addr):02X}")
        self._remember_register(int(reg_no))

    def _read_pending(self, addr: int, quantity: int, slave_addr: int) -> bool:
        frame, wire_addr, wire_slave, _note = self.main_window._build_read_frame_for_backend(addr, quantity, slave_addr)
        del frame
        for req in list(getattr(self.main_window, "pending_read_requests", []) or []):
            if str(req.get("label", "")) != "manuelles Popup":
                continue
            if int(req.get("slave_addr", -1)) != int(wire_slave):
                continue
            if int(req.get("addr", -1)) == int(addr) and int(req.get("wire_addr", -1)) == int(wire_addr) and int(req.get("quantity", -1)) == int(quantity):
                return True
        return False

    def _send_current_read(self, *, cyclic: bool = False) -> None:
        addr = self._addr()
        quantity = int(self.count_spin.value())
        slave_addr = self._bus()
        self._remember_register(addr, for_read=True)
        if cyclic and self._read_pending(addr, quantity, slave_addr):
            self.main_window._log(
                f"Zyklisches Popup-Lesen übersprungen: identischer READ noch offen ({addr}/0x{addr:04X}, Anzahl {quantity}).",
                level=6,
            )
            return
        self.result_box.setPlainText(f"Lese Register {addr} / 0x{addr:04X}, Anzahl {quantity} ...")
        self.main_window.send_read_request(addr, quantity, slave_addr=slave_addr, label="manuelles Popup")

    def read_registers(self):
        try:
            self._send_current_read(cyclic=False)
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Leseanforderung", str(exc))

    def _cyclic_read_toggled(self, checked: bool) -> None:
        if checked:
            self._remember_cyclic_interval()
            self.cyclic_read_timer.start(int(self.cyclic_interval_spin.value()) * 1000)
            self._cyclic_read_tick()
        else:
            self.cyclic_read_timer.stop()

    def _cyclic_interval_changed(self, _value: int) -> None:
        self._remember_cyclic_interval()
        if self.cyclic_read_timer.isActive():
            self.cyclic_read_timer.start(int(self.cyclic_interval_spin.value()) * 1000)

    def _cyclic_read_tick(self) -> None:
        if not self.cyclic_read_cb.isChecked():
            self.cyclic_read_timer.stop()
            return
        try:
            self._send_current_read(cyclic=True)
        except Exception as exc:
            self.main_window._log(f"Zyklisches Popup-Lesen nicht ausgeführt: {exc}")

    def show_read_response(self, start_addr: int, quantity: int, registers: list[DecodedRegister]):
        if not registers:
            self.result_box.setPlainText(
                f"Antwort erhalten, aber keine Register dekodiert.\n"
                f"Start: {start_addr} / 0x{start_addr:04X}, Anzahl: {quantity}"
            )
            return
        lines = [f"Antwort: {start_addr} / 0x{start_addr:04X}, Anzahl {quantity}", ""]
        for reg in registers:
            name = f"  {reg.name}" if reg.name else ""
            lines.append(
                f"{reg.reg} / 0x{reg.reg:04X} = {reg.raw_value} / 0x{reg.raw_value:04X} -> {reg.display_value}{name}"
            )
        self.result_box.setPlainText("\n".join(lines))
        if len(registers) == 1:
            self.value_edit.setText(str(int(registers[0].raw_value) & 0xFFFF))

    def show_read_timeout(self, start_addr: int, quantity: int):
        qty_text = "" if int(quantity) == 1 else f", Anzahl {int(quantity)}"
        self.result_box.setPlainText(f"READ Timeout: {int(start_addr)}{qty_text}")

    def show_write_frame(self):
        try:
            slave_addr = self._bus()
            addr = self._addr()
            value = self._value()
            frame, wire_addr, wire_slave, note, fc_text = self.main_window._build_write_frame_for_backend(addr, value, slave_addr)
            note_text = f" | {note}" if note else ""
            self.main_window._log(
                f"WRITE Dry-Run Popup [{self.main_window.current_backend_label()} / {fc_text}]: bus=0x{wire_slave:02X}, "
                f"addr={addr}/0x{addr:04X} -> wire={wire_addr}/0x{wire_addr:04X}, "
                f"value={value}/0x{value:04X}, TX={hexdump(frame, -1)}{note_text}"
            )
            self.send_btn.setEnabled(True)
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Schreibdaten", str(exc))

    def send_write_frame(self):
        try:
            addr = self._addr()
            value = self._value()
            self._remember_register(addr, for_write=True)
            self.main_window.send_register_write(addr, value, slave_addr=self._bus(), label="manuelles Popup")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Schreibdaten", str(exc))

    def closeEvent(self, event):
        self.cyclic_read_timer.stop()
        self._remember_current_register_if_valid()
        self._remember_cyclic_interval()
        super().closeEvent(event)
