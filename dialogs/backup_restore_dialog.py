from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class BackupRestoreDialog(QDialog):
    """Parameter-Backup/Restore fuer bekannte Parameter-Paketbereiche.

    Backup speichert nur aktuelle Werte aus den Parameterranges, keine BLOCK-Koepfe
    und keine Live-/Statuswerte. Restore zeigt eine Diff-Vorschau und schreibt erst
    nach deutlicher Sicherheitsabfrage.
    """
    BACKUP_BLOCKS = [
        ("Paket 1", 1018, 1090),
        ("Paket 2", 1101, 1180),
        ("Paket 3", 1191, 1270),
        ("Paket 4", 1281, 1360),
        ("Paket 5", 1371, 1450),
        ("Paket 6 optional", 1461, 1540),
        ("Paket 7 optional", 1551, 1630),
    ]

    def __init__(
        self,
        main_window: Any,
        *,
        app_icon_fn: Optional[Any] = None,
        app_version: str = "",
        default_bus_addr: int = 1,
        device_model_labels: Optional[dict[str, str]] = None,
    ):
        super().__init__(main_window)
        self.main_window = main_window
        self.app_version = str(app_version)
        self.default_bus_addr = int(default_bus_addr)
        self.device_model_labels = dict(device_model_labels or {})
        self.setWindowTitle("Backup / Restore Parameter")
        if app_icon_fn is not None:
            self.setWindowIcon(app_icon_fn())
        self.resize(980, 720)
        self.loaded_backup: Optional[dict[str, Any]] = None
        self._backup_reading = False
        self._backup_read_started_at = 0.0
        self._backup_read_step = 0
        self._backup_read_timer = QTimer(self)
        self._backup_read_timer.setInterval(500)
        self._backup_read_timer.timeout.connect(self._poll_backup_read_progress)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Backup/Restore liest und schreibt nur bekannte Parameterbereiche. "
            "BLOCK-Koepfe, interne HMI-Bloecke und Status-/Livewerte werden nicht geschrieben. "
            "Restore immer erst mit Diff pruefen."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self._build_backup_tab()
        self._build_restore_tab()

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _build_backup_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self.tabs.addTab(tab, "Backup")

        row = QHBoxLayout()
        self.read_btn = QPushButton("Parameterbereiche lesen")
        self.save_btn = QPushButton("Backup-Datei speichern ...")
        self.refresh_backup_btn = QPushButton("Vorschau aktualisieren")
        self.refresh_backup_btn.setToolTip("Aktualisiert die Tabelle aus den aktuell gelesenen/geladenen Backup-Daten.")
        row.addWidget(self.read_btn)
        row.addWidget(self.refresh_backup_btn)
        row.addWidget(self.save_btn)
        row.addStretch(1)
        lay.addLayout(row)

        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText("Kommentar zum Backup, z. B. Vor Änderung SG/Timer, Werkseinstellungen, Datum, Anlage ...")
        self.comment_edit.setMaximumHeight(90)
        lay.addWidget(QLabel("Backup-Kommentar:"))
        lay.addWidget(self.comment_edit)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        self.backup_info_label = QLabel("Noch kein Backup zusammengestellt.")
        self.backup_info_label.setWordWrap(True)
        lay.addWidget(self.backup_info_label)

        option_row = QHBoxLayout()
        self.show_optional_missing_check = QCheckBox("Optionale/nicht gelesene anzeigen")
        self.show_optional_missing_check.setToolTip("Zeigt optionale oder fehlende Register in der Vorschau als Hinweiszeilen an.")
        option_row.addWidget(self.show_optional_missing_check)
        option_row.addStretch(1)
        lay.addLayout(option_row)

        self.backup_table = QTableWidget(0, 6)
        self.backup_table.setHorizontalHeaderLabels(["Reg", "Code", "Name", "Rohwert", "Wert", "Status"])
        self.backup_table.verticalHeader().setVisible(False)
        self.backup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.backup_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.backup_table.setWordWrap(False)
        hdr = self.backup_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        lay.addWidget(self.backup_table, 1)

        self.read_btn.clicked.connect(self.read_backup_blocks)
        self.refresh_backup_btn.clicked.connect(self.refresh_backup_preview)
        self.save_btn.clicked.connect(self.save_backup_file)
        self.show_optional_missing_check.toggled.connect(self.refresh_backup_preview)
        self.refresh_backup_preview()

    def _build_restore_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self.tabs.addTab(tab, "Restore")

        row = QHBoxLayout()
        self.load_btn = QPushButton("Backup-Datei laden ...")
        self.restore_changed_btn = QPushButton("Geänderte schreiben")
        self.restore_selected_btn = QPushButton("Ausgewählte schreiben")
        self.restore_changed_btn.setEnabled(False)
        self.restore_selected_btn.setEnabled(False)
        row.addWidget(self.load_btn)
        row.addWidget(self.restore_changed_btn)
        row.addWidget(self.restore_selected_btn)
        row.addStretch(1)
        lay.addLayout(row)

        self.restore_info_label = QLabel("Noch keine Backup-Datei geladen.")
        self.restore_info_label.setWordWrap(True)
        lay.addWidget(self.restore_info_label)

        self.restore_table = QTableWidget(0, 8)
        self.restore_table.setHorizontalHeaderLabels(["Reg", "Code", "Name", "Aktuell", "Backup", "Wert aktuell", "Wert Backup", "Status"])
        self.restore_table.verticalHeader().setVisible(False)
        self.restore_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.restore_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.restore_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.restore_table.setWordWrap(False)
        hdr = self.restore_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        for c in (3,4,5,6,7):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        lay.addWidget(self.restore_table, 1)

        self.load_btn.clicked.connect(self.load_backup_file)
        self.restore_changed_btn.clicked.connect(lambda: self.restore_values(mode="changed"))
        self.restore_selected_btn.clicked.connect(lambda: self.restore_values(mode="selected"))

    def _backup_blocks(self) -> list[dict[str, Any]]:
        blocks = []
        for label, start, end in self.BACKUP_BLOCKS:
            optional = "optional" in str(label).lower()
            blocks.append({"label": label, "start": int(start), "end": int(end), "qty": int(end - start + 1), "optional": optional})
        return blocks

    def _backup_registers_by_optional(self) -> dict[bool, list[int]]:
        out: dict[bool, list[int]] = {False: [], True: []}
        for block in self._backup_blocks():
            optional = bool(block["optional"])
            for reg_no in range(int(block["start"]), int(block["end"]) + 1):
                info = self.main_window.regmap.get(reg_no)
                if not info:
                    continue
                dtype = str(getattr(info, "dtype", "RAW"))
                name = str(getattr(info, "name", ""))
                if dtype == "BLOCK" or name.lower().startswith("blockkopf"):
                    continue
                out[optional].append(reg_no)
        return {key: sorted(set(value)) for key, value in out.items()}

    def _backup_count_summary(self) -> dict[str, Any]:
        groups = self._backup_registers_by_optional()
        latest = self.main_window.latest_regs
        summary: dict[str, Any] = {}
        for optional, regs in groups.items():
            read = [reg_no for reg_no in regs if reg_no in latest]
            missing = [reg_no for reg_no in regs if reg_no not in latest]
            prefix = "optional" if optional else "required"
            summary[f"{prefix}_regs"] = regs
            summary[f"{prefix}_read"] = read
            summary[f"{prefix}_missing"] = missing
        summary["optional_missing_blocks"] = [
            block for block in self._backup_blocks()
            if block["optional"] and not any(reg_no in latest for reg_no in range(block["start"], block["end"] + 1))
        ]
        return summary

    def _format_block_range(self, block: dict[str, Any]) -> str:
        return f"{int(block['start'])}–{int(block['end'])}"

    def _backup_required_complete(self) -> bool:
        summary = self._backup_count_summary()
        return bool(summary["required_read"]) and not summary["required_missing"]

    def backup_registers(self) -> list[int]:
        regs: list[int] = []
        groups = self._backup_registers_by_optional()
        regs.extend(groups.get(False, []))
        regs.extend(groups.get(True, []))
        return sorted(set(regs))

    def read_backup_blocks(self):
        # Bewusst Blockweise lesen, inkl. Kopf, damit der normale Parser/Blockcheck arbeitet.
        if self._backup_reading:
            return
        blocks = self._backup_blocks()
        self._backup_reading = True
        self._backup_read_started_at = time.monotonic()
        self._backup_read_step = 0
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._set_backup_busy(True, f"Lese Paket 1/{len(blocks)}: {self._format_block_range(blocks[0])}")
        self.main_window._log("Backup: Start Parameterbereiche lesen.")
        pause = 700
        for idx, block in enumerate(blocks, start=1):
            label = str(block["label"])
            start = int(block["start"])
            qty = int(block["qty"])
            optional_text = " ja" if block["optional"] else " nein"
            self.main_window._log(f"Backup: Paket {idx}/{len(blocks)} {start}/{qty}, optional{optional_text}, angefordert.")
            self.main_window.send_read_request(start, qty, slave_addr=self.default_bus_addr, label=f"Backup {label}", delay_ms=pause)
        self.main_window._log(f"Backup: {len(blocks)} Parameterbereiche zum Lesen angefordert.")
        self._backup_read_timer.start()

    def _poll_backup_read_progress(self):
        if not self._backup_reading:
            self._backup_read_timer.stop()
            return
        blocks = self._backup_blocks()
        elapsed = max(0.0, time.monotonic() - self._backup_read_started_at)
        estimated_total = max(1.0, len(blocks) * 0.9 + 3.0)
        self._backup_read_step = min(len(blocks) - 1, int(elapsed / 0.9))
        block = blocks[self._backup_read_step]
        percent = min(95, int((elapsed / estimated_total) * 100))
        self.progress_bar.setValue(percent)
        self.backup_info_label.setText(f"Lese Paket {self._backup_read_step + 1}/{len(blocks)}: {self._format_block_range(block)} ({percent} %)")
        summary = self._backup_count_summary()
        mandatory_complete = not summary["required_missing"] and bool(summary["required_read"])
        timed_out = elapsed > estimated_total
        if (mandatory_complete and elapsed > len(blocks) * 0.9) or timed_out:
            self._finish_backup_read(timed_out=timed_out)

    def _finish_backup_read(self, timed_out: bool = False):
        self._backup_read_timer.stop()
        self._backup_reading = False
        summary = self._backup_count_summary()
        self.progress_bar.setValue(100)
        latest = self.main_window.latest_regs
        for idx, block in enumerate(self._backup_blocks(), start=1):
            known_regs = [
                reg_no for reg_no in range(block["start"], block["end"] + 1)
                if self.main_window.regmap.get(reg_no) is not None
            ]
            read_count = sum(1 for reg_no in known_regs if reg_no in latest)
            if read_count:
                self.main_window._log(f"Backup: Paket {idx}/{len(self._backup_blocks())} {block['start']}/{block['qty']} gelesen ({read_count} bekannte Werte).")
        for block in summary["optional_missing_blocks"]:
            self.main_window._log(f"Backup: {block['label']} {block['start']}/{block['qty']} nicht verfügbar, übersprungen.")
        if summary["required_missing"]:
            self.main_window._log(f"Backup: Abschluss mit Pflichtfehler, {len(summary['required_missing'])} Pflichtwerte fehlen.")
        else:
            opt_note = "optionale Werte teilweise nicht verfügbar" if summary["optional_missing"] else "optionale Werte vollständig"
            self.main_window._log(f"Backup: abgeschlossen, Pflichtwerte vollständig, {opt_note}.")
        self.refresh_backup_preview()

    def _row_values_for_reg(self, reg_no: int, backup_raw: Optional[int] = None):
        info = self.main_window.regmap.get(reg_no)
        code = self.main_window._code_for_register(reg_no) if hasattr(self.main_window, "_code_for_register") else ""
        name = self.main_window._name_for_register(reg_no, info.name if info else "") if hasattr(self.main_window, "_name_for_register") else (info.name if info else "")
        dtype = info.dtype if info else "RAW"
        raw = backup_raw
        if raw is None:
            reg = self.main_window.latest_regs.get(reg_no)
            raw = int(reg.raw_value) if reg is not None else None
        display = "--" if raw is None else self.main_window._format_cached_value(int(raw), dtype)
        return code, name, dtype, raw, display

    def _make_table_item(self, text: str, align: Optional[Qt.AlignmentFlag] = None) -> QTableWidgetItem:
        it = QTableWidgetItem(str(text))
        if align is not None:
            it.setTextAlignment(align | Qt.AlignVCenter)
        return it

    def _set_backup_busy(self, busy: bool, text: str = ""):
        self.read_btn.setEnabled(not busy)
        self.refresh_backup_btn.setEnabled(not busy)
        self.save_btn.setEnabled((not busy) and self._backup_required_complete())
        if text:
            self.backup_info_label.setText(text)
        QApplication.processEvents()

    def refresh_backup_preview(self):
        self._set_backup_busy(True, "Backup-Vorschau wird aktualisiert ...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            summary = self._backup_count_summary()
            groups = self._backup_registers_by_optional()
            rows = []
            latest = self.main_window.latest_regs
            for reg_no in groups.get(False, []) + groups.get(True, []):
                reg = latest.get(reg_no)
                optional = reg_no in set(groups.get(True, []))
                raw = int(reg.raw_value) & 0xFFFF if reg is not None else None
                if raw is None and not self.show_optional_missing_check.isChecked():
                    continue
                if raw is None:
                    status = "optional, nicht gelesen" if optional else "Pflichtwert fehlt"
                else:
                    status = "optional, gelesen" if optional else "gelesen"
                rows.append((reg_no, raw, optional, status))

            table = self.backup_table
            table.setUpdatesEnabled(False)
            table.setSortingEnabled(False)
            table.clearContents()
            table.setRowCount(len(rows))
            for row, (reg_no, raw, optional, status) in enumerate(rows):
                code, name, dtype, _raw, display = self._row_values_for_reg(reg_no, raw)
                raw_text = "--" if raw is None else f"{raw} / 0x{raw:04X}"
                values = [reg_no, code, name, raw_text, display, status]
                for col, val in enumerate(values):
                    align = Qt.AlignLeft if col in (0, 2, 5) else Qt.AlignRight
                    it = self._make_table_item(str(val), align)
                    if raw is None and optional:
                        it.setToolTip("Optionaler Bereich ist nicht verfügbar oder wurde übersprungen.")
                        it.setForeground(QBrush(QColor(130, 130, 130)))
                    elif raw is None:
                        it.setBackground(QColor(255, 220, 220))
                        it.setToolTip("Pflichtwert fehlt.")
                    table.setItem(row, col, it)
            optional_blocks = ", ".join(self._format_block_range(block) for block in summary["optional_missing_blocks"])
            if summary["required_missing"]:
                prefix = "Fehler: Pflichtwerte fehlen."
            elif summary["optional_missing"]:
                prefix = "Fertig mit Hinweis" if self.progress_bar.value() == 100 else "Backup-Vorschau"
            else:
                prefix = "Fertig" if self.progress_bar.value() == 100 else "Backup-Vorschau"
            opt_text = f" | Optionale Bereiche nicht verfügbar/übersprungen: {optional_blocks}" if optional_blocks else ""
            self.backup_info_label.setText(
                f"{prefix}: {len(summary['required_read'])} Pflichtwerte gelesen, "
                f"{len(summary['required_missing'])} Pflichtwerte fehlend, "
                f"{len(summary['optional_read'])} optionale Werte gelesen, "
                f"{len(summary['optional_missing'])} optionale Werte fehlend/übersprungen.{opt_text}"
            )
        finally:
            self.backup_table.setUpdatesEnabled(True)
            QApplication.restoreOverrideCursor()
            self._set_backup_busy(False)

    def _build_backup_data(self) -> dict[str, Any]:
        regs = []
        for reg_no in self.backup_registers():
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is None:
                continue
            info = self.main_window.regmap.get(reg_no)
            regs.append({
                "reg": int(reg_no),
                "raw_value": int(reg.raw_value) & 0xFFFF,
                "name": str(info.name if info else getattr(reg, "name", "")),
                "dtype": str(info.dtype if info else getattr(reg, "dtype", "RAW")),
                "code": self.main_window._code_for_register(reg_no) if hasattr(self.main_window, "_code_for_register") else "",
            })
        return {
            "format": "FoxAir_Phnix_Control_Parameter_Backup",
            "format_version": 1,
            "app_version": self.app_version,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "comment": self.comment_edit.toPlainText().strip(),
            "communication": self.main_window._communication_summary_text(),
            "backend": self.main_window.current_backend_key(),
            "device_model": self.main_window.current_device_model(),
            "device_model_label": self.device_model_labels.get(self.main_window.current_device_model(), self.main_window.current_device_model()),
            "register_count": len(regs),
            "blocks": [{"label": l, "start": s, "end": e} for l, s, e in self.BACKUP_BLOCKS],
            "registers": regs,
        }

    def save_backup_file(self):
        # Wichtig: Beim Speichern die Vorschau NICHT neu aufbauen.
        # Das machte die GUI bei manchen Systemen lange blockiert.
        data = self._build_backup_data()
        if not self._backup_required_complete():
            summary = self._backup_count_summary()
            QMessageBox.warning(
                self,
                "Backup unvollständig",
                f"Backup-Datei speichern ist erst aktiv, wenn alle Pflichtwerte gelesen sind.\n"
                f"Pflichtwerte fehlend: {len(summary['required_missing'])}",
            )
            self.refresh_backup_preview()
            return
        if not data["registers"]:
            QMessageBox.warning(self, "Kein Backup", "Keine Parameterwerte vorhanden. Erst Parameterbereiche lesen.")
            return
        default_name = time.strftime("foxair_phnix_backup_%Y%m%d_%H%M%S.json")
        path, _ = QFileDialog.getSaveFileName(self, "Backup speichern", os.path.join(getattr(self.main_window, "user_data_dir", self.main_window.base_dir), default_name), "JSON Backup (*.json)")
        if not path:
            return
        self.backup_info_label.setText("Backup-Datei wird geschrieben ...")
        QApplication.processEvents()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        success_message = ""
        error_message = ""
        try:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.backup_info_label.setText(f"Backup gespeichert: {len(data['registers'])} Register")
                self.main_window._log(f"Backup gespeichert: {path} ({len(data['registers'])} Register)")
                success_message = f"Gespeichert:\n{path}\n\nRegister: {len(data['registers'])}"
            except Exception as exc:
                error_message = str(exc)
        finally:
            QApplication.restoreOverrideCursor()

        if success_message:
            QMessageBox.information(self, "Backup gespeichert", success_message)
        elif error_message:
            QMessageBox.warning(self, "Backup Fehler", error_message)

    def load_backup_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Backup laden", getattr(self.main_window, "user_data_dir", self.main_window.base_dir), "JSON Backup (*.json);;Alle Dateien (*.*)")
        if not path:
            return
        self.restore_info_label.setText("Backup-Datei wird geladen ...")
        self.load_btn.setEnabled(False)
        QApplication.processEvents()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("format") != "FoxAir_Phnix_Control_Parameter_Backup":
                raise ValueError("Keine passende FoxAir/Phnix Backup-Datei.")
            self.loaded_backup = data
            QTimer.singleShot(0, self.refresh_restore_table)
            self.restore_changed_btn.setEnabled(True)
            self.restore_selected_btn.setEnabled(True)
            self.tabs.setCurrentIndex(1)
        except Exception as exc:
            QMessageBox.warning(self, "Backup laden Fehler", str(exc))
        finally:
            self.load_btn.setEnabled(True)

    def refresh_restore_table(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.restore_info_label.setText("Restore-Vorschau wird aktualisiert ...")
        QApplication.processEvents()
        try:
            data = self.loaded_backup or {}
            regs = data.get("registers", []) if isinstance(data, dict) else []
            rows = []
            changed = 0
            unknown_current = 0
            latest = self.main_window.latest_regs
            for item in regs:
                try:
                    reg_no = int(item.get("reg"))
                    backup_raw = int(item.get("raw_value")) & 0xFFFF
                except Exception:
                    continue
                current_reg = latest.get(reg_no)
                current_raw = int(current_reg.raw_value) & 0xFFFF if current_reg is not None else None
                if current_raw is None:
                    status = "aktuell unbekannt"
                    unknown_current += 1
                elif current_raw == backup_raw:
                    status = "gleich"
                else:
                    status = "geändert"
                    changed += 1
                rows.append((reg_no, current_raw, backup_raw, status))

            table = self.restore_table
            table.setUpdatesEnabled(False)
            table.setSortingEnabled(False)
            table.clearContents()
            table.setRowCount(len(rows))
            for row, (reg_no, current_raw, backup_raw, status) in enumerate(rows):
                code, name, dtype, _raw, backup_display = self._row_values_for_reg(reg_no, backup_raw)
                current_display = "--" if current_raw is None else self.main_window._format_cached_value(current_raw, dtype)
                vals = [
                    reg_no,
                    code,
                    name,
                    "--" if current_raw is None else f"{current_raw} / 0x{current_raw:04X}",
                    f"{backup_raw} / 0x{backup_raw:04X}",
                    current_display,
                    backup_display,
                    status,
                ]
                for col, val in enumerate(vals):
                    align = Qt.AlignLeft if col in (0, 2, 7) else Qt.AlignRight
                    it = self._make_table_item(str(val), align)
                    it.setData(Qt.UserRole, reg_no)
                    if status == "geändert":
                        it.setBackground(QColor(255, 235, 180))
                    elif status == "aktuell unbekannt":
                        it.setBackground(QColor(255, 220, 220))
                    table.setItem(row, col, it)
            comment = str(data.get("comment", ""))
            self.restore_info_label.setText(
                f"Backup: {data.get('saved_at', '?')} | App {data.get('app_version', '?')} | "
                f"{len(rows)} Register | geändert: {changed} | aktuell unbekannt: {unknown_current}\n"
                f"Kommentar: {comment if comment else '-'}"
            )
        finally:
            self.restore_table.setUpdatesEnabled(True)
            QApplication.restoreOverrideCursor()

    def _restore_items(self, mode: str) -> list[tuple[int, int, str]]:
        data = self.loaded_backup or {}
        by_reg = {}
        for item in data.get("registers", []):
            try:
                by_reg[int(item.get("reg"))] = int(item.get("raw_value")) & 0xFFFF
            except Exception:
                pass
        regs: list[int] = []
        if mode == "selected":
            for idx in self.restore_table.selectionModel().selectedRows():
                reg_item = self.restore_table.item(idx.row(), 0)
                if reg_item is not None:
                    regs.append(int(reg_item.data(Qt.UserRole)))
        else:
            for reg_no, backup_raw in by_reg.items():
                cur = self.main_window.latest_regs.get(reg_no)
                cur_raw = int(cur.raw_value) & 0xFFFF if cur is not None else None
                if cur_raw != backup_raw:
                    regs.append(reg_no)
        out = []
        for reg_no in sorted(set(regs)):
            if reg_no not in by_reg:
                continue
            info = self.main_window.regmap.get(reg_no)
            name = info.name if info else ""
            out.append((reg_no, by_reg[reg_no], name))
        return out

    def restore_values(self, mode: str = "changed"):
        if not self.loaded_backup:
            QMessageBox.information(self, "Kein Backup", "Bitte zuerst eine Backup-Datei laden.")
            return
        items = self._restore_items(mode)
        if not items:
            QMessageBox.information(self, "Nichts zu schreiben", "Keine passenden geänderten/ausgewählten Register gefunden.")
            return
        preview = "\n".join(f"{reg}: {value} / 0x{value:04X}  {name}" for reg, value, name in items[:25])
        more = "" if len(items) <= 25 else f"\n... plus {len(items)-25} weitere Register"
        question = (
            f"WARNUNG: Es werden {len(items)} Parameterregister geschrieben.\n\n"
            "Das kann Timer, SG Ready, Pumpen, Schutzgrenzen und andere Betriebsparameter ändern.\n"
            "Bitte nur fortfahren, wenn das Backup zur Anlage passt.\n\n"
            f"Erste Register:\n{preview}{more}\n\n"
            "Jetzt wirklich schreiben?"
        )
        answer = QMessageBox.warning(
            self,
            "Restore wirklich schreiben?",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.main_window._log("Restore abgebrochen.")
            return
        delay_ms = 450
        for reg_no, value, _name in items:
            self.main_window.send_register_write(reg_no, value, slave_addr=self.default_bus_addr, label="Restore", delay_ms=delay_ms)
        self.main_window._log(f"Restore: {len(items)} Register in Sendewarteschlange gestellt.")
