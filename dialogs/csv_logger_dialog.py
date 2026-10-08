"""Small CSV Logger controls; closing the dialog stops only its recording."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from core.csv_logger_controller import SOURCE_NAMES


class CsvLoggerDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.controller = main_window.csv_logger_controller
        self.setWindowTitle("CSV Logger")
        self.setWindowIcon(main_window.windowIcon())
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(660, 360)
        self.setMinimumSize(520, 320)
        layout = QVBoxLayout(self)
        recording_group = QGroupBox("Aufzeichnung")
        layout.addWidget(recording_group)
        form = QFormLayout(recording_group)
        self.path_edit = QLineEdit()
        self.choose_button = QPushButton("Datei wählen ...")
        file_row = QHBoxLayout()
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(self.choose_button)
        form.addRow("CSV-Datei:", file_row)
        cfg = main_window.settings.get("csv_logger", {})
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 3600)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setValue(int(cfg.get("interval_s", 30)))
        form.addRow("Intervall:", self.interval_spin)
        hint = QLabel("Register 2001–2090 · Engineering-Werte ohne Einheiten · fehlende/frisch nicht verfügbare Werte bleiben leer.")
        hint.setWordWrap(True)
        form.addRow(hint)
        status_group = QGroupBox("Status")
        layout.addWidget(status_group)
        status_form = QFormLayout(status_group)
        self.source_label = QLabel()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.last_label = QLabel()
        self.rows_label = QLabel()
        for label, widget in (("Quelle:", self.source_label), ("Status:", self.status_label),
                              ("Letzter erfolgreicher Datensatz:", self.last_label), ("Geschriebene Zeilen:", self.rows_label)):
            status_form.addRow(label, widget)
        buttons = QHBoxLayout()
        self.start_button, self.stop_button = QPushButton("Start"), QPushButton("Stop")
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch(1)
        self.close_button = QPushButton("Schließen")
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.choose_button.clicked.connect(self.choose_file)
        self.start_button.clicked.connect(self.start_logger)
        self.stop_button.clicked.connect(lambda: self.controller.stop())
        self.close_button.clicked.connect(self.close)
        self.interval_spin.valueChanged.connect(self.save_settings)
        self.controller.changed.connect(self.refresh)
        self.refresh()

    def choose_file(self):
        directory = self.main_window.settings.get("csv_logger", {}).get("last_directory") or self.main_window.user_data_dir
        path, _ = QFileDialog.getSaveFileName(self, "CSV-Datei wählen (kompatible Dateien werden ergänzt)",
            str(Path(directory) / "phnix_live.csv"), "CSV (*.csv)", options=QFileDialog.DontConfirmOverwrite)
        if path:
            self.path_edit.setText(path)
            self.save_settings()

    def save_settings(self, _value=None):
        cfg = self.main_window.settings.setdefault("csv_logger", {})
        cfg["interval_s"] = self.interval_spin.value()
        path = self.path_edit.text().strip()
        if path:
            cfg["last_directory"] = str(Path(path).expanduser().parent)
        self.main_window._save_settings(sync_main_fields=False)

    def start_logger(self):
        try:
            self.controller.start(self.path_edit.text().strip(), self.interval_spin.value())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "CSV Logger", str(exc))
            return
        self.save_settings()

    def refresh(self):
        controller = self.controller
        for widget in (self.path_edit, self.choose_button, self.interval_spin, self.start_button):
            widget.setEnabled(not controller.running)
        self.stop_button.setEnabled(controller.running)
        if controller.running or controller.source:
            self.source_label.setText(SOURCE_NAMES.get(controller.source, "—"))
        else:
            try:
                self.source_label.setText(SOURCE_NAMES[controller.available_source()[0]])
            except ValueError as exc:
                self.source_label.setText(str(exc))
        self.status_label.setText(str(controller.status))
        self.last_label.setText(controller.last_success or "—")
        self.rows_label.setText(str(controller.writer.rows_written))

    def closeEvent(self, event):
        self.controller.stop()
        self.save_settings()
        super().closeEvent(event)
