from __future__ import annotations

import re
import time
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.foxair_phnix_core import DEFAULT_BUS_ADDR, format_value_by_type, s16

DEFAULT_DEVICE_MODEL = "foxair_green_gl9_1"
DEVICE_MODEL_LABELS = {
    "foxair_green_gl9_1": "FoxAir Green 9.1",
    "foxair_green_gl13_1": "FoxAir Green 13.1",
    "foxair_green_gl17_1": "FoxAir Green 17.1",
    "phnix_everest_9": "PHNIX Everest 9",
}
KNOWLEDGE_FIELDS = ("description", "knowledge", "notes", "hint", "explanation", "default", "default_by_device", "source", "source_app_video")


def app_theme_is_dark() -> bool:
    app = QApplication.instance()
    return bool(app is not None and str(app.property("foxair_theme") or "light") == "dark")


def register_default_value(data: dict[str, Any], reg_no: Optional[int] = None, device_model: Optional[str] = None) -> str:
    if not isinstance(data, dict):
        return ""
    try:
        if reg_no is not None and int(reg_no) >= 2011:
            return ""
    except Exception:
        pass
    device_key = str(device_model or DEFAULT_DEVICE_MODEL)
    per_device = data.get("default_by_device", {})
    if isinstance(per_device, dict):
        val = per_device.get(device_key, "")
        if str(val).strip():
            return str(val).strip()
    return str(data.get("default", "")).strip()


def register_extra_info_text(data: dict[str, Any], include_source: bool = True, reg_no: Optional[int] = None, device_model: Optional[str] = None, include_default: bool = True) -> str:
    if not isinstance(data, dict):
        return ""
    parts: list[str] = []
    description = str(data.get("description", "")).strip()
    knowledge = str(data.get("knowledge", data.get("explanation", ""))).strip()
    notes = str(data.get("notes", data.get("hint", ""))).strip()
    default = register_default_value(data, reg_no=reg_no, device_model=device_model) if include_default else ""
    source = str(data.get("source", "")).strip()
    source_app = str(data.get("source_app_video", "")).strip()
    if description:
        parts.append(f"Beschreibung: {description}")
    if knowledge:
        parts.append(f"Hinweis: {knowledge}")
    if notes:
        parts.append(f"Notiz: {notes}")
    if default:
        device_label = DEVICE_MODEL_LABELS.get(str(device_model or DEFAULT_DEVICE_MODEL), str(device_model or DEFAULT_DEVICE_MODEL))
        per_device = data.get("default_by_device", {})
        label = f"Default ({device_label})" if isinstance(per_device, dict) and str(per_device.get(str(device_model or DEFAULT_DEVICE_MODEL), "")).strip() else "Default"
        parts.append(f"{label}: {default}")
    if include_source and source:
        parts.append(f"Quelle: {source}")
    if include_source and source_app:
        parts.append("Quelle: App-Video")
    return "\n".join(parts)


def register_has_extra_info(data: dict[str, Any], reg_no: Optional[int] = None, device_model: Optional[str] = None) -> bool:
    if not isinstance(data, dict):
        return False
    for k in KNOWLEDGE_FIELDS:
        if k in {"default", "default_by_device"}:
            if register_default_value(data, reg_no=reg_no, device_model=device_model):
                return True
        elif str(data.get(k, "")).strip():
            return True
    return False


def register_block_and_clean_name(name: str) -> tuple[str, str, str]:
    text = str(name or "").strip()
    m = re.match(r"^\s*([A-Z]{1,3})(\d{1,3}(?:-\d+)?)\s*/\s*(.*)$", text)
    if not m:
        m = re.match(r"^\s*([A-Z]{1,3})(\d{1,3}(?:-\d+)?)\b\s*(?:/|-|:)?\s*(.*)$", text)
    if not m:
        return "", "", text
    block = m.group(1).upper()
    return block, f"{block}{m.group(2)}", m.group(3).strip() or text


def register_meta_parts(data_or_name: Any) -> tuple[str, str, str]:
    if isinstance(data_or_name, dict):
        name = str(data_or_name.get("name", "")).strip()
        code = str(data_or_name.get("code", "")).strip()
        code_for_block = code.upper()
        block = str(data_or_name.get("block", "")).strip().upper()
        old_block, old_code, clean = register_block_and_clean_name(name)
        if not code and old_code:
            code = old_code
            code_for_block = code.upper()
        if not block:
            block_match = re.match(r"^([A-Z]{1,3})", code_for_block) if code_for_block else None
            block = block_match.group(1) if block_match else old_block
        if old_code and name != clean:
            name = clean
        return block, code, name
    return register_block_and_clean_name(str(data_or_name or ""))


def code_sort_key(code: str) -> str:
    m = re.match(r"^([A-Z]{1,3})(\d+)(.*)$", str(code or ""))
    return str(code or "") if not m else f"{m.group(1)}{int(m.group(2)):04d}{m.group(3)}"


def is_block_dtype(dtype: Any) -> bool:
    return str(dtype or "").upper() == "BLOCK"


def apply_block_header_item_style(table: QTableWidget, item: QTableWidgetItem, is_block: bool) -> None:
    font = table.font()
    dark = app_theme_is_dark()
    if is_block:
        font.setItalic(True)
        point_size = font.pointSize()
        if point_size and point_size > 7:
            font.setPointSize(point_size - 1)
        item.setForeground(QColor(170, 170, 170) if dark else QColor(95, 95, 95))
    else:
        font.setItalic(False)
        item.setForeground(QColor(235, 235, 235) if dark else QColor(0, 0, 0))
    item.setFont(font)


class SortableTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        a = self.data(Qt.UserRole + 1)
        b = other.data(Qt.UserRole + 1) if isinstance(other, QTableWidgetItem) else None
        if a is not None and b is not None:
            return str(a) < str(b)
        return super().__lt__(other)


class ParameterSettingsDialog(QDialog):
    """App-nahe Parameteransicht nach Funktionsblöcken.

    Die technische Registertabelle bleibt unverändert. Dieses Fenster nutzt
    app_label/app_values aus der Mapping-Datei, fällt aber auf technische Namen
    und value_map zurück.
    """

    PARAM_RE = re.compile(r"^\s*([A-Z]{1,3})(\d{1,3}(?:-\d+)?)\b")
    BLOCK_SHORT_DESCRIPTIONS = {
        "H": "Basis/Hardware",
        "A": "Schutz/Grenzen",
        "F": "Fan",
        "D": "Abtauen",
        "E": "EVI/EEV",
        "C": "Compressor",
        "R": "Sollwerte",
        "T": "Diagnose/Live",
        "Z": "Zone",
        "G": "Legionellen",
        "P": "Pumpe",
        "SG": "SG Ready",
    }

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._items = self._collect_parameter_items()
        self._read_expected_regs: set[int] = set()
        self._read_started_monotonic = 0.0
        self._read_status_timeout_s = 12.0
        self.setWindowTitle("Parameter Einstellungen")
        self.setMinimumSize(1080, 760)
        self.resize(1120, 820)
        self._build_ui()
        self.refresh_blocks()
        self.refresh_table()
        self._apply_tab_poll_state(save=False)
        # Beim Oeffnen direkt den ersten sichtbaren Block laden, so wie die App
        # beim Aufruf einer Parametergruppe sofort Werte anzeigt.
        QTimer.singleShot(250, self._auto_read_initial_block)

    def _apply_tab_poll_state(self, save: bool = False):
        if save:
            self.main_window.settings["tab_auto_poll"] = bool(self.tab_auto_poll_cb.isChecked())
            self.main_window.settings["tab_poll_interval_s"] = int(self.tab_poll_interval_spin.value())
            self.main_window._save_settings(sync_main_fields=False)
        if self.tab_auto_poll_cb.isChecked():
            self.tab_poll_timer.start(int(self.tab_poll_interval_spin.value()) * 1000)
        else:
            self.tab_poll_timer.stop()

    def closeEvent(self, event):
        self._apply_tab_poll_state(save=True)
        self.tab_poll_timer.stop()
        self.read_status_timer.stop()
        super().closeEvent(event)

    def _auto_read_initial_block(self):
        if self.isVisible() and self.auto_read_block_cb.isChecked() and self._visible_items():
            self.read_visible_registers(auto=True)

    def _block_description_line(self, blocks: list[str]) -> str:
        parts = []
        for block in blocks:
            desc = self.BLOCK_SHORT_DESCRIPTIONS.get(block, "")
            if desc:
                parts.append(f"{block}={desc}")
        return "   ".join(parts)

    def _collect_parameter_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for key, data in getattr(self.main_window, "register_defs", {}).items():
            try:
                reg_no = int(key, 0) if isinstance(key, str) else int(key)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            block, code, clean_name = register_meta_parts(data)
            app_label = str(data.get("app_label", ""))
            if not code:
                # Kompatibilitaet fuer Alt-Mappings, bei denen der Code nur im App-Label steckt.
                m = self.PARAM_RE.search(str(data.get("name", "")) + " " + app_label)
                if not m:
                    continue
                block = m.group(1).upper()
                code = f"{m.group(1).upper()}{m.group(2)}"
            if block == "KG":
                # KG = WP Ein/Aus Timer. Diese Register haben einen eigenen Timer-Editor
                # und sollen die normale Parameter-Einstellungsansicht nicht ueberladen.
                continue
            mode = str(data.get("mode", ""))
            is_t_diag = str(code).upper().startswith("T-DIAG")
            # Fuer diese Ansicht sind schreibbare/parametrierbare Register interessant.
            # App-Video-Labels nehmen wir immer mit, auch wenn mode fehlt.
            # T-Diag-Werte sind Diagnosewerte, sollen aber als eigener Anhang im T-Block sichtbar sein.
            if "w" not in mode.lower() and not app_label and not is_t_diag:
                continue
            items.append({
                "reg": reg_no,
                "code": code,
                "block": block,
                "name": clean_name,
                "app_label": app_label,
                "dtype": str(data.get("type", "RAW")),
                "description": str(data.get("description", "")),
                "knowledge": str(data.get("knowledge", data.get("explanation", ""))),
                "notes": str(data.get("notes", data.get("hint", ""))),
                "source": str(data.get("source", "")),
                "default": str(data.get("default", "")),
                "mode": mode,
                "value_map": data.get("value_map") or data.get("values") or {},
                "app_values": data.get("app_values") or {},
                "source_app_video": str(data.get("source_app_video", "")),
            })
        def sort_key(item: dict[str, Any]):
            code_text = str(item["code"] or "")
            num_match = re.search(r"(\d+)", code_text)
            num = int(num_match.group(1)) if num_match else 9999
            # T-Diag-Diagnosewerte gehoeren ans Ende des T-Blocks, nicht zwischen T05/T10.
            diag_tail = 1 if code_text.upper().startswith("T-DIAG") else 0
            return (item["block"], diag_tail, num, item["reg"])
        return sorted(items, key=sort_key)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel(
            "App-nahe Einstellungsansicht. Oben den Parameterblock waehlen; "
            "die Tabelle zeigt technischen/deutschen Namen, Live-Wert und Register. "
            "Schreiben erfolgt ueber das bekannte Einzelregister-Popup."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.current_block = ""
        self.block_buttons: dict[str, QPushButton] = {}
        self.block_widgets: dict[str, QWidget] = {}
        self.block_bar = QHBoxLayout()
        self.block_bar.addWidget(QLabel("Block:"))
        layout.addLayout(self.block_bar)

        top = QHBoxLayout()
        self.app_only_cb = QCheckBox("nur App-Video Parameter")
        self.app_only_cb.setToolTip("Zeigt nur Parameter, fuer die bereits ein Original-App-Label aus der Bildschirmaufnahme bekannt ist.")
        self.app_name_cb = QCheckBox("App-Name anzeigen")
        self.app_name_cb.setToolTip("Aus: erkannter deutscher/technischer Name. An: Name wie in der Original-App, falls bekannt.")
        self.live_update_cb = QCheckBox("live aktualisieren")
        self.live_update_cb.setChecked(True)
        self.auto_read_block_cb = QCheckBox("Block automatisch lesen")
        self.auto_read_block_cb.setChecked(True)
        self.auto_read_block_cb.setToolTip("Wenn aktiv, werden beim Klick auf einen Parameterblock die sichtbaren Register blockweise gelesen.")
        self.tab_auto_poll_cb = QCheckBox("Auto Poll")
        self.tab_auto_poll_cb.setToolTip("Aktuell geoeffneten Parameterblock im Intervall wiederholt lesen.")
        self.tab_auto_poll_cb.setChecked(bool(self.main_window.settings.get("tab_auto_poll", False)))
        self.tab_poll_interval_spin = QSpinBox()
        self.tab_poll_interval_spin.setRange(2, 3600)
        self.tab_poll_interval_spin.setSuffix(" s")
        self.tab_poll_interval_spin.setValue(int(self.main_window.settings.get("tab_poll_interval_s", 30)))
        self.tab_poll_interval_spin.setMaximumWidth(90)
        top.addWidget(self.app_only_cb)
        top.addWidget(self.app_name_cb)
        top.addWidget(self.live_update_cb)
        top.addWidget(self.auto_read_block_cb)
        top.addWidget(self.tab_auto_poll_cb)
        top.addWidget(self.tab_poll_interval_spin)
        top.addStretch(1)
        layout.addLayout(top)

        self.tab_poll_timer = QTimer(self)
        self.tab_poll_timer.timeout.connect(lambda: self.read_visible_registers(auto=True))
        self.tab_auto_poll_cb.stateChanged.connect(lambda _=None: self._apply_tab_poll_state(save=True))
        self.tab_poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_tab_poll_state(save=True))

        self.read_status_timer = QTimer(self)
        self.read_status_timer.setInterval(500)
        self.read_status_timer.timeout.connect(self._update_read_status)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Register", "Code", "Name", "aktueller Wert", "Rohwert", "Typ", "Info"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 62)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 68)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setMouseTracking(True)
        self.table.setToolTip("Mouse-Over zeigt Beschreibungen/Hinweise, falls im Mapping vorhanden.")
        layout.addWidget(self.table, 1)

        self.description_box = QLabel("Beschreibung: --")
        self.description_box.setWordWrap(True)
        self.description_box.setMinimumHeight(42)
        self.description_box.setStyleSheet("QLabel { background: #fffbe8; border: 1px solid #d8d0a0; padding: 6px; color: #333; }")
        layout.addWidget(self.description_box)

        buttons = QHBoxLayout()
        self.read_visible_btn = QPushButton("sichtbare lesen")
        self.refresh_btn = QPushButton("aktualisieren")
        self.write_selected_btn = QPushButton("ausgewaehltes Register schreiben ...")
        self.edit_info_btn = QPushButton("Beschreibung bearbeiten ...")
        self.close_btn = QPushButton("Schließen")
        self.count_label = QLabel("0 Parameter")
        self.read_status_label = QLabel("Status: bereit")
        self.read_status_label.setToolTip("Zeigt den aktuellen Lesestatus des sichtbaren Parameterblocks.")
        buttons.addWidget(self.read_visible_btn)
        buttons.addWidget(self.refresh_btn)
        buttons.addWidget(self.write_selected_btn)
        buttons.addWidget(self.edit_info_btn)
        buttons.addWidget(self.count_label)
        buttons.addWidget(self.read_status_label)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.app_only_cb.stateChanged.connect(lambda _=None: self.refresh_table())
        self.app_name_cb.stateChanged.connect(lambda _=None: self.refresh_table())
        self.refresh_btn.clicked.connect(self.refresh_table)
        self.read_visible_btn.clicked.connect(self.read_visible_registers)
        self.write_selected_btn.clicked.connect(self.write_selected_register)
        self.edit_info_btn.clicked.connect(self.edit_selected_description)
        self.table.itemDoubleClicked.connect(lambda _item: self.write_selected_register())
        self.table.itemEntered.connect(self._show_item_description)
        self.table.currentItemChanged.connect(lambda cur, _prev=None: self._show_item_description(cur) if cur is not None else self._clear_description_box())
        self.close_btn.clicked.connect(self.close)

    def refresh_blocks(self):
        blocks = sorted({item["block"] for item in self._items})
        # Reihenfolge wie in der Warmlink-App: H A F D E R P G C Z.
        # T/Temperatur bleibt bewusst ganz am Schluss.
        preferred = ["H", "A", "F", "D", "E", "R", "P", "G", "C", "Z", "SG", "KG", "T"]
        ordered = [b for b in preferred if b in blocks] + [b for b in blocks if b not in preferred]
        if not self.current_block or self.current_block not in ordered:
            self.current_block = ordered[0] if ordered else ""

        # Alte Block-Widgets entfernen, Label bleibt an Position 0.
        while self.block_bar.count() > 1:
            item = self.block_bar.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.block_buttons = {}
        self.block_widgets = {}

        for block in ordered:
            desc = self.BLOCK_SHORT_DESCRIPTIONS.get(block, "")
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(1, 0, 1, 0)
            box_layout.setSpacing(1)

            btn = QPushButton(block)
            btn.setCheckable(True)
            btn.setChecked(block == self.current_block)
            btn.setMinimumWidth(58 if len(block) <= 2 else 72)
            btn.setMaximumWidth(78 if len(block) <= 2 else 92)
            btn.clicked.connect(lambda _checked=False, b=block: self._select_block(b))
            self.block_buttons[block] = btn
            box_layout.addWidget(btn, 0, Qt.AlignHCenter)

            desc_label = QLabel(desc)
            desc_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            desc_label.setWordWrap(False)
            desc_label.setStyleSheet("color: #666; font-size: 9px;")
            desc_label.setToolTip(f"{block} = {desc}" if desc else block)
            box_layout.addWidget(desc_label, 0, Qt.AlignHCenter)

            self.block_widgets[block] = box
            self.block_bar.addWidget(box)
        self.block_bar.addStretch(1)

    def _select_block(self, block: str):
        self.current_block = block
        for b, btn in self.block_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(b == block)
            btn.blockSignals(False)
        self.refresh_table()
        if getattr(self, "auto_read_block_cb", None) is not None and self.auto_read_block_cb.isChecked():
            self.read_visible_registers(auto=True)

    def _visible_items(self) -> list[dict[str, Any]]:
        block = self.current_block or ""
        app_only = self.app_only_cb.isChecked()
        items = []
        for item in self._items:
            if block and item["block"] != block:
                continue
            if app_only and not item.get("app_label"):
                continue
            items.append(item)
        return items

    def _mapping_label(self, raw: int, item: dict[str, Any]) -> Optional[str]:
        # Technische/deutsche value_map bevorzugen; App-Werte nur als Fallback.
        for map_name in ("value_map", "app_values"):
            raw_map = item.get(map_name) or {}
            if not isinstance(raw_map, dict):
                continue
            for key, label in raw_map.items():
                try:
                    k = int(key, 0) if isinstance(key, str) else int(key)
                except Exception:
                    continue
                if k == raw or k == s16(raw):
                    return str(label)
        return None

    def _display_for_item(self, item: dict[str, Any]) -> tuple[str, str]:
        reg_no = int(item["reg"])
        reg = self.main_window.latest_regs.get(reg_no)
        raw: Optional[int] = None
        decoded = "--"
        if reg is not None:
            raw = int(reg.raw_value) & 0xFFFF
            mapped = self._mapping_label(raw, item)
            decoded = mapped if mapped is not None else str(reg.display_value)
        elif reg_no in self.main_window.last_values:
            raw = int(self.main_window.last_values[reg_no]) & 0xFFFF
            mapped = self._mapping_label(raw, item)
            if mapped is not None:
                decoded = mapped
            else:
                # Wichtig: auch geladene/Cache-Werte mit Einheit und Skalierung anzeigen
                # (z. B. A40 raw=5 -> 0.5 m³/h statt nur 5).
                info = self.main_window.regmap.get(reg_no)
                decoded = format_value_by_type(raw, info.dtype if info else item.get("dtype", "RAW"), info.value_map if info else None, info.bit_map if info else None)
        if raw is None:
            return "--", "--"
        return decoded, str(raw)

    def _info_text(self, item: dict[str, Any]) -> str:
        return register_extra_info_text(item, reg_no=item.get("reg"), device_model=self.main_window.current_device_model()).replace("\n", " | ")

    def _description_detail_text(self, item: dict[str, Any], include_title: bool = True) -> str:
        parts: list[str] = []
        if include_title:
            technical_name = self._display_name_for_item(item)
            title = f"{item.get('code', '')} / Register {item.get('reg')}: {technical_name}"
            parts.append(title)
            app_label = str(item.get("app_label") or "").strip()
            if app_label and app_label != technical_name:
                parts.append(f"App-Name: {app_label}")
        extra = register_extra_info_text(item, reg_no=item.get("reg"), device_model=self.main_window.current_device_model())
        if extra:
            parts.append(extra)
        return "\n".join(str(p) for p in parts if str(p).strip())

    def _find_item_by_reg(self, reg_no: int) -> Optional[dict[str, Any]]:
        for item in self._items:
            if int(item.get("reg", -1)) == int(reg_no):
                return item
        return None

    def _clear_description_box(self):
        if hasattr(self, "description_box"):
            self.description_box.setText("Beschreibung: --")

    def _show_item_description(self, table_item):
        if table_item is None:
            self._clear_description_box()
            return
        reg_no = table_item.data(Qt.UserRole)
        if reg_no is None:
            self._clear_description_box()
            return
        item = self._find_item_by_reg(int(reg_no))
        if not item:
            self._clear_description_box()
            return
        detail = self._description_detail_text(item, include_title=False)
        # Nur aussagekraeftige Beschreibungen dauerhaft anzeigen. Ohne Zusatzwissen bleibt die Box ruhig.
        has_extra = register_has_extra_info(item, reg_no=item.get("reg"), device_model=self.main_window.current_device_model())
        if has_extra and detail:
            self.description_box.setText(detail.replace("\n", "   |   "))
        else:
            self.description_box.setText(f"Beschreibung: keine Beschreibung hinterlegt fuer Register {item.get('reg')}")

    def refresh_table(self):
        items = self._visible_items()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            value_text, raw_text = self._display_for_item(item)
            name_text = self._display_name_for_item(item)
            row_values = [
                int(item["reg"]),
                item.get("code") or item.get("block", ""),
                name_text,
                value_text,
                raw_text,
                item.get("dtype", "RAW"),
                self._info_text(item),
            ]
            is_block_row = is_block_dtype(item.get("dtype", ""))
            self.table.setRowHeight(row, 19 if is_block_row else 24)
            for col, text in enumerate(row_values):
                cell = self.table.item(row, col)
                if cell is None:
                    cell = SortableTableWidgetItem()
                    self.table.setItem(row, col, cell)
                cell.setText(str(text))
                detail_tip = self._description_detail_text(item)
                cell.setToolTip(detail_tip if register_has_extra_info(item, reg_no=item.get("reg"), device_model=self.main_window.current_device_model()) else str(text))
                apply_block_header_item_style(self.table, cell, is_block_row)
                if col == 0:
                    cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    cell.setData(Qt.UserRole + 1, int(item["reg"]))
                elif col == 1:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    cell.setData(Qt.UserRole + 1, code_sort_key(str(text)))
                elif col == 4:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                cell.setData(Qt.UserRole, int(item["reg"]))
        self.table.setSortingEnabled(True)
        self.table.sortItems(1, Qt.AscendingOrder)
        self.count_label.setText(f"{len(items)} Parameter")

    def _display_name_for_item(self, item: dict[str, Any]) -> str:
        """Return the visible parameter name without splitting on punctuation.

        The mapping name is already normalized when items are collected.  Do not
        strip at '/', '-/', '-' or ':' here because valid names such as
        "Standby-/Abschalt-Temperaturdifferenz" must remain intact.
        """
        name = str(item.get("name") or "").strip()
        if name:
            return name
        app_label = str(item.get("app_label") or "").strip()
        if app_label:
            return app_label
        code = str(item.get("code") or item.get("block") or "").strip()
        if code:
            return code
        reg = item.get("reg")
        return f"Register {reg}" if reg is not None else ""

    def update_from_live_register(self, reg):
        if not self.live_update_cb.isChecked():
            return
        reg_no = int(reg.reg)
        visible_regs = {int(item["reg"]) for item in self._visible_items()}
        if reg_no in visible_regs:
            self.refresh_table()

    def _selected_reg(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return int(data) if data is not None else None

    def _parse_bus(self) -> int:
        # Parameterfenster hat absichtlich keine eigene Bus-Eingabe mehr.
        # Fuer Warmlink/WP nutzen wir die Standardadresse; Spezialfaelle laufen weiter ueber die Haupt-GUI.
        return DEFAULT_BUS_ADDR

    def edit_selected_description(self):
        reg_no = self._selected_reg()
        if reg_no is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte zuerst eine Parameterzeile auswählen.")
            return
        if self.main_window.edit_register_knowledge(reg_no):
            self._items = self._collect_parameter_items()
            self.refresh_blocks()
            self.refresh_table()
            item = self._find_item_by_reg(reg_no)
            if item:
                self.description_box.setText(self._description_detail_text(item, include_title=False).replace("\n", "   |   ") or "Beschreibung: --")

    def write_selected_register(self):
        reg_no = self._selected_reg()
        if reg_no is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte zuerst eine Parameterzeile auswählen.")
            return
        self.main_window.open_register_quick_write(reg_no, self._parse_bus())

    def read_visible_registers(self, auto: bool = False):
        items = self._visible_items()
        if not items:
            self._set_read_status("Status: keine sichtbaren Parameter", error=True)
            return
        regs = sorted({int(item["reg"]) for item in items})
        blocks = self._build_read_blocks(regs, max_span=90)
        bus = self._parse_bus()
        pause_ms = 350
        for start, qty in blocks:
            self.main_window.send_read_request(start, qty, slave_addr=bus, label=f"Parameter Einstellungen {start}/{qty}", delay_ms=pause_ms)
        self._read_expected_regs = set(regs)
        self._read_started_monotonic = time.monotonic()
        self._set_read_status(f"Status: lese {len(blocks)} Block/Blöcke für {len(regs)} Parameter ...")
        self.read_status_timer.start()
        prefix = "Auto-Blocklesen" if auto else "Parameter Einstellungen"
        self.main_window._log(f"{prefix}: {len(blocks)} Lesebloecke fuer {len(regs)} Parameter angefordert.")

    def _set_read_status(self, text: str, ok: bool = False, error: bool = False):
        if not hasattr(self, "read_status_label"):
            return
        self.read_status_label.setText(text)
        if ok:
            self.read_status_label.setStyleSheet("color: #1f7a1f; font-weight: bold;")
        elif error:
            self.read_status_label.setStyleSheet("color: #b00020; font-weight: bold;")
        else:
            self.read_status_label.setStyleSheet("color: #7a5200; font-weight: bold;")

    def _register_has_current_value(self, reg_no: int) -> bool:
        reg = self.main_window.latest_regs.get(reg_no)
        if reg is None:
            return False
        try:
            return float(getattr(reg, "timestamp", 0.0)) >= self._read_started_monotonic
        except Exception:
            return True

    def _update_read_status(self):
        if not self._read_expected_regs:
            self.read_status_timer.stop()
            self._set_read_status("Status: bereit", ok=True)
            return
        total = len(self._read_expected_regs)
        read_count = sum(1 for reg_no in self._read_expected_regs if self._register_has_current_value(reg_no))
        if read_count >= total:
            self.read_status_timer.stop()
            self._set_read_status(f"Status: erfolgreich gelesen ({read_count}/{total})", ok=True)
            return
        elapsed = time.monotonic() - self._read_started_monotonic
        if elapsed >= self._read_status_timeout_s:
            self.read_status_timer.stop()
            self._set_read_status(f"Status: Fehler/Timeout ({read_count}/{total} Werte gelesen)", error=True)
            return
        self._set_read_status(f"Status: wird gelesen ({read_count}/{total})")


    def _build_read_blocks(self, regs: list[int], max_span: int = 90) -> list[tuple[int, int]]:
        """Register in moeglichst wenige FC03-Bloecke packen.

        Anders als frueher muessen die Register nicht direkt zusammenhaengen.
        Wir lesen bewusst kleine Luecken mit, weil ein Blockrequest viel schneller ist
        als viele Einzelrequests. Max. 90 Register passt zu unseren bekannten Warmlink-
        Bloecken und bleibt deutlich unter dem Modbus-Limit.
        """
        if not regs:
            return []
        blocks: list[tuple[int, int]] = []
        start = prev = regs[0]
        for reg_no in regs[1:]:
            # Wenn der gesamte Spannbereich noch in einen sicheren Block passt, mergen.
            if (reg_no - start + 1) <= max_span:
                prev = reg_no
                continue
            blocks.append((start, prev - start + 1))
            start = prev = reg_no
        blocks.append((start, prev - start + 1))
        return blocks
