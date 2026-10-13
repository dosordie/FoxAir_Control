"""Engineering-only, Warmlink-only identity provisioning popup (issue #115)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTextEdit, QVBoxLayout, QCheckBox)

from core.device_identity import (WARNING, identity_access_error, validate_wifi_identity,
                                  decode_wifi_identity, load_identity_backup)
from core.device_identity_service import DeviceIdentityService


class DeviceIdentityDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.service = DeviceIdentityService(main_window, self)
        self.setWindowTitle("Mainboard-WiFi-ID / Kommunikationsmodul-ID")
        self.resize(760, 780)
        self._prepared_preview = None
        root = QVBoxLayout(self)
        self.fields = {}
        self._group(root, "Verbindung", [("transport", "Aktiver Transport"), ("bus", "Busadresse"),
                                         ("status", "Status")])
        self._group(root, "Aktuelle Mainboard-ID", [("identity", "WiFi-ID"), ("raw", "2001–2006"),
                                                   ("reserve", "Reserve 2007 / 2008")])
        box, form = QGroupBox("Neue ID / vollständiges Schreibpayload"), QFormLayout()
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("WF und zehn ASCII-Ziffern (exakt 12 Zeichen)")
        self.validation = QLabel()
        self.payload_preview = QTextEdit()
        self.payload_preview.setReadOnly(True)
        self.payload_preview.setMaximumHeight(150)
        self.confirmation_edit = QLineEdit()
        self.confirmation_edit.setPlaceholderText("Ziel-ID zur Bestätigung erneut eintippen")
        warning = QLabel(WARNING + "\nDas lokale Backup enthält vollständige sensible Gerätekennungen.")
        warning.setWordWrap(True)
        form.addRow("Neue ID:", self.target_edit)
        form.addRow("Validierung:", self.validation)
        form.addRow("7001–7010:", self.payload_preview)
        form.addRow(warning)
        form.addRow("Explizite Bestätigung:", self.confirmation_edit)
        box.setLayout(form)
        root.addWidget(box)
        self._group(root, "Schreib- und Prüfstatus", [("ack", "FC10 / ACK"), ("readback", "Unmittelbare Rückleseprüfung"),
                    ("reserved_ok", "Reservewörter unverändert"), ("countdown", "EEPROM-Wartezeit"),
                    ("persistence", "Prüfung nach Neustart"), ("backup", "Sensibles lokales Backup")])
        self.restart_check = QCheckBox("Ich habe das Mainboard nach Ablauf der Wartezeit tatsächlich neu gestartet und neu verbunden.")
        root.addWidget(self.restart_check)
        row = QHBoxLayout()
        self.read_btn = QPushButton("Aktuelle ID lesen")
        self.prepare_btn = QPushButton("Änderung vorbereiten")
        self.write_btn = QPushButton("ID dauerhaft schreiben")
        self.verify_btn = QPushButton("Nach Neustart erneut prüfen")
        for button in (self.read_btn, self.prepare_btn, self.write_btn, self.verify_btn):
            row.addWidget(button)
        root.addLayout(row)
        row = QHBoxLayout()
        self.restore_btn = QPushButton("Alte ID wiederherstellen …")
        close_btn = QPushButton("Schließen")
        row.addWidget(self.restore_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        root.addLayout(row)
        self.read_btn.clicked.connect(self.service.read_current)
        self.prepare_btn.clicked.connect(lambda: self.service.prepare(self.target_edit.text()))
        self.write_btn.clicked.connect(self.write_identity)
        self.verify_btn.clicked.connect(lambda: self.service.verify_after_restart(self.restart_check.isChecked()))
        self.restore_btn.clicked.connect(self.restore_identity)
        close_btn.clicked.connect(self.close)
        self.target_edit.textChanged.connect(self._target_changed)
        self.confirmation_edit.textChanged.connect(self.refresh)
        self.restart_check.toggled.connect(self.refresh)
        self.service.changed.connect(self.refresh)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.refresh()

    def _group(self, root, title, rows):
        box, form = QGroupBox(title), QFormLayout()
        for key, title_text in rows:
            label = QLabel("—")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.fields[key] = label
            form.addRow(title_text + ":", label)
        box.setLayout(form)
        root.addWidget(box)

    def _tick(self):
        self.service.tick()
        self.refresh()

    def _target_changed(self):
        self.service.invalidate_preparation()
        self.confirmation_edit.clear()
        self.refresh()

    def refresh(self):
        service = self.service
        error = identity_access_error(self.main_window)
        self.fields["transport"].setText(self.main_window.current_backend_label())
        self.fields["bus"].setText(f"0x{self.main_window._wire_slave_addr(0x63):02X}")
        self.fields["status"].setText(error or service.status)
        if service.words is not None:
            self.fields["identity"].setText(decode_wifi_identity(service.words) or "Ungültige / nicht dekodierbare ID")
            self.fields["raw"].setText("  ".join(f"{2001+i}=0x{word:04X}" for i, word in enumerate(service.words[:6])))
            self.fields["reserve"].setText(f"2007=0x{service.words[6]:04X} / 2008=0x{service.words[7]:04X}")
        target_valid = validate_wifi_identity(self.target_edit.text())
        self.validation.setText("Gültiges WF-Format" if target_valid else "Erforderlich: WF und exakt zehn ASCII-Ziffern")
        preview = "\n".join(f"{7001+i} = 0x{word:04X} ({word})" for i, word in enumerate(service.payload or []))
        if self.payload_preview.toPlainText() != preview:
            self.payload_preview.setPlainText(preview)
        if service.state == "prepared":
            key = service.preparation_revision
            if key != self._prepared_preview:
                self._prepared_preview = key
                self.confirmation_edit.clear()
                self.restart_check.setChecked(False)
        self.fields["ack"].setText("Exakt geprüft: 0x63 / FC10 / 7001 / 10" if service.ack_ok else "Noch nicht bestätigt")
        self.fields["readback"].setText(self._result(service.immediate_ok))
        self.fields["reserved_ok"].setText(self._result(service.reserve_ok))
        self.fields["countdown"].setText(f"Vor Neustart/Ausschalten noch {service.wait_seconds} s warten"
                                        if service.wait_seconds else "Kein automatischer Neustart; Persistenz separat prüfen.")
        self.fields["persistence"].setText(self._result(service.persistence_ok))
        self.fields["backup"].setText(str(service.backup_path) if service.backup_path else "Vor dem Schreiben automatisch gespeichert (sensibel)")
        available = not error and not service.busy and not service.wait_seconds
        self.target_edit.setEnabled(not service.busy and not service.wait_seconds)
        self.read_btn.setEnabled(available)
        self.prepare_btn.setEnabled(available and target_valid)
        self.confirmation_edit.setEnabled(available and service.state == "prepared")
        self.write_btn.setEnabled(available and service.state == "prepared" and
                                 self.confirmation_edit.text() == service.target and
                                 self.target_edit.text() == service.target)
        self.restart_check.setEnabled(available and service.reconnected and service.immediate_ok is True)
        self.verify_btn.setEnabled(available and service.reconnected and service.immediate_ok is True
                                   and self.restart_check.isChecked())
        has_backup = self._has_backup()
        self.restore_btn.setVisible(has_backup)
        self.restore_btn.setEnabled(available and has_backup)

    @staticmethod
    def _result(value):
        return "Bestätigt" if value is True else "Fehlgeschlagen" if value is False else "Noch nicht geprüft"

    def _has_backup(self):
        from pathlib import Path
        directory = Path(self.main_window.user_data_dir) / "device_identity_backups"
        for path in directory.glob("*.json"):
            try:
                load_identity_backup(path)
                return True
            except (OSError, ValueError, TypeError, KeyError):
                continue
        return False

    def write_identity(self):
        if self.target_edit.text() != self.service.target:
            return False
        return self.service.write(self.confirmation_edit.text())

    def restore_identity(self):
        if identity_access_error(self.main_window):
            self.refresh()
            return
        path, _ = QFileDialog.getOpenFileName(self, "Sensibles Identity-Backup auswählen",
            str(self.main_window.user_data_dir) + "/device_identity_backups", "Identity-Backup (*.json)")
        if not path:
            return
        try:
            record = load_identity_backup(path)
        except (OSError, ValueError, TypeError, KeyError):
            self.service.status = "Ungültiges Identity-Backup."
            self.refresh()
            return
        self.target_edit.setText(record["old_id"])
        self.confirmation_edit.clear()
        self.service.restore_backup(path)

    def _can_close(self):
        if self.service.busy or self.service.wait_seconds:
            self.service.status = "Serviceablauf / EEPROM-Wartezeit zuerst abwarten. Nicht ausschalten oder neu starten."
            self.refresh()
            return False
        self.service.close()
        self.timer.stop()
        return True

    def reject(self):
        if self._can_close():
            super().reject()

    def closeEvent(self, event):
        if self._can_close():
            event.accept()
        else:
            event.ignore()
