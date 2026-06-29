from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QTextEdit, QVBoxLayout,
)

from dialogs.dialog_helpers import DEVICE_MODEL_LABELS, app_icon


class KnowledgeEditorDialog(QDialog):
    """Bearbeitung der getrennten Wissensdatenbank data/foxair_phnix_knowledge.json."""

    def __init__(self, main_window: "MainWindow", reg_no: int):
        super().__init__(main_window)
        self.main_window = main_window
        self.reg_no = int(reg_no)
        self.setWindowTitle(f"Beschreibung bearbeiten - Register {self.reg_no}")
        self.setWindowIcon(app_icon())
        self.resize(720, 560)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        reg_def = self.main_window.register_defs.get(str(self.reg_no), {})
        info = self.main_window.regmap.get(self.reg_no)
        name = reg_def.get("name") if isinstance(reg_def, dict) else ""
        if not name and info:
            name = info.name
        title = QLabel(f"Register {self.reg_no} / 0x{self.reg_no:04X}  |  {name or 'unbekannt'}")
        title.setWordWrap(True)
        layout.addWidget(title)

        hint = QLabel(
            "Diese Texte werden in data/foxair_phnix_knowledge.json gespeichert und beim Start über das Register-Mapping gelegt. "
            "Damit bleibt die Wissensdatenbank getrennt vom technischen Mapping."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        form = QFormLayout()
        layout.addLayout(form)
        self.description_edit = QTextEdit(); self.description_edit.setMinimumHeight(70)
        self.knowledge_edit = QTextEdit(); self.knowledge_edit.setMinimumHeight(130)
        self.notes_edit = QTextEdit(); self.notes_edit.setMinimumHeight(80)
        self.default_edit = QLineEdit()
        self.device_default_edit = QLineEdit()
        self.source_edit = QLineEdit()
        form.addRow("Beschreibung:", self.description_edit)
        form.addRow("Hinweis/Wissen:", self.knowledge_edit)
        form.addRow("Notiz:", self.notes_edit)
        form.addRow("Default allgemein:", self.default_edit)
        self.device_default_label = QLabel()
        form.addRow(self.device_default_label, self.device_default_edit)
        form.addRow("Quelle:", self.source_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_values(self):
        data = self.main_window.get_register_knowledge(self.reg_no)
        if not data:
            # Vorhandene Mapping-Texte als Startwert anzeigen, aber erst beim Speichern in die Knowledge-Datei übernehmen.
            data = self.main_window.register_defs.get(str(self.reg_no), {}) or {}
        self.description_edit.setPlainText(str(data.get("description", "")))
        self.knowledge_edit.setPlainText(str(data.get("knowledge", data.get("explanation", ""))))
        self.notes_edit.setPlainText(str(data.get("notes", data.get("hint", ""))))
        self.default_edit.setText(str(data.get("default", "")))
        device_key = self.main_window.current_device_model()
        self.device_default_label.setText(f"Default {DEVICE_MODEL_LABELS.get(device_key, device_key)}:")
        per_device = data.get("default_by_device", {})
        self.device_default_edit.setText(str(per_device.get(device_key, "")) if isinstance(per_device, dict) else "")
        self.source_edit.setText(str(data.get("source", "")))

    def accept(self):
        data = {
            "description": self.description_edit.toPlainText().strip(),
            "knowledge": self.knowledge_edit.toPlainText().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
            "default": self.default_edit.text().strip(),
            "source": self.source_edit.text().strip(),
        }
        device_key = self.main_window.current_device_model()
        per_device = dict(self.main_window.get_register_knowledge(self.reg_no).get("default_by_device", {}) or {})
        dev_default = self.device_default_edit.text().strip()
        if dev_default:
            per_device[device_key] = dev_default
        else:
            per_device.pop(device_key, None)
        if per_device:
            data["default_by_device"] = per_device
        self.main_window.set_register_knowledge(self.reg_no, data)
        super().accept()
