from __future__ import annotations

import os
import re
import sys
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from ui.theme import APP_ICON_FILE

DEFAULT_DEVICE_MODEL = "foxair_green_gl9_1"
KNOWLEDGE_FIELDS = ("description", "knowledge", "notes", "hint", "explanation", "default", "default_by_device", "source", "source_app_video")
DEVICE_MODEL_LABELS = {
    "foxair_green_gl9_1": "FoxAir Green Line GL9-1",
    "foxair_green_gl15_3": "FoxAir Green Line GL15-3",
    "foxair_green_gl22_3": "FoxAir Green Line GL22-3",
    "foxair_blue_bl8_1": "FoxAir Blue Line BL8-1",
    "foxair_blue_bl12_3": "FoxAir Blue Line BL12-3",
    "foxair_blue_bl23_3": "FoxAir Blue Line BL23-3",
}


def app_icon() -> QIcon:
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return QIcon(os.path.join(base_path, APP_ICON_FILE))


def app_theme_is_dark() -> bool:
    app = QApplication.instance()
    return bool(app is not None and str(app.property("foxair_theme") or "light") == "dark")


def register_default_value(data: dict[str, Any], reg_no: Optional[int] = None, device_model: Optional[str] = None) -> str:
    """Defaultwert mit Geräte-Override. Ab 2011 keine Default-Anzeige, weil Live-/Statuswerte."""
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
    """Kompakter Wissenstext ohne Code/Name-Vorspann."""
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
        # Allgemeiner Default gilt fuer alle Geräte, wenn kein Geräte-Override vorhanden ist.
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
        if k == "default":
            if register_default_value(data, reg_no=reg_no, device_model=device_model):
                return True
        elif k == "default_by_device":
            if register_default_value(data, reg_no=reg_no, device_model=device_model):
                return True
        elif str(data.get(k, "")).strip():
            return True
    return False

def register_block_and_clean_name(name: str) -> tuple[str, str, str]:
    """Extrahiert Block/Code aus Mapping-Namen wie 'H31 / Pump Type'.

    Rueckgabe: (block, code, clean_name). Falls kein Block erkannt wird,
    bleibt der Name unveraendert.
    """
    text = str(name or "").strip()
    m = re.match(r"^\s*([A-Z]{1,3})(\d{1,3}(?:-\d+)?)\s*/\s*(.*)$", text)
    if not m:
        m = re.match(r"^\s*([A-Z]{1,3})(\d{1,3}(?:-\d+)?)\b\s*(?:/|-|:)?\s*(.*)$", text)
    if not m:
        return "", "", text
    block = m.group(1).upper()
    code = f"{block}{m.group(2)}"
    clean = m.group(3).strip() or text
    return block, code, clean

def register_meta_parts(data_or_name: Any) -> tuple[str, str, str]:
    """Liefert (block, code, clean_name).

    Neue Mapping-Struktur:
      name = reiner Klartext
      code = z. B. D04 / A40 / SG01
      block = z. B. D / A / SG

    Alte Struktur mit "D04 / Name" bleibt kompatibel.
    """
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
            if code_for_block:
                m = re.match(r"^([A-Z]{1,3})", code_for_block)
                block = m.group(1) if m else ""
            else:
                block = old_block
        if old_code and name != clean:
            name = clean
        return block, code, name
    return register_block_and_clean_name(str(data_or_name or ""))

def code_sort_key(code: str) -> str:
    """Sortierschluessel fuer Codes wie H01, A40, SG08."""
    text = str(code or "")
    m = re.match(r"^([A-Z]{1,3})(\d+)(.*)$", text)
    if not m:
        return text
    block, num, rest = m.groups()
    return f"{block}{int(num):04d}{rest}"

def is_block_dtype(dtype: Any) -> bool:
    return str(dtype or "").upper() == "BLOCK"


def apply_block_header_item_style(table: QTableWidget, item: QTableWidgetItem, is_block: bool) -> None:
    """Blockkopf-/Paketkopf-Zeilen optisch kleiner und kursiv darstellen."""
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
    """QTableWidgetItem mit optionalem Sortierschluessel in Qt.UserRole+1."""
    def __lt__(self, other):
        a = self.data(Qt.UserRole + 1)
        b = other.data(Qt.UserRole + 1) if isinstance(other, QTableWidgetItem) else None
        if a is not None and b is not None:
            return str(a) < str(b)
        return super().__lt__(other)
