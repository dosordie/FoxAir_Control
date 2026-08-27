from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit, QVBoxLayout)

from core.device_info import C37B_STATUS


class DeviceInfoDialog(QDialog):
    """Local, read-only view of the LTE/Warmlink device-information exchange."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Geräte-Info")
        self.resize(720, 680)
        root = QVBoxLayout(self)
        self.fields: dict[str, QLabel] = {}

        self._group(root, "Verbindung und Abfrage", [
            ("transport", "Aktiver Transport"), ("bus", "Busadresse"),
            ("updated", "Letzte vollständige/teilweise Abfrage"), ("state", "Status"),
        ])
        self.progress = QTextEdit()
        self.progress.setReadOnly(True)
        self.progress.setMaximumHeight(145)
        root.addWidget(self.progress)
        self._group(root, "Mainboard-Identität", [
            ("wifi", "WiFi Barcode / Kommunikationsmodul-ID"),
            ("date", "Vermutetes Produktionsdatum"), ("date_code", "Code-Datumsfeld"),
        ], "Nicht identisch mit der Seriennummer auf dem Typenschild; das WF-Format ist eine Vermutung.")
        self._group(root, "Cloud-/Produktfamilie", [("product", "PHNIX/Aliyun ProductKey")],
                    "Kennzeichnet die Produkt-/Cloudfamilie und ist keine individuelle Seriennummer.")
        self._group(root, "Mainboard-Hardware", [("hardware", "Hardwarecode"), ("hardware_version", "Hardwareversion")])
        self._group(root, "Mainboard-Software", [("software", "Vollständiger Softwarecode"),
                    ("firmware", "Firmwareversion"), ("internal", "Interner Versionscode")])
        self._group(root, "Service-Handshake", [("ssid", "Service-/OTA-SSID"),
                    ("ack", "C544-Quittungsstatus"), ("ack_meaning", "Bedeutung")])

        row = QHBoxLayout()
        self.read_btn = QPushButton("Sonderfunktion Update Anfrage Cloud")
        self.direct_read_btn = QPushButton("Geräte-Info auslesen")
        copy_btn = QPushButton("Werte kopieren")
        close_btn = QPushButton("Schließen")
        row.addWidget(self.read_btn)
        row.addWidget(self.direct_read_btn)
        row.addWidget(copy_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        root.addLayout(row)
        self.read_btn.clicked.connect(main_window.start_device_info_cycle)
        self.direct_read_btn.clicked.connect(main_window.read_device_info_registers)
        copy_btn.clicked.connect(self.copy_values)
        close_btn.clicked.connect(self.close)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def _group(self, root, title, rows, note=""):
        box, form = QGroupBox(title), QFormLayout()
        for key, title_text in rows:
            label = QLabel("—")
            label.setTextInteractionFlags(label.textInteractionFlags() | Qt.TextSelectableByMouse)
            label.setWordWrap(True)
            self.fields[key] = label
            form.addRow(title_text + ":", label)
        if note:
            hint = QLabel(note)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #666;")
            form.addRow("Hinweis:", hint)
        box.setLayout(form)
        root.addWidget(box)

    def refresh(self):
        tracker = self.main_window.device_info_tracker
        cached = {int(reg): int(item.raw_value) for reg, item in self.main_window.latest_regs.items()}
        tracker.hydrate_cache(cached)
        tracker.check_timeout()
        snap = tracker.snapshot
        self.fields["transport"].setText(self.main_window.current_backend_label())
        self.fields["bus"].setText(f"0x{self.main_window._wire_slave_addr(0x63):02X}")
        self.fields["updated"].setText(time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(snap.last_update)) if snap.last_update else "Noch keine Daten")
        self.fields["state"].setText(snap.state.value)
        self.fields["wifi"].setText(snap.wifi_id or "Nicht empfangen")
        self.fields["date"].setText(snap.production_date or "Unbekannt / Format nicht bestätigt")
        self.fields["date_code"].setText(snap.code_date or "—")
        self.fields["product"].setText(snap.product_key or snap.product_key_error or "Nicht empfangen")
        self.fields["hardware"].setText(snap.hardware_code or "Nicht empfangen")
        self.fields["hardware_version"].setText(snap.hardware_version or "Nicht empfangen")
        self.fields["software"].setText(snap.software_code or "Nicht empfangen")
        self.fields["firmware"].setText(snap.firmware_version or "Versionsinformation nicht empfangen")
        self.fields["internal"].setText(snap.internal_version or "—")
        self.fields["ssid"].setText(f"0x{snap.service_ssid:04X} ({snap.service_ssid})" if snap.service_ssid is not None else "Nicht empfangen")
        self.fields["ack"].setText(("Ja, " if snap.ack_status == 7 else "Nein, ") + f"Status {snap.ack_status}" if snap.ack_status is not None else "Nicht empfangen")
        self.fields["ack_meaning"].setText(C37B_STATUS.get(snap.ack_status, "Unbekannt") if snap.ack_status is not None else "—")
        marks = [(snap.triggered, "Geräteinfo angefordert"), (snap.startup_seen, "Startup-/UART-Handshake erkannt"),
                 (snap.product_key is not None, "ProductKey empfangen"),
                 (snap.block_count == 8, f"Datenblöcke {snap.block_count}/8 empfangen"),
                 (snap.hardware_code is not None, "Hardware-/Softwareinformation empfangen"),
                 (snap.ack_status == 7, "Versionsinformation vom LTE-Modem bestätigt")]
        marks[3] = (marks[3][0], f"Datenblöcke {snap.block_count}/8 empfangen")
        progress_text = "\n".join(("✓ " if done else "○ ") + text for done, text in marks)
        # Do not replace identical content every 500 ms: QTextEdit would otherwise
        # reset a user-selected scroll position to the beginning.
        if self.progress.toPlainText() != progress_text:
            scrollbar = self.progress.verticalScrollBar()
            old_position = scrollbar.value()
            was_at_bottom = old_position >= scrollbar.maximum()
            self.progress.setPlainText(progress_text)
            scrollbar.setValue(scrollbar.maximum() if was_at_bottom else old_position)
        self.read_btn.setEnabled(not snap.running and self.main_window._active_io_worker() is not None)
        self.direct_read_btn.setEnabled(self.main_window._active_io_worker() is not None)

    def copy_values(self):
        lines = [f"{label}: {self.fields[key].text()}" for key, label in [
            ("wifi", "WiFi-ID"), ("date", "Produktionsdatum"), ("product", "ProductKey"),
            ("hardware", "Hardwarecode"), ("hardware_version", "Hardwareversion"),
            ("software", "Softwarecode"), ("firmware", "Firmwareversion"),
            ("internal", "Interner Versionscode"), ("ssid", "Service-SSID"), ("ack", "Quittung")]]
        QGuiApplication.clipboard().setText("\n".join(lines))
