from __future__ import annotations

import re
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR
from dialogs.dialog_helpers import (
    SortableTableWidgetItem, app_icon, apply_block_header_item_style,
    code_sort_key, is_block_dtype, register_extra_info_text, register_has_extra_info,
    register_meta_parts,
)


class OfflineRegisterBrowserDialog(QDialog):
    """Offline-Browser fuer alle Register aus dem Mapping, ohne Verbindung."""

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Offline Register-Browser")
        self.setWindowIcon(app_icon())
        self.resize(1120, 820)
        self.items = self._collect_items()
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.addItem("Warmlink/WP", "warmlink")
        self.source_combo.addItem("Display/DWIN", "display")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("nach Name/App-Name/Beschreibung suchen ...")
        self.search_edit.setText(str(self.main_window.settings.get("offline_register_browser_search", "")))
        self.regex_cb = QCheckBox("Regex")
        self.app_name_cb = QCheckBox("App-Name anzeigen")
        self.count_label = QLabel("0 Register")
        top.addWidget(QLabel("Mapping:"))
        top.addWidget(self.source_combo)
        top.addWidget(QLabel("Suche:"))
        top.addWidget(self.search_edit, 1)
        top.addWidget(self.regex_cb)
        top.addWidget(self.app_name_cb)
        top.addWidget(self.count_label)
        layout.addLayout(top)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Reg", "Code", "Name", "Typ", "Beschreibung / Hinweis"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 58)
        h.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 68)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)
        self.description_box = QLabel("Beschreibung: --")
        self.description_box.setWordWrap(True)
        self.description_box.setMinimumHeight(46)
        self.description_box.setStyleSheet("QLabel { background: #fffbe8; border: 1px solid #d8d0a0; padding: 6px; color: #333; }")
        layout.addWidget(self.description_box)
        buttons = QHBoxLayout()
        self.write_btn = QPushButton("ausgewähltes Register schreiben ...")
        self.read_btn = QPushButton("ausgewähltes Register lesen")
        self.edit_info_btn = QPushButton("Beschreibung bearbeiten ...")
        self.close_btn = QPushButton("Schließen")
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.write_btn)
        buttons.addWidget(self.edit_info_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)
        self.source_combo.currentIndexChanged.connect(lambda _=None: self._switch_source())
        self.search_edit.textChanged.connect(self._search_text_changed)
        self.regex_cb.stateChanged.connect(lambda _=None: self.refresh())
        self.app_name_cb.stateChanged.connect(lambda _=None: self.refresh())
        self.table.itemDoubleClicked.connect(lambda _=None: self.write_selected())
        self.table.currentItemChanged.connect(lambda cur, _prev=None: self._show_selected_description())
        self.write_btn.clicked.connect(self.write_selected)
        self.read_btn.clicked.connect(self.read_selected)
        self.edit_info_btn.clicked.connect(self.edit_selected_description)
        self.close_btn.clicked.connect(self.close)
        self.refresh()

    def _search_text_changed(self, text: str):
        self.main_window.settings["offline_register_browser_search"] = str(text)
        self.main_window._save_settings(sync_main_fields=False)
        self.refresh()

    def _current_source(self) -> str:
        if hasattr(self, "source_combo"):
            return str(self.source_combo.currentData() or "warmlink")
        return "warmlink"

    def _switch_source(self):
        self.items = self._collect_items()
        self.refresh()
        self._show_selected_description()

    def _collect_items(self) -> list[dict[str, Any]]:
        out = []
        source = self._current_source()
        if source == "display":
            # Display-/DWIN-Mapping ist absichtlich getrennt. Es nutzt aktuell nur
            # Namen/Typen aus data/foxair_phnix_display_registers.json und keine
            # editierbare Knowledge-Datenbank.
            for reg, info in sorted(getattr(self.main_window.display_regmap, "items", {}).items()):
                name = str(getattr(info, "name", "") or "")
                dtype = str(getattr(info, "dtype", "RAW") or "RAW")
                out.append({
                    "reg": int(reg),
                    "block": "DWIN",
                    "code": f"0x{int(reg):04X}",
                    "name": name or f"Display/DWIN {int(reg)}",
                    "app_label": "",
                    "dtype": dtype,
                    "info": "Display-/DWIN-Diagnosemapping (getrennt von Warmlink/WP)",
                    "detail": "Display-/DWIN-Diagnosemapping. Diese Adressen dürfen die normale Warmlink-Registerliste nicht überschreiben.",
                    "has_extra": True,
                })
            return sorted(out, key=lambda x: x["reg"])

        for key, data in getattr(self.main_window, "register_defs", {}).items():
            try:
                reg = int(key, 0) if isinstance(key, str) else int(key)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            block, code, clean = register_meta_parts(data)
            info_text = register_extra_info_text(data, reg_no=reg, device_model=self.main_window.current_device_model()) or str(data.get("info", ""))
            out.append({
                "reg": reg,
                "block": block,
                "code": code,
                "name": clean,
                "app_label": str(data.get("app_label", "")),
                "dtype": str(data.get("type", "RAW")),
                "info": info_text.replace("\n", " | "),
                "detail": info_text,
                "has_extra": register_has_extra_info(data, reg_no=reg, device_model=self.main_window.current_device_model()),
            })
        return sorted(out, key=lambda x: x["reg"])

    def _filtered_items(self) -> list[dict[str, Any]]:
        text = self.search_edit.text().strip()
        if not text:
            return list(self.items)
        items = []
        try:
            if self.regex_cb.isChecked():
                pat = re.compile(text, re.IGNORECASE)
                for it in self.items:
                    hay = " ".join(str(it.get(k, "")) for k in ("name", "app_label", "info", "code", "block"))
                    if pat.search(hay):
                        items.append(it)
            else:
                needle = text.lower()
                for it in self.items:
                    hay = " ".join(str(it.get(k, "")) for k in ("name", "app_label", "info", "code", "block")).lower()
                    if needle in hay:
                        items.append(it)
        except re.error:
            return []
        return items

    def refresh(self):
        items = self._filtered_items()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(items))
        for row, it in enumerate(items):
            name = it.get("app_label") if self.app_name_cb.isChecked() and it.get("app_label") else it.get("name", "")
            block_code = it.get("code") or it.get("block", "")
            vals = [it["reg"], block_code, name, it.get("dtype", ""), it.get("info", "")]
            is_block_row = is_block_dtype(it.get("dtype", ""))
            self.table.setRowHeight(row, 19 if is_block_row else 24)
            for col, val in enumerate(vals):
                cell = self.table.item(row, col)
                if cell is None:
                    cell = SortableTableWidgetItem()
                    self.table.setItem(row, col, cell)
                cell.setText(str(val))
                cell.setToolTip(str(it.get("detail") or val))
                apply_block_header_item_style(self.table, cell, is_block_row)
                if col == 0:
                    cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    cell.setData(Qt.UserRole + 1, int(it["reg"]))
                elif col == 1:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    cell.setData(Qt.UserRole + 1, code_sort_key(str(val)))
                cell.setData(Qt.UserRole, int(it["reg"]))
        self.table.setSortingEnabled(True)
        self.count_label.setText(f"{len(items)} Register")

    def _selected_reg(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return int(data) if data is not None else int(item.text())

    def _find_visible_item_by_reg(self, reg_no: int) -> Optional[dict[str, Any]]:
        for it in self._filtered_items():
            if int(it.get("reg", -1)) == int(reg_no):
                return it
        return None

    def _show_selected_description(self):
        reg = self._selected_reg()
        if reg is None:
            self.description_box.setText("Beschreibung: --")
            return
        it = self._find_visible_item_by_reg(reg)
        detail = str((it or {}).get("detail", "")).strip()
        if detail:
            self.description_box.setText(detail.replace("\n", "   |   "))
        else:
            self.description_box.setText(f"Beschreibung: keine Beschreibung hinterlegt fuer Register {reg}")

    def edit_selected_description(self):
        reg = self._selected_reg()
        if reg is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte zuerst eine Registerzeile auswählen.")
            return
        if self.main_window.edit_register_knowledge(reg):
            self.items = self._collect_items()
            self.refresh()
            self._show_selected_description()

    def write_selected(self):
        reg = self._selected_reg()
        if reg is not None:
            bus = 0x03 if self._current_source() == "display" else DEFAULT_BUS_ADDR
            self.main_window.open_register_quick_write(reg, bus)

    def read_selected(self):
        reg = self._selected_reg()
        if reg is not None:
            bus = 0x03 if self._current_source() == "display" else DEFAULT_BUS_ADDR
            label = "Offline-Browser Display/DWIN" if self._current_source() == "display" else "Offline-Browser"
            self.main_window.send_read_request(reg, 1, slave_addr=bus, label=label)
