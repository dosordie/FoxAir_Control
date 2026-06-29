#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import ctypes
import json
import os
import queue
import re
import socket
import subprocess
import sys
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional, BinaryIO
from warmlink_raw_capture import DEFAULT_CAPTURE_SETTINGS, WarmlinkRawCapture

from ui.paths import app_program_dir as _app_program_dir, app_resource_dir as _app_resource_dir, resource_path as _resource_path
from ui.context_menu_helpers import RegisterContextAction, exec_register_context_menu
from ui.theme import (
    APP_ICON_FILE,
    PUBLIC_WARNING_TEXT,
    get_app_stylesheet,
    get_splash_close_button_stylesheet,
    get_splash_label_stylesheet,
    get_splash_stylesheet,
)
from dialogs.cloud_dialog import WarmLinkCloudDialog
from cloud.warmlink_api import (
    ENDPOINT_AUTO_WRITE,
    translate_cloud_error_message,
)
from cloud.token_store import get_password, get_token
from cloud.mapping_validation import cloud_hint_matches_local_code
from cloud.cloud_write_helpers import (
    cloud_code_for_register,
    cloud_write_choice_options,
    cloud_write_value_from_label,
    cloud_write_values_for_code,
    current_raw_text_for_cloud_write,
)
from workers.warmlink_cloud_worker import WarmLinkCloudCommandWorker

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPixmap, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from workers.display_worker import DisplayKnownReadController
from workers.warmlink_worker import WarmlinkInitReadController
from workers.standard_modbus_worker import StandardModbusInitReadController
from workers.dual_logger_worker import DualLoggerWorkerController

from cloud.warmlink_codes import (
    DEFAULT_WARMLINK_CLOUD_CODES,
    cloud_hint,
    cloud_modbus_register,
    code_confidence,
    code_unit,
    WARMLINK_CLOUD_CREDIT,
    code_display_name,
)
from core.settings_manager import ensure_defaults, load_settings, save_settings
from core.update_checker import (
    UPDATE_RELEASES_URL,
    UPDATE_REPO,
    UpdateCheckWorker,
    open_update_url,
    parse_version_tuple,
)
from core.foxair_phnix_core import (
    DEFAULT_BUS_ADDR,
    DecodedRegister,
    RegisterMap,
    WarmlinkSocketClient,
    ModbusSerialClient,
    build_read_frame,
    build_write_frame,
    build_write_registers_frame,
    build_write_single_frame,
    decode_contact_bits,
    decode_frame,
    decode_read_response_registers,
    find_frames,
    get_write_value,
    guess_device_name,
    hexdump,
    hex_ascii_line,
    numeric_value_by_type,
    format_value_by_type,
    s16,
)


APP_VERSION = "0.5.51"
BUILD_DATE = "2026-06-29"
APP_EDITION = "PUBLIC"
APP_TITLE = f"FoxAir / Phnix Control V{APP_VERSION}{' PRIVATE' if APP_EDITION.upper() == 'PRIVATE' else ''} - by DosOrDie"

FLASH_CHANGED_ROW_MS = 2000
FLASH_CHANGED_ROW_COLOR = QColor(255, 255, 130)
FLASH_CHANGED_ROW_FADE_STEPS = [
    (0, QColor(255, 255, 130)),
    (850, QColor(255, 255, 185)),
]

# V0.2.46 PUBLIC: Cloud-only-Schalter nur noch im Cloud-Fenster; Log-Drosselung bleibt aktiv.
# 1 = sehr ruhig, 7 = Debug/alles. Die eigentliche Einordnung erfolgt
# absichtlich per Textklassifikation in MainWindow._infer_log_level(), damit
# bestehende Worker-/Dialog-Signale kompatibel bleiben.
LOG_LEVEL_LABELS = [
    (1, "1 Ruhig: Werte/Fehler"),
    (2, "2 Normal: + Bedienung/Verbindung"),
    (3, "3 Schreiben: + Writes/ACK/Timer"),
    (4, "4 Chat-Diagnose: Writes + Bestätigung"),
    (5, "5 Bus: + Reads/Fremdframes"),
    (6, "6 Trace: + RAW/TX/lange Blöcke"),
    (7, "7 Debug: alles"),
]
DEFAULT_HOST = "192.168.10.43"
DEFAULT_PORT = 2001
def app_program_dir() -> str:
    """Ordner der EXE bzw. des Scripts."""
    return _app_program_dir(__file__)


def app_user_data_dir() -> str:
    """Ordner fuer benutzerspezifische Daten.

    Public/Installer-Versionen speichern Settings, Cache, Knowledge, Backups und
    Logs unter AppData, weil Program Files ohne Adminrechte nicht beschreibbar ist.
    Private/portable Versionen halten weiterhin alles neben EXE/Script.
    """
    if APP_EDITION.upper() == "PRIVATE":
        return app_program_dir()
    if os.name == "nt":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "FoxAir Phnix Control")
    root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(root, "FoxAir Phnix Control")

def app_resource_dir() -> str:
    """Ordner der mitgelieferten Programmdaten."""
    return _app_resource_dir(__file__)

DEVICE_MODELS = [
    ("foxair_green_gl9_1", "FoxAir Green Line GL9-1"),
    ("foxair_green_gl15_3", "FoxAir Green Line GL15-3"),
    ("foxair_green_gl22_3", "FoxAir Green Line GL22-3"),
    ("foxair_blue_bl8_1", "FoxAir Blue Line BL8-1"),
    ("foxair_blue_bl12_3", "FoxAir Blue Line BL12-3"),
    ("foxair_blue_bl23_3", "FoxAir Blue Line BL23-3"),
]
DEVICE_MODEL_LABELS = dict(DEVICE_MODELS)
DEFAULT_DEVICE_MODEL = "foxair_green_gl9_1"
DEVICE_MODEL_HINT = "GL = R290, BL = R32. Auswahl nur für Defaultwerte relevant."


def resource_path(relative_path: str) -> str:
    """Pfad fuer normale Ausfuehrung und PyInstaller-Bundle."""
    return _resource_path(relative_path, __file__)


def app_icon() -> QIcon:
    icon_path = resource_path(APP_ICON_FILE)
    icon = QIcon(icon_path)
    return icon


def ask_yes_no(parent, title: str, text: str, default_yes: bool = False) -> bool:
    """Deutsche Ja/Nein-Bestätigung statt Qt-Standard Yes/No."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(str(title))
    box.setText(str(text))
    yes_btn = box.addButton("Ja", QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton("Nein", QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(yes_btn if default_yes else no_btn)
    box.exec()
    return box.clickedButton() is yes_btn


def app_icon_pixmap(size: int = 96) -> QPixmap:
    pix = QPixmap(resource_path(APP_ICON_FILE))
    if pix.isNull():
        return QPixmap()
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def windows_apps_use_light_theme() -> Optional[bool]:
    """Windows-Appmodus erkennen. True=hell, False=dunkel, None=unbekannt/nicht Windows."""
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return bool(int(value))
    except Exception:
        return None


def resolve_app_theme(theme: str = "light") -> str:
    selected = (theme or "light").lower().strip()
    if selected == "system":
        detected = windows_apps_use_light_theme()
        return "light" if detected is not False else "dark"
    if selected not in ("light", "dark"):
        return "light"
    return selected


def apply_app_theme(target: Any, theme: str = "light") -> str:
    """Eigenes App-Theme setzen, damit Windows-Darkmode keine unleserlichen Mischfarben erzeugt."""
    app = QApplication.instance()
    requested = (theme or "light").lower().strip()
    selected = resolve_app_theme(requested)
    if app is not None:
        try:
            app.setStyle("Fusion")
        except Exception:
            pass
        app.setProperty("foxair_theme_request", requested)
        app.setProperty("foxair_theme", selected)
        app.setStyleSheet(get_app_stylesheet(selected))
    elif hasattr(target, "setStyleSheet"):
        target.setStyleSheet(get_app_stylesheet(selected))
    return selected


def app_theme_is_dark() -> bool:
    app = QApplication.instance()
    return bool(app is not None and str(app.property("foxair_theme") or "light") == "dark")

KNOWLEDGE_FIELDS = ("description", "knowledge", "notes", "hint", "explanation", "default", "default_by_device", "source", "source_app_video")


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


class StartupSplash(QDialog):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setObjectName("StartupSplash")
        self.setStyleSheet(get_splash_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 24)
        close_btn.setToolTip("Splash schließen")
        close_btn.setStyleSheet(get_splash_close_button_stylesheet())
        close_btn.clicked.connect(self._skip)
        top.addWidget(close_btn, 0, Qt.AlignRight | Qt.AlignTop)
        root.addLayout(top)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet(get_splash_label_stylesheet("logo"))
        pix = QPixmap(resource_path(APP_ICON_FILE))
        if not pix.isNull():
            logo_label.setPixmap(pix.scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        root.addWidget(logo_label, 0, Qt.AlignCenter)

        title = QLabel("FoxAir / Phnix Control")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(get_splash_label_stylesheet("title"))
        root.addWidget(title)

        version = QLabel(f"Version V{APP_VERSION}  •  {BUILD_DATE}")
        version.setObjectName("version")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet(get_splash_label_stylesheet("version"))
        root.addWidget(version)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        brand = QLabel("FoxAir Control\nby DosOrDie")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        brand.setStyleSheet(get_splash_label_stylesheet("brand"))
        bottom.addWidget(brand, 0, Qt.AlignRight | Qt.AlignBottom)
        root.addLayout(bottom)

        self.resize(520, 470)

    def _skip(self):
        self.clicked.emit()
        self.close()



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
        code = str(data_or_name.get("code", "")).strip().upper()
        block = str(data_or_name.get("block", "")).strip().upper()
        old_block, old_code, clean = register_block_and_clean_name(name)
        if not code and old_code:
            code = old_code
        if not block:
            if code:
                m = re.match(r"^([A-Z]{1,3})", code)
                block = m.group(1) if m else ""
            else:
                block = old_block
        if old_code and name != clean:
            name = clean
        return block, code, name
    return register_block_and_clean_name(str(data_or_name or ""))


def clean_register_name(name: str) -> str:
    return register_block_and_clean_name(name)[2]


def code_sort_key(code: str) -> str:
    """Sortierschluessel fuer Codes wie H01, A40, SG08."""
    text = str(code or "")
    m = re.match(r"^([A-Z]{1,3})(\d+)(.*)$", text)
    if not m:
        return text
    block, num, rest = m.groups()
    return f"{block}{int(num):04d}{rest}"


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

def is_block_dtype(dtype: Any) -> bool:
    return str(dtype or "").upper() == "BLOCK"


class SortableTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem mit optionalem Sortierschluessel in Qt.UserRole+1."""
    def __lt__(self, other):
        a = self.data(Qt.UserRole + 1)
        b = other.data(Qt.UserRole + 1) if isinstance(other, QTableWidgetItem) else None
        if a is not None and b is not None:
            return str(a) < str(b)
        return super().__lt__(other)

def set_windows_app_id() -> None:
    """Sorgt unter Windows dafuer, dass das Taskleistenicon sauber gruppiert wird."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FoxAir.PhnixControl.0.2.30")
    except Exception:
        pass



class ReaderWorker(QObject):
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)
    log = Signal(str)
    frame_decoded = Signal(object)
    raw_chunk = Signal(bytes)
    tx_chunk = Signal(bytes)

    def __init__(self, host: str, port: int, regmap: RegisterMap, backend_label: str = "Warmlink RAW TCP", write_single: bool = False, transport: str = "tcp", serial_port: str = "COM3", baudrate: int = 9600, parity: str = "N", bytesize: int = 8, stopbits: float = 1.0):
        super().__init__()
        self.host = host
        self.port = port
        self.regmap = regmap
        self.backend_label = backend_label
        self.write_single = bool(write_single)
        self.transport = str(transport or "tcp")
        self.serial_port = str(serial_port or "COM3")
        self.baudrate = int(baudrate)
        self.parity = str(parity or "N")
        self.bytesize = int(bytesize)
        self.stopbits = float(stopbits)
        self.running = False
        self.client = None
        self.buf = bytearray()
        self.write_queue: queue.Queue[tuple[str, int, int, int, int, bool]] = queue.Queue()
        self.next_write_monotonic = 0.0
        self.last_send_monotonic = 0.0
        self.last_send_desc = ""
        self.rx_after_last_send = True
        self.rx_timeout_logged = False
        self.total_rx_bytes = 0
        self.rx_restbuffer_since_monotonic = 0.0

    @Slot()
    def run(self):
        self.running = True
        try:
            if self.transport == "serial":
                self.log.emit(f"Verbinde zu {self.serial_port} {self.baudrate},{self.bytesize}{self.parity}{self.stopbits:g} ({self.backend_label}) ...")
                self.client = ModbusSerialClient(self.serial_port, baudrate=self.baudrate, parity=self.parity, bytesize=self.bytesize, stopbits=self.stopbits, timeout=0.5)
            else:
                self.log.emit(f"Verbinde zu {self.host}:{self.port} ({self.backend_label}) ...")
                self.client = WarmlinkSocketClient(self.host, self.port, timeout=0.5)
            self.client.connect()
            self.connected.emit()
            self.log.emit("Verbunden. Lese Stream ...")
            if self.transport == "serial" and "Warmlink" in self.backend_label:
                self.log.emit("Hinweis: Warmlink RAW ueber COM nutzt Bus 0x63. Am normalen User-Modbus-Anschluss meist Standard Modbus / Unit 1 waehlen.")

            while self.running:
                self._flush_write_queue()
                try:
                    chunk = self.client.recv(4096)
                    if not chunk:
                        self.log.emit("Verbindung geschlossen (EOF).")
                        break

                    self.raw_chunk.emit(chunk)
                    self.total_rx_bytes += len(chunk)
                    if self.transport == "serial":
                        self.log.emit(f"SERIAL RX Rohdaten: {len(chunk)} Byte, HEX={hexdump(chunk, -1)}")
                    self.rx_after_last_send = True
                    self.rx_timeout_logged = False
                    self.buf.extend(chunk)
                    before_parse_len = len(self.buf)
                    parsed_frames = find_frames(self.buf, max_len=512)
                    after_parse_len = len(self.buf)
                    if parsed_frames:
                        self.log.emit(
                            f"DEBUG RX-Parser: {len(parsed_frames)} Frame(s) direkt nach Eingang verarbeitet, "
                            f"Buffer {before_parse_len}->{after_parse_len} Byte"
                        )
                        if after_parse_len:
                            self.rx_restbuffer_since_monotonic = time.monotonic()
                            self.log.emit(
                                f"RX-Restbuffer nach Frame-Verarbeitung behalten: {after_parse_len} Byte, "
                                f"HEX={hexdump(bytes(self.buf), -1)}"
                            )
                        else:
                            self.rx_restbuffer_since_monotonic = 0.0
                    elif before_parse_len:
                        if after_parse_len:
                            if self.rx_restbuffer_since_monotonic <= 0.0:
                                self.rx_restbuffer_since_monotonic = time.monotonic()
                            self.log.emit(
                                f"DEBUG RX-Parser: nach Eingang noch kein vollstaendiges Frame, "
                                f"Restbuffer behalten: {after_parse_len} Byte, HEX={hexdump(bytes(self.buf), -1)}"
                            )
                        else:
                            self.rx_restbuffer_since_monotonic = 0.0
                            self.log.emit(
                                f"DEBUG RX-Parser: nach Eingang kein gueltiges Frame; "
                                f"Restdaten verworfen: {before_parse_len} Byte"
                            )

                    self._discard_stale_rx_restbuffer()

                    for parsed in parsed_frames:
                        frame = decode_frame(parsed, self.regmap)
                        self.frame_decoded.emit(frame)

                except socket.timeout:
                    self._discard_stale_rx_restbuffer()
                    self._check_rx_timeout()
                    self._flush_write_queue()
                    continue

        except Exception as exc:
            if self.running:
                self.error.emit(str(exc))
        finally:
            if self.client:
                self.client.close()
            self.running = False
            self.disconnected.emit()

    def _discard_stale_rx_restbuffer(self) -> None:
        if not self.buf:
            self.rx_restbuffer_since_monotonic = 0.0
            return
        if self.rx_restbuffer_since_monotonic <= 0.0:
            self.rx_restbuffer_since_monotonic = time.monotonic()
            return
        if time.monotonic() - self.rx_restbuffer_since_monotonic < 3.0:
            return
        rest = bytes(self.buf)
        self.buf.clear()
        self.rx_restbuffer_since_monotonic = 0.0
        self.log.emit(
            f"RX-Restbuffer verworfen: {len(rest)} Byte, kein gültiges Frame; "
            f"HEX={hexdump(rest, -1)}"
        )

    @Slot()
    def stop(self):
        self.running = False
        if self.client:
            self.client.close()

    def enqueue_write(self, addr: int, value: int, slave_addr: int = DEFAULT_BUS_ADDR, post_delay_ms: int = 0, write_single: Optional[bool] = None):
        use_single = self.write_single if write_single is None else bool(write_single)
        self.write_queue.put(("write", slave_addr, addr, value, post_delay_ms, use_single))
        delay_text = f", danach Pause {post_delay_ms} ms" if post_delay_ms > 0 else ""
        self.log.emit(
            f"WRITE in Sendewarteschlange: bus=0x{slave_addr:02X}, "
            f"addr={addr} / 0x{addr:04X}, value={value} / 0x{value:04X}{delay_text}"
        )

    def enqueue_write_block(self, addr: int, values: list[int] | tuple[int, ...], slave_addr: int = DEFAULT_BUS_ADDR, post_delay_ms: int = 0):
        vals = [int(v) & 0xFFFF for v in values]
        self.write_queue.put(("write_block", slave_addr, addr, vals, post_delay_ms, False))
        delay_text = f", danach Pause {post_delay_ms} ms" if post_delay_ms > 0 else ""
        preview_vals = ", ".join(f"{addr + i}={v}/0x{v:04X}" for i, v in enumerate(vals[:8]))
        more = "" if len(vals) <= 8 else f" ... (+{len(vals) - 8})"
        self.log.emit(
            f"WRITE-Block in Sendewarteschlange: bus=0x{slave_addr:02X}, "
            f"start={addr} / 0x{addr:04X}, qty={len(vals)}{delay_text}; "
            f"{preview_vals}{more}"
        )

    def enqueue_read(self, addr: int, quantity: int = 1, slave_addr: int = DEFAULT_BUS_ADDR, post_delay_ms: int = 0):
        self.write_queue.put(("read", slave_addr, addr, quantity, post_delay_ms, False))
        delay_text = f", danach Pause {post_delay_ms} ms" if post_delay_ms > 0 else ""
        self.log.emit(
            f"READ in Sendewarteschlange: bus=0x{slave_addr:02X}, "
            f"addr={addr} / 0x{addr:04X}, anzahl={quantity}{delay_text}"
        )

    def _flush_write_queue(self):
        while self.running:
            now = time.monotonic()
            if self.next_write_monotonic > now:
                return

            try:
                kind, slave_addr, addr, value_or_quantity, post_delay_ms, use_single_write = self.write_queue.get_nowait()
            except queue.Empty:
                return

            try:
                if self.buf:
                    self.log.emit(
                        f"DEBUG RX-Buffer erst beim naechsten Send-Zyklus gesehen: "
                        f"{len(self.buf)} Byte stehen vor {kind.upper()} noch im Parser-Buffer"
                    )
                if kind == "read":
                    frame = build_read_frame(addr, value_or_quantity, slave_addr=slave_addr)
                    action = (
                        f"READ gesendet: bus=0x{slave_addr:02X}, "
                        f"addr={addr} / 0x{addr:04X}, anzahl={value_or_quantity}, "
                        f"TX={hexdump(frame, -1)}"
                    )
                elif kind == "write_block":
                    vals = [int(v) & 0xFFFF for v in value_or_quantity]
                    frame = build_write_registers_frame(addr, vals, slave_addr=slave_addr)
                    preview_vals = ", ".join(f"{addr + i}={v}/0x{v:04X}" for i, v in enumerate(vals[:8]))
                    more = "" if len(vals) <= 8 else f" ... (+{len(vals) - 8})"
                    action = (
                        f"WRITE Block gesendet (FC16): bus=0x{slave_addr:02X}, "
                        f"start={addr} / 0x{addr:04X}, qty={len(vals)}, "
                        f"TX={hexdump(frame, -1)}; {preview_vals}{more}"
                    )
                else:
                    if use_single_write:
                        frame = build_write_single_frame(addr, value_or_quantity, slave_addr=slave_addr)
                        fc_text = "FC06"
                    else:
                        frame = build_write_frame(addr, value_or_quantity, slave_addr=slave_addr)
                        fc_text = "FC16"
                    action = (
                        f"WRITE gesendet ({fc_text}): bus=0x{slave_addr:02X}, "
                        f"addr={addr} / 0x{addr:04X}, value={value_or_quantity} / 0x{value_or_quantity:04X}, "
                        f"TX={hexdump(frame, -1)}"
                    )

                if not self.client or not self.client.is_connected():
                    self.error.emit("Nicht verbunden, kann nicht senden.")
                    continue
                self.tx_chunk.emit(frame)
                self.client.send(frame)
                self.last_send_monotonic = time.monotonic()
                self.last_send_desc = action
                self.rx_after_last_send = False
                self.rx_timeout_logged = False
                self.log.emit(action)
                if post_delay_ms > 0:
                    self.next_write_monotonic = time.monotonic() + (post_delay_ms / 1000.0)
                    return
            except Exception as exc:
                self.error.emit(str(exc))

    def _check_rx_timeout(self):
        if self.transport != "serial":
            return
        if self.rx_after_last_send or self.rx_timeout_logged or self.last_send_monotonic <= 0:
            return
        if (time.monotonic() - self.last_send_monotonic) >= 1.2:
            self.rx_timeout_logged = True
            self.log.emit("SERIAL RX-Timeout: nach Sendung kam keine Antwort. Bitte pruefen: richtige Kommunikationsart/Unit, A/B vertauscht, Baudrate/Parity, Abschlusswiderstand, Adapter im RS485-Mode.")


def encode_hhmm(hour: int, minute: int) -> int:
    """Timer-Zeit nach bisheriger Beobachtung: High-Byte=Stunde, Low-Byte=Minute."""
    if not 0 <= hour <= 23:
        raise ValueError("Stunde außerhalb 0..23")
    if not 0 <= minute <= 59:
        raise ValueError("Minute außerhalb 0..59")
    return ((hour & 0xFF) << 8) | (minute & 0xFF)


def decode_hhmm(value: int) -> tuple[int, int]:
    return (value >> 8) & 0xFF, value & 0xFF


class ContactDecoderDialog(QDialog):
    def __init__(self, parent: "MainWindow", value: Optional[int]):
        super().__init__(parent)
        self.main_window = parent
        self._last_value: Optional[int] = None
        self._flash_tokens: dict[int, int] = {}
        self._flash_colors: dict[int, QColor] = {}
        self.setWindowTitle("Kontaktdecoder Register 2034 / 0x07F2")
        self.resize(1030, 560)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.value_label = QLabel("2034: --")
        self.status_label = QLabel("Bereit.")
        self.status_label.setStyleSheet("color: #666;")
        self.poll_cb = QCheckBox("poll aktiv")
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 3600)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" s")
        self.read_now_btn = QPushButton("jetzt lesen")
        top.addWidget(self.value_label, 1)
        top.addWidget(self.status_label)
        top.addWidget(self.poll_cb)
        top.addWidget(QLabel("Intervall:"))
        top.addWidget(self.poll_interval_spin)
        top.addWidget(self.read_now_btn)
        layout.addLayout(top)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_once)
        self.poll_cb.stateChanged.connect(lambda _=None: self._apply_poll_state())
        self.poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_poll_state())
        self.read_now_btn.clicked.connect(self.poll_once)

        self.table = QTableWidget(16, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalHeaderLabels(["Bit", "Roh", "Name", "Status", "Bedeutung"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.set_value(value)

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        self.status_label.setText("Lese Register 2034 ...")
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2034, 1, slave_addr=slave_addr, label="Kontaktdecoder 2034")

    def _contact_status_for_bit(self, bit: int, bit_value: int) -> str:
        for row_bit, row_bit_value, _name, state, _meaning in decode_contact_bits(1 << bit if bit_value else 0):
            if row_bit == bit and row_bit_value == bit_value:
                return state
        return "Ein" if bit_value else "Aus"

    def _contact_row_color(self, bit: int, bit_value: int, value_known: bool, state: Optional[str] = None) -> QColor:
        if bit in self._flash_tokens:
            return self._flash_colors.get(bit, FLASH_CHANGED_ROW_COLOR)
        if not value_known:
            return QColor(245, 245, 245)
        status = state if state is not None else self._contact_status_for_bit(bit, bit_value)
        return QColor(220, 255, 220) if status == "Ein" else QColor(245, 245, 245)

    def _apply_contact_row_background(self, bit: int, bit_value: int, value_known: bool, state: Optional[str] = None) -> None:
        color = self._contact_row_color(bit, bit_value, value_known, state)
        for col in range(self.table.columnCount()):
            item = self.table.item(bit, col)
            if item is not None:
                item.setBackground(color)

    def _flash_contact_bit_row(self, bit: int, bit_value: int) -> None:
        token = self._flash_tokens.get(bit, 0) + 1
        self._flash_tokens[bit] = token

        def apply_flash_step(color: QColor) -> None:
            if self._flash_tokens.get(bit) != token:
                return
            self._flash_colors[bit] = color
            current = self._last_value
            current_bit = ((int(current) >> bit) & 1) if current is not None else bit_value
            self._apply_contact_row_background(bit, current_bit, current is not None)

        for delay_ms, color in FLASH_CHANGED_ROW_FADE_STEPS:
            QTimer.singleShot(delay_ms, lambda c=color: apply_flash_step(c))

        def clear_flash() -> None:
            if self._flash_tokens.get(bit) != token:
                return
            self._flash_tokens.pop(bit, None)
            self._flash_colors.pop(bit, None)
            current = self._last_value
            current_bit = ((int(current) >> bit) & 1) if current is not None else bit_value
            self._apply_contact_row_background(bit, current_bit, current is not None)
        QTimer.singleShot(FLASH_CHANGED_ROW_MS, clear_flash)

    def set_value(self, value: Optional[int]):
        old_value = self._last_value
        changed_bits: set[int] = set()
        if value is not None and old_value is not None:
            diff = (int(old_value) ^ int(value)) & 0xFFFF
            changed_bits = {bit for bit in range(16) if diff & (1 << bit)}
        self._last_value = value
        if value is None:
            self.value_label.setText("2034: --")
            self.status_label.setText("Noch nicht gelesen.")
            rows = decode_contact_bits(0)
            for bit, _bit_value, name, _state, meaning in rows:
                display_name = name if name else f"Bit {bit} / unbekannt"
                vals = [str(bit), "--", display_name, "--", meaning]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setBackground(QColor(245, 245, 245))
                    self.table.setItem(bit, col, item)
            return

        self.value_label.setText(f"2034: {value} / 0x{value:04X} / bin={value:016b}")
        self.status_label.setText("Erfolgreich gelesen." if not changed_bits else f"Erfolgreich gelesen, {len(changed_bits)} Bit(s) geändert.")
        rows = decode_contact_bits(value)
        for bit, bit_value, name, state, meaning in rows:
            display_name = name if name else f"Bit {bit} / unbekannt"
            vals = [str(bit), str(bit_value), display_name, state, meaning]
            for col, val in enumerate(vals):
                item = self.table.item(bit, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(bit, col, item)
                item.setText(val)
                item.setBackground(self._contact_row_color(bit, bit_value, True, state))
            if bit in changed_bits:
                self._flash_contact_bit_row(bit, bit_value)


class LoadOutputDecoderDialog(QDialog):
    """Decoder fuer Register 2019 / 0x07E3 Lastausgaenge."""

    def __init__(self, parent: "MainWindow", value: Optional[int]):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Lastausgangdecoder Register 2019 / 0x07E3")
        self.setWindowIcon(app_icon())
        self.resize(1030, 560)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.value_label = QLabel("2019: --")
        self.poll_cb = QCheckBox("poll aktiv")
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 3600)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" s")
        self.read_now_btn = QPushButton("jetzt lesen")
        top.addWidget(self.value_label, 1)
        top.addWidget(self.poll_cb)
        top.addWidget(QLabel("Intervall:"))
        top.addWidget(self.poll_interval_spin)
        top.addWidget(self.read_now_btn)
        layout.addLayout(top)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_once)
        self.poll_cb.stateChanged.connect(lambda _=None: self._apply_poll_state())
        self.poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_poll_state())
        self.read_now_btn.clicked.connect(self.poll_once)

        self.table = QTableWidget(16, 4)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalHeaderLabels(["Bit", "Wert", "Ausgang", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 62)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 68)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.set_value(value)

    def _bit_map(self) -> dict[int, str]:
        info = self.main_window.regmap.get(2019)
        return dict(info.bit_map or {}) if info is not None else {}

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2019, 1, slave_addr=slave_addr, label="Lastausgang 2019")

    def set_value(self, value: Optional[int]):
        bit_map = self._bit_map()
        if value is None:
            self.value_label.setText("2019: --")
            raw = 0
        else:
            raw = int(value) & 0xFFFF
            active = [str(bit) for bit in range(16) if raw & (1 << bit)]
            active_text = ",".join(active) if active else "keine"
            self.value_label.setText(f"2019: {raw} / 0x{raw:04X} / Bits EIN: {active_text}")

        for bit in range(16):
            bit_value = 1 if (raw & (1 << bit)) else 0
            name = bit_map.get(bit, "Reserviert / unbekannt")
            status = "EIN" if bit_value else "AUS"
            vals = [str(bit), "--" if value is None else str(bit_value), name, "--" if value is None else status]
            for col, val in enumerate(vals):
                item = self.table.item(bit, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(bit, col, item)
                item.setText(val)
                item.setToolTip(val)
                item.setBackground(QColor(220, 255, 220) if bit_value and value is not None else QColor(245, 245, 245))


class FaultDecoderDialog(QDialog):
    """Klartextanzeige fuer Fehlerbits und Sammelstoerung."""

    FAULT_REGS = [2085, 2086, 2087, 2088, 2089, 2090, 2081, 2082, 2083]
    FAULT_TITLES = {
        2085: "Fehler 1",
        2086: "Fehler 2",
        2087: "Fehler 3",
        2088: "Fehler 4",
        2089: "Fehler 5",
        2090: "Fehler 6",
        2081: "Fehler 7",
        2082: "Fehler 8",
        2083: "Fehler 9",
    }

    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Störungen / Fehlerdecoder")
        self.setWindowIcon(app_icon())
        self.resize(1120, 620)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.status_label = QLabel("Sammelstörung: --")
        self.poll_cb = QCheckBox("poll aktiv")
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 3600)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" s")
        self.read_now_btn = QPushButton("jetzt lesen")
        top.addWidget(self.status_label, 1)
        top.addWidget(self.poll_cb)
        top.addWidget(QLabel("Intervall:"))
        top.addWidget(self.poll_interval_spin)
        top.addWidget(self.read_now_btn)
        layout.addLayout(top)

        self.info_label = QLabel("Alarm-Ausgang: Register 2019 Bit 10. Fehlerklartexte aus Fehlerregistern 2081–2090.")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.table = QTableWidget(0, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalHeaderLabels(["Register", "Fehler", "Bit", "Raw", "Klartext"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 78)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 86)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 48)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 92)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_once)
        self.poll_cb.stateChanged.connect(lambda _=None: self._apply_poll_state())
        self.poll_interval_spin.valueChanged.connect(lambda _=None: self._apply_poll_state())
        self.read_now_btn.clicked.connect(self.poll_once)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.refresh()

    def _apply_poll_state(self):
        if self.poll_cb.isChecked():
            self.poll_timer.start(int(self.poll_interval_spin.value()) * 1000)
        else:
            self.poll_timer.stop()

    def poll_once(self):
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2019, 1, slave_addr=slave_addr, label="Störung: Lastausgang 2019")
        self.main_window.send_read_request(2081, 10, slave_addr=slave_addr, label="Störung: Fehlerregister 2081-2090")

    def _fault_rows(self) -> list[tuple[int, str, int, int, str]]:
        rows: list[tuple[int, str, int, int, str]] = []
        for reg_no in self.FAULT_REGS:
            raw = self.main_window.last_values.get(reg_no)
            if raw is None:
                continue
            raw_i = int(raw) & 0xFFFF
            if raw_i == 0:
                continue
            info = self.main_window.regmap.get(reg_no)
            bit_map = dict(info.bit_map or {}) if info is not None else {}
            for bit in range(16):
                if raw_i & (1 << bit):
                    text = bit_map.get(bit, "Fehlerbit aktiv, Klartext noch unbekannt")
                    rows.append((reg_no, self.FAULT_TITLES.get(reg_no, f"Fehler {reg_no}"), bit, raw_i, text))
        return rows

    def refresh(self):
        load_raw = self.main_window.last_values.get(2019)
        alarm_active = bool((int(load_raw) & (1 << 10))) if load_raw is not None else False
        if load_raw is None:
            self.status_label.setText("Sammelstörung: unbekannt (2019 noch nicht gelesen)")
            self.status_label.setStyleSheet("font-weight: bold;")
        elif alarm_active:
            self.status_label.setText(f"Sammelstörung: AKTIV  |  2019=0x{int(load_raw)&0xFFFF:04X}, Bit 10 = 1")
            self.status_label.setStyleSheet("font-weight: bold; color: white; background-color: #b00020; padding: 4px;")
        else:
            self.status_label.setText(f"Sammelstörung: aus  |  2019=0x{int(load_raw)&0xFFFF:04X}, Bit 10 = 0")
            self.status_label.setStyleSheet("font-weight: bold; color: #006000; padding: 4px;")

        rows = self._fault_rows()
        if not rows:
            self.table.setRowCount(1)
            vals = ["--", "--", "--", "--", "Keine aktiven Fehlerbits in den bekannten Fehlerregistern." if load_raw is not None else "Noch keine Fehlerregister gelesen."]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setBackground(QColor(245, 245, 245))
                self.table.setItem(0, col, item)
            return

        self.table.setRowCount(len(rows))
        for row, (reg_no, title, bit, raw_i, text) in enumerate(rows):
            vals = [str(reg_no), title, str(bit), f"0x{raw_i:04X}", text]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if col in (0, 2, 3):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setToolTip(val)
                item.setBackground(QColor(255, 230, 230))
                self.table.setItem(row, col, item)


class TimerEditorDialog(QDialog):
    """Editor für Timer 1..6.

    Registerschema laut Display-Firmware/ASM:
    Timer n: base = 1281 + (n-1)*7
      +0 Ein-Zeit, +1 Aus-Zeit, +2 WW, +3 HZ, +4 Kühlen, +5 Modus, +6 max. Leistung
    Bitmasken: 1323=Timer1+2, 1324=Timer3+4, 1325=Timer5+6.
    """
    TIMER_REGS = set(range(1281, 1326))
    CAPABILITY_REGS = {1021, 1028}  # H05 Kühlen vorhanden, H28 WW vorhanden
    DAY_BITS = [
        ("Mo", 0x01),
        ("Di", 0x02),
        ("Mi", 0x04),
        ("Do", 0x08),
        ("Fr", 0x10),
        ("Sa", 0x20),
        ("So", 0x40),
    ]
    ACTIVE_BIT = 0x80
    MODE_ITEMS = [
        ("Warmwasser / Code 0", 0),
        ("Heizen / Code 1", 1),
        ("Kühlen / Code 2", 2),
        ("Warmwasser + Heizen / Code 3", 3),
        ("Warmwasser + Kühlen / Code 4", 4),
        ("keinen Modus ändern / Code 9", 9),
    ]

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self.fields: dict[int, dict[str, Any]] = {}
        self.setWindowTitle("Timer 1-6 Editor")
        self.setMinimumWidth(720)
        self.setMinimumHeight(560)
        self._build_ui()
        self.load_from_live_values()

    def _timer_base(self, timer_no: int) -> int:
        return 1281 + (timer_no - 1) * 7

    def _timer_bit_reg(self, timer_no: int) -> int:
        return 1323 + ((timer_no - 1) // 2)

    def _timer_uses_high_byte(self, timer_no: int) -> bool:
        return (timer_no % 2) == 0

    def _build_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Timer 1-6 werden live aus bekannten Registern aktualisiert. "
            "Wenn du gerade ein Feld bearbeitest, wird dieses Feld nicht überschrieben. "
            "Geschrieben wird standardmäßig nur der aktuell geöffnete Timer-Tab."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        # Timer-Editor nutzt die Standard-WP-Adresse. Die Busadresse bleibt bewusst
        # aus der Oberfläche raus, weil sie im Normalbetrieb nicht geändert wird.
        self.bus_edit = QLineEdit(f"0x{DEFAULT_BUS_ADDR:02X}")
        self.bus_edit.setVisible(False)
        self.auto_update_cb = QCheckBox("live aktualisieren")
        self.auto_update_cb.setChecked(True)
        top.addWidget(self.auto_update_cb)
        top.addStretch(1)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        for timer_no in range(1, 7):
            self._add_timer_tab(timer_no)
        self.capability_label = QLabel("")
        self.capability_label.setWordWrap(True)
        layout.addWidget(self.capability_label)
        self._apply_capability_hints()

        bottom = QHBoxLayout()
        self.timer_delay_ms = QSpinBox()
        self.timer_delay_ms.setRange(0, 10000)
        self.timer_delay_ms.setSingleStep(100)
        self.timer_delay_ms.setValue(1200)
        self.timer_delay_ms.setSuffix(" ms")
        self.timer_delay_ms.setToolTip("Pause zwischen den einzelnen Registerwrites.")
        bottom.addWidget(QLabel("Pause zwischen Writes:"))
        bottom.addWidget(self.timer_delay_ms)
        bottom.addStretch(1)
        layout.addLayout(bottom)

        button_layout = QHBoxLayout()
        self.load_btn = QPushButton("Aus Live-Werten laden")
        self.read_btn = QPushButton("Alle Timer von WP lesen")
        self.send_btn = QPushButton("Aktiven Timer schreiben")
        self.send_all_btn = QPushButton("Alle 6 schreiben")
        self.close_btn = QPushButton("Schließen")
        self.load_btn.clicked.connect(self.load_from_live_values)
        self.read_btn.clicked.connect(self.read_from_wp)
        self.send_btn.clicked.connect(self.send_values)
        self.send_all_btn.clicked.connect(self.send_all_values)
        self.close_btn.clicked.connect(self.close)
        for w in (self.load_btn, self.read_btn, self.send_btn, self.send_all_btn):
            button_layout.addWidget(w)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)

    def _add_timer_tab(self, timer_no: int):
        widget = QWidget()
        form = QFormLayout(widget)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        base = self._timer_base(timer_no)
        bit_reg = self._timer_bit_reg(timer_no)
        high = self._timer_uses_high_byte(timer_no)
        byte_label = "High-Byte" if high else "Low-Byte"

        on_hour = QSpinBox(); on_hour.setRange(0, 23)
        on_min = QSpinBox(); on_min.setRange(0, 59)
        on_layout = QHBoxLayout(); on_layout.addWidget(on_hour); on_layout.addWidget(QLabel(":")); on_layout.addWidget(on_min); on_layout.addStretch(1)

        off_hour = QSpinBox(); off_hour.setRange(0, 23)
        off_min = QSpinBox(); off_min.setRange(0, 59)
        off_layout = QHBoxLayout(); off_layout.addWidget(off_hour); off_layout.addWidget(QLabel(":")); off_layout.addWidget(off_min); off_layout.addStretch(1)

        ww_temp = QDoubleSpinBox(); ww_temp.setRange(-50.0, 95.0); ww_temp.setDecimals(1); ww_temp.setSingleStep(0.5); ww_temp.setSuffix(" °C")
        heat_temp = QDoubleSpinBox(); heat_temp.setRange(-50.0, 95.0); heat_temp.setDecimals(1); heat_temp.setSingleStep(0.5); heat_temp.setSuffix(" °C")
        cool_temp = QDoubleSpinBox(); cool_temp.setRange(-50.0, 95.0); cool_temp.setDecimals(1); cool_temp.setSingleStep(0.5); cool_temp.setSuffix(" °C")

        power_kw = QDoubleSpinBox(); power_kw.setRange(0.0, 20.0); power_kw.setDecimals(1); power_kw.setSingleStep(0.1); power_kw.setSuffix(" kW")
        power_raw = QSpinBox(); power_raw.setRange(0, 0xFFFF)
        power_layout = QHBoxLayout(); power_layout.addWidget(power_kw); power_layout.addWidget(QLabel("Raw:")); power_layout.addWidget(power_raw); power_layout.addStretch(1)

        active_cb = QCheckBox("Timer aktiv")
        day_raw = QSpinBox(); day_raw.setRange(0, 0xFFFF)
        day_raw.setToolTip(f"Register {bit_reg}: {byte_label} = Timer {timer_no}, anderes Byte wird erhalten.")
        day_layout = QVBoxLayout()
        day_top = QHBoxLayout(); day_top.addWidget(active_cb); day_top.addWidget(QLabel(f"Reg {bit_reg}, {byte_label}, Raw:")); day_top.addWidget(day_raw); day_top.addStretch(1)
        day_layout.addLayout(day_top)
        checks = []
        day_bits_layout = QHBoxLayout()
        for label, bit in self.DAY_BITS:
            cb = QCheckBox(label)
            cb.setProperty("day_bit", bit)
            checks.append(cb)
            day_bits_layout.addWidget(cb)
        day_bits_layout.addStretch(1)
        day_layout.addLayout(day_bits_layout)

        mode_combo = QComboBox()
        mode_combo.addItem("Raw-Code verwenden", -1)
        for text, code in self.MODE_ITEMS:
            mode_combo.addItem(text, code)
        mode_raw = QSpinBox(); mode_raw.setRange(0, 0xFFFF)
        mode_layout = QHBoxLayout(); mode_layout.addWidget(mode_combo, 1); mode_layout.addWidget(QLabel("Raw:")); mode_layout.addWidget(mode_raw)

        form.addRow(f"Ein ({base}):", on_layout)
        form.addRow(f"Aus ({base + 1}):", off_layout)
        form.addRow(f"WW Ziel ({base + 2}):", ww_temp)
        form.addRow(f"HZ Ziel ({base + 3}):", heat_temp)
        form.addRow(f"Kühlen Ziel ({base + 4}):", cool_temp)
        form.addRow(f"Max. Leistung ({base + 6}):", power_layout)
        form.addRow(f"Tage/Aktiv ({bit_reg}):", day_layout)
        form.addRow(f"Modus ({base + 5}):", mode_layout)

        fld = {
            "base": base,
            "bit_reg": bit_reg,
            "byte_high": high,
            "on_hour": on_hour, "on_min": on_min,
            "off_hour": off_hour, "off_min": off_min,
            "ww_temp": ww_temp, "heat_temp": heat_temp, "cool_temp": cool_temp,
            "power_kw": power_kw, "power_raw": power_raw,
            "active_cb": active_cb, "day_raw": day_raw, "day_checks": checks,
            "mode_combo": mode_combo, "mode_raw": mode_raw,
        }
        self.fields[timer_no] = fld

        power_kw.valueChanged.connect(lambda _=None, t=timer_no: self._power_kw_changed(t))
        power_raw.valueChanged.connect(lambda _=None, t=timer_no: self._power_raw_changed(t))
        active_cb.stateChanged.connect(lambda _=None, t=timer_no: self._day_controls_changed(t))
        day_raw.valueChanged.connect(lambda value, t=timer_no: self._day_raw_changed(t, int(value)))
        for cb in checks:
            cb.stateChanged.connect(lambda _=None, t=timer_no: self._day_controls_changed(t))
        mode_combo.currentIndexChanged.connect(lambda _=None, t=timer_no: self._mode_combo_changed(t))
        mode_raw.valueChanged.connect(lambda value, t=timer_no: self._mode_raw_changed(t, int(value)))

        self.tabs.addTab(widget, f"Timer {timer_no}")

    def _current_timer_no(self) -> int:
        return max(1, min(6, self.tabs.currentIndex() + 1))

    def _has_focus(self, *widgets: QWidget) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        for widget in widgets:
            if focus is widget or widget.isAncestorOf(focus):
                return True
        return False

    def _set_spin_value(self, widget, value, force: bool = False):
        if not force and self._has_focus(widget):
            return
        if isinstance(widget, QDoubleSpinBox):
            if abs(float(widget.value()) - float(value)) > 0.0001:
                widget.setValue(float(value))
        else:
            if int(widget.value()) != int(value):
                widget.setValue(int(value))

    def _set_time_widgets(self, hour_widget: QSpinBox, min_widget: QSpinBox, raw_value: int, force: bool = False):
        if not force and self._has_focus(hour_widget, min_widget):
            return
        hour, minute = decode_hhmm(raw_value)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            self._set_spin_value(hour_widget, hour, force=True)
            self._set_spin_value(min_widget, minute, force=True)

    def _power_kw_changed(self, timer_no: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        self._programmatic = True
        try:
            fld["power_raw"].setValue(int(round(float(fld["power_kw"].value()) * 10.0)) & 0xFFFF)
        finally:
            self._programmatic = False

    def _power_raw_changed(self, timer_no: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        self._programmatic = True
        try:
            fld["power_kw"].setValue(int(fld["power_raw"].value()) / 10.0)
        finally:
            self._programmatic = False

    def _timer_day_byte_from_controls(self, timer_no: int) -> int:
        fld = self.fields[timer_no]
        raw = self.ACTIVE_BIT if fld["active_cb"].isChecked() else 0
        for cb in fld["day_checks"]:
            if cb.isChecked():
                raw |= int(cb.property("day_bit"))
        return raw & 0x00FF

    def _set_day_controls_from_byte(self, timer_no: int, byte_value: int):
        fld = self.fields[timer_no]
        fld["active_cb"].setChecked(bool(byte_value & self.ACTIVE_BIT))
        for cb in fld["day_checks"]:
            cb.setChecked(bool(byte_value & int(cb.property("day_bit"))))

    def _day_controls_changed(self, timer_no: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        current_pair = int(fld["day_raw"].value()) & 0xFFFF
        byte = self._timer_day_byte_from_controls(timer_no)
        if fld["byte_high"]:
            raw = (current_pair & 0x00FF) | (byte << 8)
        else:
            raw = (current_pair & 0xFF00) | byte
        self._programmatic = True
        try:
            fld["day_raw"].setValue(raw & 0xFFFF)
        finally:
            self._programmatic = False

    def _day_raw_changed(self, timer_no: int, value: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        byte = ((int(value) >> 8) & 0xFF) if fld["byte_high"] else (int(value) & 0xFF)
        self._programmatic = True
        try:
            self._set_day_controls_from_byte(timer_no, byte)
        finally:
            self._programmatic = False

    def _mode_combo_changed(self, timer_no: int):
        fld = self.fields[timer_no]
        data = fld["mode_combo"].currentData()
        if data is not None and int(data) >= 0 and fld["mode_raw"].value() != int(data):
            fld["mode_raw"].setValue(int(data))

    def _mode_raw_changed(self, timer_no: int, value: int):
        fld = self.fields[timer_no]
        for idx in range(fld["mode_combo"].count()):
            data = fld["mode_combo"].itemData(idx)
            if data is not None and int(data) == int(value):
                fld["mode_combo"].setCurrentIndex(idx)
                return
        fld["mode_combo"].setCurrentIndex(0)

    def _capability_values(self) -> tuple[bool, bool]:
        cool_reg = self.main_window.latest_regs.get(1021)
        ww_reg = self.main_window.latest_regs.get(1028)
        cooling = True if cool_reg is None else bool(int(cool_reg.raw_value))
        dhw = True if ww_reg is None else bool(int(ww_reg.raw_value))
        return cooling, dhw

    def _set_combo_item_enabled(self, combo: QComboBox, index: int, enabled: bool):
        item = combo.model().item(index) if combo.model() is not None else None
        if item is not None:
            item.setEnabled(enabled)

    def _apply_capability_hints(self):
        cooling, dhw = self._capability_values()
        text = f"Ausstattung erkannt: Kühlen={'ja' if cooling else 'nein/unbekannt deaktiviert'}, WW={'ja' if dhw else 'nein/unbekannt deaktiviert'}"
        if not cooling or not dhw:
            text += " — nicht passende Modus-Auswahlen sind ausgegraut."
        if hasattr(self, "capability_label"):
            self.capability_label.setText(text)
        for fld in self.fields.values():
            combo = fld["mode_combo"]
            for idx in range(combo.count()):
                code = combo.itemData(idx)
                enabled = True
                if code is not None and int(code) >= 0:
                    code = int(code)
                    needs_ww = code in (0, 3, 4)
                    needs_cooling = code in (2, 4)
                    if needs_ww and not dhw:
                        enabled = False
                    if needs_cooling and not cooling:
                        enabled = False
                self._set_combo_item_enabled(combo, idx, enabled)

    def load_from_live_values(self):
        for reg_no in sorted(self.TIMER_REGS | self.CAPABILITY_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg, force=True)
        self._apply_capability_hints()
        # V0.2.41 fix5: Wenn noch kein 1271ff-/Timer-Livewert geladen ist,
        # keine scheinbar sinnvollen Fantasie-Defaults mehr setzen. Leere
        # Timerfelder bleiben konsequent 0, damit ein zu früh geöffnetes Popup
        # nicht 15:00/19:00/55°C/45°C/7°C in den Dialog übernimmt.
        self._programmatic = True
        try:
            for timer_no, fld in self.fields.items():
                base = fld["base"]
                if self.main_window.latest_regs.get(base) is None:
                    self._set_time_widgets(fld["on_hour"], fld["on_min"], encode_hhmm(0, 0), force=True)
                if self.main_window.latest_regs.get(base + 1) is None:
                    self._set_time_widgets(fld["off_hour"], fld["off_min"], encode_hhmm(0, 0), force=True)
                if self.main_window.latest_regs.get(base + 2) is None:
                    fld["ww_temp"].setValue(0.0)
                if self.main_window.latest_regs.get(base + 3) is None:
                    fld["heat_temp"].setValue(0.0)
                if self.main_window.latest_regs.get(base + 4) is None:
                    fld["cool_temp"].setValue(0.0)
                if self.main_window.latest_regs.get(base + 5) is None:
                    fld["mode_raw"].setValue(0)
                    self._mode_raw_changed(timer_no, 0)
                if self.main_window.latest_regs.get(base + 6) is None:
                    fld["power_raw"].setValue(0)
                    fld["power_kw"].setValue(0.0)
                bit_reg = fld["bit_reg"]
                if self.main_window.latest_regs.get(bit_reg) is None:
                    fld["day_raw"].setValue(0)
                    self._set_day_controls_from_byte(timer_no, 0)
        finally:
            self._programmatic = False

    def update_from_live_register(self, reg, force: bool = False):
        reg_no = int(reg.reg)
        if reg_no not in self.TIMER_REGS and reg_no not in self.CAPABILITY_REGS:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        if reg_no in self.CAPABILITY_REGS:
            self._apply_capability_hints()
            return
        raw = int(reg.raw_value) & 0xFFFF
        self._programmatic = True
        try:
            if 1281 <= reg_no <= 1322:
                timer_no = ((reg_no - 1281) // 7) + 1
                offset = (reg_no - 1281) % 7
                fld = self.fields.get(timer_no)
                if not fld:
                    return
                if offset == 0:
                    self._set_time_widgets(fld["on_hour"], fld["on_min"], raw, force=force)
                elif offset == 1:
                    self._set_time_widgets(fld["off_hour"], fld["off_min"], raw, force=force)
                elif offset == 2:
                    self._set_spin_value(fld["ww_temp"], raw / 10.0, force=force)
                elif offset == 3:
                    self._set_spin_value(fld["heat_temp"], raw / 10.0, force=force)
                elif offset == 4:
                    self._set_spin_value(fld["cool_temp"], raw / 10.0, force=force)
                elif offset == 5:
                    self._set_spin_value(fld["mode_raw"], raw, force=force)
                    self._mode_raw_changed(timer_no, raw)
                elif offset == 6:
                    if force or not self._has_focus(fld["power_kw"], fld["power_raw"]):
                        fld["power_raw"].setValue(raw)
                        fld["power_kw"].setValue(raw / 10.0)
            elif 1323 <= reg_no <= 1325:
                first_timer = 1 + (reg_no - 1323) * 2
                for timer_no in (first_timer, first_timer + 1):
                    fld = self.fields.get(timer_no)
                    if not fld:
                        continue
                    if not (force or not self._has_focus(fld["active_cb"], fld["day_raw"], *fld["day_checks"])):
                        continue
                    fld["day_raw"].setValue(raw)
                    byte = ((raw >> 8) & 0xFF) if fld["byte_high"] else (raw & 0xFF)
                    self._set_day_controls_from_byte(timer_no, byte)
        finally:
            self._programmatic = False

    def silent_timer_values(self) -> list[tuple[int, int, str]]:
        return [
            (1244, 1 if self.silent_start_enable_cb.isChecked() else 0, "Silentmodus Start aktiv"),
            (1245, int(self.silent_start_hour.value()) & 0xFFFF, "Silentmodus Start Stunde"),
            (1246, int(self.silent_start_min.value()) & 0xFFFF, "Silentmodus Start Minute"),
            (1247, 1 if self.silent_stop_enable_cb.isChecked() else 0, "Silentmodus Stop aktiv"),
            (1248, int(self.silent_stop_hour.value()) & 0xFFFF, "Silentmodus Stop Stunde"),
            (1249, int(self.silent_stop_min.value()) & 0xFFFF, "Silentmodus Stop Minute"),
        ]

    def timer_values(self, timer_no: Optional[int] = None) -> list[tuple[int, int, str]]:
        if timer_no is None:
            timer_no = self._current_timer_no()
        fld = self.fields[timer_no]
        base = fld["base"]
        bit_reg = fld["bit_reg"]
        return [
            (base, encode_hhmm(int(fld["on_hour"].value()), int(fld["on_min"].value())), f"Timer {timer_no} Ein"),
            (base + 1, encode_hhmm(int(fld["off_hour"].value()), int(fld["off_min"].value())), f"Timer {timer_no} Aus"),
            (base + 2, int(round(float(fld["ww_temp"].value()) * 10.0)) & 0xFFFF, f"Timer {timer_no} WW Zieltemperatur"),
            (base + 3, int(round(float(fld["heat_temp"].value()) * 10.0)) & 0xFFFF, f"Timer {timer_no} HZ Zieltemperatur"),
            (base + 4, int(round(float(fld["cool_temp"].value()) * 10.0)) & 0xFFFF, f"Timer {timer_no} Kuehlen Zieltemperatur"),
            (base + 6, int(fld["power_raw"].value()) & 0xFFFF, f"Timer {timer_no} max. Leistung"),
            (bit_reg, int(fld["day_raw"].value()) & 0xFFFF, f"Timer {timer_no} Aktiv/Tage + Partner-Byte erhalten"),
            (base + 5, int(fld["mode_raw"].value()) & 0xFFFF, f"Timer {timer_no} Modus-Code"),
        ]

    def _pair_raw_from_controls(self, first_timer_no: int) -> int:
        low = self._timer_day_byte_from_controls(first_timer_no)
        high = self._timer_day_byte_from_controls(first_timer_no + 1)
        return ((high & 0xFF) << 8) | (low & 0xFF)

    def all_timer_values(self) -> list[tuple[int, int, str]]:
        out: list[tuple[int, int, str]] = []
        for timer_no in range(1, 7):
            for addr, value, label in self.timer_values(timer_no):
                if addr not in (1323, 1324, 1325):
                    out.append((addr, value, label))
        for first_timer, reg_no in ((1, 1323), (3, 1324), (5, 1325)):
            out.append((reg_no, self._pair_raw_from_controls(first_timer), f"Timer {first_timer}+{first_timer+1} Aktiv/Tage"))
        return out

    def _dry_run_lines(self, values: list[tuple[int, int, str]], slave_addr: int) -> list[str]:
        # PRIVATE fix53: Im Display-Bus nutzen Timer-/SG-/Popup-Mehrfachwrites
        # denselben Bedienwertpfad wie normale Display-Parameterwrites. Der Dry-Run
        # soll deshalb nicht mehr faelschlich direkte 12xx/13xx-FC06-Frames anzeigen.
        helper = getattr(self.main_window, "_timer_write_preview_lines", None)
        if callable(helper):
            return helper(values, slave_addr)
        lines = []
        for addr, value, label in values:
            frame, wire_addr, wire_slave, note, fc_text = self.main_window._build_write_frame_for_backend(addr, value, slave_addr)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")
        return lines

    def show_dry_run(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            lines = self._dry_run_lines(self.timer_values(), slave_addr)
            self.main_window._log("TIMER Dry-Run aktiver Tab:\n" + "\n".join(lines))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def show_dry_run_all(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            lines = self._dry_run_lines(self.all_timer_values(), slave_addr)
            self.main_window._log("TIMER Dry-Run alle 6:\n" + "\n".join(lines))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def read_from_wp(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.send_read_request(1281, 45, slave_addr=slave_addr, label="Timer Bereich 1281-1325")
            self.main_window._log("TIMER Lesen angefordert. Offenes Timerfenster aktualisiert sich bei eintreffenden Werten automatisch.")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Leseanforderung", str(exc))

    def send_values(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            timer_no = self._current_timer_no()
            self.main_window.send_timer_values(slave_addr, self.timer_values(timer_no), int(self.timer_delay_ms.value()), title=f"Timer {timer_no}")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def send_all_values(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.send_timer_values(slave_addr, self.all_timer_values(), int(self.timer_delay_ms.value()), title="Alle Timer 1-6")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))


class OnOffTimerEditorDialog(QDialog):
    """Editor fuer WP Ein/Aus Timer 1..6.

    Registerschema:
      1256..1267 = Timer 1..6 Start/Stop Zeit, je zwei Register
      1268 = Timer 1+2 Aktiv/Tage, 1269 = Timer 3+4, 1270 = Timer 5+6
      pro Byte: Bit7 aktiv, Bit0..6 Mo..So
      Low-Byte = erster Timer im Paar, High-Byte = zweiter Timer im Paar
    """
    TIMER_REGS = set(range(1256, 1271)) | set(range(1244, 1250))
    DAY_BITS = TimerEditorDialog.DAY_BITS
    ACTIVE_BIT = TimerEditorDialog.ACTIVE_BIT

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self.fields: dict[int, dict[str, Any]] = {}
        self.setWindowTitle("WP Ein/Aus / Silentmodus Timer")
        self.setMinimumWidth(650)
        self.setMinimumHeight(540)
        self._build_ui()
        self.load_from_live_values()

    def _time_reg(self, timer_no: int, stop: bool = False) -> int:
        return 1256 + (timer_no - 1) * 2 + (1 if stop else 0)

    def _mask_reg(self, timer_no: int) -> int:
        return 1268 + ((timer_no - 1) // 2)

    def _uses_high_byte(self, timer_no: int) -> bool:
        return (timer_no % 2) == 0

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("WP Ein/Aus Timer: 6 Timer mit Start/Stop, Aktiv und Tagen Mo-So. Silentmodus Timer ist als eigene Registerkarte enthalten.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        self.auto_update_cb = QCheckBox("live aktualisieren")
        self.auto_update_cb.setChecked(True)
        top.addWidget(self.auto_update_cb)
        top.addStretch(1)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        for timer_no in range(1, 7):
            self._add_timer_tab(timer_no)
        self._add_silent_tab()

        bottom = QHBoxLayout()
        self.timer_delay_ms = QSpinBox()
        self.timer_delay_ms.setRange(0, 10000)
        self.timer_delay_ms.setSingleStep(100)
        self.timer_delay_ms.setValue(1200)
        self.timer_delay_ms.setSuffix(" ms")
        bottom.addWidget(QLabel("Pause zwischen Writes:"))
        bottom.addWidget(self.timer_delay_ms)
        bottom.addStretch(1)
        layout.addLayout(bottom)

        buttons = QHBoxLayout()
        self.load_btn = QPushButton("Aus Live-Werten laden")
        self.read_btn = QPushButton("Timer von WP lesen")
        self.send_btn = QPushButton("Aktiven Tab schreiben")
        self.send_all_btn = QPushButton("Alle WP-Timer schreiben")
        self.close_btn = QPushButton("Schließen")
        self.load_btn.clicked.connect(self.load_from_live_values)
        self.read_btn.clicked.connect(self.read_from_wp)
        self.send_btn.clicked.connect(self.send_values)
        self.send_all_btn.clicked.connect(self.send_all_values)
        self.close_btn.clicked.connect(self.close)
        for w in (self.load_btn, self.read_btn, self.send_btn, self.send_all_btn):
            buttons.addWidget(w)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def _add_timer_tab(self, timer_no: int):
        widget = QWidget()
        form = QFormLayout(widget)
        start_reg = self._time_reg(timer_no, False)
        stop_reg = self._time_reg(timer_no, True)
        mask_reg = self._mask_reg(timer_no)
        byte_label = "High-Byte" if self._uses_high_byte(timer_no) else "Low-Byte"

        start_hour = QSpinBox(); start_hour.setRange(0, 23)
        start_min = QSpinBox(); start_min.setRange(0, 59)
        start_layout = QHBoxLayout(); start_layout.addWidget(start_hour); start_layout.addWidget(QLabel(":")); start_layout.addWidget(start_min); start_layout.addStretch(1)

        stop_hour = QSpinBox(); stop_hour.setRange(0, 23)
        stop_min = QSpinBox(); stop_min.setRange(0, 59)
        stop_layout = QHBoxLayout(); stop_layout.addWidget(stop_hour); stop_layout.addWidget(QLabel(":")); stop_layout.addWidget(stop_min); stop_layout.addStretch(1)

        active_cb = QCheckBox("Timer aktiv")
        day_raw = QSpinBox(); day_raw.setRange(0, 0xFFFF)
        day_raw.setToolTip(f"Register {mask_reg}: {byte_label} = Timer {timer_no}, Partner-Byte wird erhalten.")
        day_layout = QVBoxLayout()
        day_top = QHBoxLayout(); day_top.addWidget(active_cb); day_top.addWidget(QLabel(f"Reg {mask_reg}, {byte_label}, Raw:")); day_top.addWidget(day_raw); day_top.addStretch(1)
        day_layout.addLayout(day_top)
        checks = []
        day_bits_layout = QHBoxLayout()
        for label, bit in self.DAY_BITS:
            cb = QCheckBox(label)
            cb.setProperty("day_bit", bit)
            checks.append(cb)
            day_bits_layout.addWidget(cb)
        day_bits_layout.addStretch(1)
        day_layout.addLayout(day_bits_layout)

        form.addRow(f"Ein / Start ({start_reg}):", start_layout)
        form.addRow(f"Aus / Stop ({stop_reg}):", stop_layout)
        form.addRow(f"Tage/Aktiv ({mask_reg}):", day_layout)

        fld = {
            "start_reg": start_reg, "stop_reg": stop_reg, "mask_reg": mask_reg,
            "byte_high": self._uses_high_byte(timer_no),
            "start_hour": start_hour, "start_min": start_min,
            "stop_hour": stop_hour, "stop_min": stop_min,
            "active_cb": active_cb, "day_raw": day_raw, "day_checks": checks,
        }
        self.fields[timer_no] = fld
        active_cb.stateChanged.connect(lambda _=None, t=timer_no: self._day_controls_changed(t))
        day_raw.valueChanged.connect(lambda value, t=timer_no: self._day_raw_changed(t, int(value)))
        for cb in checks:
            cb.stateChanged.connect(lambda _=None, t=timer_no: self._day_controls_changed(t))
        self.tabs.addTab(widget, f"Timer {timer_no}")

    def _add_silent_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.silent_start_enable_cb = QCheckBox("Start aktiv")
        self.silent_stop_enable_cb = QCheckBox("Stop aktiv")
        self.silent_start_hour = QSpinBox(); self.silent_start_hour.setRange(0, 23)
        self.silent_start_min = QSpinBox(); self.silent_start_min.setRange(0, 59)
        self.silent_stop_hour = QSpinBox(); self.silent_stop_hour.setRange(0, 23)
        self.silent_stop_min = QSpinBox(); self.silent_stop_min.setRange(0, 59)
        start_time = QHBoxLayout(); start_time.addWidget(self.silent_start_hour); start_time.addWidget(QLabel(":")); start_time.addWidget(self.silent_start_min); start_time.addStretch(1)
        stop_time = QHBoxLayout(); stop_time.addWidget(self.silent_stop_hour); stop_time.addWidget(QLabel(":")); stop_time.addWidget(self.silent_stop_min); stop_time.addStretch(1)
        form.addRow("Start aktiv (1244):", self.silent_start_enable_cb)
        form.addRow("Startzeit (1245/1246):", start_time)
        form.addRow("Stop aktiv (1247):", self.silent_stop_enable_cb)
        form.addRow("Stopzeit (1248/1249):", stop_time)
        hint = QLabel("Silentmodus Timer: Start und Stop können getrennt aktiviert werden.")
        hint.setWordWrap(True)
        form.addRow("Info:", hint)
        self.tabs.addTab(widget, "Silentmodus")

    def _is_silent_tab(self) -> bool:
        return self.tabs.currentIndex() == 6

    def _current_timer_no(self) -> int:
        return max(1, min(6, self.tabs.currentIndex() + 1))

    def _has_focus(self, *widgets: QWidget) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        return any(focus is w or w.isAncestorOf(focus) for w in widgets)

    def _set_time_widgets(self, hour_widget: QSpinBox, min_widget: QSpinBox, raw: int, force: bool = False):
        if not force and self._has_focus(hour_widget, min_widget):
            return
        hour, minute = decode_hhmm(raw)
        hour_widget.setValue(max(0, min(23, hour)))
        min_widget.setValue(max(0, min(59, minute)))

    def _timer_day_byte_from_controls(self, timer_no: int) -> int:
        fld = self.fields[timer_no]
        value = self.ACTIVE_BIT if fld["active_cb"].isChecked() else 0
        for cb in fld["day_checks"]:
            if cb.isChecked():
                value |= int(cb.property("day_bit"))
        return value & 0xFF

    def _byte_from_pair_raw(self, timer_no: int, raw: int) -> int:
        return ((raw >> 8) & 0xFF) if self._uses_high_byte(timer_no) else (raw & 0xFF)

    def _set_day_controls_from_byte(self, timer_no: int, byte: int):
        fld = self.fields[timer_no]
        fld["active_cb"].setChecked(bool(byte & self.ACTIVE_BIT))
        for cb in fld["day_checks"]:
            cb.setChecked(bool(byte & int(cb.property("day_bit"))))

    def _day_controls_changed(self, timer_no: int):
        if self._programmatic:
            return
        fld = self.fields[timer_no]
        raw = int(fld["day_raw"].value()) & 0xFFFF
        byte = self._timer_day_byte_from_controls(timer_no)
        if fld["byte_high"]:
            raw = (raw & 0x00FF) | ((byte & 0xFF) << 8)
        else:
            raw = (raw & 0xFF00) | (byte & 0xFF)
        self._programmatic = True
        try:
            fld["day_raw"].setValue(raw)
        finally:
            self._programmatic = False

    def _day_raw_changed(self, timer_no: int, raw: int):
        if self._programmatic:
            return
        byte = self._byte_from_pair_raw(timer_no, raw)
        self._programmatic = True
        try:
            self._set_day_controls_from_byte(timer_no, byte)
        finally:
            self._programmatic = False

    def load_from_live_values(self):
        for reg_no in sorted(self.TIMER_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg, force=True)

    def update_from_live_register(self, reg, force: bool = False):
        reg_no = int(reg.reg)
        if reg_no not in self.TIMER_REGS:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        raw = int(reg.raw_value) & 0xFFFF
        self._programmatic = True
        try:
            if 1244 <= reg_no <= 1249:
                if reg_no == 1244:
                    self.silent_start_enable_cb.setChecked(bool(raw))
                elif reg_no == 1245:
                    self.silent_start_hour.setValue(max(0, min(23, raw)))
                elif reg_no == 1246:
                    self.silent_start_min.setValue(max(0, min(59, raw)))
                elif reg_no == 1247:
                    self.silent_stop_enable_cb.setChecked(bool(raw))
                elif reg_no == 1248:
                    self.silent_stop_hour.setValue(max(0, min(23, raw)))
                elif reg_no == 1249:
                    self.silent_stop_min.setValue(max(0, min(59, raw)))
            elif 1256 <= reg_no <= 1267:
                timer_no = ((reg_no - 1256) // 2) + 1
                fld = self.fields.get(timer_no)
                if not fld:
                    return
                if (reg_no - 1256) % 2 == 0:
                    self._set_time_widgets(fld["start_hour"], fld["start_min"], raw, force=force)
                else:
                    self._set_time_widgets(fld["stop_hour"], fld["stop_min"], raw, force=force)
            elif 1268 <= reg_no <= 1270:
                first_timer = 1 + (reg_no - 1268) * 2
                for timer_no in (first_timer, first_timer + 1):
                    fld = self.fields.get(timer_no)
                    if not fld:
                        continue
                    if not (force or not self._has_focus(fld["active_cb"], fld["day_raw"], *fld["day_checks"])):
                        continue
                    fld["day_raw"].setValue(raw)
                    self._set_day_controls_from_byte(timer_no, self._byte_from_pair_raw(timer_no, raw))
        finally:
            self._programmatic = False

    def _pair_raw_from_controls(self, first_timer_no: int) -> int:
        low = self._timer_day_byte_from_controls(first_timer_no)
        high = self._timer_day_byte_from_controls(first_timer_no + 1)
        return ((high & 0xFF) << 8) | (low & 0xFF)

    def timer_values(self, timer_no: Optional[int] = None) -> list[tuple[int, int, str]]:
        if timer_no is None:
            timer_no = self._current_timer_no()
        fld = self.fields[timer_no]
        return [
            (fld["start_reg"], encode_hhmm(int(fld["start_hour"].value()), int(fld["start_min"].value())), f"WP Ein/Aus Timer {timer_no} Start"),
            (fld["stop_reg"], encode_hhmm(int(fld["stop_hour"].value()), int(fld["stop_min"].value())), f"WP Ein/Aus Timer {timer_no} Stop"),
            (fld["mask_reg"], int(fld["day_raw"].value()) & 0xFFFF, f"WP Ein/Aus Timer {timer_no} Aktiv/Tage + Partner-Byte erhalten"),
        ]

    def all_timer_values(self) -> list[tuple[int, int, str]]:
        out: list[tuple[int, int, str]] = []
        for timer_no in range(1, 7):
            fld = self.fields[timer_no]
            out.append((fld["start_reg"], encode_hhmm(int(fld["start_hour"].value()), int(fld["start_min"].value())), f"WP Ein/Aus Timer {timer_no} Start"))
            out.append((fld["stop_reg"], encode_hhmm(int(fld["stop_hour"].value()), int(fld["stop_min"].value())), f"WP Ein/Aus Timer {timer_no} Stop"))
        for first_timer, reg_no in ((1, 1268), (3, 1269), (5, 1270)):
            out.append((reg_no, self._pair_raw_from_controls(first_timer), f"WP Ein/Aus Timer {first_timer}+{first_timer+1} Aktiv/Tage"))
        return out

    def _dry_run_lines(self, values: list[tuple[int, int, str]], slave_addr: int) -> list[str]:
        # PRIVATE fix53: Im Display-Bus nutzen Timer-/SG-/Popup-Mehrfachwrites
        # denselben Bedienwertpfad wie normale Display-Parameterwrites. Der Dry-Run
        # soll deshalb nicht mehr faelschlich direkte 12xx/13xx-FC06-Frames anzeigen.
        helper = getattr(self.main_window, "_timer_write_preview_lines", None)
        if callable(helper):
            return helper(values, slave_addr)
        lines = []
        for addr, value, label in values:
            frame, wire_addr, wire_slave, note, fc_text = self.main_window._build_write_frame_for_backend(addr, value, slave_addr)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")
        return lines

    def show_dry_run(self):
        try:
            self.main_window._log("WP EIN/AUS TIMER Dry-Run aktiver Tab:\n" + "\n".join(self._dry_run_lines(self.timer_values(), DEFAULT_BUS_ADDR)))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def show_dry_run_all(self):
        try:
            self.main_window._log("WP EIN/AUS TIMER Dry-Run alle 6:\n" + "\n".join(self._dry_run_lines(self.all_timer_values(), DEFAULT_BUS_ADDR)))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def read_from_wp(self):
        self.main_window.send_read_request(1244, 6, slave_addr=DEFAULT_BUS_ADDR, label="Silentmodus Timer 1244-1249")
        self.main_window.send_read_request(1256, 15, slave_addr=DEFAULT_BUS_ADDR, label="WP Ein/Aus Timer 1256-1270", delay_ms=600)
        self.main_window._log("WP Ein/Aus/Silent Timer Lesen angefordert.")

    def send_values(self):
        try:
            if self._is_silent_tab():
                self.main_window.send_timer_values(DEFAULT_BUS_ADDR, self.silent_timer_values(), int(self.timer_delay_ms.value()), title="Silentmodus Timer")
            else:
                timer_no = self._current_timer_no()
                self.main_window.send_timer_values(DEFAULT_BUS_ADDR, self.timer_values(timer_no), int(self.timer_delay_ms.value()), title=f"WP Ein/Aus Timer {timer_no}")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))

    def send_all_values(self):
        try:
            self.main_window.send_timer_values(DEFAULT_BUS_ADDR, self.all_timer_values(), int(self.timer_delay_ms.value()), title="WP Ein/Aus Timer 1-6")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Timer-Werte", str(exc))


class SilentTimerDialog(QDialog):
    TIMER_REGS = set(range(1244, 1250))

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Silentmodus Timer")
        self.setMinimumWidth(520)
        self.setMinimumHeight(280)
        self._build_ui()
        self.load_from_live_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("Silentmodus Timer: Start und Stop können getrennt aktiviert werden. Register 1244-1249.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.start_enable_cb = QCheckBox("Start aktiv")
        self.stop_enable_cb = QCheckBox("Stop aktiv")
        self.start_hour = QSpinBox(); self.start_hour.setRange(0, 23)
        self.start_min = QSpinBox(); self.start_min.setRange(0, 59)
        self.stop_hour = QSpinBox(); self.stop_hour.setRange(0, 23)
        self.stop_min = QSpinBox(); self.stop_min.setRange(0, 59)
        start_time = QHBoxLayout(); start_time.addWidget(self.start_hour); start_time.addWidget(QLabel(":")); start_time.addWidget(self.start_min); start_time.addStretch(1)
        stop_time = QHBoxLayout(); stop_time.addWidget(self.stop_hour); stop_time.addWidget(QLabel(":")); stop_time.addWidget(self.stop_min); stop_time.addStretch(1)
        form.addRow("Ein aktiv (1244):", self.start_enable_cb)
        form.addRow("Ein Zeit (1245/1246):", start_time)
        form.addRow("Aus aktiv (1247):", self.stop_enable_cb)
        form.addRow("Aus Zeit (1248/1249):", stop_time)
        layout.addLayout(form)

        bottom = QHBoxLayout()
        self.timer_delay_ms = QSpinBox(); self.timer_delay_ms.setRange(0, 10000); self.timer_delay_ms.setValue(1200); self.timer_delay_ms.setSuffix(" ms")
        bottom.addWidget(QLabel("Pause zwischen Writes:")); bottom.addWidget(self.timer_delay_ms); bottom.addStretch(1)
        layout.addLayout(bottom)

        buttons = QHBoxLayout()
        self.load_btn = QPushButton("Aus Live-Werten laden")
        self.read_btn = QPushButton("von WP lesen")
        self.dry_btn = QPushButton("Dry-Run")
        self.send_btn = QPushButton("schreiben")
        self.close_btn = QPushButton("Schließen")
        self.load_btn.clicked.connect(self.load_from_live_values)
        self.read_btn.clicked.connect(self.read_from_wp)
        self.dry_btn.clicked.connect(self.show_dry_run)
        self.send_btn.clicked.connect(self.send_values)
        self.close_btn.clicked.connect(self.close)
        for w in (self.load_btn, self.read_btn, self.dry_btn, self.send_btn):
            buttons.addWidget(w)
        buttons.addStretch(1); buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def load_from_live_values(self):
        for reg_no in sorted(self.TIMER_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg)

    def update_from_live_register(self, reg):
        reg_no = int(reg.reg)
        raw = int(reg.raw_value) & 0xFFFF
        if reg_no == 1244:
            self.start_enable_cb.setChecked(bool(raw))
        elif reg_no == 1245:
            self.start_hour.setValue(max(0, min(23, raw)))
        elif reg_no == 1246:
            self.start_min.setValue(max(0, min(59, raw)))
        elif reg_no == 1247:
            self.stop_enable_cb.setChecked(bool(raw))
        elif reg_no == 1248:
            self.stop_hour.setValue(max(0, min(23, raw)))
        elif reg_no == 1249:
            self.stop_min.setValue(max(0, min(59, raw)))

    def timer_values(self) -> list[tuple[int, int, str]]:
        return [
            (1244, 1 if self.start_enable_cb.isChecked() else 0, "Silentmodus Start aktiv"),
            (1245, int(self.start_hour.value()) & 0xFFFF, "Silentmodus Start Stunde"),
            (1246, int(self.start_min.value()) & 0xFFFF, "Silentmodus Start Minute"),
            (1247, 1 if self.stop_enable_cb.isChecked() else 0, "Silentmodus Stop aktiv"),
            (1248, int(self.stop_hour.value()) & 0xFFFF, "Silentmodus Stop Stunde"),
            (1249, int(self.stop_min.value()) & 0xFFFF, "Silentmodus Stop Minute"),
        ]

    def _dry_run_lines(self) -> list[str]:
        lines = []
        for addr, value, label in self.timer_values():
            frame, wire_addr, wire_slave, note, fc_text = self.main_window._build_write_frame_for_backend(addr, value, DEFAULT_BUS_ADDR)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")
        return lines

    def show_dry_run(self):
        self.main_window._log("SILENT TIMER Dry-Run:\n" + "\n".join(self._dry_run_lines()))

    def read_from_wp(self):
        self.main_window.send_read_request(1244, 6, slave_addr=DEFAULT_BUS_ADDR, label="Silentmodus Timer 1244-1249")
        self.main_window._log("Silentmodus Timer Lesen angefordert.")

    def send_values(self):
        self.main_window.send_timer_values(DEFAULT_BUS_ADDR, self.timer_values(), int(self.timer_delay_ms.value()), title="Silentmodus Timer")


class RegisterQuickWriteDialog(QDialog):
    GENERIC_VALUE_MAPS: dict[str, dict[int, str]] = {
        "TIMER_MODE": {
            0: "Warmwasser",
            1: "Heizen",
            2: "Kühlen",
            3: "Warmwasser + Heizen",
            4: "Warmwasser + Kühlen",
            9: "keinen Modus ändern / Code 9",
        },
        "MODE_0_4": {
            0: "WW",
            1: "HZ",
            2: "Kühlen",
            3: "WW + HZ",
            4: "WW + Kühlen",
        },
        "RUN_MODE": {
            0: "WW",
            1: "HZ",
            2: "Kühlen",
            3: "WW + HZ",
            4: "WW + Kühlen",
        },
        "SG_MODE": {
            0: "Aus",
            1: "Einfach / 1 Kontakt",
            2: "Erweitert / 2 Kontakte",
        },
        "ON_OFF": {
            0: "Aus",
            1: "Ein",
        },
    }

    def __init__(self, main_window: "MainWindow", reg_no: int, slave_addr: int = DEFAULT_BUS_ADDR):
        super().__init__(main_window)
        self.main_window = main_window
        self.reg_no = int(reg_no)
        self.slave_addr = int(slave_addr)
        self.value_map = self._value_map_for_register()
        self._programmatic = False
        self._last_raw: Optional[int] = None
        self._flash_token = 0
        self.setWindowTitle(f"Register {self.reg_no} schnell schreiben")
        self.setMinimumWidth(560)
        self._build_ui()
        self.refresh_from_live()

    def _dict_to_int_map(self, raw_map) -> dict[int, str]:
        out: dict[int, str] = {}
        if not isinstance(raw_map, dict):
            return out
        for key, label in raw_map.items():
            try:
                raw = int(key, 0) if isinstance(key, str) else int(key)
            except Exception:
                continue
            out[raw] = str(label)
        return dict(sorted(out.items()))

    def _value_map_for_register(self) -> dict[int, str]:
        info = self.main_window.regmap.get(self.reg_no)
        merged: dict[int, str] = {}

        # 1) Technische/deutsche Mapping-Werte aus der normalen value_map bevorzugen.
        if info and info.value_map:
            merged.update({int(k): str(v) for k, v in info.value_map.items()})

        # 2) JSON-Felder direkt lesen, damit app_values auch dann funktionieren,
        # wenn RegisterMap sie bewusst nicht in die technische value_map übernimmt.
        reg_def = getattr(self.main_window, "register_defs", {}).get(str(self.reg_no), {})
        if isinstance(reg_def, dict):
            json_map = self._dict_to_int_map(reg_def.get("value_map") or reg_def.get("values"))
            for raw, label in json_map.items():
                merged.setdefault(raw, label)
            app_map = self._dict_to_int_map(reg_def.get("app_values"))
            for raw, label in app_map.items():
                merged.setdefault(raw, label)

        if merged:
            return dict(sorted(merged.items()))

        dtype = (info.dtype if info and info.dtype else "RAW").upper()
        if dtype in self.GENERIC_VALUE_MAPS:
            return dict(self.GENERIC_VALUE_MAPS[dtype])
        if dtype == "DIGI1":
            name = (info.name if info and info.name else "").lower()
            if any(token in name for token in ("an/aus", "ein/aus", "aktiv", "enable", "silent", "kühlfunktion", "ww-funktion")):
                return dict(self.GENERIC_VALUE_MAPS["ON_OFF"])
        return {}

    def _build_ui(self):
        layout = QVBoxLayout(self)
        info = self.main_window.regmap.get(self.reg_no)
        name = info.name if info and info.name else "unbekannt"
        dtype = info.dtype if info and info.dtype else "RAW"
        self.title_label = QLabel(f"Register {self.reg_no} / 0x{self.reg_no:04X}  |  {name}  [{dtype}]")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        reg_def = getattr(self.main_window, "register_defs", {}).get(str(self.reg_no), {})
        info_text = register_extra_info_text(reg_def, include_source=False, reg_no=self.reg_no, device_model=self.main_window.current_device_model()) if isinstance(reg_def, dict) else ""
        if info_text:
            self.description_label = QLabel(info_text.replace("\n", "   |   "))
            self.description_label.setWordWrap(True)
            self.description_label.setStyleSheet("QLabel { background: #fffbe8; border: 1px solid #d8d0a0; padding: 6px; color: #333; }")
            layout.addWidget(self.description_label)

        form = QFormLayout()
        layout.addLayout(form)
        self.current_raw_label = QLabel("--")
        self.current_decoded_label = QLabel("--")
        self.write_value_edit = QLineEdit()
        scale_hint = self.main_window._write_scale_hint(self.reg_no)
        self.write_value_edit.setPlaceholderText("z.B. 1,5" if scale_hint else "z.B. 55")
        self.write_value_edit.textEdited.connect(self._write_value_text_edited)
        form.addRow("aktueller Rohwert:", self.current_raw_label)
        form.addRow("aktueller Wert:", self.current_decoded_label)

        if self.value_map:
            self.value_combo = QComboBox()
            self.value_combo.addItem("Klartext auswählen ...", None)
            for raw, label in sorted(self.value_map.items()):
                self.value_combo.addItem(f"{label}  ({raw} / 0x{raw & 0xFFFF:04X})", int(raw) & 0xFFFF)
            self.value_combo.currentIndexChanged.connect(self._value_combo_changed)
            form.addRow("Klartext:", self.value_combo)
        else:
            self.value_combo = None

        label = "zu schreibender Benutzerwert:" if scale_hint else "zu schreibender Wert:"
        if scale_hint:
            label += f" ({scale_hint})"
        form.addRow(label, self.write_value_edit)
        self.status_label = QLabel("Bereit.")
        self.status_label.setWordWrap(True)
        form.addRow("Status:", self.status_label)

        buttons = QHBoxLayout()
        self.read_btn = QPushButton("Lesen")
        self.write_btn = QPushButton("Schreiben")
        self.close_btn = QPushButton("Schließen")
        self.read_btn.clicked.connect(self.read_register)
        self.write_btn.clicked.connect(self.write_register)
        self.close_btn.clicked.connect(self.close)
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.write_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def _parse_bus(self) -> int:
        return int(self.slave_addr)

    def _select_combo_value(self, raw: int):
        if self.value_combo is None:
            return
        raw &= 0xFFFF
        self._programmatic = True
        try:
            for idx in range(self.value_combo.count()):
                data = self.value_combo.itemData(idx)
                if data is not None and int(data) == raw:
                    self.value_combo.setCurrentIndex(idx)
                    return
            self.value_combo.setCurrentIndex(0)
        finally:
            self._programmatic = False

    def _value_combo_changed(self):
        if self._programmatic or self.value_combo is None:
            return
        data = self.value_combo.currentData()
        if data is None:
            return
        value = int(data) & 0xFFFF
        self._programmatic = True
        try:
            self.write_value_edit.setText(self.main_window._display_write_input_for_register(self.reg_no, value))
        finally:
            self._programmatic = False

    def _write_value_text_edited(self):
        if self._programmatic:
            return
        try:
            raw = self.main_window.parse_register_write_value(self.reg_no, self.write_value_edit.text()) & 0xFFFF
        except Exception:
            if self.value_combo is not None:
                self._programmatic = True
                try:
                    self.value_combo.setCurrentIndex(0)
                finally:
                    self._programmatic = False
            return
        self._select_combo_value(raw)

    def _flash_value_labels(self) -> None:
        self._flash_token += 1
        token = self._flash_token
        style = "QLabel { background: #ffff82; padding: 2px; }"
        self.current_raw_label.setStyleSheet(style)
        self.current_decoded_label.setStyleSheet(style)
        def clear_flash() -> None:
            if self._flash_token != token:
                return
            self.current_raw_label.setStyleSheet("")
            self.current_decoded_label.setStyleSheet("")
        QTimer.singleShot(FLASH_CHANGED_ROW_MS, clear_flash)

    def refresh_from_live(self):
        old_raw = self._last_raw
        reg = self.main_window.latest_regs.get(self.reg_no)
        if reg is None:
            value = self.main_window.last_values.get(self.reg_no)
            if value is None:
                self.current_raw_label.setText("--")
                self.current_decoded_label.setText("--")
                return
            raw = int(value) & 0xFFFF
            info = self.main_window.regmap.get(self.reg_no)
            decoded = format_value_by_type(raw, info.dtype if info else "RAW", info.value_map if info else None, info.bit_map if info else None)
        else:
            raw = int(reg.raw_value) & 0xFFFF
            decoded = str(reg.display_value)
        self.current_raw_label.setText(f"{raw} / 0x{raw:04X} / signed={s16(raw)}")
        self.current_decoded_label.setText(decoded)
        if old_raw is not None and old_raw != raw:
            self._flash_value_labels()
        self._last_raw = raw
        self._select_combo_value(raw)
        if not self.write_value_edit.text().strip() and not self.write_value_edit.hasFocus():
            self.write_value_edit.setText(self.main_window._display_write_input_for_register(self.reg_no, raw))

    def update_from_live_register(self, reg):
        if int(reg.reg) == self.reg_no:
            self.refresh_from_live()
            self.status_label.setText("Gelesener Rohwert aktualisiert.")

    def read_register(self):
        try:
            self.status_label.setText("Lese Register ...")
            self.main_window.send_read_request(self.reg_no, 1, slave_addr=self._parse_bus(), label=f"Popup Register {self.reg_no}")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Leseanforderung", str(exc))

    def write_register(self):
        try:
            value = self.main_window.parse_register_write_value(self.reg_no, self.write_value_edit.text()) & 0xFFFF
            self.status_label.setText("Schreibe Register ...")
            self.main_window.send_register_write(self.reg_no, value, slave_addr=self._parse_bus(), label=f"Popup Register {self.reg_no}")
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültiger Schreibwert", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "Ungültiger Schreibwert", str(exc))

    def show_write_ack(self, wire_addr: int, value: int):
        self.status_label.setText(
            f"Schreiben bestätigt: Register {self.reg_no} / 0x{self.reg_no:04X} "
            f"(wire 0x{int(wire_addr):04X}) = {int(value) & 0xFFFF} / 0x{int(value) & 0xFFFF:04X}. Lese Wert erneut ..."
        )
        try:
            self.read_register()
        except Exception:
            # ACK ist bereits der Schreiberfolg; ein ausbleibender Readback darf das nicht als Fehler darstellen.
            self.status_label.setText("Schreiben bestätigt. Automatisches Nachlesen konnte nicht gestartet werden.")

    def show_write_readback_timeout(self):
        self.status_label.setText("Schreiben bestätigt. Automatisches Nachlesen ohne Antwort.")


class SGReadyEditorDialog(QDialog):
    SG_REGS = set(range(1334, 1342)) | {2133}
    READ_LABEL_VALUES = "SG Ready 1334-1341"
    READ_LABEL_STATUS = "SG Status 2133"

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self._sg_status_read_pending = False
        self._sg_read_generation = 0
        self._last_raw_values: dict[int, int] = {}
        self._flash_tokens: dict[int, int] = {}
        self.setWindowTitle("SG Ready Editor")
        self.setMinimumWidth(620)
        self._build_ui()
        self.load_from_live_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("SG Ready Register 1334-1341 plus read-only aktiver SG-Modus 2133. SG01: Aus / 1 Kontakt / 2 Kontakte. Kontaktstatus wird sofort über Register 2034 angezeigt. Der aktive SG-Modus in Register 2133 kann zeitverzögert umschalten. SG Kontakt 1: Klemme 1–2 / AI-DI16 / Fernschalter. SG Kontakt 2: Klemme 7–8 / DIN_1 / Heat/Cool On/Off / PV-Kontakt. Live-Update überschreibt keine gerade bearbeiteten Felder. Der Lese-/Schreibstatus wird global angezeigt.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        layout.addLayout(form)
        status_row = QHBoxLayout()
        self.status_label = QLabel("Bereit.")
        self.status_label.setStyleSheet("color: #666;")
        self.auto_update_cb = QCheckBox("live aktualisieren")
        self.auto_update_cb.setChecked(True)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.auto_update_cb)
        form.addRow("Status:", status_row)

        self.sg_mode_combo = QComboBox()
        self.sg_mode_combo.addItem("Aus", 0)
        self.sg_mode_combo.addItem("1 Kontakt", 1)
        self.sg_mode_combo.addItem("2 Kontakte", 2)
        form.addRow("SG Ready Auswahl (1334):", self.sg_mode_combo)

        self.raw_spins: dict[int, QSpinBox] = {}
        for reg_no, label in [
            (1335, "SG02 Schlafmodus Zeit"),
            (1336, "SG03 Mode 2 Leistung / wenig PV (RAW / 10 kW)"),
            (1337, "SG04 Mode 3 Leistung / mittel PV (RAW / 10 kW)"),
            (1341, "SG08 E-Heizer / Zusatzfunktion bei Mode 4"),
        ]:
            spin = QSpinBox(); spin.setRange(0, 0xFFFF)
            self.raw_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.temp_spins: dict[int, QDoubleSpinBox] = {}
        for reg_no, label in [
            (1338, "SG05 Mode 4 WW-Sollwertanhebung"),
            (1339, "SG06 Mode 4 HZ-Sollwertanhebung"),
            (1340, "SG07 Mode 4 Kühlen-Sollwertanhebung"),
        ]:
            spin = QDoubleSpinBox(); spin.setRange(-50.0, 25.0); spin.setDecimals(1); spin.setSingleStep(0.5); spin.setSuffix(" °C")
            self.temp_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.sg_status_label = QLabel("--")
        self.sg_status_label.setToolTip("Read-only: Register 2133 / aktiver SG-Modus. 0=WP aus oder SG deaktiviert, 1=SG Mode 1 / Schlafmodus, 2=SG Mode 2 / wenig PV, 3=SG Mode 3 / mittel PV, 4=SG Mode 4 / High PV. Kontaktstatus wird sofort über Register 2034 angezeigt; Register 2133 kann zeitverzögert umschalten.")
        form.addRow("Aktiver SG-Modus (2133, read-only):", self.sg_status_label)

        self.delay_ms = QSpinBox(); self.delay_ms.setRange(0, 10000); self.delay_ms.setValue(500); self.delay_ms.setSingleStep(100); self.delay_ms.setSuffix(" ms")
        form.addRow("Pause zwischen Writes:", self.delay_ms)

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

    def _has_focus(self, *widgets: QWidget) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        return any(focus is w or w.isAncestorOf(focus) for w in widgets)

    def load_from_live_values(self):
        for reg_no in sorted(self.SG_REGS):
            reg = self.main_window.latest_regs.get(reg_no)
            if reg is not None:
                self.update_from_live_register(reg, force=True)

    def _widget_for_reg(self, reg_no: int) -> Optional[QWidget]:
        if reg_no == 1334:
            return self.sg_mode_combo
        if reg_no in self.raw_spins:
            return self.raw_spins[reg_no]
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
        QTimer.singleShot(FLASH_CHANGED_ROW_MS, clear_flash)

    def update_from_live_register(self, reg, force: bool = False):
        reg_no = int(reg.reg)
        if reg_no not in self.SG_REGS:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        raw = int(reg.raw_value) & 0xFFFF
        old_raw = self._last_raw_values.get(reg_no)
        should_flash = old_raw is not None and old_raw != raw
        self._programmatic = True
        try:
            if reg_no == 1334:
                if force or not self._has_focus(self.sg_mode_combo):
                    idx = self.sg_mode_combo.findData(raw)
                    if idx >= 0:
                        self.sg_mode_combo.setCurrentIndex(idx)
            elif reg_no in self.raw_spins:
                spin = self.raw_spins[reg_no]
                if force or not self._has_focus(spin):
                    spin.setValue(raw)
            elif reg_no in self.temp_spins:
                spin = self.temp_spins[reg_no]
                if force or not self._has_focus(spin):
                    spin.setValue(s16(raw) / 10.0)
            elif reg_no == 2133:
                label = {0: "WP aus oder SG deaktiviert", 1: "SG Mode 1 / Schlafmodus", 2: "SG Mode 2 / wenig PV", 3: "SG Mode 3 / mittel PV", 4: "SG Mode 4 / High PV"}.get(raw, "unbekannt / nicht interpretiert")
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
        for reg_no in (1335, 1336, 1337):
            values.append((reg_no, int(self.raw_spins[reg_no].value()) & 0xFFFF, f"SG Register {reg_no}"))
        for reg_no, label in ((1338, "SG05 WW-Anhebung"), (1339, "SG06 HZ-Anhebung"), (1340, "SG07 Kuehlen-Anhebung")):
            values.append((reg_no, int(round(float(self.temp_spins[reg_no].value()) * 10.0)) & 0xFFFF, label))
        values.append((1341, int(self.raw_spins[1341].value()) & 0xFFFF, "SG08 E-Heizer / Zusatzfunktion bei Mode 4"))
        return values

    def read_from_wp(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.remove_pending_read_requests_by_label(
                {self.READ_LABEL_VALUES, self.READ_LABEL_STATUS},
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
        except Exception as exc:
            self._sg_status_read_pending = False
            QMessageBox.warning(self, "Ungültige SG-Status-Leseanforderung", str(exc))

    def send_values(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.status_label.setText("Schreibe SG Ready Werte ...")
            self.main_window.send_timer_values(slave_addr, self.sg_values(), int(self.delay_ms.value()), title="SG Ready")
            self.status_label.setText("SG Ready Schreiben gesendet.")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige SG-Werte", str(exc))



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


def display_bus_address_info(addr: int) -> tuple[str, str, str]:
    """Lesbare Displaybus-Rollen fuer das Popup 'Gesehene Bus-Adressen'."""
    addr = int(addr)
    if addr == 0x00:
        return (
            "Broadcast / WP-Livewerte",
            "FC16 2001/90 und 2091/90",
            "wird als echter WP-Livebereich übernommen",
        )
    if addr == 0x01:
        return (
            "WP-/Kopf-/Power-Modul-Rohstatus",
            "FC16 1999/16, FC03 2099/51",
            "2099/51 virtuell 91099-91149; 91105~2062 AC-Spannung, 91108~2043 DC-Bus",
        )
    if addr == 0x02:
        return (
            "DWIN/HMI-Pfad unklar",
            "FC03 3001/21 Requests gesehen",
            "bisher Diagnose, keine stabile Übernahme",
        )
    if addr == 0x03:
        return (
            "Display / DWIN-Speicher",
            "FC03 3001/21, Parameterpakete 1001ff, Writes 23xx",
            "3001-3021 sichtbar; Bedienwerte laufen über 23xx",
        )
    if addr == 0x04:
        return (
            "interner Teilnehmer/Ziel",
            "FC03 1011/14 Requests",
            "nicht übernehmen, solange Bereich mit 10xx kollidiert",
        )
    if addr == 0x05:
        return (
            "interner Teilnehmer",
            "FC03 2000/90, FC16 1001/90 Nullblock",
            "Null-/Fremdblock gesperrt, überschreibt keine WP-Werte",
        )
    if addr == DEFAULT_BUS_ADDR:
        return (
            "Warmlink/WP",
            "normaler Warmlink-Modbus",
            "Standard-WP-Adresse außerhalb Displaybus",
        )
    return ("unbekannt", "noch keine feste Zuordnung", "nur beobachten")


class BusAddressDialog(QDialog):
    """Popup fuer gesehene Bus-Adressen."""

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Gesehene Bus-Adressen")
        self.setWindowIcon(app_icon())
        self.resize(1040, 380)
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Hinweis: In Modbus-RTU-Requests ist die Adresse die Zieladresse. "
            "Die Rollen unten beschreiben die bisher beobachteten Frames/Erkenntnisse."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Bus", "Rolle", "Typische Frames", "Übernahme/Hinweis",
            "Frames", "CRC OK", "CRC BAD", "Letzter Frame"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        for col in (4, 5, 6, 7):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        btns = QHBoxLayout()
        self.refresh_btn = QPushButton("aktualisieren")
        self.close_btn = QPushButton("Schließen")
        btns.addWidget(self.refresh_btn)
        btns.addStretch(1)
        btns.addWidget(self.close_btn)
        layout.addLayout(btns)
        self.refresh_btn.clicked.connect(self.refresh)
        self.close_btn.clicked.connect(self.close)
        self.refresh()

    def refresh(self):
        stats = getattr(self.main_window, "bus_stats", {})
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(stats))
        for row, addr in enumerate(sorted(stats)):
            st = stats[addr]
            role, typical, hint = display_bus_address_info(int(addr))
            values = [
                f"0x{addr:02X}", role, typical, hint,
                str(st.get("frames", 0)), str(st.get("crc_ok", 0)),
                str(st.get("crc_bad", 0)), str(st.get("last_frame", "")),
            ]
            for col, text in enumerate(values):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(text)
                if col in (0, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setSortingEnabled(True)


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
            # Fuer diese Ansicht sind schreibbare/parametrierbare Register interessant.
            # App-Video-Labels nehmen wir immer mit, auch wenn mode fehlt.
            if "w" not in mode.lower() and not app_label:
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
            num_match = re.search(r"(\d+)", item["code"])
            num = int(num_match.group(1)) if num_match else 9999
            return (item["block"], num, item["reg"])
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
        self.tab_auto_poll_cb = QCheckBox("Block Auto-Poll")
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
        buttons.addWidget(self.read_visible_btn)
        buttons.addWidget(self.refresh_btn)
        buttons.addWidget(self.write_selected_btn)
        buttons.addWidget(self.edit_info_btn)
        buttons.addWidget(self.count_label)
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
            return
        regs = sorted({int(item["reg"]) for item in items})
        blocks = self._build_read_blocks(regs, max_span=90)
        bus = self._parse_bus()
        pause_ms = 350
        for start, qty in blocks:
            self.main_window.send_read_request(start, qty, slave_addr=bus, label=f"Parameter Einstellungen {start}/{qty}", delay_ms=pause_ms)
        prefix = "Auto-Blocklesen" if auto else "Parameter Einstellungen"
        self.main_window._log(f"{prefix}: {len(blocks)} Lesebloecke fuer {len(regs)} Parameter angefordert.")

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

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Backup / Restore Parameter")
        self.setWindowIcon(app_icon())
        self.resize(980, 720)
        self.loaded_backup: Optional[dict[str, Any]] = None

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

        self.backup_info_label = QLabel("Noch kein Backup zusammengestellt.")
        lay.addWidget(self.backup_info_label)

        self.backup_table = QTableWidget(0, 5)
        self.backup_table.setHorizontalHeaderLabels(["Reg", "Code", "Name", "Rohwert", "Wert"])
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
        lay.addWidget(self.backup_table, 1)

        self.read_btn.clicked.connect(self.read_backup_blocks)
        self.refresh_backup_btn.clicked.connect(self.refresh_backup_preview)
        self.save_btn.clicked.connect(self.save_backup_file)
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

    def backup_registers(self) -> list[int]:
        regs: list[int] = []
        for _label, start, end in self.BACKUP_BLOCKS:
            for reg_no in range(start, end + 1):
                info = self.main_window.regmap.get(reg_no)
                if not info:
                    continue
                dtype = str(getattr(info, "dtype", "RAW"))
                name = str(getattr(info, "name", ""))
                if dtype == "BLOCK" or name.lower().startswith("blockkopf"):
                    continue
                regs.append(reg_no)
        return sorted(set(regs))

    def read_backup_blocks(self):
        # Bewusst Blockweise lesen, inkl. Kopf, damit der normale Parser/Blockcheck arbeitet.
        pause = 700
        for label, start, end in self.BACKUP_BLOCKS:
            qty = end - start + 1
            self.main_window.send_read_request(start, qty, slave_addr=DEFAULT_BUS_ADDR, label=f"Backup {label}", delay_ms=pause)
        self.main_window._log(f"Backup: {len(self.BACKUP_BLOCKS)} Parameterbereiche zum Lesen angefordert.")
        QMessageBox.information(self, "Backup lesen", "Leseblöcke wurden angefordert. Nach ein paar Sekunden 'Vorschau aktualisieren' oder direkt speichern.")

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
        for btn in (self.read_btn, self.refresh_backup_btn, self.save_btn):
            btn.setEnabled(not busy)
        if text:
            self.backup_info_label.setText(text)
        QApplication.processEvents()

    def refresh_backup_preview(self):
        self._set_backup_busy(True, "Backup-Vorschau wird aktualisiert ...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            regs = self.backup_registers()
            rows = []
            latest = self.main_window.latest_regs
            for reg_no in regs:
                reg = latest.get(reg_no)
                if reg is None:
                    continue
                rows.append((reg_no, int(reg.raw_value) & 0xFFFF))

            table = self.backup_table
            table.setUpdatesEnabled(False)
            table.setSortingEnabled(False)
            table.clearContents()
            table.setRowCount(len(rows))
            for row, (reg_no, raw) in enumerate(rows):
                code, name, dtype, _raw, display = self._row_values_for_reg(reg_no, raw)
                values = [reg_no, code, name, f"{raw} / 0x{raw:04X}", display]
                for col, val in enumerate(values):
                    align = Qt.AlignLeft if col in (0, 2) else Qt.AlignRight
                    table.setItem(row, col, self._make_table_item(str(val), align))
            missing = len(regs) - len(rows)
            self.backup_info_label.setText(f"Backup-Vorschau: {len(rows)} Werte vorhanden, {missing} noch nicht gelesen.")
        finally:
            self.backup_table.setUpdatesEnabled(True)
            QApplication.restoreOverrideCursor()
            for btn in (self.read_btn, self.refresh_backup_btn, self.save_btn):
                btn.setEnabled(True)

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
            "app_version": APP_VERSION,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "comment": self.comment_edit.toPlainText().strip(),
            "communication": self.main_window._communication_summary_text(),
            "backend": self.main_window.current_backend_key(),
            "device_model": self.main_window.current_device_model(),
            "device_model_label": DEVICE_MODEL_LABELS.get(self.main_window.current_device_model(), self.main_window.current_device_model()),
            "register_count": len(regs),
            "blocks": [{"label": l, "start": s, "end": e} for l, s, e in self.BACKUP_BLOCKS],
            "registers": regs,
        }

    def save_backup_file(self):
        # Wichtig: Beim Speichern die Vorschau NICHT neu aufbauen.
        # Das machte die GUI bei manchen Systemen lange blockiert.
        data = self._build_backup_data()
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
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.backup_info_label.setText(f"Backup gespeichert: {len(data['registers'])} Register")
            self.main_window._log(f"Backup gespeichert: {path} ({len(data['registers'])} Register)")
            QMessageBox.information(self, "Backup gespeichert", f"Gespeichert:\n{path}\n\nRegister: {len(data['registers'])}")
        except Exception as exc:
            QMessageBox.warning(self, "Backup Fehler", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

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
            self.main_window.send_register_write(reg_no, value, slave_addr=DEFAULT_BUS_ADDR, label="Restore", delay_ms=delay_ms)
        self.main_window._log(f"Restore: {len(items)} Register in Sendewarteschlange gestellt.")




class DualBusLoggerDialog(QDialog):
    """Dual-Bus Diagnose-Logger für Display- und Warmlink-Bus.

    Absichtlich als eigener Dialog gekapselt, damit die Funktion später leicht
    wieder entfernt werden kann. Die beiden Streams füllen keine Hauptliste und
    verändern keine Registerwerte; sie loggen nur Zeit, Bus, Rohframes und
    Änderungen. Auf dem Warmlink-Bus kann aktiv gepollt werden, weil dort passiv
    oft wenig Verkehr anliegt.
    """

    WARMLINK_POLL_BLOCKS = [
        (1011, 6, "Soll/Flags 1011-1016"),
        (1157, 3, "Solltemperaturen 1157-1159"),
        (2011, 4, "Status 2011-2014"),
        (2019, 1, "Lastausgang 2019"),
        (2045, 4, "Temperaturen 2045-2048"),
        (2077, 1, "Durchfluss 2077"),
        (2081, 10, "Fehler 2081-2090"),
    ]

    # Diagnose: bewusst begrenzter Display/DWIN-Scan fuer Reverse Engineering.
    # Kein Vollscan ueber den gesamten DWIN-Speicher, damit der Display-Bus nicht zugemüllt wird.
    DISPLAY_DWIN_SCAN_BLOCKS = [
        (3001, 21, "DWIN 3001ff zyklischer Anzeige-/Iconblock"),
        (4544, 4, "DWIN 11C0 Defrost/Icon-Kandidaten"),
        (4720, 16, "DWIN 1270 Wertebereich"),
        (4736, 16, "DWIN 1280 Wertebereich"),
        (4752, 16, "DWIN 1290 Wertebereich"),
        (4768, 16, "DWIN 12A0 Wertebereich"),
        (4784, 16, "DWIN 12B0 Wertebereich"),
        (4800, 16, "DWIN 12C0 Wertebereich"),
        (4816, 16, "DWIN 12D0 Wertebereich"),
        (4832, 16, "DWIN 12E0 Wertebereich"),
        (4848, 16, "DWIN 12F0 Wertebereich"),
        (5920, 8, "DWIN 1720 Present-Mode Text/Pointer"),
        (5936, 8, "DWIN 1730 Operating-Status Text/Pointer"),
    ]

    # Diagnose: Display-Bus Teilnehmer 0x01 aktiv pollen.
    # Ziel: prüfen, ob die Istwerte auf dem Display-Bus von Unit 0x01 kommen
    # und mit den bekannten Warmlink-Registern korrelieren.
    DISPLAY_UNIT1_SCAN_BLOCKS = [
        (2011, 4, "Display Unit 0x01 Status 2011-2014"),
        (2019, 1, "Display Unit 0x01 Lastausgang 2019"),
        (2045, 4, "Display Unit 0x01 Temperaturen 2045-2048"),
        (2077, 1, "Display Unit 0x01 Durchfluss 2077"),
        (2099, 51, "Display Unit 0x01 Rohstatus 2099ff"),
    ]

    # Fix19/Fix21: Aktiver Paketblock-Test auf dem Display-Bus.
    # Historisch kamen die WP/Display-Daten paketweise in 90-Register-Bloecken.
    # Fix21 sendet diese Tests sequenziell (1 Read -> Antwort/Timeout -> naechster Read),
    # damit langsame Antworten nicht mehr dem falschen Startblock zugeordnet werden.
    DISPLAY_PACKET_SCAN_STARTS = [1001, 1091, 1181, 1271, 1361, 1451, 1541, 2001, 2091]
    # Unit 0x03 zuerst: im Test bestaetigt fuer 1001/1091. Danach Vergleichseinheiten.
    # Fix21: 0x02 und 0x05 ebenfalls testweise aufnehmen, weil sie auf dem
    # Display-Bus als echte Teilnehmer erscheinen. 0x00 wird NICHT aktiv
    # gelesen: das ist Modbus-Broadcast/System-Adresse; bei Reads ist keine
    # Antwort zu erwarten.
    DISPLAY_PACKET_SCAN_UNITS = [0x03, 0x01, 0x04, 0x02, 0x05]

    # Fix21: gleicher Paketblock-Test auf dem Warmlink-/WP-Bus. Damit pruefen wir,
    # ob die 10xx-/Parameterpakete auch direkt von einer WP-Adresse lieferbar sind
    # und nicht nur von der Display-Unit 0x03. Getestet wird die eingestellte
    # Warmlink Unit plus Unit 0x01 als Vergleich, falls abweichend.
    WARMLINK_PACKET_SCAN_STARTS = DISPLAY_PACKET_SCAN_STARTS

    # Alias fuer alte interne Referenzen; absichtlich nicht extern genutzt.
    DISPLAY_SCAN_BLOCKS = DISPLAY_DWIN_SCAN_BLOCKS

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Dual-Bus Logger (Diagnose)")
        self.setWindowIcon(app_icon())
        self.resize(980, 680)

        self.display_thread: Optional[QThread] = None
        self.display_worker: Optional[ReaderWorker] = None
        self.warmlink_thread: Optional[QThread] = None
        self.warmlink_worker: Optional[ReaderWorker] = None
        self.display_last: Dict[tuple[int, int], int] = {}
        self.warmlink_last: Dict[tuple[int, int], int] = {}
        self.warmlink_pending_reads: list[dict[str, Any]] = []
        self.display_pending_reads: list[dict[str, Any]] = []
        self.display_passive_pending_reads: list[dict[str, Any]] = []
        self.display_passive_seen: Dict[tuple[Any, ...], float] = {}
        self.known_warmlink_values: Dict[int, dict[str, Any]] = {}
        self.display_correlation_seen: set[tuple[int, int, int, int]] = set()
        self._stopping = False
        self.display_frames = 0
        self.warmlink_frames = 0
        self.display_last_frame_monotonic = 0.0
        self.display_raw_bin: Optional[BinaryIO] = None
        self.display_raw_hex: Optional[BinaryIO] = None
        self.display_raw_start_monotonic = 0.0
        self.display_raw_file_path = ""
        self.display_raw_hex_path = ""
        self.display_raw_bytes = 0
        self.display_raw_chunks = 0
        self.display_packet_scan_index = 0
        self.warmlink_packet_scan_index = 0
        self.dual_worker_controller = DualLoggerWorkerController(self, ReaderWorker)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Dual-Bus Diagnose-Logger: Display-Bus passiv/aktiv mithören und Warmlink-Bus aktiv pollen. "
            "Verifizierte Broadcast-Paketblöcke Unit 0x00 werden ins Hauptfenster übernommen; aktive Display-Reads bleiben Diagnose; "
            "unsichere DWIN-/Fremdblöcke bleiben Diagnose. V0.2.38: DualLogger ist getrennt; aktive Display-Pakettests bleiben Diagnose, Broadcast 0x00 hat Priorität fürs Hauptfenster."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        grid = QGridLayout()
        layout.addLayout(grid)

        host_default = str(getattr(main_window, "host_edit", QLineEdit(DEFAULT_HOST)).text() or DEFAULT_HOST)
        self.display_host_edit = QLineEdit(host_default)
        self.display_port_spin = QSpinBox(); self.display_port_spin.setRange(1, 65535); self.display_port_spin.setValue(2002)
        self.display_unit_spin = QSpinBox(); self.display_unit_spin.setRange(1, 247); self.display_unit_spin.setValue(3)

        self.warmlink_host_edit = QLineEdit(host_default)
        self.warmlink_port_spin = QSpinBox(); self.warmlink_port_spin.setRange(1, 65535); self.warmlink_port_spin.setValue(2001)
        self.warmlink_unit_spin = QSpinBox(); self.warmlink_unit_spin.setRange(1, 247); self.warmlink_unit_spin.setValue(DEFAULT_BUS_ADDR)
        self.warmlink_poll_cb = QCheckBox("Warmlink aktiv pollen")
        self.warmlink_poll_cb.setChecked(True)
        self.warmlink_poll_interval_spin = QSpinBox(); self.warmlink_poll_interval_spin.setRange(2, 3600); self.warmlink_poll_interval_spin.setValue(10); self.warmlink_poll_interval_spin.setSuffix(" s")
        self.display_passive_analyzer_cb = QCheckBox("Display Passiv-Analyzer / Rohframes + Korrelation")
        self.display_passive_analyzer_cb.setChecked(True)
        self.display_raw_file_cb = QCheckBox("Display RAW-Datenstrom in .bin + .hex.txt mitschreiben")
        self.display_raw_file_cb.setChecked(bool(getattr(main_window, "raw_file_cb", None) and main_window.raw_file_cb.isChecked()))
        self.display_scan_cb = QCheckBox("Display/DWIN Unit 0x03 Kandidaten aktiv scannen")
        self.display_scan_cb.setChecked(False)
        self.display_unit1_scan_cb = QCheckBox("Display Unit 0x01 Livewerte aktiv pollen")
        self.display_unit1_scan_cb.setChecked(False)
        self.display_packet_scan_cb = QCheckBox("Display Paketblock-Test aktiv (sequenziell, Unit 3/1/4/2/5, 1001ff..2091ff, Qty 90)")
        self.display_packet_scan_cb.setChecked(False)
        self.display_packet_scan_cb.setToolTip("Nur Diagnose: liest ganze 90er-Paketbloecke sequenziell auf Unit 0x03/0x01/0x04/0x02/0x05. Antworten werden nur diagnostisch geloggt; Hauptfenster nutzt Broadcast Unit 0x00. Unit 0x00 ist Broadcast/System und wird nicht aktiv gelesen.")
        self.warmlink_packet_scan_cb = QCheckBox("Warmlink/WP Paketblock-Test aktiv (sequenziell, Warmlink Unit + 0x01, Qty 90)")
        self.warmlink_packet_scan_cb.setChecked(False)
        self.warmlink_packet_scan_cb.setToolTip("Nur Diagnose: prueft, ob 1001ff..2091ff auch direkt ueber den Warmlink-/WP-Bus kommen. Getestet wird die eingestellte Warmlink Unit und zusaetzlich Unit 0x01.")
        self.display_scan_interval_spin = QSpinBox(); self.display_scan_interval_spin.setRange(5, 3600); self.display_scan_interval_spin.setValue(20); self.display_scan_interval_spin.setSuffix(" s")

        grid.addWidget(QLabel("Display Host:"), 0, 0); grid.addWidget(self.display_host_edit, 0, 1)
        grid.addWidget(QLabel("Display Port:"), 0, 2); grid.addWidget(self.display_port_spin, 0, 3)
        grid.addWidget(QLabel("Display Unit:"), 0, 4); grid.addWidget(self.display_unit_spin, 0, 5)
        grid.addWidget(QLabel("Warmlink Host:"), 1, 0); grid.addWidget(self.warmlink_host_edit, 1, 1)
        grid.addWidget(QLabel("Warmlink Port:"), 1, 2); grid.addWidget(self.warmlink_port_spin, 1, 3)
        grid.addWidget(QLabel("Warmlink Unit:"), 1, 4); grid.addWidget(self.warmlink_unit_spin, 1, 5)
        grid.addWidget(self.warmlink_poll_cb, 2, 0, 1, 2)
        grid.addWidget(QLabel("Warmlink Poll-Intervall:"), 2, 2); grid.addWidget(self.warmlink_poll_interval_spin, 2, 3)
        grid.addWidget(self.display_passive_analyzer_cb, 3, 0, 1, 3)
        grid.addWidget(self.display_raw_file_cb, 3, 3, 1, 3)
        grid.addWidget(self.display_scan_cb, 4, 0, 1, 2)
        grid.addWidget(self.display_unit1_scan_cb, 4, 2, 1, 2)
        grid.addWidget(self.display_packet_scan_cb, 5, 0, 1, 6)
        grid.addWidget(self.warmlink_packet_scan_cb, 6, 0, 1, 6)
        grid.addWidget(QLabel("Aktiv-Scan-Intervall:"), 7, 0); grid.addWidget(self.display_scan_interval_spin, 7, 1)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton("Start Dual-Log")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.poll_now_btn = QPushButton("Warmlink jetzt pollen")
        self.display_scan_now_btn = QPushButton("Display jetzt scannen")
        self.clear_btn = QPushButton("Log leeren")
        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.stop_btn)
        buttons.addWidget(self.poll_now_btn)
        buttons.addWidget(self.display_scan_now_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.clear_btn)
        layout.addLayout(buttons)

        self.status_label = QLabel("bereit")
        layout.addWidget(self.status_label)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 1)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_warmlink_once)
        self.display_scan_timer = QTimer(self)
        self.display_scan_timer.timeout.connect(self.poll_display_once)
        self.display_packet_step_timer = QTimer(self)
        self.display_packet_step_timer.setInterval(800)
        self.display_packet_step_timer.timeout.connect(self._display_packet_scan_step)
        self.warmlink_packet_step_timer = QTimer(self)
        self.warmlink_packet_step_timer.setInterval(900)
        self.warmlink_packet_step_timer.timeout.connect(self._warmlink_packet_scan_step)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.poll_now_btn.clicked.connect(self.poll_warmlink_once)
        self.display_scan_now_btn.clicked.connect(self.poll_display_once)
        self.clear_btn.clicked.connect(self.log_text.clear)

    def _log(self, text: str):
        # Beim Stoppen laufen aus den Worker-Threads manchmal noch queued Log-Signale ein.
        # Diese Queue-Meldungen sind dann nicht mehr hilfreich und haben das Log geflutet.
        if self._stopping and ("READ in Sendewarteschlange" in text or "WRITE in Sendewarteschlange" in text):
            return

        # V0.2.41 fix6: Dual-/DisplayWorker-Dialog folgt dem Haupt-Log-Level.
        # Dadurch bleibt auch der automatisch gestartete DisplayWorker ruhig, wenn
        # im Hauptfenster Level 1/2 gewaehlt ist. RAW-Datei-Mitschrift bleibt davon
        # unberuehrt.
        try:
            if not self.main_window._should_log_message(str(text)):
                return
        except Exception:
            pass

        stamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{stamp}] {text}")
        # Zusaetzlich im Hauptlog markieren, damit der normale Log-Export reicht.
        # Wenn dieser Dialog nur als ausgelagerter DisplayWorker fuer das Hauptfenster
        # verwendet wird, nicht mehr mit DUAL verwirren. DUAL bleibt nur fuer das
        # wirklich geoeffnete Dual-Logger-Fenster.
        prefix = "DUAL"
        try:
            if bool(getattr(self.main_window, "display_aux_takeover_active", False)) and not self.isVisible():
                if str(text).startswith("Warmlink") or str(text).startswith("WARMLINK"):
                    prefix = "WARMLINK"
                else:
                    prefix = "DISPLAY"
        except Exception:
            prefix = "DUAL"
        self.main_window._log(f"{prefix}: {text}")

    def start(self, display_only: bool = False):
        """Startet den Logger.

        display_only=True wird vom ausgelagerten DisplayWorker fuer
        "Alle bekannten Register lesen" genutzt. In diesem Modus darf NUR
        der Display-Bus geoeffnet werden; der Warmlink-Bus bleibt unberuehrt.
        Das vollstaendige Dual-Logger-Fenster startet weiterhin beide Busse.
        """
        if display_only:
            if self.display_thread:
                return
        elif self.display_thread or self.warmlink_thread:
            return
        self.display_only_mode = bool(display_only)
        self.display_last.clear(); self.warmlink_last.clear(); self.warmlink_pending_reads.clear(); self.display_pending_reads.clear()
        self.display_passive_pending_reads.clear(); self.display_passive_seen.clear()
        self.known_warmlink_values.clear(); self.display_correlation_seen.clear(); self._stopping = False
        self.display_frames = 0; self.warmlink_frames = 0
        self.display_raw_bytes = 0; self.display_raw_chunks = 0
        self.display_packet_scan_index = 0; self.warmlink_packet_scan_index = 0
        self._open_display_raw_files()
        self._start_display_worker()
        if not display_only:
            self._start_warmlink_worker()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        if (not display_only) and self.warmlink_poll_cb.isChecked():
            self.poll_timer.start(int(self.warmlink_poll_interval_spin.value()) * 1000)
            QTimer.singleShot(1200, self.poll_warmlink_once)
        if (not display_only) and self.warmlink_packet_scan_cb.isChecked():
            self.warmlink_packet_step_timer.start()
            QTimer.singleShot(2200, self._warmlink_packet_scan_step)
        if (not display_only) and (self.display_scan_cb.isChecked() or self.display_unit1_scan_cb.isChecked()):
            self.display_scan_timer.start(int(self.display_scan_interval_spin.value()) * 1000)
            QTimer.singleShot(3500, self.poll_display_once)
        if (not display_only) and self.display_packet_scan_cb.isChecked():
            self.display_packet_step_timer.start()
            QTimer.singleShot(3500, self._display_packet_scan_step)
        if display_only:
            self._log("DisplayWorker gestartet: nur Display-Bus aktiv, kein Warmlink-Bus, kein Dual-Logger-Polling.")
        else:
            self._log("Dual-Bus Logger gestartet. Display passiv analysieren aktiv, aktive Display-Scans standardmäßig AUS, Warmlink Polling optional aktiv, Display RAW-Datei optional aktiv.")

    def stop(self):
        self._stopping = True
        self.poll_timer.stop()
        self.display_scan_timer.stop()
        self.display_packet_step_timer.stop()
        self.warmlink_packet_step_timer.stop()
        self.warmlink_pending_reads.clear()
        self.display_pending_reads.clear()
        self.display_passive_pending_reads.clear()
        try:
            if self.warmlink_worker:
                while True:
                    self.warmlink_worker.write_queue.get_nowait()
        except Exception:
            pass
        try:
            if self.display_worker:
                while True:
                    self.display_worker.write_queue.get_nowait()
        except Exception:
            pass
        if getattr(self, "dual_worker_controller", None) is not None:
            self.dual_worker_controller.stop()
        else:
            if self.display_worker:
                self.display_worker.stop()
            if self.warmlink_worker:
                self.warmlink_worker.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._close_display_raw_files()
        if bool(getattr(self, "display_only_mode", False)):
            self._log("DisplayWorker Stop angefordert; Display-Pending/Queue geleert.")
        else:
            self._log("Dual-Bus Logger Stop angefordert; Pending/Queues geleert.")
        self.display_only_mode = False

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)

    def _raw_log_dir(self) -> str:
        base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        path = os.path.join(base, "logs")
        os.makedirs(path, exist_ok=True)
        return path

    def _open_display_raw_files(self):
        self._close_display_raw_files(log_close=False)
        self.display_raw_file_path = ""
        self.display_raw_hex_path = ""
        self.display_raw_start_monotonic = time.monotonic()
        self.display_raw_bytes = 0
        self.display_raw_chunks = 0
        if not getattr(self, "display_raw_file_cb", None) or not self.display_raw_file_cb.isChecked():
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.join(self._raw_log_dir(), f"display_raw_{stamp}")
        self.display_raw_file_path = base + ".bin"
        self.display_raw_hex_path = base + ".hex.txt"
        try:
            self.display_raw_bin = open(self.display_raw_file_path, "wb")
            self.display_raw_hex = open(self.display_raw_hex_path, "w", encoding="utf-8", buffering=1)
            self.display_raw_hex.write("# FoxAir/Phnix Display-Bus RAW Mitschnitt\n")
            self.display_raw_hex.write(f"# Start: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.display_raw_hex.write(f"# Host: {self.display_host_edit.text().strip()} Port: {int(self.display_port_spin.value())}\n")
            self.display_raw_hex.write("# Format: +Sekunden.millis  Richtung  Byteanzahl  HEX\n")
            self._log(f"Display RAW-Dateien geöffnet: {self.display_raw_file_path} und {self.display_raw_hex_path}")
        except Exception as exc:
            self.display_raw_bin = None
            self.display_raw_hex = None
            self._log(f"Display RAW-Dateien konnten nicht geöffnet werden: {exc}")

    def _close_display_raw_files(self, log_close: bool = True):
        path = self.display_raw_file_path
        hex_path = self.display_raw_hex_path
        try:
            if self.display_raw_hex:
                self.display_raw_hex.write(f"# Ende: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.display_raw_hex.write(f"# Chunks: {self.display_raw_chunks}, Bytes: {self.display_raw_bytes}\n")
        except Exception:
            pass
        try:
            if self.display_raw_bin:
                self.display_raw_bin.close()
        except Exception:
            pass
        try:
            if self.display_raw_hex:
                self.display_raw_hex.close()
        except Exception:
            pass
        self.display_raw_bin = None
        self.display_raw_hex = None
        if log_close and path:
            self._log(f"Display RAW-Dateien geschlossen: {path} und {hex_path} ({self.display_raw_bytes} Byte in {self.display_raw_chunks} Chunks)")

    @Slot(bytes)
    def on_display_raw_chunk(self, chunk: bytes):
        if self._stopping or not chunk:
            return
        self.display_raw_chunks += 1
        self.display_raw_bytes += len(chunk)
        if not self.display_raw_bin and not self.display_raw_hex:
            return
        rel = time.monotonic() - (self.display_raw_start_monotonic or time.monotonic())
        try:
            if self.display_raw_bin:
                self.display_raw_bin.write(chunk)
                self.display_raw_bin.flush()
        except Exception as exc:
            self._log(f"Display RAW-BIN Schreibfehler: {exc}")
            try:
                if self.display_raw_bin:
                    self.display_raw_bin.close()
            except Exception:
                pass
            self.display_raw_bin = None
        try:
            if self.display_raw_hex:
                self.display_raw_hex.write(f"+{rel:010.3f}s RX {len(chunk):04d} {hexdump(chunk, -1)}\n")
        except Exception as exc:
            self._log(f"Display RAW-HEX Schreibfehler: {exc}")
            try:
                if self.display_raw_hex:
                    self.display_raw_hex.close()
            except Exception:
                pass
            self.display_raw_hex = None

    def _start_display_worker(self):
        label = "Display-Modbus" if bool(getattr(self, "display_only_mode", False)) else "DUAL Display-Modbus"
        self.dual_worker_controller.start_display_worker(label)

    def _start_warmlink_worker(self):
        self.dual_worker_controller.start_warmlink_worker("DUAL Warmlink-Modbus")

    def _clear_display_refs(self):
        self.display_thread = None
        self.display_worker = None

    def _clear_warmlink_refs(self):
        self.warmlink_thread = None
        self.warmlink_worker = None

    def _find_pending_read(self, pending: list[dict[str, Any]], kind: str) -> tuple[Optional[int], Optional[dict[str, Any]]]:
        for idx, item in enumerate(pending):
            if str(item.get("active_scan_kind", "")) == kind:
                return idx, item
        return None, None

    def _display_packet_scan_sequence(self) -> list[tuple[int, int]]:
        return [(int(unit), int(start)) for unit in self.DISPLAY_PACKET_SCAN_UNITS for start in self.DISPLAY_PACKET_SCAN_STARTS]

    def _warmlink_packet_scan_sequence(self) -> list[tuple[int, int]]:
        primary = int(self.warmlink_unit_spin.value())
        units: list[int] = []
        for unit in (primary, 0x01):
            if 1 <= int(unit) <= 247 and int(unit) not in units:
                units.append(int(unit))
        return [(unit, int(start)) for unit in units for start in self.WARMLINK_PACKET_SCAN_STARTS]

    def _display_packet_scan_step(self):
        if self._stopping or not self.display_packet_scan_cb.isChecked():
            self.display_packet_step_timer.stop()
            return
        if not self.display_worker:
            return
        now = time.monotonic()
        idx, item = self._find_pending_read(self.display_pending_reads, "display_packet")
        if item is not None:
            age = now - float(item.get("queued_at", now))
            if age < 2.8:
                return
            try:
                self.display_pending_reads.pop(idx)  # type: ignore[arg-type]
            except Exception:
                pass
            self._log(
                f"DISPLAY AKTIV Pakettest TIMEOUT: Unit 0x{int(item.get('slave', 0)):02X}, "
                f"start={int(item.get('addr', 0))}/0x{int(item.get('addr', 0)):04X}, qty={int(item.get('qty', 0))}; naechster Block."
            )
        seq = self._display_packet_scan_sequence()
        if not seq:
            return
        slave, addr = seq[self.display_packet_scan_index % len(seq)]
        self.display_packet_scan_index += 1
        label = f"Display Pakettest SEQ Unit 0x{slave:02X} {addr}/0x{addr:04X} qty90"
        self.display_pending_reads.append({
            "slave": slave,
            "addr": addr,
            "qty": 90,
            "label": label,
            "map": "warmlink",
            "packet_test": True,
            "active_scan_kind": "display_packet",
            "queued_at": now,
        })
        self.display_worker.enqueue_read(addr, 90, slave_addr=slave, post_delay_ms=0)
        self._log(f"DISPLAY AKTIV Pakettest gesendet (sequenziell): Unit 0x{slave:02X}, start={addr}/0x{addr:04X}, qty=90")

    def _warmlink_packet_scan_step(self):
        if self._stopping or not self.warmlink_packet_scan_cb.isChecked():
            self.warmlink_packet_step_timer.stop()
            return
        if not self.warmlink_worker:
            return
        now = time.monotonic()
        idx, item = self._find_pending_read(self.warmlink_pending_reads, "warmlink_packet")
        if item is not None:
            age = now - float(item.get("queued_at", now))
            if age < 3.2:
                return
            try:
                self.warmlink_pending_reads.pop(idx)  # type: ignore[arg-type]
            except Exception:
                pass
            self._log(
                f"WARMLINK/WP Pakettest TIMEOUT: Unit 0x{int(item.get('slave', 0)):02X}, "
                f"start={int(item.get('addr', 0))}/0x{int(item.get('addr', 0)):04X}, qty={int(item.get('qty', 0))}; naechster Block."
            )
        seq = self._warmlink_packet_scan_sequence()
        if not seq:
            return
        slave, addr = seq[self.warmlink_packet_scan_index % len(seq)]
        self.warmlink_packet_scan_index += 1
        label = f"Warmlink/WP Pakettest SEQ Unit 0x{slave:02X} {addr}/0x{addr:04X} qty90"
        self.warmlink_pending_reads.append({
            "slave": slave,
            "addr": addr,
            "qty": 90,
            "label": label,
            "packet_test": True,
            "active_scan_kind": "warmlink_packet",
            "queued_at": now,
        })
        self.warmlink_worker.enqueue_read(addr, 90, slave_addr=slave, post_delay_ms=0)
        self._log(f"WARMLINK/WP Pakettest gesendet (sequenziell): Unit 0x{slave:02X}, start={addr}/0x{addr:04X}, qty=90")


    def run_known_display_packet_reads_once(self, pause_ms: int = 900) -> None:
        """Vom Hauptfenster-Button "Alle bekannten Register lesen" nutzbar.

        Fix29: Die Ablaufsteuerung fuer Display-INIT liegt nicht mehr direkt im
        Hauptfenster, sondern im ausgelagerten DisplayKnownReadController. Der
        Controller nutzt weiterhin den bewaehrten Display-Worker-Pfad aus dem
        Dual-Bus-Logger, damit Fix29 eine Strukturänderung ohne neues
        Kommunikationsverhalten bleibt.
        """
        try:
            controller = getattr(self, "_display_known_read_controller", None)
            if controller is None:
                controller = DisplayKnownReadController(self)
                self._display_known_read_controller = controller
            self._log(
                "DISPLAY-INIT: 'Alle bekannten Register lesen' läuft über "
                "den ausgelagerten DisplayWorker-Controller; Warmlink/Standard bleiben unverändert."
            )
            controller.start(pause_ms=pause_ms)
        except Exception as e:
            self._log(f"DISPLAY-INIT Fehler im DisplayWorker-Controller: {e}")

    # V0.2.38: alter Display-INIT-Fallback im Dialog entfernt; Ablauf liegt vollständig in workers/display_worker.py.

    def poll_display_once(self):
        if self._stopping:
            return
        if not self.display_worker:
            self._log("Display Scan nicht gesendet: Display-Worker nicht verbunden/gestartet.")
            return
        delay = 450
        now = time.monotonic()
        queued = 0

        # 1) Display-Bus Unit 0x01 aktiv pollen. Diese Werte werden mit dem
        # normalen Warmlink-Mapping decodiert, aber NICHT in den Registerbrowser geschrieben.
        # So pruefen wir, ob die echten Istwerte auf dem Display-Bus von Unit 0x01 kommen.
        if self.display_unit1_scan_cb.isChecked():
            for addr, qty, label in self.DISPLAY_UNIT1_SCAN_BLOCKS:
                if self._stopping:
                    return
                self.display_pending_reads.append({
                    "slave": 0x01,
                    "addr": int(addr),
                    "qty": int(qty),
                    "label": str(label),
                    "map": "warmlink",
                    "queued_at": now,
                })
                self.display_worker.enqueue_read(addr, qty, slave_addr=0x01, post_delay_ms=delay)
                queued += 1

        # 2) Fix21: Paketblock-Test laeuft NICHT mehr als Massenscan hier,
        # sondern sequenziell ueber _display_packet_scan_step(). Damit werden
        # langsame Antworten nicht dem falschen Startblock zugeordnet.
        if self.display_packet_scan_cb.isChecked() and not self.display_packet_step_timer.isActive():
            self.display_packet_step_timer.start()

        # 3) DWIN/Display-Speicher Unit 0x03 scannen. Diese Werte haben eine eigene
        # Display-Mapping-Tabelle und bleiben Diagnosewerte.
        if self.display_scan_cb.isChecked():
            slave = int(self.display_unit_spin.value())
            for addr, qty, label in self.DISPLAY_DWIN_SCAN_BLOCKS:
                if self._stopping:
                    return
                self.display_pending_reads.append({
                    "slave": slave,
                    "addr": int(addr),
                    "qty": int(qty),
                    "label": str(label),
                    "map": "display",
                    "queued_at": now,
                })
                self.display_worker.enqueue_read(addr, qty, slave_addr=slave, post_delay_ms=delay)
                queued += 1

        if len(self.display_pending_reads) > 220:
            dropped = len(self.display_pending_reads) - 220
            del self.display_pending_reads[:dropped]
            self._log(f"DISPLAY WARN: {dropped} alte Pending-Reads verworfen (keine/zu spaete Antwort).")
        self._log(
            f"Display Scan gesendet: {queued} Blöcke "
            f"(Unit 0x01={'ein' if self.display_unit1_scan_cb.isChecked() else 'aus'}, "
            f"Pakettest={'sequenziell' if self.display_packet_scan_cb.isChecked() else 'aus'}, "
            f"DWIN Unit 0x{int(self.display_unit_spin.value()):02X}={'ein' if self.display_scan_cb.isChecked() else 'aus'})."
        )

    def _associate_display_read_response(self, frame) -> bool:
        if getattr(frame, "mode", "") != "read-response":
            return False
        byte_count = int(getattr(frame, "length_field", 0) or 0)
        if byte_count <= 0 or byte_count % 2 != 0:
            return False
        qty = byte_count // 2
        slave = int(getattr(frame, "slave_addr", 0) or 0)
        match_idx = None
        for idx, item in enumerate(self.display_pending_reads):
            if int(item.get("slave", -1)) == slave and int(item.get("qty", -1)) == qty:
                match_idx = idx
                break
        if match_idx is None:
            return False
        item = self.display_pending_reads.pop(match_idx)
        start = int(item.get("addr", 0))
        label = str(item.get("label", ""))
        map_key = str(item.get("map", "display"))
        decode_map = self.main_window.regmap if map_key == "warmlink" else self.main_window.display_regmap
        regs = decode_read_response_registers(frame, start, decode_map)
        try:
            frame.typ = start
            frame.length_field = qty
            frame.registers = regs
        except Exception:
            pass
        vals = "; ".join(f"{r.reg}={r.raw_value}({r.display_value})" for r in regs[:8])
        self._log(f"DISPLAY RX zugeordnet: {label}: bus=0x{slave:02X}, start={start}/0x{start:04X}, words={qty}: {vals}{' ...' if len(regs) > 8 else ''}")

        # Fix19: Aktive Read-Responses von Paketblock-Tests ebenfalls nur dann
        # vertrauenswuerdig ins Hauptfenster uebernehmen, wenn der interne
        # WP-Paketkopf passt. Damit koennen 10xx/Timer-Bloecke testweise aktiv
        # von Unit 0x01/0x03/0x04 gelesen werden, ohne Roh-/Fremdwerte zu mischen.
        packet_info = self._validated_packet_info_from_regs(start, regs)
        if bool(item.get("packet_test", False)) or packet_info:
            if packet_info:
                end = int(packet_info.get("end", start + len(regs) - 1))
                marker = int(packet_info.get("marker", 0))
                active_kind = str(item.get("active_scan_kind", ""))
                self._log(
                    f"DISPLAY AKTIV VALIDIERTER WP-PAKETBLOCK Unit 0x{slave:02X}: "
                    f"start={start}/0x{start:04X}, ende={end}/0x{end:04X}, "
                    f"words={len(regs)}, marker=0x{marker:04X}, CRC OK, interner Start passt; "
                    "wird fuer Display-Init wieder ins Hauptfenster übernommen."
                )
                # V0.2.38 fix5: Auf Wunsch bleiben aktive Display-Init-Paketreads
                # vorerst sichtbar/nutzbar im Hauptfenster. Die Broadcasts 0x00/2001
                # und 0x00/2091 aktualisieren weiterhin zyklisch und koennen diese
                # Werte spaeter wieder ueberschreiben, sind aber nicht mehr die einzige
                # Quelle fuer das Hauptfenster.
                self._apply_regs_to_main_window(
                    regs,
                    f"aktiv gelesener Display-Init-Paketblock Unit 0x{slave:02X} {start}-{end}",
                )
                if active_kind == "display_init_button":
                    try:
                        ok_items = list(getattr(self, "display_known_init_ok_items", []) or [])
                        if not any(int(x[1]) == int(start) for x in ok_items):
                            ok_items.append((int(slave), int(start), int(qty), str(label)))
                        self.display_known_init_ok_items = ok_items
                        total = 5
                        done = len({int(x[1]) for x in ok_items})
                        self._log(
                            f"DISPLAY-INIT STATUS: OK {done}/{total} - "
                            f"Block {start}/0x{start:04X} erfolgreich gelesen; "
                            "Werte wurden ins Hauptfenster uebernommen."
                        )
                        main_window = getattr(self, "main_window", None)
                        if main_window is not None:
                            try:
                                main_window.init_read_btn.setText(f"Display-Init: {done}/{total} OK")
                            except Exception:
                                pass
                    except Exception:
                        pass
            else:
                internal_hint = ""
                try:
                    raw_words = [int(getattr(r, "raw_value", 0) or 0) & 0xFFFF for r in regs]
                    if len(raw_words) >= 10 and tuple(raw_words[:6]) == self._display_packet_signature_words():
                        internal_hint = f"; Signatur OK, Marker=0x{raw_words[8]&0xFFFF:04X}, interner Start={raw_words[9]&0xFFFF}"
                except Exception:
                    internal_hint = ""
                self._log(
                    f"DISPLAY AKTIV Pakettest ohne gueltigen WP-Paketkopf: "
                    f"Unit 0x{slave:02X}, start={start}/0x{start:04X}, words={qty}; nicht uebernommen{internal_hint}."
                )
                if str(item.get("active_scan_kind", "")) == "display_init_button":
                    try:
                        fail_items = list(getattr(self, "display_known_init_fail_items", []) or [])
                        fail_items.append((int(slave), int(start), int(qty), str(label)))
                        self.display_known_init_fail_items = fail_items
                        self._log(f"DISPLAY-INIT STATUS: ungueltige Antwort fuer Block {start}/0x{start:04X}; wird nur diagnostisch gezaehlt.")
                    except Exception:
                        pass
            active_kind = str(item.get("active_scan_kind", ""))
            if active_kind == "display_packet" and self.display_packet_step_timer.isActive():
                QTimer.singleShot(250, self._display_packet_scan_step)
            elif active_kind == "display_init_button":
                controller = getattr(self, "_display_known_read_controller", None)
                if controller is not None and hasattr(controller, "step"):
                    QTimer.singleShot(max(500, int(getattr(self, "display_known_init_pause_ms", 900))), controller.step)
        return True

    def poll_warmlink_once(self):
        if self._stopping:
            return
        if not self.warmlink_worker:
            self._log("Warmlink Poll nicht gesendet: Warmlink-Worker nicht verbunden/gestartet.")
            return
        if getattr(self, "display_known_init_active", False):
            self._log("Warmlink Poll pausiert: Display-INIT/Alle bekannten Display-Paketreads läuft gerade.")
            return
        slave = int(self.warmlink_unit_spin.value())
        # Etwas langsamer als vorher: ser2net/Warmlink antwortet zuverlaessiger,
        # und die Antworten bleiben leichter der Pending-Liste zuordenbar.
        delay = 700
        now = time.monotonic()
        for addr, qty, label in self.WARMLINK_POLL_BLOCKS:
            if self._stopping:
                return
            self.warmlink_pending_reads.append({
                "slave": slave,
                "addr": int(addr),
                "qty": int(qty),
                "label": str(label),
                "queued_at": now,
            })
            self.warmlink_worker.enqueue_read(addr, qty, slave_addr=slave, post_delay_ms=delay)
        # Alte offene Zuordnungen begrenzen, falls mal keine Antwort kam.
        if len(self.warmlink_pending_reads) > 80:
            dropped = len(self.warmlink_pending_reads) - 80
            del self.warmlink_pending_reads[:dropped]
            self._log(f"WARMLINK WARN: {dropped} alte Pending-Reads verworfen (keine/zu spaete Antwort).")
        self._log(f"Warmlink Poll gesendet: {len(self.WARMLINK_POLL_BLOCKS)} Blöcke auf Unit 0x{slave:02X}.")

    def _associate_warmlink_read_response(self, frame) -> bool:
        """FC03-Responses im Dual-Logger lokal einer gesendeten Warmlink-Anfrage zuordnen.

        Der normale Programmteil macht diese Zuordnung bereits ueber seine eigene
        Pending-Read-Liste. Im Dual-Logger laufen aber eigene Worker, deshalb
        brauchen wir hier eine kleine, leicht entfern­bare lokale Zuordnung.
        Ohne diese Zuordnung haben FC03-Responses keine Startadresse und blieben
        im Log scheinbar leer.
        """
        if getattr(frame, "mode", "") != "read-response":
            return False
        byte_count = int(getattr(frame, "length_field", 0) or 0)
        if byte_count <= 0 or byte_count % 2 != 0:
            self._log(f"WARMLINK RX read-response ohne gueltige Wortanzahl: byte_count={byte_count}, RAW={hexdump(getattr(frame, 'raw', b''), -1)}")
            return False
        qty = byte_count // 2
        slave = int(getattr(frame, "slave_addr", 0) or 0)

        match_idx = None
        for idx, item in enumerate(self.warmlink_pending_reads):
            if int(item.get("slave", -1)) == slave and int(item.get("qty", -1)) == qty:
                match_idx = idx
                break
        if match_idx is None and self.warmlink_pending_reads:
            # Fallback: in Reihenfolge zuordnen. Das ist bei sauberem Request/Response-Ablauf
            # oft besser als gar keine Werte zu sehen; wird im Log als Fallback markiert.
            match_idx = 0
            fallback = True
        else:
            fallback = False

        if match_idx is None:
            self._log(f"WARMLINK RX read-response nicht zuordenbar: bus=0x{slave:02X}, words={qty}, RAW={hexdump(getattr(frame, 'raw', b''), -1)}")
            return False

        item = self.warmlink_pending_reads.pop(match_idx)
        start = int(item.get("addr", 0))
        label = str(item.get("label", ""))
        regs = decode_read_response_registers(frame, start, self.main_window.regmap)
        try:
            frame.typ = start
            frame.length_field = qty
            frame.registers = regs
        except Exception:
            pass
        mark = " Fallback-Zuordnung" if fallback else ""
        vals = "; ".join(f"{r.reg}={r.raw_value}({r.display_value})" for r in regs[:8])
        self._log(f"WARMLINK RX zugeordnet:{mark} {label}: start={start}/0x{start:04X}, words={qty}: {vals}{' ...' if len(regs) > 8 else ''}")

        packet_info = self._validated_packet_info_from_regs(start, regs)
        if bool(item.get("packet_test", False)) or packet_info:
            if packet_info:
                end = int(packet_info.get("end", start + len(regs) - 1))
                marker = int(packet_info.get("marker", 0))
                self._log(
                    f"WARMLINK/WP VALIDIERTER WP-PAKETBLOCK Unit 0x{slave:02X}: "
                    f"start={start}/0x{start:04X}, ende={end}/0x{end:04X}, "
                    f"words={len(regs)}, marker=0x{marker:04X}, CRC OK, interner Start passt"
                )
                self._apply_regs_to_main_window(regs, f"direkt vom Warmlink/WP-Bus validierter Paketblock Unit 0x{slave:02X} {start}-{end}")
            else:
                internal_hint = ""
                try:
                    raw_words = [int(getattr(r, "raw_value", 0) or 0) & 0xFFFF for r in regs]
                    if len(raw_words) >= 10 and tuple(raw_words[:6]) == self._display_packet_signature_words():
                        internal_hint = f"; Signatur OK, Marker=0x{raw_words[8]&0xFFFF:04X}, interner Start={raw_words[9]&0xFFFF}"
                except Exception:
                    internal_hint = ""
                self._log(
                    f"WARMLINK/WP Pakettest ohne gueltigen WP-Paketkopf: "
                    f"Unit 0x{slave:02X}, start={start}/0x{start:04X}, words={qty}; nicht uebernommen{internal_hint}."
                )
            if str(item.get("active_scan_kind", "")) == "warmlink_packet" and self.warmlink_packet_step_timer.isActive():
                QTimer.singleShot(300, self._warmlink_packet_scan_step)
        return True

    def _remember_warmlink_values(self, frame):
        if not getattr(frame, "crc_ok", False):
            return
        if getattr(frame, "mode", "") == "read-request":
            return
        for reg in list(getattr(frame, "registers", []) or []):
            raw = int(getattr(reg, "raw_value", 0) or 0) & 0xFFFF
            # 0/1 erzeugt zu viele falsche Treffer; fuer Korrelation vorerst ignorieren.
            if raw in (0, 1):
                continue
            self.known_warmlink_values[raw] = {
                "reg": int(getattr(reg, "reg", 0) or 0),
                "name": str(getattr(reg, "name", "") or ""),
                "display": str(getattr(reg, "display_value", raw)),
                "seen_at": time.monotonic(),
            }

    def _display_warmlink_correlations(self, frame, regs):
        if not self.known_warmlink_values:
            return
        hits = []
        now = time.monotonic()
        for reg in regs:
            raw = int(getattr(reg, "raw_value", 0) or 0) & 0xFFFF
            if raw in (0, 1):
                continue
            info = self.known_warmlink_values.get(raw)
            if not info:
                continue
            # Nur die ersten Wiederholungen loggen, damit zyklische Frames nicht nerven.
            key = (int(getattr(frame, "slave_addr", 0) or 0), int(getattr(reg, "reg", 0) or 0), raw, int(info.get("reg", 0)))
            if key in self.display_correlation_seen:
                continue
            self.display_correlation_seen.add(key)
            age = now - float(info.get("seen_at", now) or now)
            hits.append(
                f"DREG {int(getattr(reg, 'reg', 0) or 0)}={raw} ({getattr(reg, 'display_value', raw)}) "
                f"== WREG {info.get('reg')} {info.get('name','')} ({info.get('display')}, vor {age:.1f}s)"
            )
        if hits:
            self._log("DISPLAY/WARMLINK KORRELATION: " + "; ".join(hits[:10]) + (f" ... (+{len(hits)-10})" if len(hits) > 10 else ""))

    def _frame_summary(self, prefix: str, frame, last: Dict[tuple[int, int], int], max_changes: int = 18):
        if not getattr(frame, "crc_ok", False):
            return
        if frame.mode == "read-request":
            return
        regs = list(getattr(frame, "registers", []) or [])
        changes = []
        for reg in regs:
            key = (int(frame.slave_addr), int(reg.reg))
            raw = int(reg.raw_value) & 0xFFFF
            old = last.get(key)
            if old != raw:
                last[key] = raw
                name = f" {getattr(reg, 'name', '')}" if getattr(reg, "name", "") else ""
                changes.append(f"{reg.reg}{name}: {'--' if old is None else old} -> {raw} ({getattr(reg, 'display_value', raw)})")
        if changes:
            self._log(
                f"{prefix} DIFF bus=0x{int(frame.slave_addr):02X} start={int(frame.typ)}/0x{int(frame.typ):04X} "
                f"mode={frame.mode}: " + "; ".join(changes[:max_changes]) +
                (f" ... (+{len(changes)-max_changes})" if len(changes) > max_changes else "")
            )
        elif frame.mode in {"read-response", "word-frame", "write-request"} and regs:
            # Nur sehr knapp, damit das Log nicht explodiert.
            vals = "; ".join(f"{r.reg}={r.raw_value}" for r in regs[:8])
            self._log(f"{prefix} FRAME bus=0x{int(frame.slave_addr):02X} start={int(frame.typ)} mode={frame.mode}: {vals}{' ...' if len(regs)>8 else ''}")


    def _should_log_passive_frame(self, key: tuple[Any, ...], min_interval_s: float = 8.0) -> bool:
        now = time.monotonic()
        last = self.display_passive_seen.get(key)
        if last is not None and (now - last) < min_interval_s:
            return False
        self.display_passive_seen[key] = now
        if len(self.display_passive_seen) > 1000:
            # Einfaches Begrenzen; der Analyzer ist nur TEMP/Diagnose.
            for old_key in list(self.display_passive_seen.keys())[:250]:
                self.display_passive_seen.pop(old_key, None)
        return True

    def _display_map_for_passive(self, slave: int, start: int):
        # Unit 0x00 Broadcast sowie Unit 0x01 auf dem Display-Bus nutzen bei
        # bekannten WP-Bereichen meist das normale WP/Warmlink-Mapping.
        # DWIN/Anzeige-Speicher bleibt getrennt.
        if slave == 0x00 and start in {2001, 2091}:
            return self.main_window.regmap
        if slave == 0x01 and (1000 <= start <= 2300 or start in {1999, 2001, 2099}):
            return self.main_window.regmap
        return self.main_window.display_regmap

    @staticmethod
    def _display_packet_signature_words() -> tuple[int, ...]:
        # ASCII "WF2210250475" als 6 Big-Endian Register-Worte.
        return (0x5746, 0x3232, 0x3130, 0x3235, 0x3034, 0x3735)

    def _validated_packet_info_from_words(self, start: int, words: list[int]) -> Optional[dict[str, int]]:
        """Prueft die WP-Paketkopf-Regel aus den Display-Bus-RAW-Analysen.

        Gültige WP-Kopie auf dem Display-Bus:
        - Register start..start+5 enthalten die Signatur "WF2210250475"
        - Register start+8 enthält den Paketmarker 0x0210 / 528
        - Register start+9 enthält nochmal die interne Startadresse
        - interne Startadresse muss zur Modbus-Startadresse passen

        Nur solche Pakete werden automatisch in die Hauptliste übernommen.
        """
        if len(words) < 10:
            return None
        sig = self._display_packet_signature_words()
        head = tuple((int(v) & 0xFFFF) for v in words[:6])
        if head != sig:
            return None
        marker = int(words[8]) & 0xFFFF
        internal_start = int(words[9]) & 0xFFFF
        if marker != 0x0210:
            return None
        if internal_start != int(start):
            return None
        return {
            "marker": marker,
            "internal_start": internal_start,
            "end": int(start) + len(words) - 1,
        }

    def _validated_packet_info_from_regs(self, start: int, regs) -> Optional[dict[str, int]]:
        words = [int(getattr(r, "raw_value", 0) or 0) & 0xFFFF for r in list(regs or [])]
        return self._validated_packet_info_from_words(start, words)

    def _passive_decode_read_response(self, frame) -> bool:
        byte_count = int(getattr(frame, "length_field", 0) or 0)
        if byte_count <= 0 or byte_count % 2 != 0:
            return False
        qty = byte_count // 2
        slave = int(getattr(frame, "slave_addr", 0) or 0)
        match_idx = None
        for idx, item in enumerate(self.display_passive_pending_reads):
            if int(item.get("slave", -1)) == slave and int(item.get("qty", -1)) == qty:
                match_idx = idx
                break
        if match_idx is None:
            if self._should_log_passive_frame(("rsp-unknown", slave, qty, hexdump(getattr(frame, "raw", b""), 32)), 12.0):
                self._log(
                    f"DISPLAY PASSIV READ-RSP ohne bekannte Startadresse: "
                    f"unit=0x{slave:02X}, words={qty}, raw={hexdump(getattr(frame, 'raw', b''), -1)}"
                )
            return False
        item = self.display_passive_pending_reads.pop(match_idx)
        start = int(item.get("addr", 0))
        regmap = self._display_map_for_passive(slave, start)
        regs = decode_read_response_registers(frame, start, regmap)
        try:
            frame.typ = start
            frame.length_field = qty
            frame.registers = regs
        except Exception:
            pass
        vals = "; ".join(f"{r.reg}={r.raw_value}({r.display_value})" for r in regs[:10])
        age = time.monotonic() - float(item.get("seen_at", time.monotonic()) or time.monotonic())
        self._log(
            f"DISPLAY PASSIV READ-RSP unit=0x{slave:02X} -> Master, "
            f"zu READ start={start}/0x{start:04X}, words={qty}, nach {age:.1f}s: "
            f"{vals}{' ...' if len(regs) > 10 else ''}, raw={hexdump(getattr(frame, 'raw', b''), -1)}"
        )
        return True


    def _decode_display_frame_with_regmap(self, frame, regmap: RegisterMap):
        """Bestehende Frame-Worte mit einem anderen Mapping neu beschriften.

        Der Display-Worker dekodiert zuerst mit dem Display/DWIN-Mapping.
        Broadcast-Bloecke 0x00/2001ff und 0x00/2091ff enthalten aber echte
        WP-/Warmlink-Register und sollen deshalb im Hauptfenster mit dem
        normalen WP-Mapping erscheinen.
        """
        start = int(getattr(frame, "typ", 0) or 0)
        regs = []
        for idx, old_reg in enumerate(list(getattr(frame, "registers", []) or [])):
            raw = int(getattr(old_reg, "raw_value", 0) or 0) & 0xFFFF
            reg_no = start + idx
            info = regmap.get(reg_no)
            regs.append(DecodedRegister(
                slave_addr=int(getattr(frame, "slave_addr", 0) or 0),
                reg=reg_no,
                index=idx,
                frame_type=start,
                raw_value=raw,
                signed_value=s16(raw),
                display_value=format_value_by_type(raw, info.dtype, info.value_map, info.bit_map),
                name=info.name,
                dtype=info.dtype,
                timestamp=time.time(),
            ))
        return regs

    def _apply_regs_to_main_window(self, regs, source_label: str, max_log: int = 18) -> None:
        """Uebernimmt sichere Display-Passivwerte in die Haupt-Registerliste.

        Das ist bewusst nur fuer verifizierte Quellen gedacht:
        - Unit 0x00 FC16 Broadcast 2001/2091 (echte WP-Live-/Statusbloecke)
        - ggf. spaeter sauber zugeordnete 10xx-Parameterbloecke
        """
        mw = self.main_window
        changed = []
        old_updates = mw.register_table.updatesEnabled()
        bulk = len(regs) > 20
        if bulk:
            mw._suppress_name_resize = True
            mw.register_table.setUpdatesEnabled(False)
        try:
            for reg in regs:
                reg_no = int(reg.reg)
                raw = int(reg.raw_value) & 0xFFFF
                old_known = reg_no in mw.last_values
                old = mw.last_values.get(reg_no)
                value_diff = old != raw
                was_cached = reg_no in mw.cached_regs
                # Cachewerte sind Start-/Vergleichshilfe, aber keine Live-Basis
                # fuer eine sichtbare Aenderungsmarkierung.
                real_changed = bool(old_known and (not was_cached) and value_diff)
                if was_cached:
                    mw.cached_regs.discard(reg_no)
                if value_diff:
                    if old is None:
                        mw.previous_value_texts.setdefault(reg_no, "--")
                    else:
                        mw.previous_value_texts[reg_no] = f"{old} / 0x{old:04X}"
                if real_changed:
                    changed.append(f"{reg_no}: {old} -> {raw} ({reg.display_value})")
                mw.last_values[reg_no] = raw
                if value_diff or was_cached or reg_no not in mw.table_rows:
                    mw._upsert_register_row(reg, real_changed)
                if reg_no == 2034:
                    mw._update_contact_table(raw)
                if reg_no == 2019:
                    mw._update_load_output_decoder(raw)
                    mw._update_fault_decoder()
                if reg_no in (2081, 2082, 2083, 2085, 2086, 2087, 2088, 2089, 2090):
                    mw._update_fault_decoder()
                # offene Dialoge ebenfalls mitziehen, wie beim normalen Live-Update
                for dlg in (mw.timer_dialog, mw.onoff_timer_dialog, mw.silent_timer_dialog, mw.sg_dialog, mw.parameter_dialog):
                    if dlg is not None and dlg.isVisible():
                        try:
                            dlg.update_from_live_register(reg)
                        except Exception:
                            pass
                for dlg in list(mw.register_write_dialogs.values()):
                    if dlg.isVisible():
                        try:
                            dlg.update_from_live_register(reg)
                        except Exception:
                            pass
        finally:
            if bulk:
                mw._suppress_name_resize = False
                mw.register_table.setUpdatesEnabled(old_updates)
                mw._resize_name_column()
            if changed:
                regs_to_repaint = []
                for entry in changed:
                    try:
                        regs_to_repaint.append(int(str(entry).split(":", 1)[0]))
                    except Exception:
                        pass
                mw._apply_persistent_change_backgrounds(regs_to_repaint)
            mw.reg_count_label.setText(str(len(mw.last_values)))

        if changed:
            self._log(
                f"HAUPTFENSTER Update aus {source_label}: {len(changed)} Wert(e) geändert: "
                + "; ".join(changed[:max_log])
                + (f" ... (+{len(changed) - max_log})" if len(changed) > max_log else "")
            )

    def _handle_display_broadcast_or_safe_main_values(self, frame) -> None:
        if not getattr(frame, "crc_ok", False) or not getattr(frame, "registers", None):
            return
        slave = int(getattr(frame, "slave_addr", 0) or 0)
        start = int(getattr(frame, "typ", 0) or 0)
        mode = str(getattr(frame, "mode", ""))
        func = int(getattr(frame, "func", 0) or 0)

        # Fix18: generische Vertrauensregel fuer Display-Bus-Paketbloecke.
        # Wenn der FC16-Write einen gueltigen internen WP-Paketkopf traegt
        # (Signatur WF2210250475, Marker 0x0210, interner Start == Modbus-Start),
        # wird der komplette Block als echte WP-Datenkopie ins Hauptfenster uebernommen.
        if func == 0x10 and mode in {"word-frame", "write-request"}:
            packet_info = self._validated_packet_info_from_regs(start, getattr(frame, "registers", []) or [])
            if packet_info:
                regs = self._decode_display_frame_with_regmap(frame, self.main_window.regmap)
                frame.registers = regs
                end = int(packet_info.get("end", start + len(regs) - 1))
                marker = int(packet_info.get("marker", 0))
                source_kind = "Broadcast" if slave == 0x00 else f"Write an Unit 0x{slave:02X}"
                label = f"validierter Display-Paketblock {source_kind} {start}-{end}"
                vals = "; ".join(f"{r.reg}={r.raw_value}({r.display_value})" for r in regs[:12])
                key = ("valid-packet-main", slave, start, tuple(int(r.raw_value) & 0xFFFF for r in regs[:12]))
                if self._should_log_passive_frame(key, 4.0):
                    self._log(
                        f"DISPLAY VALIDIERTER WP-PAKETBLOCK {source_kind}: "
                        f"start={start}/0x{start:04X}, ende={end}/0x{end:04X}, "
                        f"words={len(regs)}, marker=0x{marker:04X}, CRC OK, interner Start passt; "
                        f"{vals}{' ...' if len(regs) > 12 else ''}"
                    )
                self._apply_regs_to_main_window(regs, label)
                return

    def _display_passive_analyzer(self, frame, active_response: bool = False):
        if not self.display_passive_analyzer_cb.isChecked() or not getattr(frame, "crc_ok", False):
            return
        slave = int(getattr(frame, "slave_addr", 0) or 0)
        mode = str(getattr(frame, "mode", ""))
        func = int(getattr(frame, "func", 0) or 0)
        start = int(getattr(frame, "typ", 0) or 0)
        length = int(getattr(frame, "length_field", 0) or 0)
        raw_hex = hexdump(getattr(frame, "raw", b""), -1)

        if mode == "read-request":
            # Modbus-Adresse ist hier das Ziel. Der Master ist der andere Teilnehmer.
            self.display_passive_pending_reads.append({
                "slave": slave,
                "addr": start,
                "qty": length,
                "seen_at": time.monotonic(),
            })
            if len(self.display_passive_pending_reads) > 80:
                del self.display_passive_pending_reads[:len(self.display_passive_pending_reads)-80]
            key = ("read-req", slave, start, length)
            if self._should_log_passive_frame(key, 4.0):
                self._log(
                    f"DISPLAY PASSIV READ-REQ Master -> Unit 0x{slave:02X}: "
                    f"start={start}/0x{start:04X}, qty={length}, raw={raw_hex}"
                )
            return

        if mode == "read-response":
            if active_response:
                return
            self._passive_decode_read_response(frame)
            return

        if mode in {"write-request", "word-frame", "short-write", "write-single"}:
            regs = list(getattr(frame, "registers", []) or [])
            vals = "; ".join(f"{r.reg}={r.raw_value}" for r in regs[:14])
            packet_info = None
            if func == 0x10:
                packet_info = self._validated_packet_info_from_regs(start, regs)
            if packet_info:
                end = int(packet_info.get("end", start + len(regs) - 1))
                source_kind = "Broadcast Unit 0x00" if slave == 0x00 else f"Master -> Unit 0x{slave:02X}"
                key = ("valid-packet-write", slave, start, tuple(int(getattr(r, "raw_value", 0) or 0) for r in regs[:12]))
                if self._should_log_passive_frame(key, 4.0):
                    self._log(
                        f"DISPLAY PASSIV VALIDIERTER WP-PAKETBLOCK {source_kind}: "
                        f"start={start}/0x{start:04X}, ende={end}/0x{end:04X}, qty={length}, "
                        f"Signatur OK, interner Start passt, werte={vals}{' ...' if len(regs) > 14 else ''}, raw={raw_hex}"
                    )
                return
            key = ("write", slave, start, length, tuple(int(getattr(r, "raw_value", 0) or 0) for r in regs[:8]))
            if self._should_log_passive_frame(key, 4.0):
                self._log(
                    f"DISPLAY PASSIV WRITE Master -> Unit 0x{slave:02X}: "
                    f"fc=0x{func:02X}, start={start}/0x{start:04X}, qty={length}, "
                    f"werte={vals}{' ...' if len(regs) > 14 else ''}, raw={raw_hex}"
                )
            return

        if mode == "write-response":
            key = ("write-ack", slave, start, length)
            if self._should_log_passive_frame(key, 8.0):
                self._log(
                    f"DISPLAY PASSIV WRITE-ACK Unit 0x{slave:02X} -> Master: "
                    f"start={start}/0x{start:04X}, qty={length}, raw={raw_hex}"
                )
            return

        key = ("other", slave, func, mode, start, length)
        if self._should_log_passive_frame(key, 8.0):
            self._log(
                f"DISPLAY PASSIV FRAME unit=0x{slave:02X}, fc=0x{func:02X}, mode={mode}, "
                f"start={start}/0x{start:04X}, len={length}, raw={raw_hex}"
            )

    @Slot(object)
    def on_display_frame(self, frame):
        self.display_frames += 1
        self.display_last_frame_monotonic = time.monotonic()
        active_response = False
        if getattr(frame, "mode", "") == "read-response":
            active_response = self._associate_display_read_response(frame)
        self._handle_display_broadcast_or_safe_main_values(frame)
        self._display_passive_analyzer(frame, active_response=active_response)
        self._frame_summary("DISPLAY", frame, self.display_last)
        self._display_warmlink_correlations(frame, list(getattr(frame, "registers", []) or []))
        self._update_status()

    @Slot(object)
    def on_warmlink_frame(self, frame):
        self.warmlink_frames += 1
        if getattr(frame, "mode", "") == "read-response":
            self._associate_warmlink_read_response(frame)
        self._remember_warmlink_values(frame)
        self._frame_summary("WARMLINK", frame, self.warmlink_last)
        self._update_status()

    def _update_status(self):
        self.status_label.setText(f"Frames Display: {self.display_frames} | Warmlink: {self.warmlink_frames}")


BACKEND_CHOICES = [
    ("warmlink_raw", "Modbus Warmlink LTE"),
    ("standard_modbus", "Modbus Standart"),
    ("display_modbus", "Modbus Display"),
]
BACKEND_LABELS = dict(BACKEND_CHOICES)
TRANSPORT_CHOICES = [
    ("tcp", "TCP / IP / ser2net"),
    ("serial", "Serial / COM-Port"),
]
BACKEND_DEFAULTS = {
    "warmlink_raw": {
        "transport": "tcp", "host": DEFAULT_HOST, "port": DEFAULT_PORT,
        "serial_port": "COM3", "baudrate": 9600, "parity": "N", "bytesize": 8, "stopbits": 1.0,
        "unit_id": DEFAULT_BUS_ADDR, "display_translate_0x2000": False,
    },
    "standard_modbus": {
        "transport": "tcp", "host": DEFAULT_HOST, "port": 10001,
        "serial_port": "COM3", "baudrate": 9600, "parity": "N", "bytesize": 8, "stopbits": 1.0,
        "unit_id": 1, "display_translate_0x2000": False,
    },
    "display_modbus": {
        "transport": "tcp", "host": DEFAULT_HOST, "port": 10001,
        "serial_port": "COM3", "baudrate": 4800, "parity": "N", "bytesize": 8, "stopbits": 1.0,
        "unit_id": 3, "display_translate_0x2000": False,
    },
}


class CommunicationSettingsDialog(QDialog):
    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Programm-Einstellungen")
        self.setWindowIcon(app_icon())
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.backend_combo = QComboBox()
        for key, label in BACKEND_CHOICES:
            self.backend_combo.addItem(label, key)
        idx = self.backend_combo.findData(main_window.current_backend_key())
        self.backend_combo.setCurrentIndex(idx if idx >= 0 else (self.backend_combo.findData("standard_modbus") if APP_EDITION.upper() == "PUBLIC" else 0))

        self.transport_combo = QComboBox()
        for key, label in TRANSPORT_CHOICES:
            self.transport_combo.addItem(label, key)

        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox(); self.port_spin.setRange(1, 65535)
        self.serial_port_edit = QLineEdit()
        self.serial_port_edit.setPlaceholderText("z. B. COM3")
        self.baud_spin = QSpinBox(); self.baud_spin.setRange(300, 921600); self.baud_spin.setSingleStep(100)
        self.parity_combo = QComboBox()
        self.parity_combo.addItem("None / N", "N")
        self.parity_combo.addItem("Even / E", "E")
        self.parity_combo.addItem("Odd / O", "O")
        self.bytesize_combo = QComboBox()
        for n in (8, 7):
            self.bytesize_combo.addItem(str(n), n)
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItem("1", 1.0)
        self.stopbits_combo.addItem("2", 2.0)
        self.unit_spin = QSpinBox(); self.unit_spin.setRange(1, 247)
        self.translate_cb = QCheckBox("Parameterregister +0x2000 übersetzen")
        self.translate_cb.setToolTip("Entfernt: Display-Modbus schreibt/liest Register jetzt ohne automatische +0x2000-Übersetzung.")
        self.translate_cb.setVisible(False)

        self.display_write_mode_combo = QComboBox()
        self.display_write_mode_combo.addItem("FC16 Single Register (intern/fix)", "fc16")
        self.display_write_mode_combo.addItem("FC06 Single Register (nur Alt-Test)", "fc06")
        # V0.2.41 fix7: Für normale Bedienung nicht mehr auswählbar.
        # Display-Modbus nutzt intern FC16-Single-Register; Spezialpfade entscheiden selbst.
        self.display_write_mode_combo.setCurrentIndex(0)
        self.display_write_mode_combo.setToolTip(
            "Interne Alt-/Debug-Einstellung. Für normale Bedienung wird im Display-Modus FC16 verwendet; "
            "Warmlink/Standard-Modbus bleiben davon unabhängig."
        )
        self.display_write_mode_label = QLabel("Display schreiben (intern):")

        self.device_combo = QComboBox()
        for dev_key, dev_label in DEVICE_MODELS:
            self.device_combo.addItem(dev_label, dev_key)
        didx = self.device_combo.findData(main_window.current_device_model())
        self.device_combo.setCurrentIndex(didx if didx >= 0 else 0)
        self.device_hint_label = QLabel(DEVICE_MODEL_HINT)
        self.device_hint_label.setWordWrap(True)

        self.host_label = QLabel("Host:")
        self.port_label = QLabel("Port:")
        self.serial_port_label = QLabel("COM-Port:")
        self.baud_label = QLabel("Baudrate:")
        self.parity_label = QLabel("Parität:")
        self.bytesize_label = QLabel("Datenbits:")
        self.stopbits_label = QLabel("Stopbits:")
        self.unit_label = QLabel("Unit:")
        self.unit_spin.setToolTip(
            "Modbus-Slave-Adresse für aktive manuelle Lese-/Schreibbefehle. "
            "Standard-Modbus meist Unit 1; Display/HMI meist Unit 3. "
            "Passive Displaybus-Rollen wie 0x00 Broadcast oder 0x01 Rohstatus werden automatisch erkannt."
        )

        form.addRow("Kommunikationsart:", self.backend_combo)
        form.addRow("Transport:", self.transport_combo)
        form.addRow(self.host_label, self.host_edit)
        form.addRow(self.port_label, self.port_spin)
        form.addRow(self.serial_port_label, self.serial_port_edit)
        form.addRow(self.baud_label, self.baud_spin)
        form.addRow(self.parity_label, self.parity_combo)
        form.addRow(self.bytesize_label, self.bytesize_combo)
        form.addRow(self.stopbits_label, self.stopbits_combo)
        form.addRow(self.unit_label, self.unit_spin)
        form.addRow(self.display_write_mode_label, self.display_write_mode_combo)
        form.addRow("Gerät:", self.device_combo)
        form.addRow("Hinweis:", self.device_hint_label)

        self.display_dual_logger_cb = QCheckBox("Dual-Bus Logger Button im Hauptfenster anzeigen")
        self.display_dual_logger_cb.setChecked(bool(main_window.settings.get("show_dual_logger_button_display", False)))
        self.display_dual_logger_cb.setToolTip(
            "Nur für Modbus Display/HMI: zeigt den Diagnosebutton 'Dual-Bus Logger' im Hauptfenster. "
            "Standardmäßig ausgeblendet, weil der Logger ein reines Diagnosewerkzeug ist."
        )
        self.display_dual_logger_label = QLabel("Display-Diagnose:")
        form.addRow(self.display_dual_logger_label, self.display_dual_logger_cb)

        self._comm_locked_tooltip = "Bei aktiver Verbindung gesperrt. Bitte erst trennen, um diesen Wert zu ändern."
        self._comm_widget_tooltips = {
            widget: widget.toolTip() for widget in self._communication_lock_widgets(include_labels=True)
        }
        self._set_comm_widgets_locked(bool(getattr(self.main_window, "connected", False)))

        self.show_warning_cb = QCheckBox("Hinweis-Banner im Hauptfenster anzeigen")
        self.show_warning_cb.setChecked(bool(main_window.settings.get("show_public_warning", True)))
        self.show_warning_cb.setToolTip("Blendet den gelben Hinweis 'inoffizielles Tool' im Hauptfenster ein/aus.")
        form.addRow("Anzeige:", self.show_warning_cb)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("System (Windows übernehmen)", "system")
        self.theme_combo.addItem("Hell", "light")
        self.theme_combo.addItem("Dunkel", "dark")
        tidx = self.theme_combo.findData(str(main_window.settings.get("theme", "system")))
        self.theme_combo.setCurrentIndex(tidx if tidx >= 0 else 0)
        form.addRow("Darstellung:", self.theme_combo)

        self.update_asset_combo = QComboBox()
        self.update_asset_combo.addItem("Automatisch erkennen", "auto")
        self.update_asset_combo.addItem("Portable-Version bevorzugen", "portable")
        self.update_asset_combo.addItem("Setup/Installer bevorzugen", "setup")
        uidx = self.update_asset_combo.findData(str(main_window.settings.get("update_asset_mode", "auto")))
        self.update_asset_combo.setCurrentIndex(uidx if uidx >= 0 else 0)
        form.addRow("Update-Download:", self.update_asset_combo)

        self.auto_read_init_cb = QCheckBox("Basisregister nach Autoconnect/Connect lesen")
        self.auto_read_init_cb.setChecked(bool(main_window.settings.get("auto_read_init_on_startup", False)))
        self.auto_read_init_cb.setToolTip("Nach erfolgreicher Verbindung automatisch die Init-/Basisblöcke lesen.")
        form.addRow("Startup:", self.auto_read_init_cb)

        self.live_poll_cb = QCheckBox("Livewerte 20xx zyklisch lesen")
        self.live_poll_cb.setChecked(bool(main_window.settings.get("auto_poll_live_values", False)))
        self.live_poll_cb.setToolTip("Liest zyklisch die Live-/Diagnoseblöcke ab 2001/2091.")
        self.live_poll_interval_spin = QSpinBox()
        self.live_poll_interval_spin.setRange(5, 3600)
        self.live_poll_interval_spin.setValue(int(main_window.settings.get("live_poll_interval_s", 30)))
        self.live_poll_interval_spin.setSuffix(" s")
        live_poll_row = QWidget()
        live_poll_layout = QHBoxLayout(live_poll_row)
        live_poll_layout.setContentsMargins(0, 0, 0, 0)
        live_poll_layout.addWidget(self.live_poll_cb)
        live_poll_layout.addWidget(self.live_poll_interval_spin)
        live_poll_layout.addStretch(1)
        form.addRow("Auto-Poll:", live_poll_row)

        self.tab_auto_poll_cb = QCheckBox("Parameterblock im Einstellfenster zyklisch lesen")
        self.tab_auto_poll_cb.setChecked(bool(main_window.settings.get("tab_auto_poll", False)))
        self.tab_poll_interval_spin = QSpinBox()
        self.tab_poll_interval_spin.setRange(2, 3600)
        self.tab_poll_interval_spin.setValue(int(main_window.settings.get("tab_poll_interval_s", 30)))
        self.tab_poll_interval_spin.setSuffix(" s")
        tab_poll_row = QWidget()
        tab_poll_layout = QHBoxLayout(tab_poll_row)
        tab_poll_layout.setContentsMargins(0, 0, 0, 0)
        tab_poll_layout.addWidget(self.tab_auto_poll_cb)
        tab_poll_layout.addWidget(self.tab_poll_interval_spin)
        tab_poll_layout.addStretch(1)
        form.addRow("Parameter:", tab_poll_row)

        cap = dict(DEFAULT_CAPTURE_SETTINGS)
        saved_cap = main_window.settings.get("warmlink_raw_capture", {})
        if isinstance(saved_cap, dict):
            cap.update(saved_cap)
        self.capture_expert_box = QGroupBox("Expertenbereich: Warmlink RAW Langzeit-Capture")
        expert_layout = QFormLayout(self.capture_expert_box)
        self.cap_enabled_cb = QCheckBox("Warmlink RAW Langzeit-Capture aktivieren")
        self.cap_enabled_cb.setChecked(bool(cap.get("enabled", False)))
        self.cap_dir_edit = QLineEdit(str(cap.get("directory", DEFAULT_CAPTURE_SETTINGS["directory"])))
        self.cap_dir_edit.setToolTip(
            "Relative Pfade werden im FoxAir-Control-Benutzerdatenordner gespeichert.\n"
            "Absolute Pfade werden direkt verwendet."
        )
        self.cap_rx_cb = QCheckBox("RX mitschreiben"); self.cap_rx_cb.setChecked(bool(cap.get("capture_rx", True)))
        self.cap_tx_cb = QCheckBox("TX mitschreiben"); self.cap_tx_cb.setChecked(bool(cap.get("capture_tx", True)))
        self.cap_events_cb = QCheckBox("Events/Index schreiben"); self.cap_events_cb.setChecked(bool(cap.get("write_events", True)))
        self.cap_idle_spin = QSpinBox(); self.cap_idle_spin.setRange(1, 1440); self.cap_idle_spin.setValue(int(cap.get("idle_rotation_minutes", 5))); self.cap_idle_spin.setSuffix(" min")
        self.cap_file_spin = QSpinBox(); self.cap_file_spin.setRange(1, 1048576); self.cap_file_spin.setValue(int(cap.get("max_file_size_mb", 1024))); self.cap_file_spin.setSuffix(" MB")
        self.cap_total_spin = QSpinBox(); self.cap_total_spin.setRange(1, 10485760); self.cap_total_spin.setValue(int(cap.get("max_total_size_mb", 10240))); self.cap_total_spin.setSuffix(" MB")
        self.cap_retention_spin = QSpinBox(); self.cap_retention_spin.setRange(1, 3650); self.cap_retention_spin.setValue(int(cap.get("retention_days", 14))); self.cap_retention_spin.setSuffix(" Tage")
        self.cap_anomaly_cb = QCheckBox("Anomalie-Erkennung aktivieren"); self.cap_anomaly_cb.setChecked(bool(cap.get("anomaly_detection", True)))
        self.cap_status_label = QLabel("Status wird nach dem Speichern/Verbinden aktualisiert.")
        self.cap_status_label.setWordWrap(True)
        self.cap_dir_select_btn = QPushButton("Auswählen...")
        self.cap_open_btn = QPushButton("Öffnen")
        self.cap_effective_dir_label = QLabel()
        self.cap_effective_dir_label.setWordWrap(True)
        self.cap_effective_dir_label.setToolTip(
            "Das ist der tatsächliche Ordner, in dem RX/TX/Events/Summary-Dateien gespeichert werden."
        )
        self.cap_rotate_btn = QPushButton("Neues Segment starten")
        self.cap_stop_btn = QPushButton("Capture stoppen")
        cap_dir_row = QWidget(); cap_dir_layout = QHBoxLayout(cap_dir_row); cap_dir_layout.setContentsMargins(0,0,0,0)
        cap_dir_layout.addWidget(self.cap_dir_edit, 1); cap_dir_layout.addWidget(self.cap_dir_select_btn); cap_dir_layout.addWidget(self.cap_open_btn)
        cap_btn_row = QWidget(); cap_btn_layout = QHBoxLayout(cap_btn_row); cap_btn_layout.setContentsMargins(0,0,0,0)
        cap_btn_layout.addWidget(self.cap_rotate_btn); cap_btn_layout.addWidget(self.cap_stop_btn); cap_btn_layout.addStretch(1)
        expert_layout.addRow(self.cap_enabled_cb)
        expert_layout.addRow("Capture-Verzeichnis:", cap_dir_row)
        expert_layout.addRow("Effektiver Ordner:", self.cap_effective_dir_label)
        expert_layout.addRow(self.cap_rx_cb); expert_layout.addRow(self.cap_tx_cb); expert_layout.addRow(self.cap_events_cb)
        expert_layout.addRow("Tagesrotation nach Inaktivität:", self.cap_idle_spin)
        expert_layout.addRow("Max. Einzeldateigröße:", self.cap_file_spin)
        expert_layout.addRow("Max. Gesamtspeicher:", self.cap_total_spin)
        expert_layout.addRow("Aufbewahrung:", self.cap_retention_spin)
        expert_layout.addRow(self.cap_anomaly_cb)
        expert_layout.addRow("Status:", self.cap_status_label)
        expert_layout.addRow(cap_btn_row)
        layout.addWidget(self.capture_expert_box)
        self.cap_dir_edit.textChanged.connect(lambda _=None: self._update_capture_effective_dir_label())
        self.cap_dir_select_btn.clicked.connect(self._choose_capture_dir)
        self.cap_open_btn.clicked.connect(self._open_capture_dir)
        self.cap_rotate_btn.clicked.connect(lambda: getattr(main_window, "warmlink_capture", None) and main_window.warmlink_capture.force_new_segment())
        self.cap_stop_btn.clicked.connect(lambda: main_window._stop_warmlink_capture("per Einstellungen gestoppt"))
        self._update_capture_effective_dir_label()
        try:
            st = getattr(main_window, "warmlink_capture", None).get_status() if getattr(main_window, "warmlink_capture", None) else None
            if st:
                self.cap_status_label.setText(f"{'aktiv' if st.active else 'inaktiv'} | Segment {st.segment} | RX {st.rx_size} B | TX {st.tx_size} B | letzter RX {st.last_rx} | letzter TX {st.last_tx} | Anomalien {st.anomalies} | Drops {st.drops} | Fehler {st.error or '--'}")
        except Exception:
            pass

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.backend_combo.currentIndexChanged.connect(lambda _=None: self._backend_changed(load_values=True))
        self.transport_combo.currentIndexChanged.connect(lambda _=None: self._transport_changed())
        self._backend_changed(load_values=True)

    def _is_warmlink_backend_key(self, key: str) -> bool:
        return str(key or "") == "warmlink_raw"

    def _capture_base_dir(self) -> str:
        return os.path.abspath(str(getattr(self.main_window, "user_data_dir", self.main_window.base_dir)))

    @staticmethod
    def _is_absolute_capture_path(path: str) -> bool:
        text = str(path or "").strip()
        return bool(os.path.isabs(text) or re.match(r"^[A-Za-z]:[\\/]", text) or text.startswith("\\\\"))

    def _capture_dir_value(self) -> str:
        return self.cap_dir_edit.text().strip() or str(DEFAULT_CAPTURE_SETTINGS["directory"])

    def _effective_capture_dir(self) -> str:
        directory = self._capture_dir_value()
        if self._is_absolute_capture_path(directory):
            return os.path.normpath(directory)
        return os.path.abspath(os.path.join(self._capture_base_dir(), directory))

    def _capture_path_for_settings(self, selected_dir: str) -> str:
        selected = os.path.abspath(os.path.normpath(str(selected_dir)))
        base = self._capture_base_dir()
        try:
            common = os.path.commonpath([base, selected])
        except ValueError:
            common = ""
        if common == base:
            rel = os.path.relpath(selected, base)
            return "." if rel == "." else rel
        return selected

    def _update_capture_effective_dir_label(self):
        if hasattr(self, "cap_effective_dir_label"):
            self.cap_effective_dir_label.setText(self._effective_capture_dir())

    def _choose_capture_dir(self):
        start_dir = self._effective_capture_dir()
        if not os.path.isdir(start_dir):
            start_dir = self._capture_base_dir()
        chosen = QFileDialog.getExistingDirectory(self, "Capture-Verzeichnis auswählen", start_dir)
        if chosen:
            self.cap_dir_edit.setText(self._capture_path_for_settings(chosen))
            self._update_capture_effective_dir_label()

    def _open_capture_dir(self):
        path = self._effective_capture_dir()
        os.makedirs(path, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _update_capture_settings_visibility(self):
        if not hasattr(self, "capture_expert_box"):
            return
        backend = str(self.backend_combo.currentData() or "warmlink_raw")
        self.capture_expert_box.setVisible(self._is_warmlink_backend_key(backend))

    def _communication_lock_widgets(self, include_labels: bool = False) -> tuple[QWidget, ...]:
        widgets = (
            self.backend_combo, self.transport_combo, self.host_edit, self.port_spin,
            self.serial_port_edit, self.baud_spin, self.parity_combo, self.bytesize_combo,
            self.stopbits_combo, self.unit_spin,
        )
        if not include_labels:
            return widgets
        return widgets + (
            self.host_label, self.port_label, self.serial_port_label, self.baud_label,
            self.parity_label, self.bytesize_label, self.stopbits_label, self.unit_label,
        )

    def _set_comm_widgets_locked(self, locked: bool):
        locked_tooltip = self._comm_locked_tooltip
        for widget in self._communication_lock_widgets(include_labels=True):
            widget.setEnabled(not locked)
            if locked:
                widget.setToolTip(locked_tooltip)
            else:
                widget.setToolTip(self._comm_widget_tooltips.get(widget, ""))

    def _apply_communication_lock_state(self):
        self._set_comm_widgets_locked(bool(getattr(self.main_window, "connected", False)))

    def _backend_settings(self, backend: str) -> dict:
        return self.main_window._backend_settings(backend)

    def _load_cfg_to_fields(self, cfg: dict, backend: str):
        transport = str(cfg.get("transport", "tcp"))
        tidx = self.transport_combo.findData(transport)
        self.transport_combo.setCurrentIndex(tidx if tidx >= 0 else 0)
        self.host_edit.setText(str(cfg.get("host", DEFAULT_HOST)))
        self.port_spin.setValue(int(cfg.get("port", DEFAULT_PORT)))
        self.serial_port_edit.setText(str(cfg.get("serial_port", "COM3")))
        self.baud_spin.setValue(int(cfg.get("baudrate", 9600)))
        pidx = self.parity_combo.findData(str(cfg.get("parity", "N")).upper()[0])
        self.parity_combo.setCurrentIndex(pidx if pidx >= 0 else 0)
        bidx = self.bytesize_combo.findData(int(cfg.get("bytesize", 8)))
        self.bytesize_combo.setCurrentIndex(bidx if bidx >= 0 else 0)
        sidx = self.stopbits_combo.findData(float(cfg.get("stopbits", 1.0)))
        self.stopbits_combo.setCurrentIndex(sidx if sidx >= 0 else 0)
        self.unit_spin.setValue(int(cfg.get("unit_id", BACKEND_DEFAULTS.get(backend, {}).get("unit_id", 1))))
        self.translate_cb.setChecked(False)

    def _save_current_fields_to_selected_backend(self):
        backend = str(self.backend_combo.currentData() or "warmlink_raw")
        self.main_window._set_backend_settings(
            backend=backend,
            transport=str(self.transport_combo.currentData() or "tcp"),
            host=self.host_edit.text().strip(),
            port=int(self.port_spin.value()),
            unit_id=int(self.unit_spin.value()),
            display_translate=False,
            serial_port=self.serial_port_edit.text().strip(),
            baudrate=int(self.baud_spin.value()),
            parity=str(self.parity_combo.currentData() or "N"),
            bytesize=int(self.bytesize_combo.currentData() or 8),
            stopbits=float(self.stopbits_combo.currentData() or 1.0),
        )

    def _backend_changed(self, load_values: bool = True):
        backend = str(self.backend_combo.currentData() or "warmlink_raw")
        cfg = self._backend_settings(backend)
        if load_values:
            self._load_cfg_to_fields(cfg, backend)
        self.translate_cb.setVisible(False)
        self.unit_label.setVisible(backend in ("display_modbus", "standard_modbus"))
        self.unit_spin.setVisible(backend in ("display_modbus", "standard_modbus"))
        # V0.2.41 fix7: FC06/FC16 ist keine normale Benutzereinstellung mehr.
        # Display-Modbus verwendet intern FC16; Spezial-/Fallbackpfade entscheiden selbst.
        self.display_write_mode_label.setVisible(False)
        self.display_write_mode_combo.setVisible(False)
        if hasattr(self, "display_dual_logger_cb"):
            self.display_dual_logger_cb.setVisible(backend == "display_modbus")
        if hasattr(self, "display_dual_logger_label"):
            self.display_dual_logger_label.setVisible(backend == "display_modbus")
        self._update_capture_settings_visibility()
        self._transport_changed()
        self._apply_communication_lock_state()
        if backend == "warmlink_raw":
            self.info_label.setText("Modbus Warmlink LTE: Bus/Modem im Außengerät am Mainboard. WP-Busadresse bleibt intern 0x63.")
        elif backend == "standard_modbus":
            self.info_label.setText(
                "Modbus Standard: offizielle Modbus-Klemmen am Gerät, typ. Unit 1. "
                "Unit ist die Slave-Adresse; gelesen wird per FC03, einfache Schreibwerte per FC06."
            )
        else:
            self.info_label.setText(
                "Modbus Display/HMI: 4800 8N1 laut Display-CONFIG. "
                "Unit ist nur die aktive Zieladresse, normalerweise 3. "
                "Gesehen: 0x03 = Display/DWIN, 3001-3021 lesbar und Bedienwerte über 23xx; "
                "0x00 = Broadcast echter WP-Livewerte 2001/2091; "
                "0x01 = Rohstatus 2099/51, virtuell 91099-91149; 91105~2062 AC-Spannung, 91108~2043 DC-Bus (Power-Modul-Spiegel-Kandidaten); "
                "0x04 fragt 1011-1024; 0x05 liest 2000/90 und schreibt 1001/90 Nullblock. "
                "0x04/0x05 bleiben Diagnose, wenn sie bekannte WP-Bereiche berühren."
            )

    def _transport_changed(self):
        is_serial = str(self.transport_combo.currentData() or "tcp") == "serial"
        for w in (self.host_label, self.host_edit, self.port_label, self.port_spin):
            w.setVisible(not is_serial)
        for w in (self.serial_port_label, self.serial_port_edit, self.baud_label, self.baud_spin,
                  self.parity_label, self.parity_combo, self.bytesize_label, self.bytesize_combo,
                  self.stopbits_label, self.stopbits_combo):
            w.setVisible(is_serial)

    def accept(self):
        comm_locked = bool(self.main_window.connected)
        if not comm_locked:
            self._save_current_fields_to_selected_backend()
        self.main_window.settings["show_public_warning"] = bool(self.show_warning_cb.isChecked())
        self.main_window.settings["theme"] = str(self.theme_combo.currentData() or "system")
        self.main_window.settings["update_asset_mode"] = str(self.update_asset_combo.currentData() or "auto")
        self.main_window.settings["auto_read_init_on_startup"] = bool(self.auto_read_init_cb.isChecked())
        self.main_window.settings["auto_poll_live_values"] = bool(self.live_poll_cb.isChecked())
        self.main_window.settings["live_poll_interval_s"] = int(self.live_poll_interval_spin.value())
        self.main_window.settings["tab_auto_poll"] = bool(self.tab_auto_poll_cb.isChecked())
        self.main_window.settings["tab_poll_interval_s"] = int(self.tab_poll_interval_spin.value())
        selected_backend = (
            self.main_window.current_backend_key()
            if comm_locked else str(self.backend_combo.currentData() or "warmlink_raw")
        )
        if self._is_warmlink_backend_key(selected_backend):
            capture_settings = dict(self.main_window.settings.get("warmlink_raw_capture", {}))
            capture_settings.update({
                "enabled": bool(self.cap_enabled_cb.isChecked()),
                "directory": self._capture_dir_value(),
                "capture_rx": bool(self.cap_rx_cb.isChecked()),
                "capture_tx": bool(self.cap_tx_cb.isChecked()),
                "write_events": bool(self.cap_events_cb.isChecked()),
                "idle_rotation_minutes": int(self.cap_idle_spin.value()),
                "max_file_size_mb": int(self.cap_file_spin.value()),
                "max_total_size_mb": int(self.cap_total_spin.value()),
                "retention_days": int(self.cap_retention_spin.value()),
                "anomaly_detection": bool(self.cap_anomaly_cb.isChecked()),
            })
            self.main_window.settings["warmlink_raw_capture"] = capture_settings
        # V0.2.41 fix7: nicht mehr als normale Option anzeigen; intern FC16 beibehalten.
        self.main_window.settings["display_write_mode"] = "fc16"
        self.main_window.settings["show_dual_logger_button_display"] = bool(self.display_dual_logger_cb.isChecked())
        apply_app_theme(QApplication.instance(), self.main_window.settings["theme"])
        if hasattr(self.main_window, "public_warning_label"):
            self.main_window.public_warning_label.setVisible(bool(self.show_warning_cb.isChecked()))
        self.main_window.set_current_device_model(str(self.device_combo.currentData() or DEFAULT_DEVICE_MODEL))
        if not comm_locked:
            backend = str(self.backend_combo.currentData() or "warmlink_raw")
            self.main_window.apply_communication_settings(backend)
        self.main_window._apply_live_poll_timer_state()
        self.main_window._update_dual_logger_button_visibility()
        self.main_window._refresh_search_highlights()
        self.main_window._save_settings(sync_main_fields=False)
        super().accept()




class AboutDialog(QDialog):
    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Hilfe / About")
        self.setWindowIcon(app_icon())
        self.resize(560, 420)
        layout = QVBoxLayout(self)

        head = QHBoxLayout()
        icon_label = QLabel()
        pm = app_icon_pixmap(96)
        if not pm.isNull():
            icon_label.setPixmap(pm)
        head.addWidget(icon_label)

        text = QLabel(
            f"<b>FoxAir / Phnix Control</b><br>"
            f"Version V{APP_VERSION}{' PRIVATE' if APP_EDITION.upper() == 'PRIVATE' else ''}<br>"
            f"Build: {BUILD_DATE}<br>"
            f"by DosOrDie"
        )
        text.setTextFormat(Qt.RichText)
        text.setOpenExternalLinks(True)
        head.addWidget(text, 1)
        layout.addLayout(head)

        warn = QLabel(PUBLIC_WARNING_TEXT)
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #8a4b00; background: #fff3cd; border: 1px solid #ffd27a; padding: 6px; font-weight: bold;")
        layout.addWidget(warn)

        info = QLabel(
            "Inoffizielles Diagnose- und Parametrierwerkzeug für FoxAir/Phnix-basierte Wärmepumpen. "
            "Register-Schreibzugriffe können Anlagenparameter verändern. Vor Änderungen immer ein Backup erstellen."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        cloud_credit = QLabel(WARMLINK_CLOUD_CREDIT)
        cloud_credit.setWordWrap(True)
        cloud_credit.setStyleSheet("color: #666666;")
        layout.addWidget(cloud_credit)

        repo = QLabel(f'GitHub: <a href="https://github.com/{UPDATE_REPO}">https://github.com/{UPDATE_REPO}</a>')
        repo.setTextFormat(Qt.RichText)
        repo.setOpenExternalLinks(True)
        layout.addWidget(repo)

        btn_row = QHBoxLayout()
        self.update_btn = QPushButton("Update prüfen ...")
        repo_btn = QPushButton("GitHub öffnen")
        close_btn = QPushButton("Schließen")
        btn_row.addWidget(self.update_btn)
        btn_row.addWidget(repo_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.update_btn.clicked.connect(main_window.check_for_updates)
        repo_btn.clicked.connect(lambda: open_update_url(f"https://github.com/{UPDATE_REPO}"))
        close_btn.clicked.connect(self.accept)


class WPControlDialog(QDialog):
    """Einfache WP-Steuerung ähnlich Warmlink-App. Schreiben nur mit Bestätigung."""
    SET_MODE_MAP = {
        0: "Warmwasser",
        1: "Heizen",
        2: "Kühlen",
        3: "Warmwasser + Heizen",
        4: "Warmwasser + Kühlen",
    }
    RUN_MODE_MAP = {
        0: "Kühlen",
        1: "Heizen",
        2: "Abtauen",
        3: "Sterilisieren",
        4: "Warmwasser",
    }
    TARGET_REG_BY_SET_MODE = {
        0: (1157, "Warmwasser-Solltemperatur"),
        1: (1158, "Heizungssolltemperatur"),
        2: (1159, "Kühlsolltemperatur"),
        3: (1158, "Heizungssolltemperatur"),
        4: (1159, "Kühlsolltemperatur"),
    }
    TEMP_REGS = [
        (2048, "Außentemperatur"),
        (2045, "Einlass / Rücklauf"),
        (2046, "Auslass / Vorlauf"),
        (2047, "WW-Tank"),
        (2077, "Durchfluss"),
        (2013, "Solltemp. begrenzt"),
        (2014, "Solltemp. AT-Komp."),
    ]

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("WP-Steuerung")
        self.setMinimumWidth(760)
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.read_from_wp)
        self._build_ui()
        self.refresh_from_live()
        QTimer.singleShot(250, self.read_from_wp)

    def _raw(self, reg_no: int, default: Optional[int] = None) -> Optional[int]:
        try:
            if reg_no in self.main_window.latest_regs:
                return int(self.main_window.latest_regs[reg_no].raw_value) & 0xFFFF
            if reg_no in self.main_window.last_values:
                return int(self.main_window.last_values[reg_no]) & 0xFFFF
        except Exception:
            pass
        return default

    def _fmt(self, reg_no: int, raw: Optional[int]) -> str:
        if raw is None:
            return "--"
        info = self.main_window.regmap.get(int(reg_no))
        dtype = info.dtype if info and info.dtype else "RAW"
        return format_value_by_type(int(raw), dtype)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("Einfache Steuerung wie in der App. Schreibbefehle werden erst nach Bestätigung gesendet.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        status_box = QGroupBox("Status")
        layout.addWidget(status_box)
        status = QGridLayout(status_box)
        self.power_state_label = QLabel("--")
        self.set_mode_label = QLabel("--")
        self.run_mode_label = QLabel("--")
        self.silent_state_label = QLabel("--")
        status.addWidget(QLabel("Ein/Aus Status (2011):"), 0, 0)
        status.addWidget(self.power_state_label, 0, 1)
        status.addWidget(QLabel("Eingestellter Modus (1012):"), 1, 0)
        status.addWidget(self.set_mode_label, 1, 1)
        status.addWidget(QLabel("Aktueller Betrieb (2012):"), 2, 0)
        status.addWidget(self.run_mode_label, 2, 1)
        status.addWidget(QLabel("Silent (1016 Bit 1):"), 3, 0)
        status.addWidget(self.silent_state_label, 3, 1)

        live_box = QGroupBox("Wichtige Livewerte")
        layout.addWidget(live_box)
        live = QGridLayout(live_box)
        self.temp_labels: dict[int, QLabel] = {}
        for idx, (reg_no, label) in enumerate(self.TEMP_REGS):
            r = idx // 2
            c = (idx % 2) * 2
            live.addWidget(QLabel(f"{label} ({reg_no}):"), r, c)
            val = QLabel("--")
            self.temp_labels[reg_no] = val
            live.addWidget(val, r, c + 1)

        control_box = QGroupBox("Wärmepumpe Ein / Aus und Sollwerte")
        layout.addWidget(control_box)
        controls = QGridLayout(control_box)

        self.power_combo = QComboBox()
        self.power_combo.addItem("Aus", 0)
        self.power_combo.addItem("Ein", 1)
        self.power_write_btn = QPushButton("Wärmepumpe Ein/Aus schreiben (1011)")
        controls.addWidget(QLabel("Wärmepumpe Ein / Aus:"), 0, 0)
        controls.addWidget(self.power_combo, 0, 1)
        controls.addWidget(self.power_write_btn, 0, 2)

        self.mode_combo = QComboBox()
        for raw, text in self.SET_MODE_MAP.items():
            self.mode_combo.addItem(text, raw)
        self.mode_write_btn = QPushButton("Modus schreiben (1012)")
        controls.addWidget(QLabel("Modus setzen:"), 1, 0)
        controls.addWidget(self.mode_combo, 1, 1)
        controls.addWidget(self.mode_write_btn, 1, 2)

        self.target_label = QLabel("--")
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0.0, 90.0)
        self.target_spin.setDecimals(1)
        self.target_spin.setSingleStep(0.5)
        self.target_write_btn = QPushButton("passende Solltemp. schreiben")
        controls.addWidget(QLabel("aktuelle Solltemp. 2013/2014:"), 2, 0)
        controls.addWidget(self.target_label, 2, 1)
        controls.addWidget(QLabel("neue Solltemp.:"), 3, 0)
        controls.addWidget(self.target_spin, 3, 1)
        controls.addWidget(self.target_write_btn, 3, 2)

        self.ww_target_label_caption = QLabel("WW-Sollwert (1157):")
        self.ww_target_label = QLabel("--")
        self.ww_target_spin = QDoubleSpinBox()
        self.ww_target_spin.setRange(0.0, 90.0)
        self.ww_target_spin.setDecimals(1)
        self.ww_target_spin.setSingleStep(0.5)
        self.ww_target_write_btn = QPushButton("WW-Solltemp. schreiben (1157)")
        controls.addWidget(self.ww_target_label_caption, 4, 0)
        controls.addWidget(self.ww_target_label, 4, 1)
        controls.addWidget(self.ww_target_spin, 5, 1)
        controls.addWidget(self.ww_target_write_btn, 5, 2)

        self.silent_combo = QComboBox()
        self.silent_combo.addItem("Silent aus", 0)
        self.silent_combo.addItem("Silent ein", 1)
        self.silent_write_btn = QPushButton("Silent schreiben (1016 Bit 1)")
        controls.addWidget(QLabel("Silent:"), 6, 0)
        controls.addWidget(self.silent_combo, 6, 1)
        controls.addWidget(self.silent_write_btn, 6, 2)

        buttons = QHBoxLayout()
        self.read_btn = QPushButton("Status/Livewerte lesen")
        self.refresh_btn = QPushButton("aus Live-Werten aktualisieren")
        self.auto_refresh_cb = QCheckBox("Autorefresh")
        self.auto_refresh_interval = QSpinBox()
        self.auto_refresh_interval.setRange(2, 3600)
        self.auto_refresh_interval.setValue(10)
        self.auto_refresh_interval.setSuffix(" s")
        self.close_btn = QPushButton("Schließen")
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.refresh_btn)
        buttons.addSpacing(12)
        buttons.addWidget(self.auto_refresh_cb)
        buttons.addWidget(self.auto_refresh_interval)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.power_write_btn.clicked.connect(self.write_power)
        self.mode_write_btn.clicked.connect(self.write_mode)
        self.mode_combo.currentIndexChanged.connect(lambda _=None: self._update_ww_target_visibility())
        self.target_write_btn.clicked.connect(self.write_target)
        self.ww_target_write_btn.clicked.connect(self.write_ww_target)
        self.silent_write_btn.clicked.connect(self.write_silent)
        self.read_btn.clicked.connect(self.read_from_wp)
        self.refresh_btn.clicked.connect(self.refresh_from_live)
        self.auto_refresh_cb.toggled.connect(self._toggle_auto_refresh)
        self.auto_refresh_interval.valueChanged.connect(lambda _=None: self._toggle_auto_refresh(self.auto_refresh_cb.isChecked()))
        self.close_btn.clicked.connect(self.close)

    def update_from_live_register(self, reg):
        if int(getattr(reg, "reg", -1)) in {1011, 1012, 1016, 2011, 2012, 2013, 2014, 2045, 2046, 2047, 2048, 2077, 1157, 1158, 1159}:
            self.refresh_from_live()

    def refresh_from_live(self):
        power = self._raw(2011)
        self.power_state_label.setText("Ein" if power == 1 else "Aus" if power == 0 else "--")
        pset = self._raw(1011, power)
        if pset is not None:
            self.power_combo.setCurrentIndex(1 if pset == 1 else 0)

        set_mode = self._raw(1012)
        self.set_mode_label.setText(f"{set_mode} = {self.SET_MODE_MAP.get(set_mode, '--')}" if set_mode is not None else "--")
        if set_mode in self.SET_MODE_MAP:
            idx = self.mode_combo.findData(set_mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)

        run_mode = self._raw(2012)
        self.run_mode_label.setText(f"{run_mode} = {self.RUN_MODE_MAP.get(run_mode, '--')}" if run_mode is not None else "--")

        silent_raw = self._raw(1016)
        silent_on = bool((silent_raw or 0) & 0x0002) if silent_raw is not None else None
        self.silent_state_label.setText("Ein" if silent_on else "Aus" if silent_on is not None else "--")
        if silent_on is not None:
            self.silent_combo.setCurrentIndex(1 if silent_on else 0)

        vals = []
        for reg_no, label in self.TEMP_REGS:
            raw = self._raw(reg_no)
            text = self._fmt(reg_no, raw)
            self.temp_labels[reg_no].setText(text)
            if reg_no in (2013, 2014) and raw is not None:
                vals.append(text)
        self.target_label.setText(" / ".join(vals) if vals else "--")
        active_target = self._raw(2014) if self._raw(1236, 0) == 1 else self._raw(2013)
        if active_target is None:
            active_target = self._raw(2013) or self._raw(2014)
        if active_target is not None:
            self.target_spin.setValue(numeric_value_by_type(active_target, "TEMP1"))

        ww_raw = self._raw(1157)
        if ww_raw is not None:
            ww_val = numeric_value_by_type(ww_raw, "TEMP1")
            self.ww_target_label.setText(f"{ww_val:.1f} °C")
            self.ww_target_spin.setValue(ww_val)
        else:
            self.ww_target_label.setText("--")
        self._update_ww_target_visibility()

    def _update_ww_target_visibility(self):
        mode = self._raw(1012)
        if mode is None:
            mode = int(self.mode_combo.currentData()) if self.mode_combo.currentData() is not None else None
        show_ww_extra = mode in (3, 4)
        for widget in (self.ww_target_label_caption, self.ww_target_label, self.ww_target_spin, self.ww_target_write_btn):
            widget.setVisible(show_ww_extra)

    def _toggle_auto_refresh(self, enabled: bool):
        if enabled:
            self.auto_refresh_timer.start(int(self.auto_refresh_interval.value()) * 1000)
            self.read_from_wp()
        else:
            self.auto_refresh_timer.stop()

    def _confirm_write(self, title: str, text: str) -> bool:
        return ask_yes_no(self, title, text, default_yes=False)

    def write_power(self):
        value = int(self.power_combo.currentData())
        if self._confirm_write("Ein/Aus schreiben", f"Register 1011 wirklich auf {value} ({'Ein' if value else 'Aus'}) schreiben?"):
            self.main_window.send_register_write(1011, value, DEFAULT_BUS_ADDR, label="WP-Steuerung Ein/Aus")

    def write_mode(self):
        value = int(self.mode_combo.currentData())
        if self._confirm_write("Modus schreiben", f"Register 1012 wirklich auf {value} ({self.SET_MODE_MAP.get(value)}) schreiben?"):
            self.main_window.send_register_write(1012, value, DEFAULT_BUS_ADDR, label="WP-Steuerung Modus")

    def write_target(self):
        mode = self._raw(1012)
        reg_no, label = self.TARGET_REG_BY_SET_MODE.get(mode if mode is not None else int(self.mode_combo.currentData()), (1158, "Heizungssolltemperatur"))
        raw = int(round(float(self.target_spin.value()) * 10.0)) & 0xFFFF
        text = f"{label}: Register {reg_no} wirklich auf {self.target_spin.value():.1f} °C (raw {raw}) schreiben?"
        if self._confirm_write("Solltemperatur schreiben", text):
            self.main_window.send_register_write(reg_no, raw, DEFAULT_BUS_ADDR, label=f"WP-Steuerung {label}")

    def write_ww_target(self):
        raw = int(round(float(self.ww_target_spin.value()) * 10.0)) & 0xFFFF
        text = f"Warmwasser-Solltemperatur: Register 1157 wirklich auf {self.ww_target_spin.value():.1f} °C (raw {raw}) schreiben?"
        if self._confirm_write("WW-Solltemperatur schreiben", text):
            self.main_window.send_register_write(1157, raw, DEFAULT_BUS_ADDR, label="WP-Steuerung Warmwasser-Solltemperatur")

    def write_silent(self):
        current = self._raw(1016, 0) or 0
        bit = int(self.silent_combo.currentData())
        new_value = (current | 0x0002) if bit else (current & ~0x0002)
        text = f"Register 1016 Bit 1 wirklich {'setzen' if bit else 'löschen'}?\nAktuell: {current}/0x{current:04X}\nNeu: {new_value}/0x{new_value:04X}"
        if self._confirm_write("Silent schreiben", text):
            self.main_window.send_register_write(1016, new_value, DEFAULT_BUS_ADDR, label="WP-Steuerung Silent Bit 1")

    def read_from_wp(self):
        for addr, qty, label in [
            (1011, 6, "WP-Steuerung Soll/Flags 1011-1016"),
            (1157, 3, "WP-Steuerung Solltemperaturen R01-R03"),
            (2011, 4, "WP-Steuerung Status 2011-2014"),
            (2045, 4, "WP-Steuerung Temperaturen 2045-2048"),
            (2077, 1, "WP-Steuerung Durchfluss 2077"),
        ]:
            self.main_window.send_read_request(addr, qty, slave_addr=DEFAULT_BUS_ADDR, label=label, delay_ms=250)
        self.refresh_from_live()
        QTimer.singleShot(1500, self.refresh_from_live)


class CurveCanvas(QWidget):
    """Kleine Canvas-Grafik fuer die AT-Kompensationskurve ohne externe Abhaengigkeiten."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: list[tuple[float, float, bool]] = []
        self.setMinimumHeight(260)

    def set_points(self, points: list[tuple[float, float, bool]]):
        self.points = points
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(45, 15, -20, -35)
        if rect.width() <= 10 or rect.height() <= 10:
            return

        bg = self.palette().color(self.backgroundRole())
        fg = self.palette().color(self.foregroundRole())
        grid = QColor(160, 160, 160, 95)
        line = QColor(0, 160, 180)
        clip = QColor(220, 140, 0)

        painter.fillRect(self.rect(), bg)
        painter.setPen(QPen(grid, 1))
        for i in range(5):
            y = rect.top() + int(rect.height() * i / 4)
            painter.drawLine(rect.left(), y, rect.right(), y)
        for i in range(6):
            x = rect.left() + int(rect.width() * i / 5)
            painter.drawLine(x, rect.top(), x, rect.bottom())

        painter.setPen(QPen(fg, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.drawText(rect.left(), self.rect().top() + 12, "Zieltemp. °C")
        painter.drawText(rect.right() - 80, self.rect().bottom() - 5, "AT °C")

        if not self.points:
            painter.drawText(rect.center(), "Keine Kurvendaten")
            return

        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y = min(ys + [10.0])
        max_y = max(ys + [55.0])
        if max_y - min_y < 1:
            max_y = min_y + 1

        def sx(x):
            return rect.left() + (float(x) - min_x) / (max_x - min_x) * rect.width()
        def sy(y):
            return rect.bottom() - (float(y) - min_y) / (max_y - min_y) * rect.height()

        qpoints = [(sx(x), sy(y), clipped) for x, y, clipped in self.points]
        painter.setPen(QPen(line, 3))
        for (x1, y1, _), (x2, y2, _) in zip(qpoints, qpoints[1:]):
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        for (x, y, clipped), (at, target, _) in zip(qpoints, self.points):
            painter.setPen(QPen(clip if clipped else line, 2))
            painter.setBrush(clip if clipped else line)
            painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
            painter.setPen(QPen(fg, 1))
            painter.drawText(int(x) - 14, int(y) - 10, f"{target:.0f}")
            painter.drawText(int(x) - 18, rect.bottom() + 20, f"{at:.0f}")


class ATCompensationDialog(QDialog):
    """AT-Kompensationskurve Zone 1: H36/1236, Slope 1234, Offset 1235."""
    CURVE_AT_POINTS = [-30, -20, -10, 0, 10, 20]

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("AT-Kompensation")
        self.setMinimumWidth(820)
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.read_from_wp)
        self._build_ui()
        self.refresh_from_live()
        QTimer.singleShot(250, self.read_from_wp)

    def _raw(self, reg_no: int, default: Optional[int] = None) -> Optional[int]:
        try:
            if reg_no in self.main_window.latest_regs:
                return int(self.main_window.latest_regs[reg_no].raw_value) & 0xFFFF
            if reg_no in self.main_window.last_values:
                return int(self.main_window.last_values[reg_no]) & 0xFFFF
        except Exception:
            pass
        return default

    def _temp(self, reg_no: int) -> Optional[float]:
        raw = self._raw(reg_no)
        if raw is None:
            return None
        return numeric_value_by_type(raw, "TEMP1")

    def _slope(self) -> float:
        raw = self._raw(1234)
        return numeric_value_by_type(raw, "DIGI5") if raw is not None else float(self.slope_spin.value())

    def _offset(self) -> float:
        raw = self._raw(1235)
        return numeric_value_by_type(raw, "TEMP1") if raw is not None else float(self.offset_spin.value())

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.enable_cb = QCheckBox("AT-Kompensationskurve Zone 1 aktivieren (H36 / Register 1236)")
        layout.addWidget(self.enable_cb)

        status_box = QGroupBox("Aktueller Status")
        layout.addWidget(status_box)
        status = QGridLayout(status_box)
        self.current_at_label = QLabel("--")
        self.current_target_label = QLabel("--")
        self.formula_label = QLabel("vermutlich: Ziel = Offset - Slope × AT, mit Mindestbegrenzung")
        self.formula_label.setWordWrap(True)
        status.addWidget(QLabel("Außentemperatur (2048):"), 0, 0)
        status.addWidget(self.current_at_label, 0, 1)
        status.addWidget(QLabel("aktuelle kompensierte Solltemp. (2014):"), 1, 0)
        status.addWidget(self.current_target_label, 1, 1)
        status.addWidget(self.formula_label, 2, 0, 1, 2)

        edit_box = QGroupBox("Kurvenparameter")
        layout.addWidget(edit_box)
        edit = QGridLayout(edit_box)
        self.slope_spin = QDoubleSpinBox(); self.slope_spin.setRange(0.0, 3.5); self.slope_spin.setDecimals(1); self.slope_spin.setSingleStep(0.1)
        self.offset_spin = QDoubleSpinBox(); self.offset_spin.setRange(0.0, 85.0); self.offset_spin.setDecimals(1); self.offset_spin.setSingleStep(0.5)
        self.min_target_spin = QDoubleSpinBox(); self.min_target_spin.setRange(0.0, 60.0); self.min_target_spin.setDecimals(1); self.min_target_spin.setSingleStep(0.5); self.min_target_spin.setValue(15.0)
        edit.addWidget(QLabel("Slope 1234:"), 0, 0); edit.addWidget(self.slope_spin, 0, 1)
        edit.addWidget(QLabel("Offset 1235:"), 0, 2); edit.addWidget(self.offset_spin, 0, 3)
        edit.addWidget(QLabel("Mindestwert Anzeige:"), 1, 0); edit.addWidget(self.min_target_spin, 1, 1)
        self.slope_spin.valueChanged.connect(lambda _=None: self.update_curve_table())
        self.offset_spin.valueChanged.connect(lambda _=None: self.update_curve_table())
        self.min_target_spin.valueChanged.connect(lambda _=None: self.update_curve_table())

        self.curve_canvas = CurveCanvas(self)
        layout.addWidget(self.curve_canvas)

        self.curve_table = QTableWidget(0, 3)
        self.curve_table.setHorizontalHeaderLabels(["AT °C", "berechnete Zieltemp. °C", "Hinweis"])
        self.curve_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.curve_table.verticalHeader().setVisible(False)
        self.curve_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.curve_table)

        buttons = QHBoxLayout()
        self.read_btn = QPushButton("von WP lesen")
        self.apply_live_btn = QPushButton("aus Live-Werten laden")
        self.write_enable_btn = QPushButton("H36 schreiben")
        self.write_params_btn = QPushButton("Slope/Offset schreiben")
        self.auto_refresh_cb = QCheckBox("Autorefresh")
        self.auto_refresh_interval = QSpinBox()
        self.auto_refresh_interval.setRange(2, 3600)
        self.auto_refresh_interval.setValue(10)
        self.auto_refresh_interval.setSuffix(" s")
        self.close_btn = QPushButton("Schließen")
        for w in (self.read_btn, self.apply_live_btn, self.write_enable_btn, self.write_params_btn):
            buttons.addWidget(w)
        buttons.addSpacing(12)
        buttons.addWidget(self.auto_refresh_cb)
        buttons.addWidget(self.auto_refresh_interval)
        buttons.addStretch(1); buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.read_btn.clicked.connect(self.read_from_wp)
        self.apply_live_btn.clicked.connect(self.refresh_from_live)
        self.auto_refresh_cb.toggled.connect(self._toggle_auto_refresh)
        self.auto_refresh_interval.valueChanged.connect(lambda _=None: self._toggle_auto_refresh(self.auto_refresh_cb.isChecked()))
        self.write_enable_btn.clicked.connect(self.write_enable)
        self.write_params_btn.clicked.connect(self.write_params)
        self.close_btn.clicked.connect(self.close)

    def update_from_live_register(self, reg):
        if int(getattr(reg, "reg", -1)) in {1234, 1235, 1236, 2014, 2048}:
            self.refresh_from_live()

    def refresh_from_live(self):
        enabled = self._raw(1236)
        if enabled is not None:
            self.enable_cb.setChecked(bool(enabled))
        slope = self._raw(1234)
        if slope is not None:
            self.slope_spin.setValue(numeric_value_by_type(slope, "DIGI5"))
        offset = self._raw(1235)
        if offset is not None:
            self.offset_spin.setValue(numeric_value_by_type(offset, "TEMP1"))
        at = self._temp(2048)
        target = self._temp(2014)
        self.current_at_label.setText("--" if at is None else f"{at:.1f} °C")
        self.current_target_label.setText("--" if target is None else f"{target:.1f} °C")
        self.update_curve_table()

    def update_curve_table(self):
        slope = float(self.slope_spin.value())
        offset = float(self.offset_spin.value())
        min_target = float(self.min_target_spin.value())
        curve_points: list[tuple[float, float, bool]] = []
        self.curve_table.setRowCount(len(self.CURVE_AT_POINTS))
        for row, at in enumerate(self.CURVE_AT_POINTS):
            raw_target = offset - slope * float(at)
            target = max(min_target, raw_target)
            was_clipped = target != raw_target
            curve_points.append((float(at), float(target), was_clipped))
            clipped = "Mindestwert" if was_clipped else ""
            for col, text in enumerate((f"{at:.1f}", f"{target:.1f}", clipped)):
                item = QTableWidgetItem(text)
                self.curve_table.setItem(row, col, item)
        if hasattr(self, "curve_canvas"):
            self.curve_canvas.set_points(curve_points)

    def _toggle_auto_refresh(self, enabled: bool):
        if enabled:
            self.auto_refresh_timer.start(int(self.auto_refresh_interval.value()) * 1000)
            self.read_from_wp()
        else:
            self.auto_refresh_timer.stop()

    def _confirm_write(self, title: str, text: str) -> bool:
        return ask_yes_no(self, title, text, default_yes=False)

    def write_enable(self):
        value = 1 if self.enable_cb.isChecked() else 0
        if self._confirm_write("AT-Kompensation schreiben", f"Register 1236 / H36 wirklich auf {value} ({'Ein' if value else 'Aus'}) schreiben?"):
            self.main_window.send_register_write(1236, value, DEFAULT_BUS_ADDR, label="AT-Kompensation H36")

    def write_params(self):
        slope_raw = int(round(float(self.slope_spin.value()) * 10.0)) & 0xFFFF
        offset_raw = int(round(float(self.offset_spin.value()) * 10.0)) & 0xFFFF
        text = f"Slope 1234 = {self.slope_spin.value():.1f} (raw {slope_raw})\nOffset 1235 = {self.offset_spin.value():.1f} °C (raw {offset_raw})\n\nWirklich schreiben?"
        if self._confirm_write("AT-Kurvenparameter schreiben", text):
            self.main_window.send_register_write(1234, slope_raw, DEFAULT_BUS_ADDR, label="AT-Kompensation Slope")
            self.main_window.send_register_write(1235, offset_raw, DEFAULT_BUS_ADDR, label="AT-Kompensation Offset", delay_ms=350)

    def read_from_wp(self):
        for addr, qty, label in [(1234, 3, "AT-Kompensation 1234-1236"), (2014, 1, "AT-Kompensation aktuelle Solltemp. 2014"), (2048, 1, "AT-Kompensation Außentemperatur 2048")]:
            self.main_window.send_read_request(addr, qty, slave_addr=DEFAULT_BUS_ADDR, label=label, delay_ms=250)
        self.refresh_from_live()
        QTimer.singleShot(1500, self.refresh_from_live)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(app_icon())
        self.resize(1400, 900)

        resource_dir = app_resource_dir()
        program_dir = app_program_dir()
        self.base_dir = resource_dir
        self.program_dir = program_dir
        self.regmap_path = os.path.join(resource_dir, "data/foxair_phnix_registers.json")
        self.display_regmap_path = os.path.join(resource_dir, "data/foxair_phnix_display_registers.json")
        # Rueckwaertskompatibel: alte Warmlink-Dateinamen werden beim ersten Start noch gelesen.
        old_regmap_path = os.path.join(resource_dir, "warmlink_registers.json")
        if not os.path.exists(self.regmap_path) and os.path.exists(old_regmap_path):
            self.regmap_path = old_regmap_path

        # User-/Arbeitsdateien:
        # PUBLIC/Installer: AppData (Program Files ist ohne Adminrechte nicht beschreibbar).
        # PRIVATE/Portable: Programmordner.
        self.user_data_dir = app_user_data_dir()
        self.cache_file_path = os.path.join(self.user_data_dir, "foxair_phnix_last_values.json")
        self.old_cache_file_path = os.path.join(self.user_data_dir, "warmlink_last_values.json")
        self.settings_path = os.path.join(self.user_data_dir, "foxair_phnix_settings.json")
        self.old_settings_path = os.path.join(self.user_data_dir, "warmlink_gui_settings.json")
        self.knowledge_path = os.path.join(self.user_data_dir, "data/foxair_phnix_knowledge.json")
        self.bundled_knowledge_path = os.path.join(resource_dir, "data/foxair_phnix_knowledge.json")
        self.settings = self._load_settings()
        self._restore_main_window_size()
        apply_app_theme(QApplication.instance(), str(self.settings.get("theme", "system")))
        self.knowledge_defs = self._load_knowledge_defs()
        self.regmap = RegisterMap(self.regmap_path)
        # Display-/DWIN-Adressen bekommen bewusst ein eigenes Diagnose-Mapping.
        # Sie duerfen die normale Warmlink/WP-Registertabelle nicht ueberschreiben.
        self.display_regmap = RegisterMap(self.display_regmap_path) if os.path.exists(self.display_regmap_path) else RegisterMap("")
        self.register_defs = self._load_register_defs()

        self.thread: Optional[QThread] = None
        self.worker: Optional[ReaderWorker] = None

        self.table_rows: Dict[int, int] = {}
        self.latest_regs: Dict[int, object] = {}
        self.last_values: Dict[int, int] = {}
        self.previous_value_texts: Dict[int, str] = {}
        self.register_flash_tokens: Dict[int, int] = {}
        self.register_flash_colors: Dict[int, QColor] = {}
        # Display-/DWIN-Diagnosewerte strikt getrennt von der Warmlink-Hauptliste.
        self.display_latest_regs: Dict[int, object] = {}
        self.display_last_values: Dict[int, int] = {}
        self.display_previous_value_texts: Dict[int, str] = {}
        self.raw_dump = bytearray()
        self.connected = False
        self.foreign_frame_count = 0
        self.bus_rows: Dict[int, int] = {}
        self.bus_stats: Dict[int, dict] = {}
        # V0.2.44 PUBLIC: stark wiederholte Bus-Diagnosezeilen werden
        # zusammengefasst, damit das GUI-Log bei Poll-Stuermen (z. B.
        # 0x02/3001) nicht tausende identische Zeilen pro Sekunde anhaengt.
        self.log_throttle_state: Dict[tuple[Any, ...], dict[str, Any]] = {}
        self.raw_file: Optional[BinaryIO] = None
        self.raw_file_path: Optional[str] = None
        self.warmlink_capture: Optional[WarmlinkRawCapture] = None
        self.capture_log_queue: queue.Queue[str] = queue.Queue()
        self.cached_regs: set[int] = set()
        # Register, deren Wert sich seit dem letzten "Hauptfenster leeren" geändert hat.
        # Die Markierung bleibt bewusst dauerhaft stehen, bis die Hauptliste geleert wird.
        self.register_change_highlights: set[int] = set()
        self.pending_read_requests: list[dict[str, Any]] = []
        self.pending_write_requests: list[dict[str, Any]] = []
        self.pending_read_timeout_timer = QTimer(self)
        self.pending_read_timeout_timer.setInterval(500)
        self.pending_read_timeout_timer.timeout.connect(self._check_pending_read_timeouts)
        self.pending_read_timeout_timer.start()
        self.display_last_frame_monotonic = 0.0
        self.display_init_retry_items: list[tuple[int, int, str, int, int]] = []
        self.display_init_retry_round = False
        self.display_init_waiting_since = 0.0
        self.display_init_timeout_s = 8.0
        self.display_init_bus_idle_ms = 450
        self.observed_display_read_requests: list[dict[str, Any]] = []
        # Display-/HMI-Diagnose: Rohblock-Snapshots fuer Kandidatensuche.
        # Diese Werte werden bewusst getrennt von der Haupt-Registerliste gehalten.
        self.display_hmi_block_snapshots: Dict[tuple[int, int, str], list[int]] = {}
        self.display_hmi_block_snapshot_times: Dict[tuple[int, int, str], float] = {}
        # PRIVATE Display-Tests: ACK-Zeitstempel fuer aktiv injizierte FC16-Schreibbefehle.
        # Key: (slave, start_addr, qty). Wichtig, weil die bisherigen Tests fast immer
        # nur dann wirken, wenn das Display Unit 0x03 den Write wirklich quittiert.
        self.display_write_ack_times: Dict[tuple[int, int, int], float] = {}
        self.display_fake_reboot_state: dict[str, Any] = {}
        # fix12: Display-Reboot-Fake ist am Display-Bus die Standard-Snapshot-Methode
        # fuer "Alle Register lesen" und Popup-Aktualisierungen. Cooldown verhindert,
        # dass mehrere Popup-Reads denselben Reboot-Snapshot mehrfach starten.
        self.display_fake_reboot_last_success_time: float = 0.0
        self.display_fake_reboot_last_source: str = ""
        self.display_user_value_state: dict[str, Any] = {}
        # V0.2.41 PRIVATE: Timer-/Popup-Mehrfachwrites am Displaybus laufen ACK-gesteuert
        # und bevorzugt als kompakte FC16-Blockwrites, damit keine Einzelwrites im
        # normalen Displaybus-Verkehr verloren gehen.
        self.display_timer_batch_state: dict[str, Any] = {}
        # V0.2.41 PRIVATE: Merker, damit der automatische Hinweis/Init-Lauf bei
        # fehlenden Display-Parameterpaketen nicht bei jedem Klick neu nervt.
        self.display_param_init_prompted_contexts: set[str] = set()
        # V0.2.41 fix5: Popup-Oeffnung kann warten, bis die benoetigten
        # Display-Parameterpakete wirklich angekommen sind. Key = Kontextname,
        # Value = Startzeit monotonic.
        self.display_pending_popup_open_started: dict[str, float] = {}
        # V0.2.41 fix5: sichtbarer, nicht blockierender Hinweis beim Klick auf
        # ein Popup, solange die benoetigten Display-Live-/Parameterwerte laden.
        self.display_pending_popup_wait_messages: dict[str, QMessageBox] = {}
        # fix9: normale Display-Parameterwrites (Rechtsklick/Popups) laufen
        # nacheinander ACK-gesteuert ueber den 23xx-Bedienwertpfad.
        self.display_user_value_queue: list[dict[str, Any]] = []
        self.display_hmi_no_response_requests: list[dict[str, Any]] = []
        self.value_search_target: Optional[float] = None
        self.value_search_tolerance: float = 0.0
        self.value_search_mode: str = "raw"
        self.value_search_matches: set[int] = set()
        self.value_search_context: set[int] = set()
        self.name_search_matches: set[int] = set()
        self.contact_dialog: Optional[ContactDecoderDialog] = None
        self.load_output_dialog: Optional[LoadOutputDecoderDialog] = None
        self.fault_dialog: Optional[FaultDecoderDialog] = None
        self.timer_dialog: Optional[TimerEditorDialog] = None
        self.onoff_timer_dialog: Optional[OnOffTimerEditorDialog] = None
        self.silent_timer_dialog: Optional[SilentTimerDialog] = None
        self.sg_dialog: Optional[SGReadyEditorDialog] = None
        self.wp_control_dialog: Optional[WPControlDialog] = None
        self.at_comp_dialog: Optional[ATCompensationDialog] = None
        self.parameter_dialog: Optional[ParameterSettingsDialog] = None
        self.manual_register_dialog: Optional[ManualRegisterDialog] = None
        self.bus_dialog: Optional[BusAddressDialog] = None
        self.offline_dialog: Optional[OfflineRegisterBrowserDialog] = None
        self.backup_restore_dialog: Optional[BackupRestoreDialog] = None
        self.dual_logger_dialog: Optional[DualBusLoggerDialog] = None
        self.warmlink_cloud_dialog: Optional[WarmLinkCloudDialog] = None
        self.cloud_write_thread: Optional[QThread] = None
        self.cloud_write_worker: Optional[WarmLinkCloudCommandWorker] = None
        self.cloud_write_code: str = ""
        self.cloud_overlay_by_reg: dict[int, dict[str, Any]] = {}
        self.cloud_last_rows: list[dict[str, Any]] = []
        self.about_dialog: Optional[AboutDialog] = None
        self.update_thread: Optional[QThread] = None
        self.update_worker: Optional[UpdateCheckWorker] = None
        self.register_write_dialogs: Dict[tuple[int, int], RegisterQuickWriteDialog] = {}
        self.last_contact_value: Optional[int] = None
        self.last_load_output_value: Optional[int] = None
        self.init_read_queue: list[tuple[int, int, str, int]] = []
        self.init_read_active = False
        self.warmlink_init_controller = WarmlinkInitReadController(self)
        self.standard_modbus_init_controller = StandardModbusInitReadController(self)
        # V0.2.41: Display-Init liest 90er-WP-Paketblöcke sequenziell.
        # Nicht mehr nach fixer Pause alles raushauen, sondern Antwort/Timeout abwarten.
        self.init_display_packet_mode = False
        self.init_waiting_for_display_packet = False
        self._suppress_name_resize = False

        self._build_ui()
        self._setup_capture_gui_log_timer()
        self._setup_help_actions()
        # V0.2.38: alter GUI-Init-Timer entfernt.
        # Init-Lesen wird jetzt je Backend durch eigene Controller gesteuert.
        self.init_read_timer = None
        self.cache_timer = QTimer(self)
        self.cache_timer.timeout.connect(lambda: self.save_value_cache(silent=True))
        self._apply_cache_timer_state()
        self.live_poll_timer = QTimer(self)
        self.live_poll_timer.timeout.connect(self._live_poll_tick)
        self.live_poll_step = 0
        self._apply_live_poll_timer_state()
        self._log(f"Register-Mapping: {self.regmap_path} ({len(self.regmap)} Einträge)")
        if os.path.exists(self.display_regmap_path):
            self._log(f"Display-Diagnose-Mapping: {self.display_regmap_path} ({len(self.display_regmap)} Einträge, getrennt von Warmlink)")
        if self.cache_load_start_cb.isChecked():
            self.load_value_cache(silent=False)
        # PRIVATE fix16: Bereichsfarben nach dem ersten Qt-Layout/Stylesheet-Pass
        # nochmal setzen. Dadurch greifen 10xx/30xx-Farben auch direkt nach
        # Programmstart/Cache-Aufbau, nicht erst nach dem ersten Live-Read.
        QTimer.singleShot(0, self._refresh_search_highlights)
        QTimer.singleShot(250, self._refresh_search_highlights)
        QTimer.singleShot(1000, self._refresh_search_highlights)
        self._log(f"Benutzerdaten: {self.user_data_dir}")
        QTimer.singleShot(700, self._autoconnect_if_enabled)
        QTimer.singleShot(1700, self._autostart_warmlink_cloud_if_enabled)
        if APP_EDITION.upper() == "PUBLIC":
            QTimer.singleShot(2500, self.check_for_updates_on_startup)

    def _setup_help_actions(self):
        # Kein sichtbares Menue mehr: Die alte Menueleiste mit "Hilfe" belegte
        # unter Windows eine eigene Zeile. F1 bleibt als unsichtbare Aktion aktiv;
        # zusaetzlich gibt es einen kleinen About-Button in der oberen Kopfzeile.
        about_action = QAction("About", self)
        about_action.setShortcut("F1")
        about_action.triggered.connect(self.open_about_dialog)
        self.addAction(about_action)

    def open_about_dialog(self):
        if self.about_dialog is None or not self.about_dialog.isVisible():
            self.about_dialog = AboutDialog(self)
            self.about_dialog.finished.connect(lambda _=None: setattr(self, "about_dialog", None))
            self.about_dialog.show()
        else:
            self.about_dialog.raise_()
            self.about_dialog.activateWindow()

    def open_warmlink_cloud_dialog(self):
        if self.warmlink_cloud_dialog is None:
            self.warmlink_cloud_dialog = WarmLinkCloudDialog(self)
            self.warmlink_cloud_dialog.finished.connect(lambda _=None: setattr(self, "warmlink_cloud_dialog", None))
        self.warmlink_cloud_dialog.show()
        self.warmlink_cloud_dialog.raise_()
        self.warmlink_cloud_dialog.activateWindow()

    def _autostart_warmlink_cloud_if_enabled(self):
        cfg = self.settings.get("warmlink_cloud", {})
        if not isinstance(cfg, dict) or not cfg.get("auto_start_polling"):
            return
        username = str(cfg.get("username", "")).strip()
        if not username:
            self._log("WarmLink Cloud Autostart übersprungen: keine E-Mail gespeichert")
            return
        if self.warmlink_cloud_dialog is None:
            self.warmlink_cloud_dialog = WarmLinkCloudDialog(self)
            self.warmlink_cloud_dialog.finished.connect(lambda _=None: setattr(self, "warmlink_cloud_dialog", None))
        self._log("WarmLink Cloud Autostart: Polling im Hintergrund startet ...")
        self.warmlink_cloud_dialog._start_worker(poll_once=False)

    def _autoconnect_if_enabled(self):
        if self.autoconnect_cb.isChecked() and not self.connected:
            self._log("Autoconnect aktiv: verbinde mit letzter IP/Port ...")
            self.connect_to_device()

    def _load_knowledge_defs(self) -> dict[str, Any]:
        try:
            path = self.knowledge_path if os.path.exists(self.knowledge_path) else getattr(self, "bundled_knowledge_path", self.knowledge_path)
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return raw if isinstance(raw, dict) else {}
        except Exception as exc:
            print(f"Knowledge-Datei konnte nicht gelesen werden: {exc}")
            return {}

    def _load_register_defs(self) -> dict[str, Any]:
        try:
            with open(self.regmap_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            defs = raw if isinstance(raw, dict) else {}
        except Exception:
            return {}
        # Mapping beim Laden normalisieren: neue Struktur code/block/name, alte "A40 / Name" bleibt kompatibel.
        for _key, _data in list(defs.items()):
            if isinstance(_data, dict):
                block, code, clean = register_meta_parts(_data)
                if clean:
                    _data["name"] = clean
                if code:
                    _data["code"] = code
                if block:
                    _data["block"] = block
        # Wissensdatenbank überlagert nur Erklär-/Notizfelder, nicht technische Basisfelder.
        for key, extra in getattr(self, "knowledge_defs", {}).items():
            if not isinstance(extra, dict):
                continue
            skey = str(key)
            base = defs.setdefault(skey, {})
            if not isinstance(base, dict):
                continue
            for field in ("description", "knowledge", "notes", "hint", "explanation", "default", "source", "source_app_video"):
                if field in extra and str(extra.get(field, "")).strip():
                    base[field] = extra[field]
            if isinstance(extra.get("default_by_device"), dict):
                cleaned = {str(k): str(v) for k, v in extra["default_by_device"].items() if str(v).strip()}
                if cleaned:
                    base["default_by_device"] = cleaned
        return defs

    def get_register_knowledge(self, reg_no: int) -> dict[str, Any]:
        raw = getattr(self, "knowledge_defs", {}).get(str(int(reg_no)), {})
        return dict(raw) if isinstance(raw, dict) else {}

    def set_register_knowledge(self, reg_no: int, data: dict[str, Any]):
        reg_key = str(int(reg_no))
        clean = {}
        for k, v in data.items():
            if k == "default_by_device" and isinstance(v, dict):
                dv = {str(dk): str(dv) for dk, dv in v.items() if str(dv).strip()}
                if dv:
                    clean[k] = dv
            elif str(v).strip():
                clean[k] = v
        if clean:
            self.knowledge_defs[reg_key] = clean
        else:
            self.knowledge_defs.pop(reg_key, None)
        os.makedirs(os.path.dirname(self.knowledge_path), exist_ok=True)
        with open(self.knowledge_path, "w", encoding="utf-8") as f:
            json.dump(self.knowledge_defs, f, ensure_ascii=False, indent=2)
        self.register_defs = self._load_register_defs()
        self._log(f"Wissensdatenbank gespeichert: Register {reg_no} ({self.knowledge_path})")

    def edit_register_knowledge(self, reg_no: int) -> bool:
        dlg = KnowledgeEditorDialog(self, int(reg_no))
        return dlg.exec() == QDialog.Accepted

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        top = QHBoxLayout()
        main_layout.addLayout(top)

        self.public_warning_label = QLabel(PUBLIC_WARNING_TEXT)
        self.public_warning_label.setWordWrap(True)
        self.public_warning_label.setStyleSheet("color: #8a4b00; background: #fff3cd; border: 1px solid #ffd27a; padding: 4px; font-weight: bold;")
        self.public_warning_label.setVisible(bool(self.settings.get("show_public_warning", True)))
        main_layout.addWidget(self.public_warning_label)

        self.backend_combo = QComboBox()
        for key, label in BACKEND_CHOICES:
            self.backend_combo.addItem(label, key)
        backend_saved = str(self.settings.get("backend", "standard_modbus" if APP_EDITION.upper() == "PUBLIC" else "warmlink_raw"))
        if backend_saved not in BACKEND_LABELS:
            backend_saved = "standard_modbus" if APP_EDITION.upper() == "PUBLIC" else "warmlink_raw"
        idx = self.backend_combo.findData(backend_saved)
        self.backend_combo.setCurrentIndex(idx if idx >= 0 else 0)

        active_cfg = self._backend_settings(backend_saved)
        self.host_edit = QLineEdit(str(active_cfg.get("host", DEFAULT_HOST)))
        self.port_edit = QSpinBox()
        self.port_edit.setRange(1, 65535)
        self.port_edit.setValue(int(active_cfg.get("port", DEFAULT_PORT)))
        self.unit_spin = QSpinBox()
        self.unit_spin.setRange(1, 247)
        self.unit_spin.setValue(int(active_cfg.get("unit_id", DEFAULT_BUS_ADDR)))
        self.unit_spin.setMaximumWidth(70)
        self.display_translate_cb = QCheckBox("Display +0x2000")
        self.display_translate_cb.setToolTip("Entfernt: Display-Modbus schreibt/liest Register jetzt ohne automatische +0x2000-Übersetzung.")
        self.display_translate_cb.setChecked(False)
        self.display_translate_cb.setVisible(False)
        self.comm_settings_btn = QPushButton("Programm-Einstellungen ...")
        self.cloud_btn = QPushButton("WarmLink Cloud / LTE ...")
        self.cloud_btn.setToolTip("Optionale WarmLink/Linked-Go Cloud-Anbindung: lesen, Overlay, Wertefinder und Schreiben bekannter Cloud-Codes.")
        self.comm_summary_label = QLabel("")
        self.comm_summary_label.setMinimumWidth(360)

        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.autoconnect_cb = QCheckBox("Autoconnect")
        self.autoconnect_cb.setToolTip("Beim Programmstart automatisch mit letzter IP/Port verbinden.")
        self.autoconnect_cb.setChecked(bool(self.settings.get("autoconnect_on_start", APP_EDITION == "PRIVATE")))

        self.known_only_cb = QCheckBox("nur bekannte Register anzeigen")
        self.known_only_cb.setChecked(False)
        self.log_changes_only_cb = QCheckBox("nur Änderungen loggen")
        self.log_changes_only_cb.setChecked(True)
        self.log_level_combo = QComboBox()
        self.log_level_combo.setToolTip("Log-Level 1=ruhig, 7=Debug/alles. Für Chat-Diagnose Level 4; RAW/TX nur mit RAW anzeigen oder Level 6/7.")
        for level, label in LOG_LEVEL_LABELS:
            self.log_level_combo.addItem(label, level)
        saved_log_level = int(self.settings.get("log_level", 2))
        lvl_idx = self.log_level_combo.findData(saved_log_level)
        self.log_level_combo.setCurrentIndex(lvl_idx if lvl_idx >= 0 else 1)
        self.raw_log_cb = QCheckBox("RAW anzeigen (HEX+ASCII)")
        self.raw_log_cb.setToolTip("Zeigt Rohbytes im sichtbaren Log als HEX+ASCII. Nur für Debug nötig; RAW-Datei-Mitschrift bleibt separat.")
        self.raw_file_cb = QCheckBox("Raw in Datei (nc/bin)")
        self.raw_ascii_cb = QCheckBox("Raw ASCII-Vorschau")
        self.raw_ascii_cb.setChecked(True)
        self.raw_ascii_cb.setVisible(False)
        self.clear_log_btn = QPushButton("Log leeren")
        self.clear_log_btn.setToolTip("Nur das sichtbare Logfenster leeren; Raw-Datei und Registerwerte bleiben erhalten.")
        self.clear_main_btn = QPushButton("Hauptfenster leeren")
        self.clear_main_btn.setToolTip("Registertabelle/Hauptwerte leeren; Verbindung, Log, Raw-Datei und Werte-Cache-Datei bleiben unverändert.")

        self.about_btn = QPushButton("About")
        self.about_btn.setMaximumWidth(72)
        self.about_btn.setToolTip("Hilfe / About (F1)")

        top.addWidget(self.comm_settings_btn)
        top.addWidget(self.cloud_btn)
        top.addWidget(self.comm_summary_label)
        top.addWidget(self.connect_btn)
        top.addWidget(self.disconnect_btn)
        top.addWidget(self.autoconnect_cb)
        top.addWidget(self.known_only_cb)
        top.addWidget(self.log_changes_only_cb)
        top.addWidget(QLabel("Log:"))
        top.addWidget(self.log_level_combo)
        top.addWidget(self.raw_log_cb)
        top.addWidget(self.raw_file_cb)
        # V0.2.41 fix6: eigene RAW-ASCII-Option ist überflüssig;
        # RAW anzeigen liefert jetzt immer HEX+ASCII. Checkbox bleibt nur
        # intern/kompatibel, wird aber nicht mehr in die Kopfzeile gesetzt.
        top.addWidget(self.clear_log_btn)
        top.addWidget(self.clear_main_btn)
        top.addStretch(1)
        top.addWidget(self.about_btn)

        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter, 1)

        upper = QSplitter(Qt.Horizontal)
        splitter.addWidget(upper)

        self.register_table = QTableWidget(0, 14)
        self.register_table.setHorizontalHeaderLabels([
            "Reg", "Code", "Name", "Typ", "Rohwert", "Letzter Wert", "Signed", "Wert", "Frame", "Bus", "Zeit", "Cloud", "Cloud-Code", "Cloud-Zeit"
        ])
        header = self.register_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.register_table.setColumnWidth(0, 58)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.register_table.setColumnWidth(1, 68)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.register_table.setColumnWidth(6, 76)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.register_table.setColumnWidth(7, 130)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(11, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(12, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(13, QHeaderView.ResizeToContents)
        self.register_table.setSortingEnabled(False)  # wichtig: sonst werden row-Indizes beim Live-Update falsch
        self.register_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.register_table.setAlternatingRowColors(False)
        self.register_table.itemDoubleClicked.connect(self.open_manual_register_dialog_from_table_item)
        upper.addWidget(self.register_table)

        side = QWidget()
        side.setMinimumWidth(390)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(6, 6, 6, 6)
        side_layout.setSpacing(6)

        side_scroll = QScrollArea()
        side_scroll.setWidgetResizable(True)
        side_scroll.setWidget(side)
        side_scroll.setMinimumWidth(420)
        upper.addWidget(side_scroll)
        upper.setStretchFactor(0, 5)
        upper.setStretchFactor(1, 1)

        manual_box = QGroupBox("Lesen / Schreiben")
        side_layout.addWidget(manual_box)
        manual_layout = QGridLayout(manual_box)
        manual_layout.setContentsMargins(8, 8, 8, 8)

        self.write_bus_edit = QLineEdit(f"0x{DEFAULT_BUS_ADDR:02X}")
        self.write_addr_edit = QLineEdit("1334")
        self.write_value_edit = QLineEdit("0")
        self.write_dry_btn = QPushButton("Frame anzeigen")
        self.write_send_btn = QPushButton("ECHT senden")
        self.write_send_btn.setEnabled(False)
        self.read_count_spin = QSpinBox()
        self.read_count_spin.setRange(1, 125)
        self.read_count_spin.setValue(1)
        self.read_btn = QPushButton("FC03 lesen")
        self.manual_register_btn = QPushButton("Register lesen/schreiben ...")
        self.init_read_btn = QPushButton("Alle bekannten Register lesen")
        self.init_pause_spin = QSpinBox()
        self.init_pause_spin.setRange(100, 5000)
        self.init_pause_spin.setValue(900)
        self.init_pause_spin.setSingleStep(100)
        self.init_pause_spin.setSuffix(" ms")
        self.init_pause_spin.setMaximumWidth(95)
        self.init_pause_spin.setToolTip("Pause zwischen den Init-Leseblöcken. Höher stellen, wenn die WP/Warmlink langsam antwortet.")

        manual_layout.addWidget(self.init_read_btn, 0, 0)
        manual_layout.addWidget(QLabel("Pause:"), 0, 1)
        manual_layout.addWidget(self.init_pause_spin, 0, 2)
        manual_layout.addWidget(self.manual_register_btn, 1, 0, 1, 4)
        manual_layout.setColumnStretch(3, 1)

        display_exp_box = QGroupBox("Display-Experimente PRIVATE")
        # fix11: Der PRIVATE Display-Testbereich bleibt im Code vorhanden,
        # wird aber in der normalen UI ausgeblendet. Bei Bedarf kann er zum
        # Debuggen sehr schnell wieder sichtbar gemacht werden.
        self.display_exp_box = display_exp_box
        side_layout.addWidget(display_exp_box)
        display_exp_box.setVisible(False)
        display_exp_layout = QGridLayout(display_exp_box)
        display_exp_layout.setContentsMargins(8, 8, 8, 8)
        display_exp_layout.setHorizontalSpacing(6)
        display_exp_layout.setVerticalSpacing(4)
        self.display_fake_reboot_btn = QPushButton("Display Reboot Fake")
        self.display_fake_reboot_btn.setToolTip("fix9: ACK-gesteuert. Erst 5112H=0 mit ACK, dann 0BC3H=8000 mit ACK/Retry. Der echte Master sollte danach die Parameterpakete 1001/1091/... an Unit 3 schreiben.")
        self.display_sim_reg_edit = QLineEdit("1012")
        self.display_sim_reg_edit.setMaximumWidth(82)
        self.display_sim_value_edit = QLineEdit("1")
        self.display_sim_value_edit.setMaximumWidth(82)
        self.display_sim_variant_combo = QComboBox()
        self.display_sim_variant_combo.addItem("A: nur Benutzerwert", "A")
        self.display_sim_variant_combo.addItem("B: Benutzerwert + 0BC3", "B")
        self.display_sim_variant_combo.addItem("C: Paketwert + Benutzerwert + 0BC3", "C")
        self.display_sim_variant_combo.setCurrentIndex(0)
        self.display_sim_variant_combo.setToolTip(
            "PRIVATE Testmatrix fuer Display-Bedienung. fix9-Default ist A: nur Register+0x2000. "
            "Das Display soll 0BC3 selbst setzen. B/C bleiben als Fallback-/Diagnosevarianten."
        )
        self.display_sim_user_change_btn = QPushButton("Display-Wert testen")
        self.display_sim_heat_btn = QPushButton("Heizen")
        self.display_sim_cool_btn = QPushButton("Kühlen")
        self.display_sim_ww_btn = QPushButton("WW")
        self.display_sim_ww_btn.setToolTip("Setzt Modus-Register 1012 auf 0 = Warmwasser (laut MODE_0_4 Mapping).")
        display_exp_layout.addWidget(self.display_fake_reboot_btn, 0, 0, 1, 4)
        display_exp_layout.addWidget(QLabel("Reg:"), 1, 0)
        display_exp_layout.addWidget(self.display_sim_reg_edit, 1, 1)
        display_exp_layout.addWidget(QLabel("Wert:"), 1, 2)
        display_exp_layout.addWidget(self.display_sim_value_edit, 1, 3)
        display_exp_layout.addWidget(QLabel("Variante:"), 2, 0)
        display_exp_layout.addWidget(self.display_sim_variant_combo, 2, 1, 1, 3)
        display_exp_layout.addWidget(self.display_sim_user_change_btn, 3, 0, 1, 4)
        display_exp_layout.addWidget(self.display_sim_heat_btn, 4, 0, 1, 1)
        display_exp_layout.addWidget(self.display_sim_cool_btn, 4, 1, 1, 1)
        display_exp_layout.addWidget(self.display_sim_ww_btn, 4, 2, 1, 2)

        search_box = QGroupBox("Wertsuche")
        side_layout.addWidget(search_box)
        search_layout = QGridLayout(search_box)
        search_layout.setContentsMargins(8, 8, 8, 8)
        search_layout.setHorizontalSpacing(6)
        search_layout.setVerticalSpacing(4)
        self.search_value_edit = QLineEdit("55")
        self.search_value_edit.setToolTip("Dezimal/Hex bei Rohwert, Dezimalzahl bei decodiertem Wert, z. B. 55, 0x0037 oder 34.5.")
        self.search_tolerance_spin = QDoubleSpinBox()
        self.search_tolerance_spin.setRange(0.0, 100000.0)
        self.search_tolerance_spin.setDecimals(3)
        self.search_tolerance_spin.setValue(0.0)
        self.search_tolerance_spin.setMaximumWidth(90)
        self.search_tolerance_spin.setToolTip("Wert-Toleranz: Suchwert 340, Toleranz 5 findet 335..345.")
        self.search_decoded_cb = QCheckBox("dec.")
        self.search_decoded_cb.setToolTip("Aus: Rohwert/signed. An: decodierter Wert nach Typ/Skalierung.")
        self.value_search_live_cb = QCheckBox("Live")
        self.value_search_live_cb.setChecked(True)
        self.value_search_count_label = QLabel("0 Treffer")
        self.search_value_btn = QPushButton("Suchen")
        self.clear_search_btn = QPushButton("X")
        self.clear_search_btn.setMaximumWidth(34)
        search_layout.addWidget(QLabel("Wert:"), 0, 0)
        search_layout.addWidget(self.search_value_edit, 0, 1, 1, 3)
        search_layout.addWidget(QLabel("±"), 1, 0)
        search_layout.addWidget(self.search_tolerance_spin, 1, 1)
        search_layout.addWidget(self.search_decoded_cb, 1, 2)
        search_layout.addWidget(self.value_search_live_cb, 1, 3)
        search_layout.addWidget(self.search_value_btn, 2, 0, 1, 2)
        search_layout.addWidget(self.clear_search_btn, 2, 2)
        search_layout.addWidget(self.value_search_count_label, 2, 3)

        name_search_box = QGroupBox("Namenssuche")
        side_layout.addWidget(name_search_box)
        name_search_layout = QGridLayout(name_search_box)
        name_search_layout.setContentsMargins(8, 8, 8, 8)
        name_search_layout.setHorizontalSpacing(6)
        name_search_layout.setVerticalSpacing(4)
        self.name_search_edit = QLineEdit()
        self.name_search_edit.setPlaceholderText("Timer|SG|Schalter")
        self.name_search_regex_cb = QCheckBox("Regex")
        self.name_search_btn = QPushButton("Suchen")
        self.clear_name_search_btn = QPushButton("X")
        self.clear_name_search_btn.setMaximumWidth(34)
        self.name_search_count_label = QLabel("0 Treffer")
        name_search_layout.addWidget(QLabel("Name:"), 0, 0)
        name_search_layout.addWidget(self.name_search_edit, 0, 1, 1, 3)
        name_search_layout.addWidget(self.name_search_regex_cb, 1, 0)
        name_search_layout.addWidget(self.name_search_btn, 1, 1)
        name_search_layout.addWidget(self.clear_name_search_btn, 1, 2)
        name_search_layout.addWidget(self.name_search_count_label, 1, 3)

        special_box = QGroupBox("Funktionen")
        side_layout.addWidget(special_box)
        special_layout = QGridLayout(special_box)
        special_layout.setContentsMargins(8, 8, 8, 8)
        self.contact_value_label = QLabel("2034: --")
        self.contact_popup_btn = QPushButton("Kontaktdecoder ...")
        self.load_output_popup_btn = QPushButton("Lastausgangdecoder ...")
        self.fault_popup_btn = QPushButton("Störungen / Fehler ...")
        self.sg_popup_btn = QPushButton("SG Ready Editor ...")
        self.timer_editor_btn = QPushButton("Betriebsart Timer 1-6 ...")
        self.onoff_timer_btn = QPushButton("WP Ein/Aus Timer ...")
        self.param_settings_btn = QPushButton("Parameter Einstellungen ...")
        self.offline_browser_btn = QPushButton("Offline Register-Browser ...")
        self.bus_popup_btn = QPushButton("Gesehene Bus-Adressen ...")
        self.dual_logger_btn = QPushButton("Dual-Bus Logger (Diagnose) ...")
        self.dual_logger_btn.setToolTip("Nur bei Modbus Display/HMI sichtbar, wenn in Programm-Einstellungen aktiviert.")
        self.backup_restore_btn = QPushButton("Backup / Restore ...")
        self.wp_control_btn = QPushButton("WP-Steuerung ...")
        self.at_comp_btn = QPushButton("AT-Kompensation ...")
        self.contact_value_label.setVisible(False)
        special_layout.addWidget(self.wp_control_btn, 0, 0, 1, 2)
        special_layout.addWidget(self.at_comp_btn, 1, 0, 1, 2)
        special_layout.addWidget(self.param_settings_btn, 2, 0, 1, 2)
        special_layout.addWidget(self.onoff_timer_btn, 3, 0, 1, 2)
        special_layout.addWidget(self.timer_editor_btn, 4, 0, 1, 2)
        special_layout.addWidget(self.sg_popup_btn, 5, 0, 1, 2)
        special_layout.addWidget(self.contact_popup_btn, 6, 0, 1, 2)
        special_layout.addWidget(self.load_output_popup_btn, 7, 0, 1, 2)
        special_layout.addWidget(self.fault_popup_btn, 8, 0, 1, 2)
        special_layout.addWidget(self.backup_restore_btn, 9, 0, 1, 2)
        special_layout.addWidget(self.offline_browser_btn, 10, 0, 1, 2)
        special_layout.addWidget(self.bus_popup_btn, 11, 0, 1, 2)
        special_layout.addWidget(self.dual_logger_btn, 12, 0, 1, 2)
        self._update_contact_table(None)
        self._update_fault_button_style()

        # Tabelle fuer Bus-Adressen bleibt intern bestehen, wird aber nicht mehr
        # in der Seitenleiste angezeigt. Sichtbar ist sie ueber das Popup.
        self.bus_table = QTableWidget(0, 6)
        self.bus_table.setHorizontalHeaderLabels([
            "Bus", "Frames", "CRC OK", "CRC BAD", "Letzter Frame", "Vermutung"
        ])
        self.bus_table.verticalHeader().setVisible(False)
        self.bus_table.setSortingEnabled(False)

        cache_box = QGroupBox("Werte-Cache")
        side_layout.addWidget(cache_box)
        cache_outer_layout = QVBoxLayout(cache_box)
        cache_outer_layout.setContentsMargins(8, 8, 8, 8)
        cache_top = QHBoxLayout()
        self.cache_toggle_btn = QPushButton("Einstellungen ...")
        self.cache_load_btn = QPushButton("Cache laden")
        self.cache_save_btn = QPushButton("Cache speichern")
        cache_top.addWidget(self.cache_toggle_btn)
        cache_top.addWidget(self.cache_load_btn)
        cache_top.addWidget(self.cache_save_btn)
        cache_top.addStretch(1)
        cache_outer_layout.addLayout(cache_top)

        self.cache_options_widget = QWidget()
        cache_layout = QFormLayout(self.cache_options_widget)
        cache_layout.setContentsMargins(0, 4, 0, 0)
        self.cache_load_start_cb = QCheckBox("beim Start laden")
        self.cache_save_exit_cb = QCheckBox("beim Beenden speichern")
        self.cache_save_cyclic_cb = QCheckBox("zyklisch speichern")
        self.cache_interval_spin = QSpinBox()
        self.cache_interval_spin.setRange(5, 3600)
        self.cache_interval_spin.setValue(int(self.settings.get("cache_interval_s", 60)))
        self.cache_interval_spin.setSuffix(" s")
        self.cache_load_start_cb.setChecked(bool(self.settings.get("cache_load_on_start", False)))
        self.cache_save_exit_cb.setChecked(bool(self.settings.get("cache_save_on_exit", True)))
        self.cache_save_cyclic_cb.setChecked(bool(self.settings.get("cache_save_cyclic", False)))
        cache_layout.addRow(self.cache_load_start_cb)
        cache_layout.addRow(self.cache_save_exit_cb)
        cache_layout.addRow(self.cache_save_cyclic_cb)
        cache_layout.addRow("Intervall:", self.cache_interval_spin)
        self.cache_options_widget.setVisible(False)
        cache_outer_layout.addWidget(self.cache_options_widget)

        stats_box = QGroupBox("Status")
        side_layout.addWidget(stats_box)
        stats_layout = QGridLayout(stats_box)
        self.status_label = QLabel("getrennt")
        self.frame_count_label = QLabel("0")
        self.reg_count_label = QLabel("0")
        self.last_crc_label = QLabel("--")
        self.last_bus_label = QLabel("--")
        self.direction_label = QLabel("--")
        self.foreign_count_label = QLabel("0")
        self.raw_file_label = QLabel("--")
        stats_layout.addWidget(QLabel("Verbindung:"), 0, 0)
        stats_layout.addWidget(self.status_label, 0, 1)
        stats_layout.addWidget(QLabel("Frames:"), 1, 0)
        stats_layout.addWidget(self.frame_count_label, 1, 1)
        stats_layout.addWidget(QLabel("Register:"), 2, 0)
        stats_layout.addWidget(self.reg_count_label, 2, 1)
        stats_layout.addWidget(QLabel("Letzte CRC:"), 3, 0)
        stats_layout.addWidget(self.last_crc_label, 3, 1)
        stats_layout.addWidget(QLabel("Letzte Bus-Adresse:"), 4, 0)
        stats_layout.addWidget(self.last_bus_label, 4, 1)
        stats_layout.addWidget(QLabel("Richtung/Vermutung:"), 5, 0)
        stats_layout.addWidget(self.direction_label, 5, 1)
        stats_layout.addWidget(QLabel("Fremdframes:"), 6, 0)
        stats_layout.addWidget(self.foreign_count_label, 6, 1)
        stats_layout.addWidget(QLabel("Raw-Datei:"), 7, 0)
        stats_layout.addWidget(self.raw_file_label, 7, 1)
        side_layout.addStretch(1)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("log_view")
        self.log_text.setReadOnly(True)
        if hasattr(self.log_text.document(), "setMaximumBlockCount"):
            self.log_text.document().setMaximumBlockCount(int(self.settings.get("max_log_lines", 3000)))
        splitter.addWidget(self.log_text)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([620, 240])
        self.log_text.setMinimumHeight(170)

        self.comm_settings_btn.clicked.connect(self.open_communication_settings)
        self.about_btn.clicked.connect(self.open_about_dialog)
        self.cloud_btn.clicked.connect(self.open_warmlink_cloud_dialog)
        self.connect_btn.clicked.connect(self.connect_to_device)
        self.disconnect_btn.clicked.connect(self.disconnect_from_device)
        self.write_dry_btn.clicked.connect(self.show_write_frame)
        self.write_send_btn.clicked.connect(self.send_write_frame)
        self.read_btn.clicked.connect(self.send_read_from_fields)
        self.manual_register_btn.clicked.connect(self.open_manual_register_dialog)
        self.display_fake_reboot_btn.clicked.connect(self.send_display_fake_reboot)
        self.display_sim_user_change_btn.clicked.connect(self.send_display_simulated_user_value_from_fields)
        self.display_sim_heat_btn.clicked.connect(lambda: self.send_display_simulated_mode(1))
        self.display_sim_cool_btn.clicked.connect(lambda: self.send_display_simulated_mode(2))
        self.display_sim_ww_btn.clicked.connect(lambda: self.send_display_simulated_mode(0))
        self.timer_editor_btn.clicked.connect(self.open_timer_editor)
        self.onoff_timer_btn.clicked.connect(self.open_onoff_timer_editor)
        self.init_read_btn.clicked.connect(self.send_init_reads)
        self.search_value_btn.clicked.connect(self.search_value_now)
        self.clear_search_btn.clicked.connect(self.clear_value_search)
        self.search_value_edit.returnPressed.connect(self.search_value_now)
        self.search_decoded_cb.stateChanged.connect(lambda _=None: self.search_value_now())
        self.search_tolerance_spin.valueChanged.connect(lambda _=None: self.search_value_now())
        self.name_search_btn.clicked.connect(self.search_name_now)
        self.clear_name_search_btn.clicked.connect(self.clear_name_search)
        self.name_search_edit.returnPressed.connect(self.search_name_now)
        self.known_only_cb.stateChanged.connect(lambda _=None: self.rebuild_table_filter())
        self.log_level_combo.currentIndexChanged.connect(lambda _=None: self._on_log_level_changed())
        self.raw_file_cb.stateChanged.connect(lambda _=None: self.on_raw_file_checkbox_changed())
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.clear_main_btn.clicked.connect(self.clear_main_window_values)
        self.contact_popup_btn.clicked.connect(self.open_contact_decoder)
        self.load_output_popup_btn.clicked.connect(self.open_load_output_decoder)
        self.fault_popup_btn.clicked.connect(self.open_fault_decoder)
        self.sg_popup_btn.clicked.connect(self.open_sg_editor)
        self.wp_control_btn.clicked.connect(self.open_wp_control)
        self.at_comp_btn.clicked.connect(self.open_at_compensation)
        self.param_settings_btn.clicked.connect(self.open_parameter_settings)
        self.offline_browser_btn.clicked.connect(self.open_offline_browser)
        self.bus_popup_btn.clicked.connect(self.open_bus_addresses)
        self.dual_logger_btn.clicked.connect(self.open_dual_logger_dialog)
        self.backup_restore_btn.clicked.connect(self.open_backup_restore)
        self.cache_toggle_btn.clicked.connect(self.toggle_cache_options)
        self.cache_load_btn.clicked.connect(lambda: self.load_value_cache(silent=False))
        self.cache_save_btn.clicked.connect(lambda: self.save_value_cache(silent=False))
        self.cache_save_cyclic_cb.stateChanged.connect(lambda _=None: self._apply_cache_timer_state())
        self.cache_interval_spin.valueChanged.connect(lambda _=None: self._apply_cache_timer_state())
        self.register_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.register_table.customContextMenuRequested.connect(self.open_register_context_menu)

        self.frame_count = 0
        self._backend_changed()
        self._update_dual_logger_button_visibility()
        QTimer.singleShot(0, self._refresh_search_highlights)

    def _load_settings(self) -> dict:
        for path in (self.settings_path, getattr(self, "old_settings_path", "")):
            if path and os.path.exists(path):
                data = load_settings(path)
                if isinstance(data, dict):
                    return ensure_defaults(data)
        return ensure_defaults({})

    def _settings_data_snapshot(self) -> dict:
        """Erzeugt die persistente Settings-Struktur.

        Wichtig: backend_settings wird direkt aus self.settings genommen. Dadurch
        werden Werte aus den Programm-Einstellungen nicht versehentlich wieder
        durch alte Hauptfenster-Felder überschrieben.
        """
        return {
            "backend": self.current_backend_key(),
            "backend_settings": self.settings.get("backend_settings", {}),
            "device_model": self.current_device_model(),
            "autoconnect_on_start": self.autoconnect_cb.isChecked(),
            "cache_load_on_start": self.cache_load_start_cb.isChecked(),
            "cache_save_on_exit": self.cache_save_exit_cb.isChecked(),
            "cache_save_cyclic": self.cache_save_cyclic_cb.isChecked(),
            "cache_interval_s": int(self.cache_interval_spin.value()),
            "show_public_warning": bool(self.settings.get("show_public_warning", True)),
            "theme": str(self.settings.get("theme", "system")),
            "update_asset_mode": str(self.settings.get("update_asset_mode", "auto")),
            "auto_read_init_on_startup": bool(self.settings.get("auto_read_init_on_startup", False)),
            "auto_poll_live_values": bool(self.settings.get("auto_poll_live_values", False)),
            "live_poll_interval_s": int(self.settings.get("live_poll_interval_s", 30)),
            "tab_auto_poll": bool(self.settings.get("tab_auto_poll", False)),
            "tab_poll_interval_s": int(self.settings.get("tab_poll_interval_s", 30)),
            "display_write_mode": str(self.settings.get("display_write_mode", "fc16")),
            "manual_register_dialog": self.settings.get("manual_register_dialog", {}),
            "show_dual_logger_button_display": bool(self.settings.get("show_dual_logger_button_display", False)),
            "log_level": int(self.settings.get("log_level", 2)),
            "main_window": self.settings.get("main_window", {}),
            "warmlink_cloud": self.settings.get("warmlink_cloud", {}),
            "warmlink_raw_capture": self.settings.get("warmlink_raw_capture", {}),
        }

    def _write_settings_file(self):
        data = save_settings(self.settings_path, self._settings_data_snapshot())
        self.settings.update(data)

    def _restore_main_window_size(self):
        cfg = self.settings.get("main_window", {})
        if not isinstance(cfg, dict):
            cfg = {}
        try:
            width = max(900, int(cfg.get("width", 1400) or 1400))
        except Exception:
            width = 1400
        try:
            height = max(600, int(cfg.get("height", 900) or 900))
        except Exception:
            height = 900
        self.settings["main_window"] = {
            "width": width,
            "height": height,
            "maximized": bool(cfg.get("maximized", False)),
        }
        if self.settings["main_window"]["maximized"]:
            QTimer.singleShot(0, self.showMaximized)
        else:
            self.resize(width, height)

    def _update_main_window_settings(self):
        maximized = bool(self.isMaximized())
        size_source = self.normalGeometry().size() if maximized and self.normalGeometry().isValid() else self.size()
        self.settings["main_window"] = {
            "width": max(900, int(size_source.width())),
            "height": max(600, int(size_source.height())),
            "maximized": maximized,
        }

    def current_device_model(self) -> str:
        dev = str(self.settings.get("device_model", DEFAULT_DEVICE_MODEL))
        # alte Testbezeichnung korrigieren: eine BlueLine GL8 gibt es nicht, nur BL8.
        if dev == "foxair_blue_gl8_1":
            dev = "foxair_blue_bl8_1"
            self.settings["device_model"] = dev
        if dev not in DEVICE_MODEL_LABELS:
            dev = DEFAULT_DEVICE_MODEL
        return dev

    def set_current_device_model(self, device_model: str):
        dev = str(device_model or DEFAULT_DEVICE_MODEL)
        if dev == "foxair_blue_gl8_1":
            dev = "foxair_blue_bl8_1"
        if dev not in DEVICE_MODEL_LABELS:
            dev = DEFAULT_DEVICE_MODEL
        self.settings["device_model"] = dev
        self._save_settings(sync_main_fields=False)
        label = DEVICE_MODEL_LABELS.get(dev, dev)
        self._log(f"Geräteauswahl für Defaultwerte: {label} ({DEVICE_MODEL_HINT})")
        if self.parameter_dialog is not None and self.parameter_dialog.isVisible():
            self.parameter_dialog.refresh_table()
        if self.offline_dialog is not None and self.offline_dialog.isVisible():
            self.offline_dialog.items = self.offline_dialog._collect_items()
            self.offline_dialog.refresh()

    def _save_settings(self, sync_main_fields: bool = True):
        try:
            if sync_main_fields:
                cfg = self._backend_settings(self.current_backend_key())
                self._set_backend_settings(
                    backend=self.current_backend_key(),
                    transport=str(cfg.get("transport", "tcp")),
                    host=self.host_edit.text().strip(),
                    port=int(self.port_edit.value()),
                    unit_id=int(self.unit_spin.value()),
                    display_translate=False,
                    serial_port=str(cfg.get("serial_port", "COM3")),
                    baudrate=int(cfg.get("baudrate", 9600)),
                    parity=str(cfg.get("parity", "N")),
                    bytesize=int(cfg.get("bytesize", 8)),
                    stopbits=float(cfg.get("stopbits", 1.0)),
                )
            self._write_settings_file()
        except PermissionError as exc:
            self._log(f"SETTINGS speichern fehlgeschlagen: {exc}")
            self._log(f"Hinweis: Einstellungsdatei liegt bei {self.settings_path}. Bitte Schreibrechte für diesen Ordner prüfen.")
        except Exception as exc:
            self._log(f"SETTINGS speichern fehlgeschlagen: {exc}")

    def _backend_settings(self, backend: str) -> dict:
        backend = backend if backend in BACKEND_LABELS else ("standard_modbus" if APP_EDITION.upper() == "PUBLIC" else "warmlink_raw")
        defaults = dict(BACKEND_DEFAULTS.get(backend, BACKEND_DEFAULTS["standard_modbus" if APP_EDITION.upper() == "PUBLIC" else "warmlink_raw"]))
        all_settings = self.settings.setdefault("backend_settings", {})
        saved = all_settings.get(backend, {})
        if not isinstance(saved, dict):
            saved = {}
        # Migration alter v0.2.0 Settings, nur wenn noch keine Backend-Settings existieren.
        if not saved and any(k in self.settings for k in ("host", "port", "unit_id", "display_translate_0x2000")):
            saved = {
                "transport": self.settings.get("transport", defaults.get("transport", "tcp")),
                "host": self.settings.get("host", defaults.get("host")),
                "port": self.settings.get("port", defaults.get("port")),
                "serial_port": self.settings.get("serial_port", defaults.get("serial_port", "COM3")),
                "baudrate": self.settings.get("baudrate", defaults.get("baudrate", 9600)),
                "parity": self.settings.get("parity", defaults.get("parity", "N")),
                "bytesize": self.settings.get("bytesize", defaults.get("bytesize", 8)),
                "stopbits": self.settings.get("stopbits", defaults.get("stopbits", 1.0)),
                "unit_id": self.settings.get("unit_id", defaults.get("unit_id")),
                "display_translate_0x2000": self.settings.get("display_translate_0x2000", defaults.get("display_translate_0x2000")),
            }
        defaults.update(saved)
        if backend == "display_modbus":
            defaults["display_translate_0x2000"] = False
        return defaults

    def _set_backend_settings(self, backend: str, transport: str, host: str, port: int, unit_id: int, display_translate: bool,
                              serial_port: str = "COM3", baudrate: int = 9600, parity: str = "N", bytesize: int = 8, stopbits: float = 1.0):
        backend = backend if backend in BACKEND_LABELS else "warmlink_raw"
        transport = transport if transport in ("tcp", "serial") else "tcp"
        self.settings.setdefault("backend_settings", {})[backend] = {
            "transport": transport,
            "host": str(host).strip(),
            "port": int(port),
            "serial_port": str(serial_port).strip() or "COM3",
            "baudrate": int(baudrate),
            "parity": str(parity or "N").upper()[0],
            "bytesize": int(bytesize),
            "stopbits": float(stopbits),
            "unit_id": int(unit_id),
            "display_translate_0x2000": False,
        }

    def apply_communication_settings(self, backend: str):
        backend = backend if backend in BACKEND_LABELS else ("standard_modbus" if APP_EDITION.upper() == "PUBLIC" else "warmlink_raw")
        idx = self.backend_combo.findData(backend)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        cfg = self._backend_settings(backend)
        self.host_edit.setText(str(cfg.get("host", DEFAULT_HOST)))
        self.port_edit.setValue(int(cfg.get("port", DEFAULT_PORT)))
        self.unit_spin.setValue(int(cfg.get("unit_id", DEFAULT_BUS_ADDR)))
        self.display_translate_cb.setChecked(False)
        if hasattr(self, "write_bus_edit"):
            self.write_bus_edit.setText(f"0x{int(self.unit_spin.value()):02X}")
        self._update_comm_summary()
        self._save_settings(sync_main_fields=False)
        self._log(f"Kommunikation eingestellt: {self._communication_summary_text()}")

    def open_communication_settings(self):
        dlg = CommunicationSettingsDialog(self)
        dlg.exec()

    def _communication_summary_text(self) -> str:
        backend = self.current_backend_key()
        cfg = self._backend_settings(backend)
        parts = [self.current_backend_label()]
        if str(cfg.get("transport", "tcp")) == "serial":
            parts.append(f"{cfg.get('serial_port', 'COM3')} {int(cfg.get('baudrate', 9600))},{int(cfg.get('bytesize', 8))}{str(cfg.get('parity', 'N')).upper()[0]}{float(cfg.get('stopbits', 1.0)):g}")
        else:
            parts.append(f"{self.host_edit.text().strip()}:{int(self.port_edit.value())}")
        if backend in ("display_modbus", "standard_modbus"):
            parts.append(f"Unit {int(self.unit_spin.value())}")
        return " | ".join(parts)

    def _update_comm_summary(self):
        if not hasattr(self, "comm_summary_label"):
            return
        self.comm_summary_label.setText(self._communication_summary_text())

    def _apply_cache_timer_state(self):
        if not hasattr(self, "cache_timer"):
            return
        if self.cache_save_cyclic_cb.isChecked():
            self.cache_timer.start(int(self.cache_interval_spin.value()) * 1000)
            self._log(f"Werte-Cache zyklisch aktiv: alle {int(self.cache_interval_spin.value())} s")
        else:
            self.cache_timer.stop()

    def _apply_live_poll_timer_state(self):
        if not hasattr(self, "live_poll_timer"):
            return
        if bool(self.settings.get("auto_poll_live_values", False)) and self.connected:
            interval_s = max(5, int(self.settings.get("live_poll_interval_s", 30)))
            self.live_poll_timer.start(interval_s * 1000)
            self._log(f"Livewerte-Auto-Poll aktiv: alle {interval_s} s (Registerblöcke 2001/2091)")
        else:
            self.live_poll_timer.stop()

    def _live_poll_tick(self):
        if not self.connected or not self.worker:
            if hasattr(self, "live_poll_timer"):
                self.live_poll_timer.stop()
            return
        try:
            slave_addr = self._parse_int_text(self.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        blocks = [(2001, 90, "Livewerte 2001/0x07D1"), (2091, 90, "Livewerte 2091/0x082B")]
        addr, qty, label = blocks[int(getattr(self, "live_poll_step", 0)) % len(blocks)]
        self.live_poll_step = int(getattr(self, "live_poll_step", 0)) + 1
        self.send_read_request(addr, qty, slave_addr=slave_addr, label=f"Auto-Poll {label}")

    def _snapshot_for_register(self, reg_no: int) -> dict:
        reg = self.latest_regs[reg_no]
        return {
            "reg": int(reg.reg),
            "raw_value": int(reg.raw_value),
            "slave_addr": int(getattr(reg, "slave_addr", DEFAULT_BUS_ADDR)),
            "frame_type": int(getattr(reg, "frame_type", reg.reg)),
            "name": str(getattr(reg, "name", "")),
            "dtype": str(getattr(reg, "dtype", "RAW")),
            "timestamp": float(getattr(reg, "timestamp", time.time())),
        }

    def save_value_cache(self, silent: bool = False):
        try:
            data = {
                "saved_at": time.time(),
                "host": self.host_edit.text().strip(),
                "port": int(self.port_edit.value()),
                "registers": [self._snapshot_for_register(reg_no) for reg_no in sorted(self.latest_regs)],
            }
            os.makedirs(os.path.dirname(self.cache_file_path), exist_ok=True)
            with open(self.cache_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if not silent:
                self._log(f"Werte-Cache gespeichert: {self.cache_file_path} ({len(data['registers'])} Register)")
        except Exception as exc:
            self._log(f"Werte-Cache speichern fehlgeschlagen: {exc}")

    def _display_parts_for_register(self, reg_no: int, fallback_name: str = "") -> tuple[str, str, str]:
        data = getattr(self, "register_defs", {}).get(str(int(reg_no)), {})
        if isinstance(data, dict):
            block, code, clean = register_meta_parts(data)
            if code or block or clean:
                return block, code, clean
        return register_block_and_clean_name(fallback_name)

    def _code_for_register(self, reg_no: int) -> str:
        block, code, _clean = self._display_parts_for_register(int(reg_no), "")
        return code or block

    def _name_for_register(self, reg_no: int, fallback_name: str = "") -> str:
        _block, _code, clean = self._display_parts_for_register(int(reg_no), fallback_name)
        return clean or fallback_name

    def _unit_for_register(self, reg_no: int) -> str:
        data = getattr(self, "register_defs", {}).get(str(int(reg_no)), {})
        if isinstance(data, dict):
            return str(data.get("unit", "") or "").strip()
        return ""


    def _display_value_for_main_table(self, reg: DecodedRegister) -> str:
        info = self.regmap.get(int(reg.reg))
        unit = self._unit_for_register(int(reg.reg))
        dtype = info.dtype if info else getattr(reg, "dtype", "RAW")
        value_map = info.value_map if info else None
        bit_map = info.bit_map if info else None
        return format_value_by_type(
            int(reg.raw_value),
            dtype,
            value_map,
            bit_map,
            unit=unit or None,
        )

    def _display_value_with_register_unit(self, reg_no: int, display_value: str) -> str:
        unit = self._unit_for_register(int(reg_no))
        text = str(display_value)
        if not unit:
            return text

        known_units = (
            "m³/h",
            "kW/h",
            "days",
            "kWh",
            "rpm",
            "bar",
            "°C",
            "kW",
            "COP",
            "K",
            "%",
            "A",
            "V",
            "W",
            "Hz",
            "min",
            "s",
            "h",
            "N",
        )
        suffix_match = re.search(
            rf"(^|\s)({'|'.join(re.escape(suffix) for suffix in known_units)})$",
            text,
        )
        if suffix_match:
            display_unit = suffix_match.group(2)
            if display_unit != unit:
                self._log(
                    f"Einheit nicht angehängt, display_value enthält bereits Einheit: "
                    f"reg={int(reg_no)}, display_value={text!r}, register_unit={unit!r}",
                    level=7,
                )
            return text
        return f"{text} {unit}".strip()

    def _cached_register_from_snapshot(self, item: dict) -> Optional[DecodedRegister]:
        try:
            reg_no = int(item["reg"])
            raw_value = int(item["raw_value"]) & 0xFFFF
            info = self.regmap.get(reg_no)
            dtype = info.dtype if info.dtype != "RAW" or not item.get("dtype") else str(item.get("dtype", "RAW"))
            name = info.name or str(item.get("name", ""))
            return DecodedRegister(
                slave_addr=int(item.get("slave_addr", DEFAULT_BUS_ADDR)),
                reg=reg_no,
                index=0,
                frame_type=int(item.get("frame_type", reg_no)),
                raw_value=raw_value,
                signed_value=s16(raw_value),
                display_value=self._format_cached_value(raw_value, dtype),
                name=name,
                dtype=dtype,
                timestamp=float(item.get("timestamp", time.time())),
            )
        except Exception:
            return None

    def _format_cached_value(self, raw_value: int, dtype: str) -> str:
        # Gleiche Darstellung wie der Parser; lokal gehalten, damit Cache-Laden ohne Live-Frame funktioniert.
        signed = s16(raw_value)
        if dtype in ("TEMP", "TEMP1"):
            return f"{signed / 10.0:.1f} °C"
        if dtype in ("TEMP05", "TEMP_0_5", "STEP_0_5C"):
            return f"{signed / 2.0:.1f} °C"
        if dtype in ("BAR_X10", "PRESSURE_BAR_X10"):
            return f"{signed / 10.0:.1f} bar"
        if dtype in ("AMP_X2", "CURRENT_A_X2"):
            return f"{signed / 2.0:.1f} A"
        if dtype in ("AMP_X10", "CURRENT_A_X10"):
            return f"{signed / 10.0:.1f} A"
        if dtype in ("VOLT", "VOLTS", "V"):
            return f"{signed} V"
        if dtype in ("WATT", "WATTS", "POWER_W"):
            return f"{signed} W"
        if dtype in ("RPM", "FAN_RPM"):
            return f"{signed} rpm"
        if dtype in ("KWH_PER_H", "KW_PER_H"):
            return f"{signed} kW/h"
        if dtype in ("KWH", "ENERGY_KWH"):
            return f"{signed} kWh"
        if dtype in ("FLOW_M3H_X100", "FLOW_X100"):
            return f"{signed / 100.0:.1f} m³/h"
        if dtype in ("FLOW_M3H_X10", "FLOW_X10"):
            return f"{signed / 10.0:.1f} m³/h"
        if dtype in ("MINUTES", "MIN"):
            return f"{signed} min"
        if dtype in ("SECONDS", "SEC"):
            return f"{signed} s"
        if dtype in ("HOURS", "HOUR"):
            return f"{signed} h"
        if dtype in ("DAYS", "DAY"):
            return f"{signed} days"
        if dtype in ("HZ", "FREQUENCY_HZ"):
            return f"{signed} Hz"
        if dtype in ("STEPS_N", "EEV_STEPS", "STEPS"):
            return f"{signed} N"
        if dtype in ("PERCENT", "PCT"):
            return f"{signed} %"
        if dtype in ("DIGI5",):
            return f"{signed / 10.0:.1f}"
        if dtype == "DIGI6":
            return f"{signed / 1000.0:.3f}"
        if dtype == "DIGI19":
            return f"{signed / 100.0:.2f}"
        if dtype == "DIGI4":
            return f"{signed / 5.0:.1f}"
        if dtype == "DIGI1":
            return f"{signed}"
        if dtype == "DIGI9":
            return f"{signed} raw / evtl. {signed / 10.0:.1f}"
        return str(signed)

    def load_value_cache(self, silent: bool = False):
        cache_path = self.cache_file_path
        if not os.path.exists(cache_path) and os.path.exists(getattr(self, "old_cache_file_path", "")):
            cache_path = self.old_cache_file_path
        if not os.path.exists(cache_path):
            if not silent:
                self._log(f"Werte-Cache nicht gefunden: {self.cache_file_path}")
            return
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("registers", []) if isinstance(data, dict) else []
            loaded = 0
            for item in items:
                reg = self._cached_register_from_snapshot(item)
                if reg is None:
                    continue
                self.cached_regs.add(reg.reg)
                self.latest_regs[reg.reg] = reg
                self.last_values[reg.reg] = int(reg.raw_value)
                self.previous_value_texts.setdefault(reg.reg, "--")
                if not (self.known_only_cb.isChecked() and not reg.name):
                    self._upsert_register_row(reg, changed=False)
                loaded += 1
            self._recalculate_value_search()
            self._recalculate_name_search()
            self._refresh_search_highlights()
            self.reg_count_label.setText(str(len(self.last_values)))
            if not silent:
                stamp = data.get("saved_at")
                stamp_text = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(stamp)) if stamp else "unbekannt"
                self._log(f"Werte-Cache geladen: {loaded} Register, Stand {stamp_text}. Geladene neutrale Zeilen sind grau; 10xx/30xx behalten ihre Bereichsfarbe.")
        except Exception as exc:
            self._log(f"Werte-Cache laden fehlgeschlagen: {exc}")

    def check_for_updates_on_startup(self):
        self.check_for_updates(silent_no_update=True)

    def check_for_updates(self, silent_no_update: bool = False):
        if self.update_thread is not None:
            if not silent_no_update:
                QMessageBox.information(self, "Update", "Update-Prüfung läuft bereits.")
            return
        self.update_check_silent_no_update = bool(silent_no_update)
        if hasattr(self, "update_check_btn"):
            self.update_check_btn.setEnabled(False)
            self.update_check_btn.setText("prüfe ...")
        self._log(f"Update-Prüfung: {UPDATE_REPO} Releases ...")

        self.update_thread = QThread(self)
        self.update_worker = UpdateCheckWorker(APP_VERSION)
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.result.connect(self._update_check_finished)
        self.update_worker.error.connect(self._update_check_error)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self._update_check_cleanup)
        self.update_thread.start()

    def _detect_installation_kind(self) -> str:
        """Best effort: setup/portable erkennen. Manuell über Einstellungen übersteuerbar."""
        if getattr(sys, "frozen", False):
            exe_dir = os.path.abspath(os.path.dirname(sys.executable)).lower()
            program_files = [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("LOCALAPPDATA", "")]
            for root in program_files:
                root = os.path.abspath(root).lower() if root else ""
                if root and exe_dir.startswith(root.lower()):
                    return "setup"
        return "portable"

    def _select_update_asset(self, assets: list) -> Optional[dict]:
        valid = []
        for a in assets or []:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name", "")).lower()
            dl = str(a.get("browser_download_url") or a.get("url") or "").strip()
            if not dl or "source" in name or name.endswith(".txt"):
                continue
            valid.append(a)
        mode = str(self.settings.get("update_asset_mode", "auto")).lower()
        if mode == "auto":
            mode = self._detect_installation_kind()
        def has(asset: dict, word: str) -> bool:
            return word in str(asset.get("name", "")).lower()
        if mode == "setup":
            preferred = next((a for a in valid if has(a, "setup") or has(a, "installer")), None)
            if preferred:
                return preferred
        if mode == "portable":
            preferred = next((a for a in valid if has(a, "portable")), None)
            if preferred:
                return preferred
        return next((a for a in valid if not has(a, "source")), None)

    @Slot(dict)
    def _update_check_finished(self, info: dict):
        tag = str(info.get("tag") or "").strip()
        url = str(info.get("html_url") or UPDATE_RELEASES_URL).strip()
        assets = info.get("assets") if isinstance(info.get("assets"), list) else []
        current = parse_version_tuple(APP_VERSION)
        latest = parse_version_tuple(tag)

        primary_asset = self._select_update_asset(assets)
        primary_url = str((primary_asset or {}).get("browser_download_url") or (primary_asset or {}).get("url") or url)

        if latest > current:
            asset_lines = []
            for a in assets[:6]:
                asset_lines.append(f"- {a.get('name')}")
            asset_text = "\n".join(asset_lines) if asset_lines else "Keine Assets gefunden. Release-Seite öffnen."
            box = QMessageBox(self)
            box.setWindowTitle("Update verfügbar")
            box.setIcon(QMessageBox.Information)
            box.setText(f"Neue Version verfügbar: {tag}\nAktuell installiert: V{APP_VERSION}")
            box.setInformativeText(f"Download/Release:\n{asset_text}")
            open_btn = box.addButton("Download öffnen", QMessageBox.AcceptRole)
            box.addButton("Später", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == open_btn:
                open_update_url(primary_url)
            self._log(f"Update verfügbar: {tag} ({url})")
        else:
            if not getattr(self, "update_check_silent_no_update", False):
                QMessageBox.information(self, "Update", f"Keine neuere Version gefunden.\nAktuell: V{APP_VERSION}\nGitHub: {tag or 'unbekannt'}")
            self._log(f"Update-Prüfung: keine neuere Version gefunden ({tag or 'unbekannt'}).")

    @Slot(str)
    def _update_check_error(self, message: str):
        if not getattr(self, "update_check_silent_no_update", False):
            QMessageBox.warning(self, "Update-Prüfung fehlgeschlagen", f"GitHub konnte nicht geprüft werden.\n\n{message}")
        self._log(f"Update-Prüfung fehlgeschlagen: {message}")

    def _update_check_cleanup(self):
        self.update_thread = None
        self.update_worker = None
        self.update_check_silent_no_update = False
        if hasattr(self, "update_check_btn"):
            self.update_check_btn.setEnabled(True)
            self.update_check_btn.setText("Update prüfen ...")

    def current_log_level(self) -> int:
        try:
            if hasattr(self, "log_level_combo"):
                return int(self.log_level_combo.currentData() or 2)
        except Exception:
            pass
        try:
            return int(self.settings.get("log_level", 2))
        except Exception:
            return 2

    def _infer_log_level(self, text: str) -> int:
        """Ordnet bestehende Logtexte in Level 1..7 ein.

        fix7-Ziel: Level 4 soll fuer Chat-Diagnose reichen, aber ohne
        Fremdframe-/RAW-/Nullblock-Spam. Rohbytes, TX und lange Wertebloecke
        wandern nach Level 6; reine Busbeobachtung nach Level 5.
        """
        t = str(text or "")
        u = t.upper()

        # Immer wichtig / ruhig sichtbar.
        if any(k in u for k in ("FEHLER", "ERROR", "WARN", "FEHLGESCHLAGEN", "ABBRUCH", "ABGEBROCHEN", "TIMEOUT")):
            return 1
        if t.startswith("REG ") or t.startswith("DREG "):
            return 1
        if any(k in u for k in ("ERFOLGREICH", "ÜBERNOMMEN", "UEBERNOMMEN", "GEÄNDERT", "GEAENDERT")):
            return 1

        # Explizite Roh-/Trace-Daten zuerst nach oben ziehen, auch wenn darin
        # z. B. FC16, DISPLAY-HMI oder FREMD-FRAME vorkommt.
        if t.startswith("RX ") or "RAW=" in u or "TX=" in u or "ROHDATEN" in u:
            return 6
        if "SENDEWARTESCHLANGE" in u or "WRITE GESENDET" in u or "BLOCKWRITE WIRD GESENDET" in u:
            return 6
        if "PASSIVE WERTE" in u or "READ WERTE:" in u:
            return 6

        # Bedienung, Verbindung, allgemeiner Status.
        if any(k in u for k in ("VERBINDE", "VERBUNDEN", "GETRENNT", "AUTOCONNECT", "CACHE", "BENUTZERDATEN", "REGISTER-MAPPING", "DISPLAY-DIAGNOSE-MAPPING", "LOG GELEERT", "HAUPTFENSTER GELEERT", "UPDATE", "POPUP", "BITTE WARTEN", "KOMMUNIKATION EINGESTELLT", "LOG-LEVEL GESETZT")):
            return 2

        # Schreib-/Timer-Diagnose: wichtig fuer normale Chat-Analyse.
        if any(k in u for k in ("TIMER", "SG READY", "AT-KOMP", "WP EIN/AUS", "SILENT", "PARAMETERWRITE", "WRITE/ACK", "WRITE/ECHO", "0BC3", "ACK", "FC16 WIRD GESENDET", "FC06 WIRD GESENDET", "BEDIENWERT", "USERWERT", "DISPLAY-INIT", "REBOOT FAKE")):
            return 3

        # Level 4: bestaetigende Diagnose ohne volle Rohdaten.
        if any(k in u for k in ("READ/RESPONSE PASST ZU ANFRAGE", "DREG ", "DISPLAY-HMI DIFF", "DISPLAY-HMI SNAPSHOT", "DISPLAY-HMI DISPLAY-PARAMETERPAKET", "BEKANNTES 10XX", "BEKANNTES 11XX", "BEKANNTES 12XX", "BEKANNTES 13XX", "BEKANNTES 14XX", "BEKANNTES 15XX", "KANDIDAT ISTMODUS", "VALIDIERT")):
            return 4

        # Level 5: Bus-/Read-Beobachtung, Fremdteilnehmer, passive Zuordnung.
        if any(k in u for k in ("READ/REQUEST", "READ/RESPONSE", "PASSIVE RESPONSE", "PAKETBLOCK", "FREMD-FRAME", "BUS NEU", "BUS=0X", "VERMUTUNG=", "ROHSTATUS", "DISPLAY-HMI", "WARMLINK/WP PAKETTEST")):
            return 5

        # Level 6: sonstige Queue/TX/lokale Worker-Details.
        if any(k in u for k in (" GESENDET", "SERIAL RX", "QUEUE", "TRACE")):
            return 6

        return 2

    def _should_log_message(self, text: str, level: Optional[int] = None, force: bool = False) -> bool:
        if force:
            return True
        needed = int(level) if level is not None else self._infer_log_level(str(text))
        return int(needed) <= int(self.current_log_level())

    def _log(self, text: str, level: Optional[int] = None, force: bool = False):
        if not self._should_log_message(str(text), level=level, force=force):
            return
        stamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{stamp}] {text}")
        self._trim_gui_log()

    def _trim_gui_log(self):
        max_lines = int(self.settings.get("max_log_lines", 3000)) if hasattr(self, "settings") else 3000
        doc = self.log_text.document()
        if hasattr(doc, "setMaximumBlockCount"):
            if int(doc.maximumBlockCount()) != max_lines:
                doc.setMaximumBlockCount(max_lines)
            return
        overflow = doc.blockCount() - max_lines
        if overflow <= 0:
            return
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.Start)
        for _ in range(min(overflow, 500)):
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _log_throttled(
        self,
        throttle_key: tuple[Any, ...],
        text: str,
        *,
        summary_text: Optional[str] = None,
        level: Optional[int] = None,
        interval_s: float = 1.0,
        reset_s: float = 3.0,
        force: bool = False,
    ):
        """Loggt die erste Zeile sofort und fasst schnelle Wiederholungen zusammen.

        Die Bus-/Frame-Verarbeitung selbst bleibt unveraendert; nur die
        Textausgabe wird gedrosselt. Dadurch gehen keine Werte verloren, aber
        Poll-Stuerme wie 0x02/3001 blockieren die GUI nicht mehr mit Log-Spam.
        """
        text = str(text)
        if not self._should_log_message(text, level=level, force=force):
            return

        now = time.monotonic()
        state = self.log_throttle_state.get(throttle_key)
        if not state or now - float(state.get("last_seen", 0.0)) > reset_s:
            self.log_throttle_state[throttle_key] = {
                "first_seen": now,
                "last_seen": now,
                "last_summary": now,
                "suppressed": 0,
                "summary": summary_text or text,
            }
            self._log(text, level=level, force=True)
            return

        state["last_seen"] = now
        state["suppressed"] = int(state.get("suppressed", 0)) + 1
        if now - float(state.get("last_summary", 0.0)) >= interval_s:
            suppressed = int(state.get("suppressed", 0))
            elapsed = max(0.1, now - float(state.get("first_seen", now)))
            summary = str(state.get("summary") or summary_text or text)
            self._log(f"{summary} - wiederholt {suppressed}x in {elapsed:.1f}s", level=level, force=True)
            state["first_seen"] = now
            state["last_summary"] = now
            state["suppressed"] = 0

    def _on_log_level_changed(self):
        try:
            level = int(self.log_level_combo.currentData() or 2)
        except Exception:
            level = 2
        self.settings["log_level"] = level
        try:
            self._save_settings(sync_main_fields=False)
        except Exception:
            pass
        label = self.log_level_combo.currentText() if hasattr(self, "log_level_combo") else str(level)
        self._log(f"Log-Level gesetzt: {label}", force=True)

    def clear_log(self):
        self.log_text.clear()
        self._log("Log geleert. Raw-Datei/Registerwerte unverändert.")

    def clear_main_window_values(self):
        """Nur die Haupt-Registeransicht leeren, ohne Log/Verbindung/Cache-Datei anzufassen."""
        old_count = len(self.last_values)
        self.register_table.setSortingEnabled(False)
        self.register_table.setUpdatesEnabled(False)
        try:
            self.register_table.setRowCount(0)
            self.table_rows.clear()
            self.latest_regs.clear()
            self.last_values.clear()
            self.previous_value_texts.clear()
            self.cached_regs.clear()
            self.register_change_highlights.clear()
            self.cloud_overlay_by_reg.clear()
            self.last_contact_value = None
            self.last_load_output_value = None
            self._update_contact_table(None)
            self._update_load_output_decoder(None)
            self._update_fault_button_style()
            if self.value_search_target is not None:
                self.value_search_matches = []
                self._refresh_search_highlights()
            if self.name_search_edit.text().strip():
                self.name_search_matches = []
            self.reg_count_label.setText("0")
        finally:
            self.register_table.setUpdatesEnabled(True)
        self._log(f"Hauptfenster geleert: {old_count} Registerwert(e) entfernt. Log, Raw-Datei und Cache-Datei unverändert.")

    def _parse_int_text(self, text: str) -> int:
        text = str(text).strip().replace("_", "")
        if not text:
            raise ValueError("Leere Eingabe")
        # Erlaubt neben Dezimal und 0x... auch DWIN/ASM-Schreibweise wie 0BC3H oder 5112H.
        # Wichtig fuer Display-Diagnose: 5112H ist 0x5112 / dez. 20754, nicht dezimal 5112.
        sign = 1
        if text[0] in "+-":
            if text[0] == "-":
                sign = -1
            text = text[1:].strip()
        lower = text.lower()
        if lower.endswith("h"):
            return sign * int(text[:-1], 16)
        if lower.startswith("0x"):
            return sign * int(text, 16)
        if any(c in "abcdefABCDEF" for c in text):
            return sign * int(text, 16)
        return sign * int(text, 10)

    def _write_scale_for_dtype(self, dtype: str) -> Decimal | None:
        dtype = (dtype or "RAW").upper()
        if dtype in ("TEMP", "TEMP1", "DIGI5", "POWER_KW_X10", "KW_X10", "BAR_X10", "PRESSURE_BAR_X10", "FLOW_M3H_X10", "FLOW_X10", "AMP_X10", "CURRENT_A_X10"):
            return Decimal("10")
        if dtype in ("TEMP05", "TEMP_0_5", "STEP_0_5C", "AMP_X2", "CURRENT_A_X2"):
            return Decimal("2")
        if dtype in ("FLOW_M3H_X100", "FLOW_X100", "COP_X100", "COP100", "DIGI19"):
            return Decimal("100")
        if dtype == "DIGI6":
            return Decimal("1000")
        if dtype == "DIGI4":
            return Decimal("5")
        return None

    def _write_scale_hint(self, reg_no: int) -> str:
        info = self.regmap.get(int(reg_no))
        dtype = info.dtype if info else "RAW"
        scale = self._write_scale_for_dtype(dtype)
        if scale is None:
            return ""
        return f"{dtype}: Benutzerwert, raw×{scale}"

    def _parse_decimal_text(self, text: str) -> Decimal:
        original = str(text).strip()
        normalized = original.replace("_", "").replace(",", ".")
        if not normalized:
            raise ValueError("Leere Eingabe")
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError(f"Ungültiger Zahlenwert: {original}") from exc

    def parse_register_write_value(self, reg_no: int, text: str, *, raw: bool = False) -> int:
        """Parst Schreibwerte aus Register-Kontexten.

        Standard ist der Benutzerwert des bekannten Registertyps (z. B. TEMP1:
        1,5 °C -> raw 15). Explizite Raw-Schreibpfade rufen diese Methode mit
        raw=True auf oder verwenden weiterhin _parse_int_text().
        """
        if raw:
            return self._parse_int_text(text)
        info = self.regmap.get(int(reg_no))
        dtype = info.dtype if info else "RAW"
        scale = self._write_scale_for_dtype(dtype)
        if scale is None:
            try:
                return self._parse_int_text(text)
            except ValueError as exc:
                original = str(text).strip()
                if "," in original or "." in original:
                    raise ValueError(f"Ungültiger Zahlenwert: {original}") from exc
                raise
        dec = self._parse_decimal_text(text)
        raw_dec = (dec * scale).to_integral_value(rounding=ROUND_HALF_UP)
        return int(raw_dec)

    def _display_write_input_for_register(self, reg_no: int, raw_value: int) -> str:
        info = self.regmap.get(int(reg_no))
        dtype = info.dtype if info else "RAW"
        if self._write_scale_for_dtype(dtype) is None:
            return str(int(raw_value) & 0xFFFF)
        value = numeric_value_by_type(int(raw_value) & 0xFFFF, dtype)
        return f"{value:.3f}".rstrip("0").rstrip(".")

    def current_backend_key(self) -> str:
        if hasattr(self, "backend_combo"):
            return str(self.backend_combo.currentData() or "warmlink_raw")
        return "standard_modbus" if APP_EDITION.upper() == "PUBLIC" else "warmlink_raw"

    def current_backend_label(self) -> str:
        if hasattr(self, "backend_combo"):
            return str(self.backend_combo.currentText())
        return "Warmlink RAW TCP"

    def current_unit_id(self) -> int:
        try:
            return int(self.unit_spin.value())
        except Exception:
            return DEFAULT_BUS_ADDR

    def _translate_register_for_backend(self, addr: int) -> tuple[int, str]:
        # Display-Modbus: keine automatische +0x2000-Übersetzung mehr.
        # DWIN/XRAM-Adressen bitte direkt eingeben, z.B. 0x0BC3 oder 0x5112.
        return int(addr), ""

    def _wire_slave_addr(self, requested: Optional[int] = None) -> int:
        backend = self.current_backend_key()
        if backend == "display_modbus":
            # Display/HMI-Bus: Standard ist die Unit aus den Einstellungen (meist 3).
            # Für manuelle Diagnose im Lesen/Schreiben-Feld muss eine abweichende
            # Busadresse aber wirklich verwendet werden. Bisher wurde hier immer
            # die Einstellungs-Unit genommen, dadurch gingen Tests auf 4/5/6
            # trotzdem an 3. Andere Backends bleiben unverändert.
            if requested is not None and int(requested) != DEFAULT_BUS_ADDR:
                return int(requested)
            return self.current_unit_id()
        if backend == "standard_modbus":
            return self.current_unit_id()
        return int(requested if requested is not None else DEFAULT_BUS_ADDR)

    def _display_write_mode(self) -> str:
        # V0.2.41 fix7: Für den Display-Modus ist FC16-Single-Register der
        # normale Schreibmodus. FC06 bleibt nur noch in altem Settingbestand
        # erhalten, wird aber nicht mehr aktiv benutzt. Spezialpfade/Fallbacks
        # haben eigene explizite Logik.
        return "fc16"

    def _write_single_for_backend(self) -> bool:
        backend = self.current_backend_key()
        if backend == "display_modbus":
            return self._display_write_mode() == "fc06"
        return backend == "standard_modbus"

    def _build_write_frame_for_backend(self, addr: int, value: int, slave_addr: int) -> tuple[bytes, int, int, str, str]:
        wire_slave = self._wire_slave_addr(slave_addr)
        wire_addr, note = self._translate_register_for_backend(addr)
        if self._write_single_for_backend():
            return build_write_single_frame(wire_addr, value, slave_addr=wire_slave), wire_addr, wire_slave, note, "FC06"
        return build_write_frame(wire_addr, value, slave_addr=wire_slave), wire_addr, wire_slave, note, "FC16"

    def _build_read_frame_for_backend(self, addr: int, quantity: int, slave_addr: int) -> tuple[bytes, int, int, str]:
        wire_slave = self._wire_slave_addr(slave_addr)
        wire_addr, note = self._translate_register_for_backend(addr)
        return build_read_frame(wire_addr, quantity, slave_addr=wire_slave), wire_addr, wire_slave, note

    def _backend_changed(self):
        # Kompatibilitätsmethode für alte Signalpfade; Werte werden jetzt über das Kommunikations-Popup gesetzt.
        if hasattr(self, "write_bus_edit"):
            self.write_bus_edit.setText(f"0x{int(self.unit_spin.value()):02X}")
        # Fix34: Beim Wechsel von Display auf Warmlink/Standard darf ein alter
        # Display-INIT/DisplayWorker-Zustand den Init-Button nicht dauerhaft sperren.
        if self.current_backend_key() != "display_modbus" and bool(getattr(self, "display_aux_takeover_active", False)):
            try:
                dlg = getattr(self, "dual_logger_dialog", None)
                if dlg is not None:
                    dlg.stop()
            except Exception as exc:
                self._log(f"DisplayWorker Stop bei Backendwechsel fehlgeschlagen: {exc}")
            self.display_aux_takeover_active = False
        self._update_init_read_button_state()
        self._update_comm_summary()
        self._update_dual_logger_button_visibility()
        self._refresh_search_highlights()

    def _update_init_read_button_state(self):
        if not hasattr(self, "init_read_btn"):
            return
        display_active = False
        try:
            dlg = getattr(self, "dual_logger_dialog", None)
            display_active = bool(dlg is not None and getattr(dlg, "display_known_init_active", False))
        except Exception:
            display_active = False
        warmlink_active = bool(getattr(getattr(self, "warmlink_init_controller", None), "active", False))
        standard_active = bool(getattr(getattr(self, "standard_modbus_init_controller", None), "active", False))
        generic_active = bool(getattr(self, "init_read_active", False)) and (display_active or warmlink_active or standard_active)
        if display_active:
            self.init_read_btn.setEnabled(False)
            self.init_read_btn.setText("Display-Init läuft ...")
        elif warmlink_active or standard_active or generic_active:
            self.init_read_btn.setEnabled(False)
            self.init_read_btn.setText("Init läuft ...")
        else:
            self.init_read_btn.setEnabled(True)
            self.init_read_btn.setText("Alle bekannten Register lesen")

    def connect_to_device(self):
        if self.thread:
            return

        host = self.host_edit.text().strip()
        port = int(self.port_edit.value())
        cfg = self._backend_settings(self.current_backend_key())
        if str(cfg.get("transport", "tcp")) == "tcp" and not host:
            QMessageBox.warning(self, "Kommunikation", "Bitte in Programm-Einstellungen ... zuerst Host/IP eintragen.")
            return

        self.thread = QThread()
        self.worker = ReaderWorker(
            host, port, self.regmap,
            backend_label=self.current_backend_label(),
            write_single=self._write_single_for_backend(),
            transport=str(cfg.get("transport", "tcp")),
            serial_port=str(cfg.get("serial_port", "COM3")),
            baudrate=int(cfg.get("baudrate", 9600)),
            parity=str(cfg.get("parity", "N")),
            bytesize=int(cfg.get("bytesize", 8)),
            stopbits=float(cfg.get("stopbits", 1.0)),
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.connected.connect(self.on_connected)
        self.worker.disconnected.connect(self.on_disconnected)
        self.worker.error.connect(self.on_error)
        self.worker.log.connect(self._log)
        self.worker.frame_decoded.connect(self.on_frame_decoded)
        self.worker.raw_chunk.connect(self.on_raw_chunk)
        self.worker.tx_chunk.connect(self.on_tx_chunk)
        self.worker.disconnected.connect(self.thread.quit)
        self.worker.disconnected.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_thread_refs)

        self.thread.start()

    def disconnect_from_device(self):
        # Wenn Display-INIT den ausgelagerten DisplayWorker benutzt, ist die
        # normale Hauptverbindung eventuell schon per EOF weg. Disconnect soll
        # dann trotzdem den noch laufenden Display-/Warmlink-Hilfsworker stoppen.
        if bool(getattr(self, "display_aux_takeover_active", False)):
            dlg = getattr(self, "dual_logger_dialog", None)
            if dlg is not None:
                try:
                    dlg.stop()
                except Exception as exc:
                    self._log(f"DisplayWorker Stop-Fehler: {exc}")
            self.display_aux_takeover_active = False
            self.connected = False
            self.status_label.setText("getrennt")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.write_send_btn.setEnabled(False)
            if hasattr(self, "live_poll_timer"):
                self.live_poll_timer.stop()
            self._close_raw_file()
            self._log("DisplayWorker/Display-INIT Verbindung gestoppt.")
            return

        if self.worker:
            self.worker.stop()
        self._close_raw_file()

    @Slot()
    def _clear_thread_refs(self):
        self.thread = None
        self.worker = None

    @Slot()
    def on_connected(self):
        self.connected = True
        self.status_label.setText("verbunden")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.write_send_btn.setEnabled(True)
        self._update_init_read_button_state()
        self._start_warmlink_capture_if_enabled()
        if self.raw_file_cb.isChecked():
            self._open_raw_file()
        if bool(self.settings.get("auto_read_init_on_startup", False)):
            QTimer.singleShot(800, self.send_init_reads)
        self._apply_live_poll_timer_state()

    @Slot()
    def on_disconnected(self):
        # Beim Backend "Modbus Display" wird fuer "Alle bekannten Register lesen"
        # absichtlich der robuste DisplayWorker-Pfad benutzt. Dadurch trennt die
        # urspruengliche Hauptverbindung auf Port 2002 (EOF), waehrend der
        # DisplayWorker weiter laeuft und Werte ins Hauptfenster liefert. Das darf
        # die Haupt-UI nicht auf "getrennt" setzen, sonst wirkt die App kaputt
        # und ein zweiter Init-Lauf wird unnoetig blockiert.
        if bool(getattr(self, "display_aux_takeover_active", False)):
            self.connected = True
            self.status_label.setText("DisplayWorker aktiv")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            # Schreiben/Lesen läuft in diesem Zustand über den aktiven DisplayWorker.
            self.write_send_btn.setEnabled(True)
            if hasattr(self, "live_poll_timer"):
                self.live_poll_timer.stop()
            self._close_raw_file()
            self._log("Display-Hauptverbindung wurde vom DisplayWorker abgeloest; UI bleibt verbunden, Disconnect stoppt den DisplayWorker.")
            return

        self.connected = False
        self.status_label.setText("getrennt")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.write_send_btn.setEnabled(False)
        self._update_init_read_button_state()
        if hasattr(self, "live_poll_timer"):
            self.live_poll_timer.stop()
        self._close_raw_file()
        self._stop_warmlink_capture("gestoppt")

    @Slot(str)
    def on_error(self, text: str):
        self._log(f"FEHLER: {text}")

    def _setup_capture_gui_log_timer(self):
        self.capture_gui_log_timer = QTimer(self)
        self.capture_gui_log_timer.setInterval(500)
        self.capture_gui_log_timer.timeout.connect(self._drain_capture_gui_log_queue)
        self.capture_gui_log_timer.start()

    def _capture_thread_log(self, text: str):
        try:
            self.capture_log_queue.put_nowait(str(text))
        except queue.Full:
            pass

    @Slot()
    def _drain_capture_gui_log_queue(self):
        for _ in range(50):
            try:
                text = self.capture_log_queue.get_nowait()
            except queue.Empty:
                break
            self._log(text)

    def _capture_settings(self) -> dict:
        cfg = dict(DEFAULT_CAPTURE_SETTINGS)
        saved = self.settings.get("warmlink_raw_capture", {})
        if isinstance(saved, dict):
            cfg.update(saved)
        return cfg

    def _is_warmlink_backend_key(self, key: str) -> bool:
        return str(key or "") == "warmlink_raw"

    def _start_warmlink_capture_if_enabled(self):
        if not self._is_warmlink_backend_key(self.current_backend_key()):
            self.warmlink_capture = None
            cfg = self._capture_settings()
            if bool(cfg.get("enabled", False)):
                self._log("Warmlink Capture nicht gestartet: Backend ist nicht Modbus Warmlink LTE.")
            return
        cfg = self._capture_settings()
        if not bool(cfg.get("enabled", False)):
            self.warmlink_capture = None
            return
        baseline = None
        try:
            if 2104 in self.latest_regs:
                baseline = int(self.latest_regs[2104].raw_value)
        except Exception:
            baseline = None
        self.warmlink_capture = WarmlinkRawCapture(cfg, getattr(self, "user_data_dir", self.base_dir), self._capture_thread_log)
        self.warmlink_capture.start(baseline=baseline)

    def _stop_warmlink_capture(self, reason: str = "gestoppt"):
        cap = getattr(self, "warmlink_capture", None)
        if cap is not None:
            cap.stop(reason, join=True, timeout=3.0)
            self.warmlink_capture = None
        self._drain_capture_gui_log_queue()

    def _open_raw_file(self):
        if self.raw_file:
            return
        log_dir = os.path.join(getattr(self, "user_data_dir", self.base_dir), "raw_logs")
        os.makedirs(log_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.raw_file_path = os.path.join(log_dir, f"foxair_phnix_raw_{stamp}.bin")
        self.raw_file = open(self.raw_file_path, "ab")
        self.raw_file_label.setText(os.path.basename(self.raw_file_path))
        self._log(f"RAW-Datei geöffnet: {self.raw_file_path}")

    def _close_raw_file(self):
        if self.raw_file:
            try:
                self.raw_file.flush()
                self.raw_file.close()
            finally:
                self._log(f"RAW-Datei geschlossen: {self.raw_file_path}")
                self.raw_file = None
                self.raw_file_path = None
                self.raw_file_label.setText("--")

    @Slot()
    def on_raw_file_checkbox_changed(self):
        if self.raw_file_cb.isChecked() and self.connected:
            self._open_raw_file()
        elif not self.raw_file_cb.isChecked():
            self._close_raw_file()

    @Slot(bytes)
    def on_tx_chunk(self, chunk: bytes):
        cap = getattr(self, "warmlink_capture", None)
        if cap is not None:
            cap.capture_tx(chunk)

    @Slot(bytes)
    def on_raw_chunk(self, chunk: bytes):
        cap = getattr(self, "warmlink_capture", None)
        if cap is not None:
            cap.capture_rx(chunk)
        self.raw_dump.extend(chunk)
        pending_count = len(getattr(self, "pending_read_requests", []) or [])
        if pending_count:
            pending_preview = ", ".join(
                f"0x{int(r.get('slave_addr', 0)):02X}:{int(r.get('addr', 0))}/{int(r.get('quantity', 0))}"
                for r in list(getattr(self, "pending_read_requests", []) or [])[:4]
            )
            more = "" if pending_count <= 4 else f" ... (+{pending_count - 4})"
            self._log(f"DEBUG RX: {len(chunk)} Byte eingegangen, Pending-Read offen: {pending_preview}{more}", level=7, force=True)
        else:
            self._log(f"DEBUG RX: {len(chunk)} Byte eingegangen, kein Pending-Read offen", level=7)
        if self.raw_file_cb.isChecked():
            if not self.raw_file:
                self._open_raw_file()
            if self.raw_file:
                self.raw_file.write(chunk)
                self.raw_file.flush()
        if self.raw_log_cb.isChecked():
            # V0.2.41 fix6: RAW anzeigen liefert immer HEX+ASCII.
            # Die separate RAW-ASCII-Checkbox ist damit überflüssig.
            # Explizit eingeschaltetes RAW wird unabhängig vom Log-Level angezeigt.
            self._log(f"RX {len(chunk)}B: {hex_ascii_line(chunk, -1)}", level=7, force=True)

    def _frame_direction_text(self, frame) -> str:
        if frame.slave_addr == DEFAULT_BUS_ADDR:
            if frame.mode in ("short-write", "write-request", "write-response") or frame.func == 0x03:
                return f"RX FC{frame.func:02X} WP 0x63"
            return f"RX Daten WP 0x63 / FC{frame.func:02X}"
        return f"RX andere Adresse 0x{frame.slave_addr:02X} ({guess_device_name(frame.slave_addr, frame.crc_ok)})"


    def _sorted_row_for_bus(self, addr: int) -> int:
        row = 0
        for existing_addr in sorted(self.bus_rows):
            if existing_addr >= addr:
                break
            row += 1
        return row

    def _insert_sorted_bus_row(self, addr: int) -> int:
        row = self._sorted_row_for_bus(addr)
        self.bus_table.insertRow(row)
        for existing_addr, existing_row in list(self.bus_rows.items()):
            if existing_row >= row:
                self.bus_rows[existing_addr] = existing_row + 1
        self.bus_rows[addr] = row
        return row

    def _update_bus_table(self, frame):
        addr = frame.slave_addr
        is_new = addr not in self.bus_stats
        stats = self.bus_stats.setdefault(addr, {
            "frames": 0,
            "crc_ok": 0,
            "crc_bad": 0,
            "last_frame": "",
            "guess": guess_device_name(addr, frame.crc_ok),
        })
        stats["frames"] += 1
        if frame.crc_ok:
            stats["crc_ok"] += 1
        else:
            stats["crc_bad"] += 1
        stats["last_frame"] = f"FC{frame.func:02X} 0x{frame.typ:04X} / {frame.mode} / {time.strftime('%H:%M:%S')}"
        # Wenn dieselbe Adresse mal mit CRC OK gesehen wird, ist sie eher echt als Resync-Muell.
        stats["guess"] = guess_device_name(addr, frame.crc_ok or stats["crc_ok"] > 0)

        row = self.bus_rows.get(addr)
        if row is None:
            row = self._insert_sorted_bus_row(addr)

        values = [
            f"0x{addr:02X}",
            str(stats["frames"]),
            str(stats["crc_ok"]),
            str(stats["crc_bad"]),
            stats["last_frame"],
            stats["guess"],
        ]
        for col, value in enumerate(values):
            item = self.bus_table.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.bus_table.setItem(row, col, item)
            item.setText(value)
            if col in (0, 1, 2, 3):
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        if self.bus_dialog is not None and self.bus_dialog.isVisible():
            self.bus_dialog.refresh()

        if is_new:
            self._log(f"BUS neu gesehen: 0x{addr:02X} -> {stats['guess']}")

    @Slot(object)
    def on_frame_decoded(self, frame):
        self.frame_count += 1
        self.frame_count_label.setText(str(self.frame_count))
        if self.current_backend_key() == "display_modbus":
            self.display_last_frame_monotonic = time.monotonic()
        self.last_crc_label.setText(
            f"0x{frame.crc_got:04X} / calc 0x{frame.crc_calc:04X} / {'OK' if frame.crc_ok else 'BAD'}"
        )
        direction = self._frame_direction_text(frame)
        self.last_bus_label.setText(f"0x{frame.slave_addr:02X}")
        self.direction_label.setText(direction)
        self._update_bus_table(frame)
        matched_pending_read = self._apply_pending_read_response(frame)
        matched_passive_read = False
        if self.current_backend_key() == "display_modbus" and not matched_pending_read:
            matched_passive_read = self._apply_observed_display_read_response(frame)

        expected_slave = self._wire_slave_addr(DEFAULT_BUS_ADDR)
        throttle_repeated_bus = self.current_backend_key() == "display_modbus" and getattr(frame, "crc_ok", False)
        throttle_key_base = (
            int(frame.slave_addr),
            int(frame.func),
            int(frame.typ),
            str(frame.mode),
            int(frame.length_field),
        )

        if frame.slave_addr != expected_slave:
            self.foreign_frame_count += 1
            self.foreign_count_label.setText(str(self.foreign_frame_count))
            foreign_text = (
                f"FREMD-FRAME: addr=0x{frame.slave_addr:02X}, func=0x{frame.func:02X}, "
                f"typ=0x{frame.typ:04X}, mode={frame.mode}, crc={'OK' if frame.crc_ok else 'BAD'}, "
                f"vermutung={guess_device_name(frame.slave_addr, frame.crc_ok)}, "
                f"RAW={hexdump(frame.raw, -1)}"
            )
            if throttle_repeated_bus:
                self._log_throttled(
                    ("foreign-frame",) + throttle_key_base,
                    foreign_text,
                    summary_text=(
                        f"FREMD-FRAME zusammengefasst: addr=0x{frame.slave_addr:02X}, "
                        f"func=0x{frame.func:02X}, typ=0x{frame.typ:04X}, mode={frame.mode}"
                    ),
                    level=6,
                )
            else:
                self._log(foreign_text)

        if frame.mode == "read-request":
            read_text = (
                f"READ/Request gesehen: bus=0x{frame.slave_addr:02X}, "
                f"addr={frame.typ} / 0x{frame.typ:04X}, anzahl={frame.length_field}"
            )
            if throttle_repeated_bus:
                self._log_throttled(
                    ("read-request",) + throttle_key_base,
                    read_text,
                    summary_text=(
                        f"READ/Request zusammengefasst: bus=0x{frame.slave_addr:02X}, "
                        f"addr={frame.typ} / 0x{frame.typ:04X}, anzahl={frame.length_field}"
                    ),
                    level=5,
                )
            else:
                self._log(read_text)
            self._remember_display_read_request(frame)
        elif frame.mode == "read-response":
            if frame.registers:
                self._log(
                    f"READ/Response zugeordnet: bus=0x{frame.slave_addr:02X}, "
                    f"addr={frame.typ} / 0x{frame.typ:04X}, register={len(frame.registers)}"
                )
            else:
                self._log(
                    f"READ/Response gesehen: bus=0x{frame.slave_addr:02X}, "
                    f"bytes={frame.length_field}, RAW={hexdump(frame.raw, -1)}"
                )

        write_value = get_write_value(frame.payload)
        if write_value is not None:
            self._log(
                f"WRITE/Echo gesehen: bus=0x{frame.slave_addr:02X}, addr={frame.typ} / 0x{frame.typ:04X}, "
                f"value={write_value} / 0x{write_value:04X}"
            )
            if self.current_backend_key() == "display_modbus" and int(frame.typ) == 3011:
                self._log(
                    "DISPLAY-HMI: 3011/0x0BC3 gesehen = DWIN/Parameter-Sync-Flag, "
                    "nicht als normales WP-Register werten."
                )
        elif frame.mode == "write-response":
            self._log(
                f"WRITE/ACK gesehen: bus=0x{frame.slave_addr:02X}, "
                f"addr={frame.typ} / 0x{frame.typ:04X}, anzahl={frame.length_field}"
            )
            self._remember_display_write_ack(frame)
            self._apply_pending_write_ack(frame)


        if self.current_backend_key() == "display_modbus":
            self._display_hmi_log_block_diff(frame)
            self._display_hmi_log_safe_display_values(frame, matched_pending_read=matched_pending_read)

        apply_register_values = True
        if self.current_backend_key() == "display_modbus":
            apply_register_values = self._display_hmi_should_apply_registers(
                frame, expected_slave=expected_slave, matched_pending_read=matched_pending_read,
                matched_passive_read=matched_passive_read
            )

        changed_regs_for_live_search: list[int] = []
        bulk_table_update = apply_register_values and len(frame.registers) > 10
        old_table_updates = self.register_table.updatesEnabled()
        if bulk_table_update:
            self._suppress_name_resize = True
            self.register_table.setUpdatesEnabled(False)

        display_hmi_1012_fallback_value = None
        display_hmi_frame_had_true_2012 = False

        for reg in (frame.registers if apply_register_values else []):
            if int(getattr(reg, "reg", -1)) == 2104:
                cap = getattr(self, "warmlink_capture", None)
                if cap is not None:
                    cap.note_register_2104(getattr(reg, "raw_value", 0), str(getattr(reg, "display_value", getattr(reg, "raw_value", ""))))
            if self.known_only_cb.isChecked() and not reg.name:
                continue

            old_known = reg.reg in self.last_values
            old_value = self.last_values.get(reg.reg)
            value_diff = old_value != reg.raw_value
            was_cached = reg.reg in self.cached_regs
            # PRIVATE fix51: Erster Live-Wert nach Programmstart/Leeren ist ein
            # Initialwert und soll NICHT als Änderung markiert werden. Auch ein
            # vom Cache geladener Altwert zaehlt noch nicht als Live-Basis; erst
            # ab dem zweiten echten Live-Wert darf die Änderungsfarbe greifen.
            changed = bool(old_known and (not was_cached) and value_diff)
            if was_cached:
                self.cached_regs.discard(reg.reg)
            if value_diff:
                if old_value is None:
                    self.previous_value_texts.setdefault(reg.reg, "--")
                else:
                    self.previous_value_texts[reg.reg] = f"{old_value} / 0x{old_value:04X}"
            if changed:
                changed_regs_for_live_search.append(reg.reg)
            self.last_values[reg.reg] = reg.raw_value

            if self.current_backend_key() == "display_modbus":
                if int(reg.reg) == 1012 and changed:
                    display_hmi_1012_fallback_value = int(reg.raw_value) & 0xFFFF
                elif int(reg.reg) == 2012:
                    display_hmi_frame_had_true_2012 = True

            if changed or was_cached or reg.reg not in self.table_rows:
                self._upsert_register_row(reg, changed)

            if reg.reg == 2034:
                self._update_contact_table(reg.raw_value)
            if reg.reg == 2019:
                self._update_load_output_decoder(reg.raw_value)
                self._update_fault_decoder()
            if reg.reg in (2081, 2082, 2083, 2085, 2086, 2087, 2088, 2089, 2090):
                self._update_fault_decoder()

            if self.timer_dialog is not None and self.timer_dialog.isVisible():
                self.timer_dialog.update_from_live_register(reg)

            if self.onoff_timer_dialog is not None and self.onoff_timer_dialog.isVisible():
                self.onoff_timer_dialog.update_from_live_register(reg)

            if self.silent_timer_dialog is not None and self.silent_timer_dialog.isVisible():
                self.silent_timer_dialog.update_from_live_register(reg)

            if self.sg_dialog is not None and self.sg_dialog.isVisible():
                self.sg_dialog.update_from_live_register(reg)

            if self.parameter_dialog is not None and self.parameter_dialog.isVisible():
                self.parameter_dialog.update_from_live_register(reg)

            for dialog in list(self.register_write_dialogs.values()):
                if dialog.isVisible():
                    dialog.update_from_live_register(reg)

            if changed and (not self.log_changes_only_cb.isChecked() or reg.name):
                name = f" {reg.name}" if reg.name else ""
                self._log(
                    f"REG {reg.reg}{name}: {old_value if old_value is not None else '--'} -> "
                    f"{reg.raw_value} ({reg.display_value})"
                )

        # Display-HMI: 1012 (Sollmodus) und 2012 (Ist-/Betriebsstatus) verwenden
        # unterschiedliche Codetabellen. Ein früherer Diagnose-Fallback 1012 -> 2012
        # hat dadurch falsche Werte erzeugt und wird bewusst nicht mehr angewendet.
        # 2012 wird im Display-Modbus nur noch aus echten 2012-Datenframes aktualisiert.
        if (
            self.current_backend_key() == "display_modbus"
            and display_hmi_1012_fallback_value is not None
            and not display_hmi_frame_had_true_2012
        ):
            self._log(
                "DISPLAY-HMI: 1012 geändert, 2012 aber nicht nachgeführt "
                "(1012=Sollmodus, 2012=Iststatus; unterschiedliche Codetabelle)."
            )

        if bulk_table_update:
            self._suppress_name_resize = False
            self.register_table.setUpdatesEnabled(old_table_updates)
            self._resize_name_column()

        # PRIVATE fix51: Nach Bulk-Updates die gespeicherten Aenderungsfarben
        # erneut setzen, weil Qt die Tabelle erst danach neu zeichnet.
        if changed_regs_for_live_search:
            self._apply_persistent_change_backgrounds(changed_regs_for_live_search)

        if self.value_search_target is not None and self.value_search_live_cb.isChecked():
            old_hits = set(self.value_search_matches)
            hits = self._recalculate_value_search()
            matched_changed = sorted(r for r in changed_regs_for_live_search if r in self.value_search_matches)
            if set(hits) != old_hits or matched_changed:
                self._refresh_search_highlights()
                hit_text = ", ".join(str(r) for r in hits[:30]) if hits else "kein Treffer"
                if len(hits) > 30:
                    hit_text += f", ... (+{len(hits) - 30})"
                changed_text = ""
                if matched_changed:
                    changed_text = "; neuer/passender Wert in: " + ", ".join(str(r) for r in matched_changed[:20])
                self._log(
                    f"WERTSUCHE live aktualisiert: {self._value_search_description()}: "
                    f"{len(hits)} Register(n): {hit_text}{changed_text}"
                )

        self.reg_count_label.setText(str(len(self.last_values)))

    def _display_hmi_apply_2012_fallback_from_1012(self, raw_value: int) -> None:
        """Display-HMI-Fallback: 2012 anhand 1012 nachführen.

        Auf dem Displaybus sehen wir die 1012-Änderung zuverlässig im
        Addr-0x03/1001ff-Parameterpaket. Der echte 2012-Statusblock kommt auf
        diesem Bus bisher nur initial bzw. nicht zyklisch als Nutzdaten. Für die
        Übersicht im Display-Diagnosemodus spiegeln wir daher 1012 nach 2012,
        aber nur mit eindeutiger Logmeldung.
        """
        raw_value = int(raw_value) & 0xFFFF
        info = self.regmap.get(2012)
        old_known = 2012 in self.last_values
        old_value = self.last_values.get(2012)
        value_diff = old_value != raw_value
        was_cached = 2012 in self.cached_regs
        changed = bool(old_known and (not was_cached) and value_diff)
        if was_cached:
            self.cached_regs.discard(2012)
        if value_diff:
            if old_value is None:
                self.previous_value_texts.setdefault(2012, "--")
            else:
                self.previous_value_texts[2012] = f"{old_value} / 0x{old_value:04X}"
        reg = DecodedRegister(
            slave_addr=0x03,
            reg=2012,
            index=11,
            frame_type=0x03E9,
            raw_value=raw_value,
            signed_value=s16(raw_value),
            display_value=format_value_by_type(raw_value, info.dtype, info.value_map, info.bit_map),
            name=info.name,
            dtype=info.dtype,
            timestamp=time.time(),
        )
        self.last_values[2012] = raw_value
        if changed or was_cached or 2012 not in self.table_rows:
            self._upsert_register_row(reg, changed)
        if changed:
            self._log(
                "DISPLAY-HMI Fallback: 2012 aus 1012 nachgeführt, "
                f"weil kein zyklischer echter 2012-Statusblock kam: "
                f"{old_value if old_value is not None else '--'} -> {raw_value} ({reg.display_value})"
            )
        if self.parameter_dialog is not None and self.parameter_dialog.isVisible():
            self.parameter_dialog.update_from_live_register(reg)
        for dialog in list(self.register_write_dialogs.values()):
            if dialog.isVisible():
                dialog.update_from_live_register(reg)
        self.reg_count_label.setText(str(len(self.last_values)))

    def _resize_name_column(self):
        self.register_table.resizeColumnToContents(2)
        if self.register_table.columnWidth(2) > 360:
            self.register_table.setColumnWidth(2, 360)

    def _sorted_row_for_reg(self, reg_no: int) -> int:
        # Neue Register werden nach Registernummer einsortiert, auch wenn sie
        # später empfangen werden. Dadurch bleibt die Live-Tabelle stabil ohne
        # Qt-Sortierung, die zuvor Werte optisch in falsche Zeilen schieben konnte.
        row = 0
        for existing_reg in sorted(self.table_rows):
            if existing_reg >= reg_no:
                break
            row += 1
        return row

    def _insert_sorted_register_row(self, reg_no: int) -> int:
        row = self._sorted_row_for_reg(reg_no)
        self.register_table.insertRow(row)
        for existing_reg, existing_row in list(self.table_rows.items()):
            if existing_row >= row:
                self.table_rows[existing_reg] = existing_row + 1
        self.table_rows[reg_no] = row
        return row

    def _register_area_color(self, reg_no: int, dark: bool) -> Optional[QColor]:
        """Dauerfarbe der Registerbereiche in der Haupttabelle."""
        reg_no = int(reg_no)
        # Virtuelle Diagnosebereiche zuerst pruefen, weil 91099ff sonst in
        # die allgemeine 3000+-DWIN-Farbe fallen wuerde.
        if 91000 <= reg_no < 91200:
            return QColor(28, 52, 58) if dark else QColor(220, 242, 252)
        if 1000 <= reg_no < 1600:
            return QColor(28, 50, 34) if dark else QColor(224, 246, 224)
        # PRIVATE fix52: Live-/Statuswerte ab 2000 bekommen im hellen Design
        # dauerhaft ein helles Orange. Aenderungen werden dunkler orange.
        # 3000+ bleibt ein eigener DWIN-/Displaybereich und wird deshalb vorher
        # nicht vom 2000er-Block abgefangen.
        if 2000 <= reg_no < 3000:
            return QColor(58, 43, 24) if dark else QColor(255, 239, 210)
        if reg_no >= 3000:
            return QColor(45, 38, 70) if dark else QColor(238, 230, 255)
        return None

    def _register_changed_color(self, reg_no: int, dark: bool) -> QColor:
        """Aenderungsfarbe, passend zum jeweiligen Bereich, deutlich kraeftiger.

        PRIVATE fix52: 2000er-Werte sind nun im Normalzustand hellorange und
        bei Aenderung dunkelorange. Geaenderte Register bleiben bis
        "Hauptfenster leeren" markiert.
        """
        reg_no = int(reg_no)
        if 91000 <= reg_no < 91200:
            return QColor(12, 104, 128) if dark else QColor(80, 185, 225)
        if 1000 <= reg_no < 1600:
            return QColor(18, 112, 45) if dark else QColor(85, 195, 95)
        if 2000 <= reg_no < 3000:
            return QColor(118, 70, 18) if dark else QColor(255, 172, 82)
        if reg_no >= 3000:
            return QColor(94, 58, 150) if dark else QColor(158, 112, 230)
        return QColor(120, 92, 20) if dark else QColor(255, 198, 45)

    def _register_search_color(self, dark: bool) -> QColor:
        """Deutliche Suchtreffer-Farbe, absichtlich nicht orange.

        So kollidiert die Suchmarkierung nicht mehr mit dem 2000er-Statusbereich.
        """
        return QColor(36, 72, 130) if dark else QColor(125, 205, 255)

    def _register_change_highlight_active(self, reg_no: int) -> bool:
        """True, wenn eine Zeile seit dem letzten Leeren geändert wurde."""
        return int(reg_no) in self.register_change_highlights

    def _mark_register_changed_for_color(self, reg_no: int) -> None:
        """Änderungsfarbe dauerhaft halten, bis "Hauptfenster leeren" gedrückt wird."""
        reg_no = int(reg_no)
        self.register_change_highlights.add(reg_no)
        # PRIVATE fix51: direkt auf die bestehende Zeile anwenden. Bisher war
        # die Markierung zwar gespeichert, konnte aber danach durch normale
        # Bereichs-/Cache-/Such-Refreshes optisch wieder verschwinden.
        self._apply_register_row_visual_state(reg_no, force_changed=True)

    def _background_for_register(self, reg_no: int, changed: bool) -> QColor:
        dark = app_theme_is_dark()
        reg_no = int(reg_no)

        # Priorität: Suchtreffer und Änderungen. Änderungen bleiben bis
        # "Hauptfenster leeren" sichtbar; dadurch werden sie nicht von einem
        # Tabellen-/Cache-/Such-Refresh wieder auf die normale Bereichsfarbe gesetzt.
        if reg_no in self.value_search_matches or reg_no in self.name_search_matches:
            return self._register_search_color(dark)
        if changed or self._register_change_highlight_active(reg_no):
            return self._register_changed_color(reg_no, dark)

        area = self._register_area_color(reg_no, dark)
        if area is not None:
            return area

        # Cache-Grau nur für neutrale Bereiche verwenden. 10xx/30xx/91xxx behalten
        # ihre Bereichsfarbe auch direkt nach Cache-/Tabellenaufbau.
        if reg_no in self.cached_regs:
            return QColor(55, 55, 55) if dark else QColor(225, 225, 225)

        return QColor(37, 37, 37) if dark else QColor(255, 255, 255)

    def _set_table_item_background(self, item: QTableWidgetItem, color: QColor) -> None:
        # PRIVATE fix51: explizit QBrush setzen. Das ist robuster als QColor
        # direkt und verhindert, dass Stylesheet/alternating-row-color die
        # geaenderte Zeile optisch wieder auf die Grundfarbe zurueckzieht.
        brush = QBrush(color)
        item.setData(Qt.BackgroundRole, brush)
        item.setBackground(brush)

    def _apply_register_row_visual_state(self, reg_no: int, force_changed: bool = False) -> None:
        """Setzt Hintergrund/Fett fuer eine komplette Haupttabellen-Zeile.

        Das ist die eine zentrale Stelle fuer Bereichsfarbe + dauerhafte
        Aenderungsmarkierung. Sie wird nach Upsert, Such-Refresh, Cache-/
        Filter-Rebuild und Theme-Wechsel verwendet.
        """
        reg_no = int(reg_no)
        row = self.table_rows.get(reg_no)
        if row is None:
            return
        active_changed = bool(force_changed or self._register_change_highlight_active(reg_no))
        color = self.register_flash_colors.get(reg_no, FLASH_CHANGED_ROW_COLOR) if reg_no in self.register_flash_tokens else self._background_for_register(reg_no, active_changed)
        reg = self.latest_regs.get(reg_no)
        is_block_row = is_block_dtype(getattr(reg, "dtype", ""))
        for col in range(self.register_table.columnCount()):
            item = self.register_table.item(row, col)
            if item is None:
                continue
            # Grundschrift/Farbe zuerst herstellen. PRIVATE fix52: Änderungen
            # werden nicht fett markiert. Nur aktive Suchtreffer werden bewusst
            # fett dargestellt, damit sie sich klar von Bereichsfarben abheben.
            apply_block_header_item_style(self.register_table, item, is_block_row)
            is_search_hit = reg_no in self.value_search_matches or reg_no in self.name_search_matches
            font = item.font()
            font.setBold(bool(is_search_hit))
            item.setFont(font)
            if is_search_hit:
                # Suchtreffer zusätzlich mit kontrastreicher Schriftfarbe darstellen.
                item.setForeground(QColor(0, 0, 0) if not app_theme_is_dark() else QColor(255, 255, 255))
            self._set_table_item_background(item, color)

    def flash_register_row(self, reg_no: int) -> None:
        reg_no = int(reg_no)
        token = self.register_flash_tokens.get(reg_no, 0) + 1
        self.register_flash_tokens[reg_no] = token

        def apply_flash_step(color: QColor) -> None:
            if self.register_flash_tokens.get(reg_no) != token:
                return
            self.register_flash_colors[reg_no] = color
            self._apply_register_row_visual_state(reg_no)

        for delay_ms, color in FLASH_CHANGED_ROW_FADE_STEPS:
            QTimer.singleShot(delay_ms, lambda c=color: apply_flash_step(c))

        def clear_flash() -> None:
            if self.register_flash_tokens.get(reg_no) != token:
                return
            self.register_flash_tokens.pop(reg_no, None)
            self.register_flash_colors.pop(reg_no, None)
            self._apply_register_row_visual_state(reg_no)
        QTimer.singleShot(FLASH_CHANGED_ROW_MS, clear_flash)

    def _apply_persistent_change_backgrounds(self, only_regs: Optional[list[int]] = None) -> None:
        """PRIVATE fix51: geaenderte Zeilen nach Refreshes erneut sichtbar machen."""
        regs = only_regs if only_regs is not None else list(self.table_rows.keys())
        for reg_no in regs:
            if int(reg_no) in self.table_rows:
                self._apply_register_row_visual_state(int(reg_no))
        self.register_table.viewport().update()

    def _upsert_register_row(self, reg, changed: bool):
        self.latest_regs[reg.reg] = reg
        row = self.table_rows.get(reg.reg)
        if row is None:
            row = self._insert_sorted_register_row(reg.reg)

        block, code, clean_name = self._display_parts_for_register(reg.reg, reg.name)
        values = [
            str(reg.reg),
            code or block,
            clean_name,
            reg.dtype,
            f"{reg.raw_value} / 0x{reg.raw_value:04X}",
            self.previous_value_texts.get(reg.reg, "--"),
            str(reg.signed_value),
            self._display_value_for_main_table(reg),
            f"0x{reg.frame_type:04X}",
            f"0x{getattr(reg, 'slave_addr', DEFAULT_BUS_ADDR):02X}",
            time.strftime("%H:%M:%S", time.localtime(reg.timestamp)),
        ]
        cloud_info = self.cloud_overlay_by_reg.get(int(reg.reg), {})
        if cloud_info:
            values.extend([
                str(cloud_info.get("value", "")),
                str(cloud_info.get("code", "")),
                str(cloud_info.get("lastFetch", "")),
            ])
        else:
            values.extend(["", "", ""])
        is_block_row = is_block_dtype(reg.dtype)
        self.register_table.setRowHeight(row, 19 if is_block_row else 24)
        if changed:
            self._mark_register_changed_for_color(reg.reg)
            self.flash_register_row(reg.reg)

        for col, value in enumerate(values):
            item = self.register_table.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.register_table.setItem(row, col, item)
            item.setText(value)
            if col == 0:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            elif col == 1:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            elif col in (4, 5, 6):
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if col == 2 and value:
                item.setToolTip(reg.name)
            apply_block_header_item_style(self.register_table, item, is_block_row)

        # PRIVATE fix51: Hintergrund nach dem kompletten Text-/Font-Update setzen,
        # damit er nicht mehr durch Style-/Refresh-Schritte verloren geht.
        self._apply_register_row_visual_state(reg.reg, force_changed=changed)
        self._apply_cloud_only_visibility_for_reg(reg.reg)

        if not getattr(self, "_suppress_name_resize", False):
            self._resize_name_column()


    def _parse_cloud_numeric_value(self, value: Any) -> tuple[int, str]:
        text = str(value if value is not None else "").strip()
        if not text:
            return 0, ""
        if set(text) <= {"0", "1"} and len(text) > 4:
            try:
                return int(text, 2), text
            except Exception:
                return 0, text
        try:
            fval = float(text.replace(",", "."))
            return int(round(fval)), text
        except Exception:
            return 0, text

    def _cloud_display_text(self, code: str, value: Any) -> str:
        """Cloud-Wert fuer die Haupttabelle wie lokale Werte anzeigen.

        Cloud-Werte kommen oft bereits skaliert (z.B. Temperaturen als 34.5),
        lokale Register brauchen aber teils Rohwerte (/10). Deshalb werden hier
        nur sichere Klartext-Maps angewendet; ansonsten bleibt der Cloud-Wert
        mit Einheit unveraendert.
        """
        text = str(value if value is not None else "").strip()
        if not text:
            return ""

        hint = cloud_hint(code)
        maps: list[Any] = [
            hint.get("write_values"),
            hint.get("value_map"),
            hint.get("values"),
        ]
        reg_no = cloud_modbus_register(code)
        reg_info = self.regmap.get(int(reg_no)) if reg_no is not None else None
        if reg_info is not None and getattr(reg_info, "value_map", None):
            maps.append(reg_info.value_map)

        raw_int: Optional[int] = None
        try:
            raw_int = int(float(text.replace(",", ".")))
        except Exception:
            raw_int = None

        for mapping in maps:
            if not isinstance(mapping, dict):
                continue
            if text in mapping:
                return f"{text} = {mapping[text]}"
            if raw_int is not None:
                if raw_int in mapping:
                    return f"{raw_int} = {mapping[raw_int]}"
                if str(raw_int) in mapping:
                    return f"{raw_int} = {mapping[str(raw_int)]}"

        unit = code_unit(code)
        return f"{text} {unit}".strip()

    def _cloud_only_enabled(self) -> bool:
        cfg = self.settings.get("warmlink_cloud", {})
        if not isinstance(cfg, dict):
            return True
        return bool(cfg.get("show_cloud_only", True))

    def _is_cloud_only_register(self, reg_no: int) -> bool:
        reg = self.latest_regs.get(int(reg_no))
        if reg is None:
            return False
        try:
            return int(getattr(reg, "slave_addr", -1)) == 0xC1 and int(getattr(reg, "frame_type", -1)) == 0xC10D
        except Exception:
            return False

    def _has_local_register_entry(self, reg_no: int) -> bool:
        """True, wenn die Haupttabelle bereits eine echte lokale Registerzeile hat."""
        reg = self.latest_regs.get(int(reg_no))
        if reg is None:
            return False
        return not self._is_cloud_only_register(int(reg_no))

    def _apply_cloud_only_visibility_for_reg(self, reg_no: int) -> None:
        row = self.table_rows.get(int(reg_no))
        if row is None:
            return
        hide = self._is_cloud_only_register(int(reg_no)) and not self._cloud_only_enabled()
        self.register_table.setRowHidden(row, bool(hide))

    def _apply_cloud_only_visibility(self) -> None:
        for reg_no in list(self.table_rows.keys()):
            self._apply_cloud_only_visibility_for_reg(int(reg_no))

    def _on_main_cloud_only_toggled(self) -> None:
        cfg = self.settings.setdefault("warmlink_cloud", {})
        cfg["show_cloud_only"] = self._cloud_only_enabled()
        try:
            self._save_settings(sync_main_fields=False)
        except Exception:
            pass
        if self._cloud_only_enabled() and self.cloud_last_rows:
            self.apply_cloud_rows_to_main(self.cloud_last_rows, show_cloud_only=True)
        else:
            self._apply_cloud_only_visibility()
        self._log(f"Cloud-only Zeilen: {'ein' if self._cloud_only_enabled() else 'aus'}", level=2)

    def _is_safe_cloud_local_mapping(
        self, cloud_code: str, local_code: str, hint: dict[str, Any] | None = None
    ) -> bool:
        """Return True only for fachlich passende Cloud-/Lokal-Code-Mappings."""
        return cloud_hint_matches_local_code(cloud_code, hint or cloud_hint(cloud_code), local_code)

    def _validated_cloud_modbus_register(self, cloud_code: str, hint: dict[str, Any] | None = None) -> tuple[int | None, str, str]:
        """Validate a Cloud hint against the static local register map.

        This intentionally uses data/foxair_phnix_registers.json via the loaded
        RegisterMap/register_defs and does not depend on already-read Modbus
        rows.
        """
        hint = hint or cloud_hint(cloud_code)
        reg_no = cloud_modbus_register(cloud_code)
        if reg_no is None:
            return None, "", "no_register"
        try:
            reg_no = int(reg_no)
        except Exception:
            return None, "", "invalid_register"
        if reg_no not in getattr(self.regmap, "items", {}):
            return None, "", "unknown_register"
        local_code = self._code_for_register(reg_no)
        if not self._is_safe_cloud_local_mapping(cloud_code, local_code, hint):
            return None, local_code, "code_mismatch"
        return reg_no, local_code, ""

    def apply_cloud_rows_to_main(self, rows: list[dict[str, Any]], show_cloud_only: bool = True) -> None:
        """Cloud-Werte als Overlay in der Haupttabelle anzeigen.

        Lokale Modbus-Werte bleiben die Quelle der Wahrheit; Cloud wird nur als
        Zusatzspalte angezeigt. Wenn ein gemapptes Register lokal noch nicht in
        der Tabelle existiert, kann eine Cloud-only-Zeile angelegt werden.
        """
        if rows is None:
            return
        self.cloud_last_rows = [dict(r) for r in rows if isinstance(r, dict)]
        show_cloud_only = bool(show_cloud_only and self._cloud_only_enabled())
        changed_regs: list[int] = []
        seen_cloud_codes: set[str] = set()
        seen_registers: set[int] = set()
        for row in rows:
            if not isinstance(row, dict) or not row.get("supported"):
                continue
            code = str(row.get("code", "")).strip()
            if not code or code in seen_cloud_codes:
                continue
            seen_cloud_codes.add(code)
            hint = cloud_hint(code)
            reg_no, local_code, validation_error = self._validated_cloud_modbus_register(code, hint)
            raw_reg_no = cloud_modbus_register(code)
            if reg_no is None:
                try:
                    stale_reg = int(raw_reg_no) if raw_reg_no is not None else None
                except Exception:
                    stale_reg = None
                if stale_reg is not None and stale_reg in self.cloud_overlay_by_reg:
                    self.cloud_overlay_by_reg.pop(stale_reg, None)
                    changed_regs.append(stale_reg)
                if validation_error == "code_mismatch":
                    self._log(
                        f"Cloud mapping skipped: code mismatch cloud={code} "
                        f"local={local_code or '?'} reg={raw_reg_no}",
                        level=2,
                    )
                continue
            if reg_no in seen_registers:
                continue
            seen_registers.add(reg_no)
            has_local_register = self._has_local_register_entry(reg_no)
            has_existing_row = reg_no in self.table_rows
            value = row.get("value", "")
            info = {
                "code": code,
                "value": self._cloud_display_text(code, value),
                "raw_value": value,
                "lastFetch": row.get("lastFetch", ""),
                "confidence": code_confidence(code),
                "dataType": row.get("dataType", ""),
            }
            self.cloud_overlay_by_reg[reg_no] = info
            changed_regs.append(reg_no)
            if show_cloud_only and not has_local_register and not has_existing_row:
                reg_info = self.regmap.get(reg_no)
                raw_int, display_text = self._parse_cloud_numeric_value(value)
                mapped_name = getattr(reg_info, "name", "") if reg_info is not None else ""
                mapped_dtype = getattr(reg_info, "dtype", "") if reg_info is not None else ""
                name = str(hint.get("name") or mapped_name or f"Cloud {code}")
                dtype = str(mapped_dtype or row.get("dataType") or "CLOUD")
                disp = self._cloud_display_text(code, value)
                try:
                    signed = s16(raw_int & 0xFFFF)
                except Exception:
                    signed = raw_int
                self._upsert_register_row(DecodedRegister(
                    slave_addr=0xC1,
                    reg=int(reg_no),
                    index=0,
                    frame_type=0xC10D,
                    raw_value=raw_int & 0xFFFF,
                    signed_value=signed,
                    display_value=disp,
                    name=name,
                    dtype=dtype,
                    timestamp=time.time(),
                ), changed=False)
        self._apply_cloud_only_visibility()
        for reg_no in changed_regs:
            self._refresh_cloud_cells_for_register(reg_no)
        if changed_regs:
            self.register_table.viewport().update()

    def clear_cloud_overlay(self) -> None:
        regs = list(self.cloud_overlay_by_reg.keys())
        self.cloud_overlay_by_reg.clear()
        self.cloud_last_rows = []
        for reg_no in regs:
            self._refresh_cloud_cells_for_register(reg_no)
        self._apply_cloud_only_visibility()

    def _refresh_cloud_cells_for_register(self, reg_no: int) -> None:
        row = self.table_rows.get(int(reg_no))
        if row is None:
            return
        cloud_info = self.cloud_overlay_by_reg.get(int(reg_no), {})
        vals = [
            str(cloud_info.get("value", "")) if cloud_info else "",
            str(cloud_info.get("code", "")) if cloud_info else "",
            str(cloud_info.get("lastFetch", "")) if cloud_info else "",
        ]
        for off, val in enumerate(vals):
            col = 11 + off
            item = self.register_table.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.register_table.setItem(row, col, item)
            item.setText(val)
            if cloud_info:
                item.setToolTip(f"Cloud {cloud_info.get('code')} ({cloud_info.get('confidence', '')})")
        self._apply_register_row_visual_state(int(reg_no))

    def _update_contact_table(self, value: Optional[int]):
        self.last_contact_value = value
        if value is None:
            self.contact_value_label.setText("2034: --")
        else:
            active_bits = [str(bit) for bit, bit_value, _name, _state, _meaning in decode_contact_bits(value) if bit_value]
            active_text = ",".join(active_bits) if active_bits else "keine"
            self.contact_value_label.setText(f"2034: 0x{value:04X} / Bits: {active_text}")
        if self.contact_dialog is not None and self.contact_dialog.isVisible():
            self.contact_dialog.set_value(value)

    def _update_load_output_decoder(self, value: Optional[int]):
        self.last_load_output_value = value
        if self.load_output_dialog is not None and self.load_output_dialog.isVisible():
            self.load_output_dialog.set_value(value)

    def _fault_alarm_active(self) -> bool:
        value = self.last_values.get(2019, self.last_load_output_value)
        try:
            return bool(int(value) & (1 << 10)) if value is not None else False
        except Exception:
            return False

    def _active_fault_count(self) -> int:
        count = 0
        for reg_no in (2085, 2086, 2087, 2088, 2089, 2090, 2081, 2082, 2083):
            try:
                raw = int(self.last_values.get(reg_no, 0)) & 0xFFFF
            except Exception:
                raw = 0
            count += raw.bit_count()
        return count

    def _update_fault_button_style(self):
        alarm = self._fault_alarm_active()
        cnt = self._active_fault_count()
        if alarm or cnt:
            text = "Störungen / Fehler ..."
            if cnt:
                text += f" ({cnt})"
            self.fault_popup_btn.setText(text)
            self.fault_popup_btn.setStyleSheet("QPushButton { background-color: #b00020; color: white; font-weight: bold; }")
        else:
            self.fault_popup_btn.setText("Störungen / Fehler ...")
            self.fault_popup_btn.setStyleSheet("")

    def _update_fault_decoder(self):
        self._update_fault_button_style()
        if self.fault_dialog is not None and self.fault_dialog.isVisible():
            self.fault_dialog.refresh()


    def open_manual_register_dialog(self):
        self._show_manual_register_dialog()

    def _show_manual_register_dialog(self) -> ManualRegisterDialog:
        if self.manual_register_dialog is None or not self.manual_register_dialog.isVisible():
            self.manual_register_dialog = ManualRegisterDialog(self)
            self.manual_register_dialog.finished.connect(lambda _=None: setattr(self, "manual_register_dialog", None))
            self.manual_register_dialog.show()
        else:
            self.manual_register_dialog.show()
            self.manual_register_dialog.raise_()
            self.manual_register_dialog.activateWindow()
        return self.manual_register_dialog

    def _open_manual_register_dialog_for_register(self, reg_no: int, slave_addr: int | None = None):
        dialog = self._show_manual_register_dialog()
        if slave_addr is None:
            slave_addr = DEFAULT_BUS_ADDR
        dialog.set_address(int(reg_no), int(slave_addr))
        dialog.raise_()
        dialog.activateWindow()

    def open_bus_addresses(self):
        if self.bus_dialog is None or not self.bus_dialog.isVisible():
            self.bus_dialog = BusAddressDialog(self)
            self.bus_dialog.finished.connect(lambda _=None: setattr(self, "bus_dialog", None))
            self.bus_dialog.show()
        else:
            self.bus_dialog.refresh()
            self.bus_dialog.raise_()
            self.bus_dialog.activateWindow()

    def open_offline_browser(self):
        if self.offline_dialog is None or not self.offline_dialog.isVisible():
            self.offline_dialog = OfflineRegisterBrowserDialog(self)
            self.offline_dialog.finished.connect(lambda _=None: setattr(self, "offline_dialog", None))
            self.offline_dialog.show()
        else:
            self.offline_dialog.refresh()
            self.offline_dialog.raise_()
            self.offline_dialog.activateWindow()

    def open_dual_logger_dialog(self):
        if self.dual_logger_dialog is None or not self.dual_logger_dialog.isVisible():
            self.dual_logger_dialog = DualBusLoggerDialog(self)
            self.dual_logger_dialog.finished.connect(lambda _=None: setattr(self, "dual_logger_dialog", None))
            self.dual_logger_dialog.show()
        else:
            self.dual_logger_dialog.raise_()
            self.dual_logger_dialog.activateWindow()

    def open_contact_decoder(self):
        if self.contact_dialog is None or not self.contact_dialog.isVisible():
            self.contact_dialog = ContactDecoderDialog(self, self.last_contact_value)
            self.contact_dialog.finished.connect(lambda _=None: setattr(self, "contact_dialog", None))
            self.contact_dialog.show()
        else:
            self.contact_dialog.raise_()
            self.contact_dialog.activateWindow()

    def open_load_output_decoder(self):
        if self.load_output_dialog is None or not self.load_output_dialog.isVisible():
            self.load_output_dialog = LoadOutputDecoderDialog(self, self.last_load_output_value if self.last_load_output_value is not None else self.last_values.get(2019))
            self.load_output_dialog.finished.connect(lambda _=None: setattr(self, "load_output_dialog", None))
            self.load_output_dialog.show()
        else:
            self.load_output_dialog.raise_()
            self.load_output_dialog.activateWindow()

    def open_fault_decoder(self):
        if self.fault_dialog is None or not self.fault_dialog.isVisible():
            self.fault_dialog = FaultDecoderDialog(self)
            self.fault_dialog.finished.connect(lambda _=None: setattr(self, "fault_dialog", None))
            self.fault_dialog.show()
        else:
            self.fault_dialog.refresh()
            self.fault_dialog.raise_()
            self.fault_dialog.activateWindow()


    def open_backup_restore(self):
        if self.backup_restore_dialog is None or not self.backup_restore_dialog.isVisible():
            self.backup_restore_dialog = BackupRestoreDialog(self)
            self.backup_restore_dialog.finished.connect(lambda _=None: setattr(self, "backup_restore_dialog", None))
            self.backup_restore_dialog.show()
        else:
            self.backup_restore_dialog.raise_()
            self.backup_restore_dialog.activateWindow()

    def _update_dual_logger_button_visibility(self):
        if not hasattr(self, "dual_logger_btn"):
            return
        visible = (
            self.current_backend_key() == "display_modbus"
            and bool(self.settings.get("show_dual_logger_button_display", False))
        )
        self.dual_logger_btn.setVisible(visible)

    def toggle_cache_options(self):
        visible = not self.cache_options_widget.isVisible()
        self.cache_options_widget.setVisible(visible)
        self.cache_toggle_btn.setText("Einstellungen ausblenden" if visible else "Einstellungen ...")

    def _refresh_search_highlights(self):
        # PRIVATE fix51: Such-/Bereichs-/Aenderungsfarben immer ueber die
        # zentrale Zeilenfunktion setzen. So bleiben dauerhaft geaenderte
        # Register dunkler, bis "Hauptfenster leeren" gedrueckt wird.
        self._apply_persistent_change_backgrounds()

    def _parse_search_target(self) -> float:
        text = self.search_value_edit.text().strip().replace(",", ".")
        if not text:
            raise ValueError("Leerer Suchwert")
        mode = "decoded" if self.search_decoded_cb.isChecked() else "raw"
        if mode == "raw":
            return float(int(text, 0))
        if text.lower().startswith("0x"):
            return float(int(text, 16))
        return float(text)

    def _value_search_description(self) -> str:
        if self.value_search_target is None:
            return "inaktiv"
        mode_text = "Rohwert/signed" if self.value_search_mode == "raw" else "decodiert"
        return f"{mode_text} {self.value_search_target:g} ±{self.value_search_tolerance:g}"

    def _set_value_search_count(self, count: int):
        if hasattr(self, "value_search_count_label"):
            self.value_search_count_label.setText(f"{count} Treffer")

    def _set_name_search_count(self, count: int):
        if hasattr(self, "name_search_count_label"):
            self.name_search_count_label.setText(f"{count} Treffer")

    def _reg_matches_value_search(self, reg) -> bool:
        if self.value_search_target is None:
            return False
        target = float(self.value_search_target)
        tol = float(self.value_search_tolerance)
        if self.value_search_mode == "decoded":
            candidate = numeric_value_by_type(int(reg.raw_value), str(reg.dtype))
            return abs(candidate - target) <= tol
        raw = int(reg.raw_value)
        signed = s16(raw)
        return abs(float(raw) - target) <= tol or abs(float(signed) - target) <= tol

    def _recalculate_value_search(self) -> list[int]:
        self.value_search_matches = set()
        self.value_search_context = set()
        if self.value_search_target is None:
            self._set_value_search_count(0)
            return []

        for reg_no, reg in self.latest_regs.items():
            if self._reg_matches_value_search(reg):
                self.value_search_matches.add(reg_no)
        hits = sorted(self.value_search_matches)
        self._set_value_search_count(len(hits))
        return hits

    def search_value_now(self):
        try:
            self.value_search_mode = "decoded" if self.search_decoded_cb.isChecked() else "raw"
            self.value_search_target = self._parse_search_target()
            self.value_search_tolerance = float(self.search_tolerance_spin.value())
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Wertsuche", str(exc))
            return

        hits = self._recalculate_value_search()
        self._refresh_search_highlights()

        if hits:
            hit_text = ", ".join(str(r) for r in hits[:30])
            if len(hits) > 30:
                hit_text += f", ... (+{len(hits) - 30})"
            self._log(
                f"WERTSUCHE {self._value_search_description()}: "
                f"{len(hits)} Treffer in Register(n): {hit_text}. "
                f"Live={'an' if self.value_search_live_cb.isChecked() else 'aus'}."
            )
            first_row = self.table_rows.get(hits[0])
            if first_row is not None:
                self.register_table.scrollToItem(self.register_table.item(first_row, 0))
        else:
            self._log(
                f"WERTSUCHE {self._value_search_description()}: "
                f"kein Treffer in aktuell empfangenen Registern. "
                f"Live={'an' if self.value_search_live_cb.isChecked() else 'aus'}."
            )

    def clear_value_search(self):
        self.value_search_target = None
        self.value_search_matches = set()
        self.value_search_context = set()
        self._set_value_search_count(0)
        self._refresh_search_highlights()
        self._log("WERTSUCHE Markierung gelöscht.")

    def _recalculate_name_search(self) -> list[int]:
        self.name_search_matches = set()
        text = self.name_search_edit.text().strip() if hasattr(self, "name_search_edit") else ""
        if not text:
            self._set_name_search_count(0)
            return []
        try:
            if self.name_search_regex_cb.isChecked():
                pattern = re.compile(text, re.IGNORECASE)
                for reg_no, reg in self.latest_regs.items():
                    if pattern.search(str(reg.name or "")):
                        self.name_search_matches.add(reg_no)
            else:
                needle = text.lower()
                for reg_no, reg in self.latest_regs.items():
                    if needle in str(reg.name or "").lower():
                        self.name_search_matches.add(reg_no)
        except re.error as exc:
            raise ValueError(f"Regex ungültig: {exc}")
        hits = sorted(self.name_search_matches)
        self._set_name_search_count(len(hits))
        return hits

    def search_name_now(self):
        try:
            hits = self._recalculate_name_search()
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Namenssuche", str(exc))
            return
        self._refresh_search_highlights()
        text = self.name_search_edit.text().strip()
        if hits:
            hit_text = ", ".join(str(r) for r in hits[:30])
            if len(hits) > 30:
                hit_text += f", ... (+{len(hits) - 30})"
            self._log(f"NAMENSSUCHE '{text}': {len(hits)} Treffer: {hit_text}")
            first_row = self.table_rows.get(hits[0])
            if first_row is not None:
                self.register_table.scrollToItem(self.register_table.item(first_row, 0))
        else:
            self._log(f"NAMENSSUCHE '{text}': kein Treffer im Namensfeld.")

    def clear_name_search(self):
        self.name_search_edit.clear()
        self.name_search_matches = set()
        self._set_name_search_count(0)
        self._refresh_search_highlights()
        self._log("NAMENSSUCHE Markierung gelöscht.")

    def _check_endblock_signature(self, frame, start_addr: int):
        # Viele 90er-Blöcke beginnen mit einer festen Signatur.
        # Beispiel aus bekannten Dumps: 5AA6 3232 3130 3235 3034 3735.
        expected = [22342, 12850, 12592, 12853, 12340, 14133]
        if len(frame.registers) < len(expected):
            return
        starts = {1001, 1091, 1181, 1271, 1361, 1451, 1541, 2001, 2091}
        if start_addr not in starts:
            return
        got = [int(r.raw_value) & 0xFFFF for r in frame.registers[:len(expected)]]
        if got == expected:
            return
        got_text = ", ".join(f"0x{v:04X}" for v in got)
        self._log(f"WARNUNG: Blocksignatur bei {start_addr}/0x{start_addr:04X} unerwartet: {got_text}")

    def _remember_display_read_request(self, frame) -> None:
        """Merkt passive Display/HMI-Read-Requests, damit die folgende Response
        einem Startregister zugeordnet werden kann. Das ist nur fuer Display-Modbus
        aktiv; Warmlink/Standard-Modbus bleiben unverändert.
        """
        if self.current_backend_key() != "display_modbus":
            return
        if frame.mode != "read-request" or not frame.crc_ok:
            return
        if int(frame.length_field) <= 0:
            return
        now = time.time()
        self.observed_display_read_requests = [
            r for r in self.observed_display_read_requests
            if now - float(r.get("time", now)) < 8.0
        ]
        self.observed_display_read_requests.append({
            "slave_addr": int(frame.slave_addr),
            "addr": int(frame.typ),
            "quantity": int(frame.length_field),
            "time": now,
        })

    def _apply_observed_display_read_response(self, frame) -> bool:
        """Ordnet passive Display/HMI-Read-Responses dem vorher gesehenen
        Read-Request gleicher Adresse/Laenge zu und dekodiert so die Register.
        """
        if self.current_backend_key() != "display_modbus":
            return False
        if frame.mode != "read-response" or not frame.crc_ok:
            return False
        now = time.time()
        self.observed_display_read_requests = [
            r for r in self.observed_display_read_requests
            if now - float(r.get("time", now)) < 8.0
        ]
        for req in list(self.observed_display_read_requests):
            if int(req["slave_addr"]) != int(frame.slave_addr):
                continue
            quantity = int(req["quantity"])
            if len(frame.payload) != quantity * 2:
                continue
            start_addr = int(req["addr"])
            frame.typ = start_addr
            frame.length_field = quantity
            # Label am Frame merken, damit Display-Backend gezielte Init-WP-Paketreads
            # anders behandeln kann als manuelle/DWIN-Diagnose-Reads.
            req_label = str(req.get("label", ""))
            try:
                frame.pending_read_label = req_label
            except Exception:
                pass
            # Im Display-Modbus-Modus getrennt dekodieren: DWIN-/Display-Adressen
            # bekommen Diagnose-Namen, ohne das normale Warmlink-Mapping zu veraendern.
            # Ausnahme: gezielte WP-Paketblock-Reads auf Display Unit 0x03 sollen mit dem
            # normalen Warmlink/WP-Mapping dekodiert und ins Hauptfenster übernommen werden.
            # Fix10: 0x03/1001ff..1541ff sind echte WP-Parameterpakete im
            # Display-Speicher. Auch wenn sie passiv vom Display-Bus kommen,
            # muessen sie mit dem normalen WP-/Warmlink-Mapping dekodiert werden,
            # sonst fehlen Value-Maps/Klartexte wie 1012: 0=WW, 1=Heizen, 2=Kuehlen.
            is_display_wp_param_packet = (
                int(frame.slave_addr) == 0x03
                and int(start_addr) in {1001, 1091, 1181, 1271, 1361, 1451, 1541}
            )
            force_wp_map = (
                "WP-Paketblock" in req_label
                or "Display Init Paketblock" in req_label
                or is_display_wp_param_packet
            )
            use_display_map = (
                self.current_backend_key() == "display_modbus"
                and not force_wp_map
                and (
                    "DWIN" in req_label
                    or "Display" in req_label
                    or int(frame.slave_addr) in {0x02, 0x03, 0x04, 0x05}
                    or int(start_addr) >= 3000
                    or 0x1200 <= int(start_addr) <= 0x1AFF
                )
            )
            decode_map = getattr(self, "display_regmap", self.regmap) if use_display_map else self.regmap
            frame.registers = decode_read_response_registers(frame, start_addr, decode_map)
            self._check_endblock_signature(frame, start_addr)
            self.observed_display_read_requests.remove(req)
            self._log(
                f"DISPLAY-HMI passive Response zugeordnet: bus=0x{frame.slave_addr:02X}, "
                f"addr={start_addr} / 0x{start_addr:04X}, {quantity} Register"
            )
            if frame.registers:
                value_lines = []
                for reg in frame.registers[:8]:
                    name = f" {reg.name}" if reg.name else ""
                    value_lines.append(f"{reg.reg}={reg.raw_value}/0x{reg.raw_value:04X} ({reg.display_value}){name}")
                more = "" if len(frame.registers) <= 8 else f" ... (+{len(frame.registers) - 8})"
                self._log("DISPLAY-HMI passive Werte: " + "; ".join(value_lines) + more)
            return True
        return False

    def _display_hmi_log_block_diff(self, frame) -> None:
        """Display-/HMI-Diagnose: Rohwerte bestimmter Blöcke vergleichen.

        Ziel ist die Suche nach dem echten Ist-/Betriebsstatus, der am Display
        angezeigt wird, aber bisher nicht als normales Register 2012 im
        Display-Mitschnitt auftaucht. Die Ausgabe ist reine Diagnose und ändert
        keine Registerwerte in der Hauptliste.
        """
        if self.current_backend_key() != "display_modbus":
            return
        if not getattr(frame, "crc_ok", False) or not getattr(frame, "registers", None):
            return

        slave = int(frame.slave_addr)
        start = int(frame.typ)
        mode = str(frame.mode)

        tracked = False
        label = ""
        # Roh-/Statusblock der Hauptplatine: gesperrt, aber vollständig beobachten.
        if slave == 0x01 and start in {1999, 2001} and mode in {"word-frame", "write-request"}:
            tracked = True
            label = "0x01/1999ff Rohstatus"
        # Sauber zuordenbarer 2099ff-Block: Kandidaten fuer Iststatus/Icons/Zähler.
        elif slave == 0x01 and start == 2099 and mode == "read-response":
            tracked = True
            label = "0x01/2099ff Live-/Status"
        # DWIN-Anzeigeblock: kann Icons/Display-Seiten enthalten.
        elif slave in {0x02, 0x03} and start == 3001 and mode == "read-response":
            tracked = True
            label = f"0x{slave:02X}/3001ff DWIN-Anzeige"
        # HMI-Parameterpaket: hier sehen wir 1012 als Soll-/Auswahlmodus.
        elif slave == 0x03 and start in {1001, 1091, 1181, 1271, 1361, 1451, 1541} and mode in {"word-frame", "read-response"}:
            tracked = True
            label = f"0x03/{start}ff Parameter"
        # 0x05 schreibt bisher meist Nullblöcke; trotzdem als Fremdblock beobachten.
        elif slave == 0x05 and start in {1001, 2000} and mode in {"word-frame", "read-response"}:
            tracked = True
            label = f"0x05/{start}ff Fremdblock"

        if not tracked:
            return

        words = [int(r.raw_value) & 0xFFFF for r in frame.registers]
        key = (slave, start, mode)
        old_words = self.display_hmi_block_snapshots.get(key)
        self.display_hmi_block_snapshots[key] = words
        self.display_hmi_block_snapshot_times[key] = time.monotonic()

        def reg_label(index: int) -> str:
            return f"{start + index}/W{index + 1}"

        def fmt_word(index: int, value: int) -> str:
            return f"{reg_label(index)}={value}/0x{value:04X}"

        if old_words is None:
            # Erste Sichtung: bei kleinen/unklaren Blöcken vollständig, bei langen
            # Blöcken Anfang + wichtige Verdachtswörter loggen.
            if len(words) <= 24:
                preview = ", ".join(fmt_word(i, v) for i, v in enumerate(words))
            else:
                head = [fmt_word(i, words[i]) for i in range(min(12, len(words)))]
                suspects = []
                for reg_no in (1012, 2012, 2105, 2108, 2110, 2115, 2116, 2118, 2120):
                    idx = reg_no - start
                    if 0 <= idx < len(words):
                        suspects.append(fmt_word(idx, words[idx]))
                tail = [fmt_word(len(words) - 1, words[-1])] if words else []
                preview = ", ".join(dict.fromkeys(head + suspects + tail))
            self._log(
                f"DISPLAY-HMI SNAPSHOT {label} ({len(words)} Wörter, mode={mode}): {preview}"
            )
            return

        changes = []
        max_len = max(len(old_words), len(words))
        for i in range(max_len):
            old = old_words[i] if i < len(old_words) else None
            new = words[i] if i < len(words) else None
            if old == new:
                continue
            if old is None:
                changes.append(f"{reg_label(i)}: -- -> {new}/0x{new:04X}")
            elif new is None:
                changes.append(f"{reg_label(i)}: {old}/0x{old:04X} -> --")
            else:
                changes.append(f"{reg_label(i)}: {old}/0x{old:04X} -> {new}/0x{new:04X}")

        if not changes:
            return

        # Bei Display-Diagnose nicht jeden Refresh überladen, aber genug zeigen,
        # um Kandidaten für den Istmodus zu finden.
        shown = changes[:18]
        more = "" if len(changes) <= len(shown) else f" ... (+{len(changes) - len(shown)} weitere)"
        self._log(f"DISPLAY-HMI DIFF {label}: " + "; ".join(shown) + more)

        # Zusatzhinweis, wenn sich in einem Block genau kleine 0..4-Werte ändern:
        # Das sind interessante Kandidaten für Betriebsmodus/Icon/Seitenstatus.
        candidates = []
        for i, (old, new) in enumerate(zip(old_words, words)):
            if old != new and 0 <= int(new) <= 4:
                candidates.append(f"{reg_label(i)}={new}")
        if candidates:
            self._log(
                "DISPLAY-HMI KANDIDAT Istmodus/Icon kleiner Code: "
                + ", ".join(candidates[:12])
                + (" ..." if len(candidates) > 12 else "")
            )

    def _display_hmi_log_safe_display_values(self, frame, matched_pending_read: bool = False) -> None:
        """Loggt sichere Display-Bus-Werte separat, ohne die Warmlink-Hauptliste zu ändern.

        Fix9: Fix8 war zu hart und hat auch die bekannten 10xx-Parameterpakete
        aus dem Display-Mitschnitt komplett "stumm" gemacht. Diese Werte sind für
        die Diagnose nützlich, dürfen aber nicht in latest_regs/last_values landen,
        weil sonst Warmlink-Register wie 2101ff überschrieben/verfälscht werden.
        """
        if self.current_backend_key() != "display_modbus":
            return
        if matched_pending_read:
            return
        if not getattr(frame, "crc_ok", False) or not getattr(frame, "registers", None):
            return

        slave = int(frame.slave_addr)
        start = int(frame.typ)
        mode = str(frame.mode)

        safe_param_starts = {1001, 1091, 1181, 1271, 1361, 1451, 1541}
        should_log = False
        label = ""

        # Von der Display-/DWIN-Unit 0x03 kommende Parameterpakete sind bekannte
        # 10xx/11xx/12xx... Einstellwerte. Wir loggen sie als DREG separat.
        if slave == 0x03 and start in safe_param_starts and mode in {"word-frame", "read-response"}:
            should_log = True
            label = f"Display-Parameterpaket 0x03/{start}ff"

        if not should_log:
            return

        changes = []
        for reg in frame.registers:
            reg_no = int(reg.reg)
            raw = int(reg.raw_value) & 0xFFFF
            old = self.display_last_values.get(reg_no)
            self.display_latest_regs[reg_no] = reg
            if old == raw:
                continue
            self.display_last_values[reg_no] = raw
            name = f" {reg.name}" if getattr(reg, "name", "") else ""
            changes.append(f"DREG {reg_no}{name}: {'--' if old is None else old} -> {raw} ({reg.display_value})")

        if changes:
            self._log(f"DISPLAY-HMI {label}: {len(changes)} getrennte Diagnosewerte geändert (nicht Hauptliste).")
            for line in changes[:80]:
                self._log(line)
            if len(changes) > 80:
                self._log(f"DISPLAY-HMI {label}: ... (+{len(changes) - 80} weitere DREG-Änderungen)")

    def _display_hmi_virtual_regs_0x01_2099(self, frame) -> list[DecodedRegister]:
        """PRIVATE fix14: 0x01/2099ff als virtuellen Diagnosebereich abbilden.

        Der Rohstatus auf Bus 0x01 nutzt echte Adressen 2099-2149, ist aber
        nicht identisch/vertraulich genug, um die normalen WP-Register 2099ff
        zu ueberschreiben. Darum wird er im Hauptfenster als 91099-91149
        sichtbar gemacht.
        """
        virt_start = 91099
        source_start = int(getattr(frame, "typ", 2099) or 2099)
        regs: list[DecodedRegister] = []
        # PRIVATE fix18: zwei Rohstatuswerte wurden mit echten WP-Werten
        # korreliert. Im Log verhaelt sich 91105 wie 2062 (AC-Eingang)
        # und 91108 wie 2043 (DC-Power-Bus). Die Quelle bleibt Bus 0x01;
        # als Absender/Rolle ist Power-Modul-Spiegel plausibel, aber noch
        # nicht endgueltig bestaetigt.
        special_names = {
            91105: "Displaybus 0x01 Power-Modul-Spiegel: AC-Eingangsspannung wie 2062 (virtuell, Kandidat)",
            91108: "Displaybus 0x01 Power-Modul-Spiegel: DC-Power-Bus-Spannung wie 2043 (virtuell, Kandidat)",
        }
        special_units = {91105: "V", 91108: "V"}
        for idx, old_reg in enumerate(list(getattr(frame, "registers", []) or [])):
            raw = int(getattr(old_reg, "raw_value", 0) or 0) & 0xFFFF
            orig_reg = source_start + idx
            virt_reg = virt_start + idx
            name = special_names.get(virt_reg, f"Displaybus 0x01 Rohstatus {orig_reg}/0x{orig_reg:04X} (virtuell)")
            unit = special_units.get(virt_reg)
            # PRIVATE fix51: format_value_by_type erwartet value_map/bit_map,
            # keine Einheit. Ein String "V" als value_map kann eine Exception
            # ausloesen und dadurch die komplette virtuelle 91099ff-Uebernahme
            # abbrechen. Deshalb die Einheit hier manuell anhaengen.
            display_value = f"{s16(raw)} {unit}" if unit else format_value_by_type(raw, "DIGI1")
            regs.append(DecodedRegister(
                slave_addr=int(getattr(frame, "slave_addr", 0) or 0),
                reg=virt_reg,
                index=idx,
                frame_type=virt_start,
                raw_value=raw,
                signed_value=s16(raw),
                display_value=display_value,
                name=name,
                dtype="DIGI1",
                timestamp=time.time(),
            ))
        return regs

    def _display_hmi_promote_0x01_2099_virtual(self, frame) -> bool:
        if self.current_backend_key() != "display_modbus":
            return False
        if int(getattr(frame, "slave_addr", -1)) != 0x01:
            return False
        if int(getattr(frame, "typ", -1)) != 2099:
            return False
        if str(getattr(frame, "mode", "")) != "read-response":
            return False
        if not getattr(frame, "registers", None):
            return False
        frame.registers = self._display_hmi_virtual_regs_0x01_2099(frame)
        frame.typ = 91099
        frame.length_field = len(frame.registers)
        return True

    def _display_hmi_is_extra_main_window_candidate(self, frame) -> bool:
        """PRIVATE fix12: zusätzliche Display-Bus-Werte ins Hauptfenster übernehmen.

        Ziel:
        - DWIN-/Display-Werte ab 3000 sichtbar machen, weil die WP diese Werte
          vom Display zyklisch abfragt (z. B. 3001ff / 3011 / 3021).
        - Fremdteilnehmer 0x04/0x05 nur dann übernehmen, wenn deren Register-
          nummern nicht mit bekannten WP-/Warmlink-Registern kollidieren.

        Warmlink RAW und Standard-Modbus rufen diese Logik nicht auf.
        """
        if self.current_backend_key() != "display_modbus":
            return False
        if not getattr(frame, "crc_ok", False) or not getattr(frame, "registers", None):
            return False
        mode = str(getattr(frame, "mode", ""))
        if mode not in {"read-response", "word-frame", "write-request"}:
            return False
        slave = int(getattr(frame, "slave_addr", 0) or 0)
        start = int(getattr(frame, "typ", 0) or 0)
        regs = list(getattr(frame, "registers", []) or [])

        # Unit 0x02/0x03: echter DWIN-/Display-Speicher. Alles ab 3000
        # darf sichtbar werden; diese Nummern kollidieren nicht mit den
        # normalen 10xx/20xx-WP-Paketen.
        if slave in {0x02, 0x03} and start >= 3000:
            return True

        # Unit 0x04/0x05: nur unbekannte/nicht belegte Registerbereiche in die
        # Hauptliste übernehmen. Bekannte WP-Register wie 1001ff/2000ff bleiben
        # Diagnose, damit Null-/Fremdblöcke keine echten WP-Werte überschreiben.
        if slave in {0x04, 0x05}:
            wp_known = getattr(self.regmap, "items", {})
            for reg in regs:
                reg_no = int(getattr(reg, "reg", 0) or 0)
                if reg_no in wp_known:
                    return False
            # Sicherheitsgurt: Niedrige unbekannte Bereiche nur dann aufnehmen,
            # wenn sie sicher außerhalb der bekannten WP-Paketzone liegen.
            if start >= 3000:
                return True
            if all((int(getattr(r, "reg", 0) or 0) < 1000 or int(getattr(r, "reg", 0) or 0) > 2300) for r in regs):
                return True

        return False

    def _display_hmi_should_apply_registers(self, frame, expected_slave: int, matched_pending_read: bool, matched_passive_read: bool) -> bool:
        """Entscheidet, welche Display/HMI-Register in die Hauptliste dürfen.

        Fix8: Display-/DWIN-Bus bleibt grundsaetzlich Diagnose. Die Hauptliste nutzt
        normalerweise das Warmlink/WP-Mapping und nur vertrauenswuerdige Quellen.
        V0.2.38 fix5: validierte aktive Display-Init-WP-Paketbloecke 0x03/10xx
        duerfen vorerst wieder ins Hauptfenster, bis ein besserer Init-Weg gefunden ist.
        """
        if matched_pending_read:
            pending_label = str(getattr(frame, "pending_read_label", ""))
            if (
                "WP-Paketblock" in pending_label
                and int(frame.slave_addr) == 0x03
                and int(frame.typ) in {1001, 1091, 1181, 1271, 1361, 1451, 1541, 2001, 2091}
            ):
                info = self._validated_packet_info_from_regs(int(frame.typ), frame.registers)
                if info:
                    self._log(
                        f"DISPLAY-HMI: aktiver WP-Paketblock 0x03/{frame.typ}ff validiert; "
                        "wird vorerst wieder in die Hauptliste uebernommen."
                    )
                    return True
                else:
                    self._log(
                        f"DISPLAY-HMI: aktiver WP-Paketblock 0x03/{frame.typ}ff ohne gültigen Paketkopf; "
                        "nicht übernommen."
                    )
                return False
            if self._display_hmi_is_extra_main_window_candidate(frame):
                self._log(
                    f"DISPLAY-HMI fix12: aktive/manuelle Display-Antwort Bus 0x{frame.slave_addr:02X} "
                    f"{frame.typ}/0x{frame.typ:04X} wird als zusätzlicher Display-Wert in die Hauptliste übernommen."
                )
                return True
            self._log(
                f"DISPLAY-HMI: manuelle Antwort addr {frame.typ}/0x{frame.typ:04X} "
                "nur im Popup/Log ausgewertet; nicht in Haupt-Registerliste übernommen."
            )
            return False

        # Hauptdaten vom Display-Bus: die WP schreibt diese Bloecke als
        # Broadcast auf den Bus. Das sind echte Warmlink/WP-Register und duerfen
        # daher wieder in die Hauptliste.
        if int(frame.slave_addr) == 0x00 and int(frame.typ) in {2001, 2091} and frame.mode in {"word-frame", "write-request"}:
            self._log(
                f"DISPLAY-HMI: Broadcast 0x00/{frame.typ}ff als echte WP-Livewerte "
                "in Hauptliste übernommen."
            )
            return True

        # 0x01 / 1999ff bzw. 2001ff erscheint auf dem Displaybus häufig als
        # FC16-ACK bzw. unklarer Statuspfad. Nur Diagnose, keine Hauptliste.
        if int(frame.slave_addr) == 0x01 and int(frame.typ) in {1999, 2001}:
            if frame.mode == "write-response":
                self._log(
                    f"DISPLAY-HMI DEBUG: Addr 0x01 / {frame.typ}ff FC16-ACK ohne Nutzdaten "
                    "gesehen; 1999/2001-Statusblock nicht übernommen."
                )
                return False
            if frame.mode in {"word-frame", "write-request"}:
                preview = ""
                if frame.registers:
                    pairs = [f"{r.reg}={r.raw_value}/0x{r.raw_value:04X}" for r in frame.registers[:8]]
                    preview = "; Wertevorschau: " + ", ".join(pairs)
                    if len(frame.registers) > 8:
                        preview += f", ... (+{len(frame.registers) - 8})"
                self._log(
                    f"DISPLAY-HMI DEBUG: Addr 0x01 / {frame.typ}ff {frame.mode} "
                    f"mit {len(frame.registers)} dekodierten Worten gesperrt; "
                    "20xx/2012 daraus aktuell nicht vertrauenswürdig" + preview
                )
                return False

        # 0x01 / 2099ff ist auf dem Displaybus nuetzlich, kollidiert aber mit
        # echten WP-Registern. PRIVATE fix14: als virtueller Diagnosebereich
        # 91099-91149 uebernehmen, statt 2099ff zu ueberschreiben.
        if int(frame.slave_addr) == 0x01 and int(frame.typ) == 2099:
            # PRIVATE fix51: nicht mehr hart von matched_passive_read abhaengig machen.
            # Entscheidend ist, dass der Frame bereits als 2099/read-response mit
            # Registerliste vorliegt. Dann ist der virtuelle Bereich sicher, weil er
            # 2099ff nicht ueberschreibt, sondern nach 91099ff verschiebt.
            if frame.registers and str(getattr(frame, "mode", "")) == "read-response":
                if self._display_hmi_promote_0x01_2099_virtual(frame):
                    self._log(
                        "DISPLAY-HMI fix21: 0x01/2099ff Rohstatus als virtuellen "
                        "Diagnosebereich 91099-91149 in die Hauptliste übernommen "
                        "(Warmlink-2099ff bleibt unverändert)."
                    )
                    return True
            self._log(
                "DISPLAY-HMI: 0x01/2099ff Rohstatus nur Diagnose; "
                "nicht in Hauptliste übernommen (Warmlink-Mapping bleibt unverändert)."
            )
            return False

        if int(frame.slave_addr) == 0x03 and int(frame.typ) in {1001, 1091, 1181, 1271, 1361, 1451, 1541}:
            self._log(
                f"DISPLAY-HMI: bekanntes 10xx/Parameterpaket 0x03/{frame.typ}ff "
                "wieder in Hauptliste übernommen."
            )
            return True

        if self._display_hmi_is_extra_main_window_candidate(frame):
            self._log(
                f"DISPLAY-HMI fix12: Bus 0x{frame.slave_addr:02X} "
                f"{frame.typ}/0x{frame.typ:04X} mode={frame.mode} "
                "als zusätzlicher Display-/Fremdwert in die Hauptliste übernommen."
            )
            return True

        if frame.registers:
            self._log(
                f"DISPLAY-HMI: Registerwerte von Bus 0x{frame.slave_addr:02X}, "
                f"Quelle {frame.typ}/0x{frame.typ:04X}, mode={frame.mode} "
                "nicht in Hauptliste übernommen."
            )
        return False

    def _pending_read_timeout_s(self, req: dict[str, Any]) -> float:
        label = str(req.get("label", ""))
        if label.startswith("manuell") or label.startswith("manuelles Popup"):
            return 5.0
        return 15.0

    def has_pending_read_request(self, label: str, slave_addr: Optional[int] = None) -> bool:
        for req in list(getattr(self, "pending_read_requests", []) or []):
            if str(req.get("label", "")) != str(label):
                continue
            if slave_addr is not None and int(req.get("slave_addr", -1)) != int(slave_addr):
                continue
            return True
        return False

    def remove_pending_read_requests_by_label(self, labels: set[str], log_prefix: str = "READ") -> int:
        labels = {str(label) for label in labels}
        removed = 0
        for req in list(getattr(self, "pending_read_requests", []) or []):
            if str(req.get("label", "")) not in labels:
                continue
            try:
                self.pending_read_requests.remove(req)
                removed += 1
            except ValueError:
                pass
        dlg = getattr(self, "dual_logger_dialog", None)
        display_pending = getattr(dlg, "display_pending_reads", None) if dlg is not None else None
        if isinstance(display_pending, list):
            keep = [req for req in display_pending if str(req.get("label", "")) not in labels]
            removed += len(display_pending) - len(keep)
            display_pending[:] = keep
        if removed:
            self._log(f"{log_prefix}: {removed} alte Pending-Read(s) entfernt: {', '.join(sorted(labels))}", force=True)
        return removed

    def _check_pending_read_timeouts(self) -> None:
        now = time.time()
        for req in list(getattr(self, "pending_read_requests", []) or []):
            timeout_s = self._pending_read_timeout_s(req)
            if now - float(req.get("time", now)) < timeout_s:
                continue
            try:
                self.pending_read_requests.remove(req)
            except ValueError:
                continue
            addr = int(req.get("addr", req.get("wire_addr", 0)))
            qty = int(req.get("quantity", 1))
            label = f" ({req.get('label')})" if req.get("label") else ""
            qty_text = "" if qty == 1 else f", {qty} Register"
            rx_bytes_at_send = int(req.get("rx_count_at_send", 0))
            rx_bytes_now = rx_bytes_at_send
            restbuffer_present = bool(req.get("restbuffer_at_send", False))
            restbuffer_len = int(req.get("restbuffer_len_at_send", 0))
            worker = self._active_io_worker()
            if worker is not None:
                rx_bytes_now = int(getattr(worker, "total_rx_bytes", rx_bytes_at_send))
                restbuffer_len = len(getattr(worker, "buf", b"") or b"")
                restbuffer_present = restbuffer_present or restbuffer_len > 0
            rx_during_wait = rx_bytes_now > rx_bytes_at_send
            self._log(
                f"READ Timeout{label}: {addr}{qty_text}; "
                f"RX waehrend Wartezeit: {'ja' if rx_during_wait else 'nein'} "
                f"({max(0, rx_bytes_now - rx_bytes_at_send)} Byte); "
                f"Restbuffer vorhanden: {'ja' if restbuffer_present else 'nein'}"
                f"{f' ({restbuffer_len} Byte)' if restbuffer_present else ''}",
                force=True,
            )
            req_label = str(req.get("label", ""))
            if req_label.startswith("manuelles Popup") and self.manual_register_dialog is not None and self.manual_register_dialog.isVisible():
                try:
                    self.manual_register_dialog.show_read_timeout(addr, qty)
                except AttributeError:
                    pass
            if req_label.startswith("Popup Register"):
                key = (int(req.get("slave_addr", DEFAULT_BUS_ADDR)), int(req.get("addr", addr)))
                dialog = getattr(self, "register_write_dialogs", {}).get(key)
                if dialog is not None and dialog.isVisible():
                    try:
                        dialog.show_write_readback_timeout()
                    except AttributeError:
                        pass
            if str(req.get("label", "")) in (SGReadyEditorDialog.READ_LABEL_VALUES, SGReadyEditorDialog.READ_LABEL_STATUS):
                sg_dialog = getattr(self, "sg_dialog", None)
                if sg_dialog is not None and sg_dialog.isVisible():
                    if str(req.get("label", "")) == SGReadyEditorDialog.READ_LABEL_STATUS:
                        sg_dialog.show_sg_status_timeout()
                    else:
                        sg_dialog.status_label.setText("SG Ready Werte Timeout / keine Antwort.")

    def _apply_pending_read_response(self, frame) -> bool:
        if frame.mode != "read-response":
            return False
        if self.pending_read_requests:
            self._log(f"DEBUG Pending-Read-Pruefung: {len(self.pending_read_requests)} offen fuer RX read-response bus=0x{int(frame.slave_addr):02X}, bytes={len(frame.payload)}", level=7, force=True)
        self._check_pending_read_timeouts()
        for req in list(self.pending_read_requests):
            if int(req["slave_addr"]) != int(frame.slave_addr):
                continue
            quantity = int(req["quantity"])
            if len(frame.payload) != quantity * 2:
                continue
            start_addr = int(req["addr"])
            frame.typ = start_addr
            frame.length_field = quantity
            # Im Display-Modbus-Modus getrennt dekodieren: DWIN-/Display-Adressen
            # bekommen Diagnose-Namen, ohne das normale Warmlink-Mapping zu veraendern.
            req_label = str(req.get("label", ""))
            try:
                frame.pending_read_label = req_label
            except Exception:
                pass
            # Fix10: passive/aktive 0x03/1001ff..1541ff-Paketantworten sind
            # WP-Parameterpakete, keine DWIN-Diagnosewerte. Mit WP-Mapping bleiben
            # Klartexte/Value-Maps wie 1012=Heizen/Kuehlen/WW auch nach einem
            # Bedienwert-Write sichtbar.
            is_display_wp_param_packet = (
                int(frame.slave_addr) == 0x03
                and int(start_addr) in {1001, 1091, 1181, 1271, 1361, 1451, 1541}
            )
            force_wp_map = (
                "WP-Paketblock" in req_label
                or "Display Init Paketblock" in req_label
                or is_display_wp_param_packet
            )
            use_display_map = (
                self.current_backend_key() == "display_modbus"
                and not force_wp_map
                and (
                    "DWIN" in req_label
                    or "Display" in req_label
                    or int(frame.slave_addr) in {0x02, 0x03, 0x04, 0x05}
                    or int(start_addr) >= 3000
                    or 0x1200 <= int(start_addr) <= 0x1AFF
                )
            )
            decode_map = getattr(self, "display_regmap", self.regmap) if use_display_map else self.regmap
            frame.registers = decode_read_response_registers(frame, start_addr, decode_map)
            # Falls mehrere Display-Reads doch einmal überlappen: WP-Paketkopf enthält
            # den echten internen Start im Wort 10. Dann nach internem Start neu dekodieren.
            if force_wp_map:
                info = self._validated_packet_info_from_regs(start_addr, frame.registers)
                if not info and len(getattr(frame, "registers", []) or []) >= 10:
                    internal_start = int(frame.registers[9].raw_value) & 0xFFFF
                    if internal_start in {1001, 1091, 1181, 1271, 1361, 1451, 1541, 2001, 2091}:
                        frame.typ = internal_start
                        start_addr = internal_start
                        frame.registers = decode_read_response_registers(frame, start_addr, self.regmap)
                        self._log(
                            f"DISPLAY-INIT: Antwort per internem Paketstart neu zugeordnet: "
                            f"{int(req.get('addr', start_addr))}/0x{int(req.get('addr', start_addr)):04X} -> "
                            f"{start_addr}/0x{start_addr:04X}"
                        )
            self._check_endblock_signature(frame, start_addr)
            self.pending_read_requests.remove(req)
            label = f" ({req.get('label')})" if req.get("label") else ""
            self._log(f"READ/Response passt zu Anfrage{label}: {start_addr} / 0x{start_addr:04X}, {quantity} Register")
            if frame.registers:
                value_lines = []
                for reg in frame.registers[:12]:
                    name = f" {reg.name}" if reg.name else ""
                    value_lines.append(f"{reg.reg}={reg.raw_value}/0x{reg.raw_value:04X} ({reg.display_value}){name}")
                more = "" if len(frame.registers) <= 12 else f" ... (+{len(frame.registers) - 12})"
                self._log("READ Werte: " + "; ".join(value_lines) + more)
            if str(req.get("label", "")).startswith("manuelles Popup") and self.manual_register_dialog is not None and self.manual_register_dialog.isVisible():
                self.manual_register_dialog.show_read_response(start_addr, quantity, frame.registers)
            if req_label == SGReadyEditorDialog.READ_LABEL_STATUS:
                sg_dialog = getattr(self, "sg_dialog", None)
                if sg_dialog is not None and sg_dialog.isVisible():
                    for reg in frame.registers:
                        if int(reg.reg) == 2133:
                            sg_dialog.update_from_live_register(reg, force=True)
                            break
            if self.current_backend_key() != "display_modbus":
                for controller_name in ("warmlink_init_controller", "standard_modbus_init_controller"):
                    controller = getattr(self, controller_name, None)
                    if controller is not None and getattr(controller, "active", False):
                        try:
                            controller.notify_response(start_addr, quantity, int(frame.slave_addr))
                        except Exception:
                            pass
            return True
        return False

    def _active_io_worker(self):
        """Liefert den Worker, auf den manuell gelesen/geschrieben werden soll.

        Beim Display-Init übernimmt der ausgelagerte DisplayWorker den Bus. Die
        alte Hauptverbindung kann dann bereits EOF sein, obwohl Display-Mithören
        und aktives Senden über den DisplayWorker noch funktionieren. Manuelle
        Display-Reads/Writes müssen dann genau diesen Worker benutzen.
        """
        if self.current_backend_key() == "display_modbus":
            dlg = getattr(self, "dual_logger_dialog", None)
            aux_worker = getattr(dlg, "display_worker", None) if dlg is not None else None
            if aux_worker is not None:
                return aux_worker
        if self.connected and self.worker:
            return self.worker
        return None

    def send_read_from_fields(self):
        try:
            slave_addr = self._parse_int_text(self.write_bus_edit.text())
            addr = self._parse_int_text(self.write_addr_edit.text())
            quantity = int(self.read_count_spin.value())
            self.send_read_request(addr, quantity, slave_addr=slave_addr, label="manuell")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Leseanforderung", str(exc))

    def send_read_request(self, addr: int, quantity: int = 1, slave_addr: int = DEFAULT_BUS_ADDR, label: str = "", delay_ms: int = 0):
        # fix11: Popup-/Parameter-Aktualisierungen am Display-Bus nicht mehr als
        # normale FC03-Reads absetzen. Stattdessen den bewährten Reboot-Snapshot
        # anstoßen. Manuelle FC03-Reads bleiben absichtlich direkt möglich, damit
        # wir den gestern gefundenen Qty90-Direktlese-Pfad weiter testen können.
        if self._display_should_redirect_read_to_reboot_snapshot(addr, quantity, slave_addr, label):
            self._log(
                f"DISPLAY-SNAPSHOT fix12: Leseanforderung '{label or 'ohne Label'}' "
                f"{int(addr)}/0x{int(addr):04X}, qty={int(quantity)} wird nicht direkt gelesen, "
                "sondern über Display Reboot Fake aktualisiert."
            )
            self._start_display_reboot_snapshot(source_label=(label or f"Read {addr}/{quantity}"), force=False)
            return
        frame, wire_addr, wire_slave, note = self._build_read_frame_for_backend(addr, quantity, slave_addr)
        note_text = f", {note}" if note else ""
        if self.current_backend_key() == "display_modbus" and int(slave_addr) != int(wire_slave):
            note_text += f", Display-Unit aus Einstellungen verwendet: Eingabe 0x{int(slave_addr):02X} -> TX 0x{wire_slave:02X}"
        self._log(
            f"READ wird GESENDET [{self.current_backend_label()}]: bus=0x{wire_slave:02X}, "
            f"addr={addr}/0x{addr:04X} -> wire={wire_addr}/0x{wire_addr:04X}, "
            f"anzahl={quantity}, TX={hexdump(frame, -1)}{note_text}"
        )
        io_worker = self._active_io_worker()
        if io_worker is None:
            self._log("READ nicht gesendet: keine aktive Verbindung / kein aktiver Worker.")
            return

        # Wenn der DisplayWorker den Bus übernommen hat, landen die Antworten im
        # DualBusLoggerDialog und nicht mehr im normalen MainWindow-Framepfad.
        # Dann muss auch die Pending-Zuordnung dort eingetragen werden, sonst
        # erscheinen kurze Antworten wie 03 03 02 00 00 nur als "ohne bekannte Startadresse".
        routed_to_aux_display = False
        if self.current_backend_key() == "display_modbus":
            dlg = getattr(self, "dual_logger_dialog", None)
            aux_worker = getattr(dlg, "display_worker", None) if dlg is not None else None
            if aux_worker is not None and io_worker is aux_worker:
                routed_to_aux_display = True
                try:
                    map_key = "display" if (int(wire_addr) >= 3000 or int(wire_slave) in {0x02, 0x03, 0x05}) else "warmlink"
                    if any(
                        int(req.get("slave", -1)) == int(wire_slave)
                        and int(req.get("addr", -1)) == int(wire_addr)
                        and int(req.get("qty", -1)) == int(quantity)
                        for req in list(dlg.display_pending_reads)
                    ):
                        self._log(
                            f"DISPLAY READ nicht doppelt gestapelt: bus=0x{int(wire_slave):02X}, "
                            f"wire=0x{int(wire_addr):04X}, qty={int(quantity)}.",
                            level=6,
                            force=True,
                        )
                        return
                    dlg.display_pending_reads.append({
                        "slave": int(wire_slave),
                        "addr": int(wire_addr),
                        "qty": int(quantity),
                        "label": str(label or "manuell"),
                        "map": map_key,
                        "queued_at": time.monotonic(),
                    })
                    if len(dlg.display_pending_reads) > 220:
                        del dlg.display_pending_reads[:len(dlg.display_pending_reads) - 220]
                except Exception as exc:
                    self._log(f"DISPLAY WARN: Pending-Read im DisplayWorker konnte nicht eingetragen werden: {exc}")

        if not routed_to_aux_display:
            for req in list(getattr(self, "pending_read_requests", []) or []):
                if (
                    int(req.get("slave_addr", -1)) == int(wire_slave)
                    and int(req.get("wire_addr", -1)) == int(wire_addr)
                    and int(req.get("quantity", -1)) == int(quantity)
                ):
                    self._log(
                        f"READ nicht doppelt gestapelt: identischer Pending-Read bereits offen "
                        f"(bus=0x{int(wire_slave):02X}, addr={int(addr)}/0x{int(addr):04X}, qty={int(quantity)}, "
                        f"bestehend={req.get('label') or '-'}, neu={label or '-'}).",
                        level=6,
                        force=True,
                    )
                    return
            self.pending_read_requests.append({
                "slave_addr": wire_slave,
                "addr": addr,
                "wire_addr": wire_addr,
                "quantity": quantity,
                "label": label,
                "time": time.time(),
                "rx_count_at_send": int(getattr(io_worker, "total_rx_bytes", 0)),
                "restbuffer_at_send": bool(getattr(io_worker, "buf", None)),
                "restbuffer_len_at_send": len(getattr(io_worker, "buf", b"") or b""),
            })
            self._log(
                f"DEBUG Pending-Read offen: bus=0x{int(wire_slave):02X}, "
                f"addr={int(addr)}/0x{int(addr):04X}, qty={int(quantity)}, label={label or '-'}",
                level=7, force=True,
            )
            if getattr(io_worker, "buf", None):
                self._log(
                    f"DEBUG RX-Buffer vor neuem Send nicht leer: {len(io_worker.buf)} Byte; "
                    "wird durch den laufenden Reader/Parser verarbeitet.",
                    level=7, force=True,
                )
        io_worker.enqueue_read(wire_addr, quantity, slave_addr=wire_slave, post_delay_ms=delay_ms)

    # V0.2.38: alter GUI-interner Display-Init-Pfad entfernt. Display-Init läuft nur noch über DisplayKnownReadController.

    def send_init_reads(self):
        try:
            slave_addr = self._parse_int_text(self.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR

        backend = self.current_backend_key()
        backend_label = self.current_backend_label()
        # Fix23: Erkennung bewusst doppelt absichern. In Fix22 konnte trotz sichtbarem
        # Label "Modbus Display" der alte Standard-Initpfad genutzt werden. Zusätzlich
        # darf hier NICHT die UI-Unit (oft 0x01) verwendet werden: die bislang erfolgreichen
        # aktiven Display-Paketreads antworten auf Unit 0x03.
        is_display_backend = (backend == "display_modbus") or ("display" in str(backend_label).lower())
        if is_display_backend:
            # fix11: Am Display-Bus ist der Reboot-Fake vorerst die stabilste
            # Snapshot-/Abfrage-Methode: das Display setzt 0BC3=8000 und der echte
            # Master lädt die Parameterpakete 1001/1091/... erneut in Unit 0x03.
            # Die alte aktive Qty90-Display-Read-Logik bleibt im Code/DualLogger
            # erhalten, ist aber NICHT mehr der Standard für diesen Button.
            self._log(
                "DISPLAY-SNAPSHOT fix12: 'Alle bekannten Register lesen' nutzt jetzt Display Reboot Fake "
                "statt aktiver Qty90-Reads. Warmlink/Standard-Modbus bleiben unverändert."
            )
            self._start_display_reboot_snapshot(source_label="Alle bekannten Register lesen", force=True)
            return

        # Fix33: Warmlink und Standard-Modbus sind nun getrennte Init-Controller.
        # Beide nutzen den bestehenden Haupt-Reader, aber Ablauf/Logging/Pending-Handling
        # liegen in getrennten Worker-Hilfsdateien.
        pause_ms = int(self.init_pause_spin.value()) if getattr(self, "init_pause_spin", None) is not None else 900
        if backend == "standard_modbus":
            self.standard_modbus_init_controller.start(slave_addr=slave_addr, pause_ms=pause_ms)
        else:
            self.warmlink_init_controller.start(slave_addr=slave_addr, pause_ms=pause_ms)
        return

    # V0.2.38: alter generischer Init-Timerpfad entfernt. Warmlink/Standard/Display nutzen eigene Controller.

    def open_manual_register_dialog_from_table_item(self, item):
        if item is None:
            return
        row = item.row()
        reg_item = self.register_table.item(row, 0)
        if reg_item is None:
            return
        try:
            reg_no = int(reg_item.text())
        except ValueError:
            return
        try:
            bus_text = self.register_table.item(row, 9).text() if self.register_table.item(row, 9) else self.write_bus_edit.text()
            slave_addr = self._parse_int_text(bus_text)
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self._open_manual_register_dialog_for_register(reg_no, slave_addr)

    def open_register_context_menu(self, pos):
        item = self.register_table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        reg_item = self.register_table.item(row, 0)
        if reg_item is None:
            return
        try:
            reg_no = int(reg_item.text())
        except ValueError:
            return
        try:
            bus_text = self.register_table.item(row, 9).text() if self.register_table.item(row, 9) else self.write_bus_edit.text()
            row_slave_addr = self._parse_int_text(bus_text)
        except Exception:
            row_slave_addr = DEFAULT_BUS_ADDR

        result = exec_register_context_menu(self, reg_no, self.register_table.viewport().mapToGlobal(pos))
        if result is None:
            return
        if result.action == RegisterContextAction.QUICK_WRITE:
            self.open_register_quick_write(reg_no, row_slave_addr)
        elif result.action == RegisterContextAction.CLOUD_WRITE:
            self.open_cloud_write_for_register(reg_no)
        elif result.action == RegisterContextAction.READ_ONE:
            self.send_read_request(reg_no, 1, slave_addr=row_slave_addr, label="Rechtsklick")
        elif result.action == RegisterContextAction.READ_TEN:
            self.send_read_request(reg_no, 10, slave_addr=row_slave_addr, label="Rechtsklick 10er")
        elif result.action == RegisterContextAction.USE_WRITE_ADDRESS:
            self._open_manual_register_dialog_for_register(reg_no, row_slave_addr)


    def _cloud_write_credentials(self) -> tuple[str | None, str | None, str | None, str | None]:
        """Zugangsdaten fuer Cloud-Schreiben aus Dialog/Settings/Keyring holen."""
        cfg = self.settings.get("warmlink_cloud", {}) if isinstance(self.settings.get("warmlink_cloud", {}), dict) else {}
        cfg.setdefault("save_token", True)
        user = str(cfg.get("username", "")).strip()
        device_code = str(cfg.get("selected_device_code", "")).strip()
        use_token = bool(cfg.get("save_token", True))
        pw: str | None = None
        token: str | None = None

        dlg = self.warmlink_cloud_dialog
        if dlg is not None:
            try:
                user = dlg.username_edit.text().strip() or user
                device_code = dlg._selected_device_code() or device_code
                use_token = bool(dlg.save_token_cb.isChecked())
                if use_token and getattr(dlg, "_cloud_token_username", "") == user:
                    token = getattr(dlg, "_cloud_token", None)
                pw = dlg._password()
            except Exception:
                pw = None

        if not user:
            return None, None, None, device_code or None
        if use_token and not token:
            try:
                token = get_token(user)
            except Exception as exc:
                self._log("WarmLink Cloud: Token konnte nicht aus dem OS-Keyring gelesen werden: " + str(exc))
                token = None
        if token:
            if not pw:
                try:
                    pw = get_password(user)
                except Exception as exc:
                    self._log("WarmLink Cloud: Passwort konnte nicht für Token-Fallback gelesen werden: " + str(exc))
                    pw = None
            return user, pw, token, device_code or None
        if pw:
            return user, pw, None, device_code or None
        try:
            pw = get_password(user)
        except Exception as exc:
            QMessageBox.warning(self, "WarmLink Cloud", f"Passwort konnte nicht aus dem OS-Keyring gelesen werden:\n{exc}")
            return user, None, None, device_code or None
        return user, pw, None, device_code or None

    def _ask_cloud_value(self, reg_no: int, cloud_code: str) -> str | None:
        values = cloud_write_values_for_code(cloud_code)
        current_raw = current_raw_text_for_cloud_write(self.latest_regs.get(int(reg_no)))
        options, current_index = cloud_write_choice_options(values, current_raw)
        if options:
            labels = [label for _value, label in options]
            item, ok = QInputDialog.getItem(
                self,
                "Wert per Cloud schreiben",
                f"Register {reg_no} / Cloud-Code {cloud_code}:\nWert wählen:",
                labels,
                current_index,
                False,
            )
            if not ok:
                return None
            return cloud_write_value_from_label(options, item)

        text, ok = QInputDialog.getText(
            self,
            "Wert per Cloud schreiben",
            f"Register {reg_no} / Cloud-Code {cloud_code}:\nCloud-Wert eingeben:",
            text=current_raw,
        )
        if not ok:
            return None
        text = str(text).strip()
        return text if text != "" else None

    def open_cloud_write_for_register(self, reg_no: int):
        cloud_code = cloud_code_for_register(reg_no, require_write_allowed=True)
        if not cloud_code:
            QMessageBox.information(self, "WarmLink Cloud", f"Für Register {reg_no} ist kein freigegebener Cloud-Schreibcode gemappt.")
            return
        value = self._ask_cloud_value(reg_no, cloud_code)
        if value is None:
            return
        user, pw, token, device_code = self._cloud_write_credentials()
        if not user or not (pw or token):
            QMessageBox.warning(
                self,
                "WarmLink Cloud",
                "Cloud-Zugang fehlt. Bitte im Fenster 'WarmLink Cloud / LTE' Benutzername eintragen und das Passwort speichern.",
            )
            return
        name = code_display_name(cloud_code)
        device_txt = device_code if device_code else "automatisch: erstes Cloud-Gerät"
        if not ask_yes_no(
            self,
            "Wert per Cloud schreiben",
            f"Wirklich per WarmLink Cloud senden?\n\n"
            f"Register: {reg_no}\nCloud-Code: {cloud_code} - {name}\nWert: {value}\nDevice: {device_txt}\n\n"
            "Der Befehl wird über die Cloud an die Wärmepumpe gesendet.",
            default_yes=False,
        ):
            return
        self.send_cloud_write(cloud_code, value, device_code=device_code, label=f"Register {reg_no}")

    def send_cloud_write(self, cloud_code: str, value: str, device_code: str | None = None, label: str = ""):
        if self.cloud_write_thread is not None:
            QMessageBox.information(self, "WarmLink Cloud", "Es läuft bereits ein Cloud-Schreibbefehl.")
            return
        user, pw, token, saved_device_code = self._cloud_write_credentials()
        if not user or not (pw or token):
            QMessageBox.warning(self, "WarmLink Cloud", "Cloud-Zugang fehlt oder Passwort ist nicht im Keyring gespeichert.")
            return
        dev = str(device_code or saved_device_code or "").strip()
        self._log(f"WarmLink Cloud schreiben: {cloud_code}={value} ({label or 'Hauptfenster'})")
        self.cloud_write_code = str(cloud_code)
        self.cloud_write_thread = QThread(self)
        self.cloud_write_worker = WarmLinkCloudCommandWorker(
            username=user,
            password=pw or "",
            device_code=dev,
            code=str(cloud_code),
            value=str(value),
            endpoint=ENDPOINT_AUTO_WRITE,
            dry_run=False,
            initial_token=token,
        )
        self.cloud_write_worker.moveToThread(self.cloud_write_thread)
        self.cloud_write_thread.started.connect(self.cloud_write_worker.run)
        self.cloud_write_worker.log.connect(self._log)
        self.cloud_write_worker.result.connect(self._on_cloud_write_result_current)
        self.cloud_write_worker.error.connect(self._on_cloud_write_error)
        self.cloud_write_worker.finished.connect(self.cloud_write_thread.quit)
        self.cloud_write_worker.finished.connect(self.cloud_write_worker.deleteLater)
        self.cloud_write_thread.finished.connect(self._cloud_write_finished)
        self.cloud_write_thread.start()

    def _on_cloud_write_result_current(self, data: dict):
        self._on_cloud_write_result(self.cloud_write_code, data)

    def _on_cloud_write_result(self, cloud_code: str, data: dict):
        ok = bool(data.get("isReusltSuc") or data.get("isResultSuc") or data.get("success"))
        msg = translate_cloud_error_message(str(data.get("error_msg") or data.get("message") or ""))
        endpoint = str(data.get("endpoint") or "")
        payload = data.get("payload")
        readback = data.get("readback") if isinstance(data, dict) else None
        rb_txt = ""
        if isinstance(readback, dict):
            rb_val = readback.get("value")
            rb_status = readback.get("status") or ("OK" if readback.get("supported") else "")
            if rb_val not in (None, ""):
                rb_txt = f"; Readback {cloud_code}: {rb_val} {rb_status}".rstrip()
        log_txt = json.dumps({"ok": ok, "endpoint": endpoint, "message": msg, "payload": payload, "readback": readback}, ensure_ascii=False)
        self._log("WarmLink Cloud Schreibantwort: " + log_txt)
        if ok:
            # V0.2.44 fix4: Erfolg/Readback nur noch im Log. Kein Erfolgs-Popup,
            # damit Rechtsklick-Schreiben nicht am Ende wie "keine Rueckmeldung" wirkt.
            self.statusBar().showMessage(f"Cloud-Schreiben OK: {cloud_code}={payload if payload is None else data.get('payload', '')}", 6000)
            self._log(f"WarmLink Cloud schreiben OK: {cloud_code} via {endpoint}; {msg or 'Success'}{rb_txt}")
        else:
            QMessageBox.warning(self, "WarmLink Cloud", f"Cloud-Schreiben nicht erfolgreich.\nEndpoint: {endpoint}\nMeldung: {msg or data.get('error_code') or 'unbekannt'}")

    def _on_cloud_write_error(self, text: str):
        self._log("WarmLink Cloud Schreibfehler: " + str(text))
        QMessageBox.warning(self, "WarmLink Cloud", "Cloud-Schreiben fehlgeschlagen:\n" + translate_cloud_error_message(str(text)))

    def _cloud_write_finished(self):
        if self.cloud_write_thread is not None:
            self.cloud_write_thread.deleteLater()
        self.cloud_write_thread = None
        self.cloud_write_worker = None
        self.cloud_write_code = ""

    def open_register_quick_write(self, reg_no: int, slave_addr: int = DEFAULT_BUS_ADDR):
        # Display-Modbus: bekannte Parameterregister erst nach geladenem Paket öffnen,
        # damit aktueller Wert/Klartext nicht leer oder alt ist. Warmlink/Standard
        # bleiben unverändert.
        if self.current_backend_key() == "display_modbus":
            try:
                wire_slave = self._wire_slave_addr(slave_addr)
                if int(wire_slave) == 0x03:
                    _user_addr, block_start, _mask = self._display_user_variable_for_param_reg(int(reg_no))
                    cb = lambda rn=int(reg_no), sa=int(slave_addr): self.open_register_quick_write(rn, sa)
                    if not self._display_wait_for_param_blocks_before_popup(f"Schnellschreiben {int(reg_no)}", [int(block_start)], cb):
                        return
            except Exception:
                pass
        key = (int(slave_addr), int(reg_no))
        dialog = self.register_write_dialogs.get(key)
        if dialog is None or not dialog.isVisible():
            dialog = RegisterQuickWriteDialog(self, reg_no, slave_addr)
            self.register_write_dialogs[key] = dialog
            dialog.finished.connect(lambda _=None, k=key: self.register_write_dialogs.pop(k, None))
            dialog.show()
        else:
            dialog.refresh_from_live()
            dialog.raise_()
            dialog.activateWindow()

    def _display_param_mask_for_block_start(self, start_addr: int) -> int:
        masks = {
            1001: 0x0002,
            1091: 0x0004,
            1181: 0x0008,
            1271: 0x0010,
            1361: 0x0020,
            1451: 0x0040,
            1541: 0x0080,
        }
        if int(start_addr) not in masks:
            raise ValueError(f"Kein 0BC3-Maskenbit für Paketstart {start_addr}")
        return masks[int(start_addr)]

    def _display_param_block_start_for_reg(self, reg_no: int) -> int:
        reg_no = int(reg_no)
        for start in (1001, 1091, 1181, 1271, 1361, 1451, 1541):
            if start <= reg_no <= start + 89:
                return start
        raise ValueError("Display-Paketwert aktuell nur für Paketblöcke 1001..1630 unterstützt")

    def _display_user_variable_for_param_reg(self, reg_no: int) -> tuple[int, int, int]:
        """Mappt einen normalen Paket-/Kommunikationswert auf die DWIN-Benutzervariable.

        Beobachtung/ASM Four_Variable_Communication:
          03F3H/03F4H... = Kommunikationswerte im 1001er Paket
          23F3H/23F4H... = Benutzer-/Displaywerte
          33F3H...       = Benutzer-Cache
          13F3H...       = Kommunikations-Cache

        Für Bedien-Simulation schreiben wir deshalb NICHT den Cache und NICHT
        den kompletten 90er Block, sondern nur die 23xx-Benutzervariable und
        danach das passende 0BC3-Modified-Flag.
        """
        reg_no = int(reg_no)
        block_start = self._display_param_block_start_for_reg(reg_no)
        if reg_no < block_start + 10:
            raise ValueError(
                f"Register {reg_no} liegt im Paketkopf {block_start}-{block_start + 9}. "
                "Für Display-Bedienung bitte einen Nutzwert ab +10 wählen, z.B. 1012."
            )
        return reg_no + 0x2000, block_start, self._display_param_mask_for_block_start(block_start)

    def _display_param_block_words_loaded(self, block_start: int) -> bool:
        """V0.2.41 PRIVATE: Prüft, ob ein Display-Parameterpaket schon im Speicher ist.

        Am Displaybus sind Dialoge wie Timer, AT-Kompensation und Parameterwrite
        auf frische 10xx/12xx/13xx/14xx/15xx-Pakete angewiesen. Sonst schreiben
        wir schnell mit alten/fehlenden Partnerwerten. Als geladen gilt entweder
        ein echter 90er-Snapshot von Unit 0x03 oder sichtbare Hauptfensterwerte
        aus demselben Paket.
        """
        try:
            start = int(block_start)
            for mode in ("read-response", "word-frame"):
                words = self.display_hmi_block_snapshots.get((0x03, start, mode))
                if words and len(words) >= 20:
                    return True
            # Hauptfensterwerte reichen als Fallback; +10 überspringt den Paketkopf.
            for reg_no in range(start + 10, start + 90):
                if reg_no in self.latest_regs or reg_no in self.last_values:
                    return True
        except Exception:
            pass
        return False

    def _display_missing_param_blocks(self, required_blocks: Optional[list[int]] = None) -> list[int]:
        blocks = required_blocks or [1001, 1091, 1181, 1271, 1361, 1451, 1541]
        missing: list[int] = []
        for block in blocks:
            try:
                block_i = int(block)
            except Exception:
                continue
            if not self._display_param_block_words_loaded(block_i):
                missing.append(block_i)
        return missing

    def _ensure_display_param_blocks_loaded_once(
        self,
        context: str,
        required_blocks: Optional[list[int]] = None,
        *,
        block_write: bool = False,
    ) -> bool:
        """Sichert Display-Modbus-Dialoge gegen fehlenden 10xx/12xx..15xx-Cache ab.

        Rückgabe True = benötigte Blöcke sind vorhanden oder Backend ist nicht Display.
        Rückgabe False = es wurde einmalig ein Init/Snapshot gestartet; aktuellen
        Schreibvorgang nicht senden und nach dem Init erneut versuchen.
        """
        if self.current_backend_key() != "display_modbus":
            return True
        missing = self._display_missing_param_blocks(required_blocks)
        if not missing:
            return True
        context_key = str(context or "Display-Parameter")
        missing_txt = ", ".join(f"{m}ff" for m in missing)
        message = (
            f"DISPLAY-INIT V0.2.41 ({context_key}): benötigte Parameterpakete fehlen noch: {missing_txt}. "
            "Ich starte einmal automatisch 'Alle bekannten Register lesen'. "
            "Bitte den Schreibvorgang nach dem Einlesen noch einmal ausführen."
        )
        self._log(message)
        if context_key not in self.display_param_init_prompted_contexts:
            self.display_param_init_prompted_contexts.add(context_key)
            try:
                QMessageBox.information(
                    self,
                    "Display-Parameter erst einlesen",
                    "Für diesen Display-Modbus-Schreibpfad fehlen noch Parameterpakete.\n\n"
                    f"Fehlend: {missing_txt}\n\n"
                    "Ich starte jetzt einmal automatisch 'Alle bekannten Register lesen'.\n"
                    "Danach den Schreibvorgang bitte noch einmal starten."
                )
            except Exception:
                pass
        try:
            self.send_init_reads()
        except Exception as exc:
            self._log(f"DISPLAY-INIT V0.2.41 ({context_key}): automatischer Init-Start fehlgeschlagen: {exc}")
        return False


    def _display_close_wait_message(self, key: str) -> None:
        """V0.2.41 fix5: modelosen Ladehinweis fuer Display-Popups schliessen."""
        try:
            msg = self.display_pending_popup_wait_messages.pop(str(key), None)
            if msg is not None:
                msg.close()
                msg.deleteLater()
        except Exception:
            pass

    def _display_show_wait_message(self, key: str, missing_txt: str) -> None:
        """V0.2.41 fix5: sofort sichtbarer Hinweis statt scheinbar nichts tun."""
        if self.current_backend_key() != "display_modbus":
            return
        key = str(key or "Display-Popup")
        if key in self.display_pending_popup_wait_messages:
            try:
                msg = self.display_pending_popup_wait_messages[key]
                msg.raise_()
                msg.activateWindow()
            except Exception:
                pass
            return
        try:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Lade Display-Werte")
            msg.setText(f"{key}: Lade Werte, bitte warten …")
            msg.setInformativeText(
                f"Fehlend: {missing_txt}\n\n"
                "Ich lese die benoetigten Display-Parameterpakete jetzt automatisch.\n"
                "Das Popup oeffnet sich danach selbst."
            )
            msg.setStandardButtons(QMessageBox.NoButton)
            msg.setWindowModality(Qt.NonModal)
            msg.show()
            self.display_pending_popup_wait_messages[key] = msg
        except Exception:
            pass

    def _display_wait_for_param_blocks_before_popup(
        self,
        context: str,
        required_blocks: list[int],
        retry_callback,
        *,
        timeout_s: float = 45.0,
        retry_ms: int = 1000,
    ) -> bool:
        """V0.2.41 fix5: Display-Popup erst nach geladenen Live-/Parameterwerten öffnen.

        Rückgabe True = Popup darf jetzt geöffnet werden.
        Rückgabe False = Snapshot läuft/weiter warten; retry_callback wird geplant.
        Nur im Backend "Modbus Display" aktiv. Warmlink/Standard-Modbus bleiben
        unverändert und öffnen Popups sofort.
        """
        if self.current_backend_key() != "display_modbus":
            return True
        key = str(context or "Display-Popup")
        missing = self._display_missing_param_blocks(required_blocks)
        snapshot_busy = bool(getattr(self, "display_fake_reboot_state", {}) and self.display_fake_reboot_state.get("active"))
        if not missing and not snapshot_busy:
            self.display_pending_popup_open_started.pop(key, None)
            self._display_close_wait_message(key)
            return True

        now = time.monotonic()
        started = float(self.display_pending_popup_open_started.get(key, 0.0) or 0.0)
        missing_txt = ", ".join(f"{m}ff" for m in missing)
        if snapshot_busy:
            if missing_txt:
                missing_txt += "; Snapshot/Displaybus noch beschaeftigt"
            else:
                missing_txt = "Snapshot/Displaybus noch beschaeftigt"

        # Sichtbarer Soforthinweis bei jedem Klick, falls noch kein Hinweis offen ist.
        # Damit wirkt der Button nicht mehr "tot", waehrend 1271ff/1181ff/... laden.
        # PRIVATE fix5: Auch wenn der benoetigte Block schon da ist, aber der
        # Reboot-Snapshot noch weitere Pakete liest, bleibt das Popup zu. Sonst
        # koennen direkte Writes in den laufenden Snapshot fallen und z.B. 0x24E8
        # ohne ACK verloren gehen.
        self._display_show_wait_message(key, missing_txt)

        if started <= 0.0:
            self.display_pending_popup_open_started[key] = now
            if missing:
                self._log(
                    f"DISPLAY-POPUP V0.2.41 fix5 ({key}): Werte fehlen noch ({missing_txt}). "
                    "Ich starte einmal den Snapshot und öffne das Popup automatisch, sobald die Werte da sind und der Displaybus frei ist."
                )
                try:
                    self.send_init_reads()
                except Exception as exc:
                    self._log(f"DISPLAY-POPUP V0.2.41 fix5 ({key}): automatischer Snapshot-Start fehlgeschlagen: {exc}")
            else:
                self._log(
                    f"DISPLAY-POPUP V0.2.41 fix5 ({key}): benötigte Werte sind da, "
                    "aber der Snapshot/Displaybus läuft noch. Popup öffnet automatisch, sobald der Bus frei ist."
                )
        elif now - started >= float(timeout_s):
            self.display_pending_popup_open_started.pop(key, None)
            self._display_close_wait_message(key)
            self._log(
                f"DISPLAY-POPUP V0.2.41 fix5 ({key}): Wartezeit abgelaufen ({missing_txt}). "
                "Popup wird trotzdem geöffnet; unbekannte Felder bleiben 0/--."
            )
            return True
        QTimer.singleShot(int(retry_ms), retry_callback)
        return False

    def _display_current_param_raw_value(self, reg_no: int) -> Optional[int]:
        """Liefert den aktuell bekannten Rohwert eines Display-Parameterregisters."""
        try:
            reg_i = int(reg_no)
            if reg_i in self.latest_regs:
                return int(getattr(self.latest_regs[reg_i], "raw_value", 0)) & 0xFFFF
            if reg_i in self.last_values:
                return int(self.last_values[reg_i]) & 0xFFFF
            block_start = self._display_param_block_start_for_reg(reg_i)
            offset = reg_i - block_start
            for mode in ("read-response", "word-frame"):
                words = self.display_hmi_block_snapshots.get((0x03, block_start, mode))
                if words and 0 <= offset < len(words):
                    return int(words[offset]) & 0xFFFF
        except Exception:
            return None
        return None

    def _display_user_write_variant(self) -> str:
        combo = getattr(self, "display_sim_variant_combo", None)
        if combo is None:
            return "A"
        try:
            variant = str(combo.currentData() or "A").strip().upper()
        except Exception:
            variant = "A"
        return variant if variant in {"A", "B", "C"} else "A"

    @staticmethod
    def _display_user_write_variant_text(variant: str) -> str:
        variant = str(variant or "A").strip().upper()
        if variant == "A":
            return "A: nur Benutzerwert (Register + 0x2000), Display soll 0BC3 selbst setzen"
        if variant == "C":
            return "C: Paketwert + Benutzerwert + 0BC3-Flag"
        return "B: Benutzerwert + 0BC3-Flag"

    def _display_user_write_plan(
        self,
        variant: str,
        target_reg: int,
        user_addr: int,
        target_value: int,
        block_start: int,
        mask: int,
    ) -> list[dict[str, Any]]:
        """Erzeugt die PRIVATE-Testvarianten für simulierte Display-Bedienung.

        A: nur 23xx-Benutzervariable schreiben. Damit testen wir, ob die echte
           Display-Logik das Modified-Flag selbst setzt.
        B: 23xx-Benutzervariable + 0BC3-Maske. Nur noch Fallback, falls
           das Display das Modified-Flag nicht selbst setzt.
        C: zusätzlich den 03xx/Paket-Kommunikationswert schreiben. Damit testen
           wir, ob der Master beim 1001-Read nur diesen Wert ausliest.
        """
        variant = str(variant or "A").strip().upper()
        target_reg = int(target_reg)
        user_addr = int(user_addr)
        target_value = int(target_value) & 0xFFFF
        block_start = int(block_start)
        mask = int(mask) & 0xFFFF
        steps: list[dict[str, Any]] = []
        if variant == "C":
            steps.append({
                "addr": target_reg,
                "value": target_value,
                "delay": 500,
                "label": f"Variante C Paketwert: Reg {target_reg}=0x{target_value:04X}",
            })
        steps.append({
            "addr": user_addr,
            "value": target_value,
            "delay": 700 if variant in {"B", "C"} else 0,
            "label": f"Variante {variant} Benutzerwert: User 0x{user_addr:04X}=0x{target_value:04X}",
        })
        if variant in {"B", "C"}:
            steps.append({
                "addr": 0x0BC3,
                "value": mask,
                "delay": 0,
                "label": f"Variante {variant} Änderungsflag Paket {block_start}: 0BC3=0x{mask:04X}",
            })
        return steps

    def _display_cached_param_block_words(self, start_addr: int, quantity: int = 90) -> tuple[Optional[list[int]], str]:
        start_addr = int(start_addr)
        quantity = int(quantity)

        # Beste Quelle: Roh-Snapshots direkt vom Display-Bus Unit 0x03. Diese wurden
        # beim echten Display-Reboot bzw. bei Display-Bedienung beobachtet.
        for mode in ("read-response", "word-frame"):
            words = self.display_hmi_block_snapshots.get((0x03, start_addr, mode))
            if words and len(words) >= quantity:
                return [int(v) & 0xFFFF for v in words[:quantity]], f"Display-Snapshot Unit 0x03/{start_addr}ff ({mode})"

        # Fallback: Hauptliste, falls die bekannten 10xx-Pakete bereits übernommen wurden.
        missing = []
        vals = []
        for reg_no in range(start_addr, start_addr + quantity):
            reg = self.latest_regs.get(reg_no)
            if reg is None:
                missing.append(reg_no)
                continue
            vals.append(int(reg.raw_value) & 0xFFFF)
        if not missing and len(vals) == quantity:
            return vals, f"Hauptliste {start_addr}-{start_addr + quantity - 1}"

        # Zweiter Fallback: getrennte Display-Diagnosewerte.
        missing = []
        vals = []
        for reg_no in range(start_addr, start_addr + quantity):
            reg = self.display_latest_regs.get(reg_no)
            if reg is None:
                missing.append(reg_no)
                continue
            vals.append(int(reg.raw_value) & 0xFFFF)
        if not missing and len(vals) == quantity:
            return vals, f"DREG/Display-Diagnose {start_addr}-{start_addr + quantity - 1}"

        return None, (
            f"Kein vollständiger Display-Paketblock {start_addr}-{start_addr + quantity - 1} im Cache. "
            "Erst warten, bis der Block durch Display-Reboot/Display-Bedienung/Display Reboot Fake gesehen wurde."
        )

    def _display_block_header_warning(self, start_addr: int, words: list[int]) -> str:
        if len(words) < 10:
            return "Block ist kürzer als 10 Wörter."
        expected_sig = [0x5746, 0x3232, 0x3130, 0x3235, 0x3034, 0x3735]
        warnings = []
        if words[:6] != expected_sig:
            warnings.append("Signatur WF2210250475 passt nicht")
        if (words[8] & 0xFFFF) != 0x0210:
            warnings.append(f"Marker-Länge W9 ist 0x{words[8] & 0xFFFF:04X}, erwartet 0x0210")
        if (words[9] & 0xFFFF) != int(start_addr):
            warnings.append(f"interner Start W10 ist {words[9] & 0xFFFF}, erwartet {start_addr}")
        return "; ".join(warnings)

    def _enqueue_display_write_block(self, start_addr: int, words: list[int], label: str = "", post_delay_ms: int = 0) -> bool:
        io_worker = self._active_io_worker()
        if io_worker is None:
            self._log("DISPLAY-BlockWRITE nicht gesendet: keine aktive Verbindung / kein aktiver Worker.")
            return False
        start_addr = int(start_addr)
        vals = [int(v) & 0xFFFF for v in words]
        frame = build_write_registers_frame(start_addr, vals, slave_addr=0x03)
        extra = f" ({label})" if label else ""
        preview = "; ".join(f"{start_addr + i}={v}/0x{v:04X}" for i, v in enumerate(vals[:12]))
        more = "" if len(vals) <= 12 else f" ... (+{len(vals) - 12})"
        self._log(
            f"DISPLAY-BlockWRITE wird GESENDET{extra}: Unit 0x03, start={start_addr}/0x{start_addr:04X}, "
            f"qty={len(vals)}, TX={hexdump(frame, -1)}; {preview}{more}"
        )
        io_worker.enqueue_write_block(start_addr, vals, slave_addr=0x03, post_delay_ms=post_delay_ms)
        return True

    def _enqueue_display_fc16_single(self, addr: int, value: int, label: str = "", post_delay_ms: int = 0) -> bool:
        io_worker = self._active_io_worker()
        if io_worker is None:
            self._log("DISPLAY-FC16 nicht gesendet: keine aktive Verbindung / kein aktiver Worker.")
            return False
        addr = int(addr)
        value = int(value) & 0xFFFF
        frame = build_write_frame(addr, value, slave_addr=0x03)
        extra = f" ({label})" if label else ""
        self._log(
            f"DISPLAY-FC16 wird GESENDET{extra}: Unit 0x03, addr={addr}/0x{addr:04X}, "
            f"value={value}/0x{value:04X}, TX={hexdump(frame, -1)}"
        )
        io_worker.enqueue_write(addr, value, slave_addr=0x03, post_delay_ms=post_delay_ms, write_single=False)
        return True

    def _apply_pending_write_ack(self, frame) -> bool:
        if getattr(frame, "mode", "") != "write-response":
            return False
        for req in list(getattr(self, "pending_write_requests", []) or []):
            if int(req.get("slave_addr", -1)) != int(getattr(frame, "slave_addr", -2)):
                continue
            if int(req.get("wire_addr", -1)) != int(getattr(frame, "typ", -2)):
                continue
            qty = int(getattr(frame, "length_field", 1) or 1)
            if qty != int(req.get("quantity", 1)):
                continue
            try:
                self.pending_write_requests.remove(req)
            except ValueError:
                pass
            label = str(req.get("label", ""))
            self._log(
                f"WRITE/ACK passt zu Anfrage ({label or 'ohne Label'}): "
                f"addr={int(req.get('addr', frame.typ))} / 0x{int(req.get('addr', frame.typ)):04X}, "
                f"wire=0x{int(req.get('wire_addr', frame.typ)):04X}"
            )
            if label.startswith("Popup Register"):
                key = (int(req.get("requested_slave_addr", req.get("slave_addr", DEFAULT_BUS_ADDR))), int(req.get("addr", -1)))
                dialog = getattr(self, "register_write_dialogs", {}).get(key)
                if dialog is not None and dialog.isVisible():
                    dialog.show_write_ack(int(req.get("wire_addr", frame.typ)), int(req.get("value", 0)))
            return True
        return False

    def _remember_display_write_ack(self, frame) -> None:
        """Merkt FC16-ACKs fuer die Display-PRIVATE-Tests.

        Die bisherigen Logs zeigen: gesendet reicht nicht. Der Wert wirkt erst
        zuverlaessig, wenn Unit 0x03 den FC16-Write als write-response quittiert.
        """
        try:
            if self.current_backend_key() != "display_modbus":
                return
            if getattr(frame, "mode", "") != "write-response":
                return
            slave = int(getattr(frame, "slave_addr", -1))
            addr = int(getattr(frame, "typ", -1))
            qty = int(getattr(frame, "length_field", 0) or 0)
            if slave < 0 or addr < 0 or qty <= 0:
                return
            now = time.monotonic()
            self.display_write_ack_times[(slave, addr, qty)] = now
            # Fuer Single-Register FC16 zusaetzlich normalisieren, falls ein Parser
            # die Menge anders liefert. Unsere Tests schreiben immer qty=1.
            if qty == 1:
                self.display_write_ack_times[(slave, addr, 1)] = now
        except Exception:
            return

    def _display_write_ack_time(self, addr: int, qty: int = 1, slave: int = 0x03) -> float:
        return float(self.display_write_ack_times.get((int(slave), int(addr), int(qty)), 0.0) or 0.0)

    def _display_write_ack_seen_since(self, addr: int, since: float, qty: int = 1, slave: int = 0x03) -> bool:
        return self._display_write_ack_time(addr, qty=qty, slave=slave) >= float(since or 0.0)

    def _display_snapshot_time(self, slave: int, start: int, mode: str) -> float:
        return float(self.display_hmi_block_snapshot_times.get((int(slave), int(start), str(mode)), 0.0) or 0.0)

    def _display_0bc3_value_from_3001(self) -> Optional[int]:
        for slave in (0x03, 0x02):
            words = self.display_hmi_block_snapshots.get((slave, 3001, "read-response"))
            if words and len(words) >= 11:
                return int(words[10]) & 0xFFFF  # 3001 + 10 = 3011 / 0BC3
        return None

    def _display_reboot_fresh_param_blocks(self, since: float) -> list[int]:
        starts = [1001, 1091, 1181, 1271, 1361, 1451]
        fresh: list[int] = []
        for start in starts:
            if (
                self._display_snapshot_time(0x03, start, "word-frame") >= since
                or self._display_snapshot_time(0x03, start, "read-response") >= since
            ):
                fresh.append(start)
        return fresh

    def send_display_fake_reboot(self, _checked: bool = False):
        """PRIVATE/Debug-Button: Reboot-Fake mit Bestätigung.

        fix12: Der sichtbare Testbereich ist ausgeblendet. Die gleiche Logik wird
        ohne Bestätigung über _start_display_reboot_snapshot() als Display-Standard
        für 'Alle bekannten Register lesen' und Popup-Aktualisierungen benutzt.
        """
        self._start_display_fake_reboot(prompt=True, source_label="Display Reboot Fake", force=True)

    def _start_display_reboot_snapshot(self, source_label: str = "Display Snapshot", force: bool = False) -> bool:
        """Startet den Reboot-Fake ohne Dialog als Display-Snapshot-Abfrage.

        Nur Backend 'Modbus Display'. Warmlink/Standard-Modbus werden nie berührt.
        force=True wird z.B. vom Button 'Alle bekannten Register lesen' verwendet.
        Popup-Leseanforderungen nutzen force=False und werden per Cooldown entprellt.
        """
        return self._start_display_fake_reboot(prompt=False, source_label=source_label, force=force)

    def _start_display_fake_reboot(self, prompt: bool = False, source_label: str = "Display Reboot Fake", force: bool = False) -> bool:
        if self.current_backend_key() != "display_modbus":
            if prompt:
                QMessageBox.warning(self, "Nur Modbus Display", "Display Reboot Fake ist nur im Backend 'Modbus Display' sinnvoll.")
            else:
                self._log(f"DISPLAY Reboot Fake fix11 ({source_label}): nicht gestartet, Backend ist nicht Modbus Display.")
            return False
        if self.display_fake_reboot_state.get("active"):
            msg = f"DISPLAY Reboot Fake fix11 ({source_label}): läuft bereits, Anfrage wird zusammengefasst."
            if prompt:
                QMessageBox.information(self, "Display Reboot Fake", "Ein Display-Reboot-Fake läuft bereits.")
            self._log(msg)
            return False
        io_worker = self._active_io_worker()
        if io_worker is None:
            # Normaler Display-Startpfad fuer Snapshot-Abfragen: falls die alte
            # Hauptverbindung nicht aktiv ist, den bewaehrten ausgelagerten
            # DisplayWorker starten und danach denselben Reboot-Fake ausloesen.
            if self.dual_logger_dialog is None:
                self.dual_logger_dialog = DualBusLoggerDialog(self)
                self.dual_logger_dialog.finished.connect(lambda _=None: setattr(self, "dual_logger_dialog", None))
            self.display_aux_takeover_active = True
            self.connected = True
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self._log(
                f"DISPLAY Reboot Fake fix11 ({source_label}): kein aktiver Display-Worker, "
                "starte DisplayWorker und sende danach automatisch."
            )
            try:
                self.dual_logger_dialog.start(display_only=True)
            except Exception as exc:
                self._log(f"DISPLAY Reboot Fake fix11 ({source_label}): DisplayWorker-Start fehlgeschlagen: {exc}")
                return False
            QTimer.singleShot(1400, lambda: self._start_display_fake_reboot(prompt=False, source_label=source_label, force=force))
            return True

        now = time.monotonic()
        if not force and self.display_fake_reboot_last_success_time > 0:
            age = now - float(self.display_fake_reboot_last_success_time)
            if age < 8.0:
                self._log(
                    f"DISPLAY-SNAPSHOT fix12 ({source_label}): letzter erfolgreicher Reboot-Snapshot "
                    f"ist erst {age:.1f}s alt ({self.display_fake_reboot_last_source or '-'}), kein neuer Start."
                )
                return False
        if prompt:
            frame_5112 = build_write_frame(0x5112, 0x0000, slave_addr=0x03)
            frame_0bc3 = build_write_frame(0x0BC3, 0x8000, slave_addr=0x03)
            question = (
                "Display Reboot Fake senden?\n\n"
                "fix11/fix8 ist ACK-gesteuert:\n"
                "1) 5112H = 0000H senden und auf ACK warten\n"
                "2) erst danach 0BC3H = 8000H senden und auf ACK/3001-Poll warten\n"
                "3) wenn 0BC3 nicht sichtbar wird, wird gezielt nur 0BC3 erneut gesendet\n"
                "4) danach warten bis frische 1001/1091/1181/1271/1361/1451-Blöcke kommen\n\n"
                f"TX 5112H: {hexdump(frame_5112, -1)}\n"
                f"TX 0BC3H: {hexdump(frame_0bc3, -1)}"
            )
            if not ask_yes_no(self, "Display Reboot Fake?", question, default_yes=False):
                self._log("Display Reboot Fake abgebrochen: nicht gesendet.")
                return False
        self.display_fake_reboot_state = {
            "active": True,
            "attempt": 0,
            "max_attempts": 3,
            "started": time.monotonic(),
            "attempt_started": 0.0,
            "phase": "idle",
            "5112_retries": 0,
            "flag_retries": 0,
            "last_send_addr": None,
            "last_send_time": 0.0,
            "source_label": str(source_label or "Display Reboot Fake"),
        }
        self._log(f"DISPLAY Reboot Fake fix11 ({source_label}): gestartet.")
        self._display_fake_reboot_attempt()
        return True

    def _display_fake_reboot_attempt(self):
        state = self.display_fake_reboot_state
        if not state.get("active"):
            return
        attempt = int(state.get("attempt", 0)) + 1
        state["attempt"] = attempt
        state["attempt_started"] = time.monotonic()
        state["5112_retries"] = 0
        state["flag_retries"] = 0
        self._log(f"DISPLAY Reboot Fake fix11: Versuch {attempt}/{state.get('max_attempts', 3)} gestartet.")
        self._display_fake_reboot_send_5112()

    def _display_fake_reboot_send_5112(self):
        state = self.display_fake_reboot_state
        if not state.get("active"):
            return
        state["phase"] = "wait_5112_ack"
        state["last_send_addr"] = 0x5112
        state["last_send_time"] = time.monotonic()
        retry = int(state.get("5112_retries", 0)) + 1
        state["5112_retries"] = retry
        self._enqueue_display_fc16_single(0x5112, 0x0000, f"Display Reboot Fake fix12: 5112H=0 ACK-Test {retry}")
        QTimer.singleShot(1600, self._display_fake_reboot_check_5112_ack)

    def _display_fake_reboot_check_5112_ack(self):
        state = self.display_fake_reboot_state
        if not state.get("active") or state.get("phase") != "wait_5112_ack":
            return
        sent_at = float(state.get("last_send_time", 0.0) or 0.0)
        if self._display_write_ack_seen_since(0x5112, sent_at):
            self._log("DISPLAY Reboot Fake fix11: ACK für 5112H gesehen, sende jetzt 0BC3H=8000H.")
            QTimer.singleShot(350, self._display_fake_reboot_send_flag)
            return
        if int(state.get("5112_retries", 0)) < 3:
            self._log("DISPLAY Reboot Fake fix11: kein ACK für 5112H, sende 5112H erneut.")
            self._display_fake_reboot_send_5112()
            return
        self._log("DISPLAY Reboot Fake fix11: kein ACK für 5112H nach 3 Versuchen; starte kompletten Versuch neu.")
        self._display_fake_reboot_retry_or_fail()

    def _display_fake_reboot_send_flag(self):
        state = self.display_fake_reboot_state
        if not state.get("active"):
            return
        state["phase"] = "wait_flag_ack"
        state["last_send_addr"] = 0x0BC3
        state["last_send_time"] = time.monotonic()
        retry = int(state.get("flag_retries", 0)) + 1
        state["flag_retries"] = retry
        self._enqueue_display_fc16_single(0x0BC3, 0x8000, f"Display Reboot Fake fix12: 0BC3H=8000H ACK-Test {retry}")
        QTimer.singleShot(1700, self._display_fake_reboot_check_flag_ack)

    def _display_fake_reboot_check_flag_ack(self):
        state = self.display_fake_reboot_state
        if not state.get("active") or state.get("phase") != "wait_flag_ack":
            return
        sent_at = float(state.get("last_send_time", 0.0) or 0.0)
        flag = self._display_0bc3_value_from_3001()
        if self._display_write_ack_seen_since(0x0BC3, sent_at) or flag == 0x8000:
            self._log(
                "DISPLAY Reboot Fake fix11: 0BC3H-ACK/Flag gesehen, warte auf 3001-Poll und Parameterblöcke."
            )
            state["phase"] = "wait_upload"
            state["upload_wait_started"] = time.monotonic()
            QTimer.singleShot(900, self._display_fake_reboot_check_upload)
            return
        if int(state.get("flag_retries", 0)) < 4:
            self._log("DISPLAY Reboot Fake fix11: kein ACK für 0BC3H, sende nur 0BC3H erneut.")
            self._display_fake_reboot_send_flag()
            return
        self._log("DISPLAY Reboot Fake fix11: kein ACK für 0BC3H nach mehreren Versuchen; starte kompletten Versuch neu.")
        self._display_fake_reboot_retry_or_fail()

    def _display_fake_reboot_check_upload(self):
        state = self.display_fake_reboot_state
        if not state.get("active") or state.get("phase") != "wait_upload":
            return
        since = float(state.get("attempt_started", 0.0) or 0.0)
        wait_started = float(state.get("upload_wait_started", since) or since)
        flag = self._display_0bc3_value_from_3001()
        fresh = self._display_reboot_fresh_param_blocks(since)
        if len(fresh) >= 4:
            source = str(state.get("source_label") or "Display Reboot Fake")
            self.display_fake_reboot_last_success_time = time.monotonic()
            self.display_fake_reboot_last_source = source
            self._log(
                "DISPLAY Reboot Fake fix11 ERFOLG: frische Parameterblöcke gesehen: "
                f"{fresh}; 0BC3 aktuell {('--' if flag is None else '0x%04X' % flag)}; Quelle={source}."
            )
            self.display_fake_reboot_state = {}
            return
        age = time.monotonic() - wait_started
        if flag == 0x8000:
            if age < 14.0:
                self._log(
                    "DISPLAY Reboot Fake fix11: 0BC3=0x8000 sichtbar, warte weiter auf Parameterblöcke "
                    f"(bisher {fresh or '-'})."
                )
                QTimer.singleShot(1200, self._display_fake_reboot_check_upload)
                return
        else:
            # Sobald der nächste 3001-Poll 0 statt 8000 zeigt, brauchen wir nicht 14s warten.
            # Dann ist das Flag nicht angekommen/übernommen: gezielt nur 0BC3 nachsetzen.
            if age >= 3.0 and int(state.get("flag_retries", 0)) < 5:
                self._log(
                    "DISPLAY Reboot Fake fix11: 3001-Poll zeigt 0BC3 nicht als 0x8000 "
                    f"({('--' if flag is None else '0x%04X' % flag)}), setze nur 0BC3 erneut."
                )
                self._display_fake_reboot_send_flag()
                return
            if age < 8.0:
                QTimer.singleShot(1000, self._display_fake_reboot_check_upload)
                return
        self._log(
            "DISPLAY Reboot Fake fix11: noch kein vollständiger Upload; "
            f"0BC3={('--' if flag is None else '0x%04X' % flag)}, frische Blöcke={fresh or '-'}"
        )
        self._display_fake_reboot_retry_or_fail()

    def _display_fake_reboot_retry_or_fail(self):
        state = self.display_fake_reboot_state
        if not state.get("active"):
            return
        attempt = int(state.get("attempt", 1))
        max_attempts = int(state.get("max_attempts", 3))
        if attempt < max_attempts:
            QTimer.singleShot(700, self._display_fake_reboot_attempt)
        else:
            self._log("DISPLAY Reboot Fake fix11 FEHLGESCHLAGEN: nach 3 Versuchen kein sicherer Parameter-Upload gesehen.")
            self.display_fake_reboot_state = {}

    def _display_read_range_intersects_param_packet(self, addr: int, quantity: int) -> bool:
        try:
            start = int(addr)
            end = start + max(1, int(quantity)) - 1
        except Exception:
            return False
        # Bekannte Display/WP-Parameterpakete. Header-Wörter zaehlen hier mit,
        # weil z.B. Backup/Parameterfenster bewusst komplette Bloecke anfordern.
        for block_start in (1001, 1091, 1181, 1271, 1361, 1451, 1541):
            block_end = block_start + 89
            if start <= block_end and end >= block_start:
                return True
        return False

    def _display_should_redirect_read_to_reboot_snapshot(
        self,
        addr: int,
        quantity: int,
        slave_addr: int,
        label: str = "",
    ) -> bool:
        """Entscheidet, ob ein Display-FC03-Read durch Reboot-Snapshot ersetzt wird.

        fix11: Nur normale UI-/Popup-Aktualisierungen. Manuelle FC03-Reads und
        die alte aktive Qty90-Forschung bleiben direkt möglich.
        """
        if self.current_backend_key() != "display_modbus":
            return False
        if not self._display_read_range_intersects_param_packet(addr, quantity):
            return False
        text = str(label or "").strip().lower()
        # Manuell/Direkt/Diagnose soll direkt lesbar bleiben, damit wir den
        # Qty90-Pfad weiter untersuchen koennen.
        direct_markers = (
            "manuell", "rechtsklick", "auto-poll", "offline", "display wp-paketblock",
            "display-init", "display pakettest", "direkt", "direct", "scan",
        )
        if any(marker in text for marker in direct_markers):
            return False
        # Diese Labels kommen aus normalen Popups/Arbeitsabläufen, die nur einen
        # aktuellen Parameter-Snapshot brauchen.
        popup_markers = (
            "popup register", "timer", "parameter", "backup", "restore", "sg ready",
            "silentmodus", "wp ein/aus", "wp steuerung", "at-komp", "kompensation",
        )
        if any(marker in text for marker in popup_markers):
            return True
        return False

    def _display_param_user_write_candidate(self, addr: int, slave_addr: int) -> Optional[tuple[int, int, int]]:
        """Erkennt normale Display-Parameterwerte, die per 23xx-Bedienpfad geschrieben werden sollen.

        fix9: Bei Backend "Modbus Display" sollen Rechtsklick/Popups die echten
        Parameterpakete nicht direkt beschreiben. Statt z.B. 1012=2 schreiben wir
        23F4=2. Die Display-Logik setzt danach 0BC3 selbst; nur falls das nicht
        passiert, setzt die ACK-State-Machine das Flag als Fallback.
        """
        if self.current_backend_key() != "display_modbus":
            return None
        info = self.regmap.get(int(addr))
        if not info or not str(getattr(info, "name", "") or "").strip():
            return None
        try:
            wire_slave = self._wire_slave_addr(slave_addr)
        except Exception:
            wire_slave = self.current_unit_id()
        # Der gefundene Bedienpfad gilt fuer das echte DWIN/HMI-Display Unit 0x03.
        if int(wire_slave) != 0x03:
            return None
        try:
            return self._display_user_variable_for_param_reg(int(addr))
        except Exception:
            return None

    def _display_user_value_make_job(
        self,
        target_reg: int,
        target_value: int,
        user_addr: int,
        block_start: int,
        mask: int,
        *,
        source_label: str = "",
        preferred_variant: str = "A",
        fallback_variants: Optional[list[str]] = None,
        delay_ms_after: int = 0,
        final_check_mode: str = "strict",
    ) -> dict[str, Any]:
        variant = str(preferred_variant or "A").strip().upper()
        if variant not in {"A", "B", "C"}:
            variant = "A"
        if fallback_variants is None:
            # Normalfall: echte Bedienung. A reicht inzwischen nachweislich; B/C nur Rettungsanker.
            fallback_variants = ["B", "C"] if variant == "A" else (["C"] if variant == "B" else [])
        fallback_variants = [str(v).strip().upper() for v in fallback_variants if str(v).strip().upper() in {"A", "B", "C"}]
        return {
            "active": True,
            "target_reg": int(target_reg),
            "user_addr": int(user_addr),
            "target_value": int(target_value) & 0xFFFF,
            "block_start": int(block_start),
            "mask": int(mask) & 0xFFFF,
            "requested_variant": variant,
            "variant": variant,
            "fallback_variants": fallback_variants,
            "fallback_used": False,
            "sequence_no": 0,
            "source_label": str(source_label or ""),
            "delay_ms_after": int(delay_ms_after or 0),
            "final_check_mode": str(final_check_mode or "strict").strip().lower(),
        }

    def _display_user_value_start_job(self, job: dict[str, Any]):
        self.display_user_value_state = dict(job)
        source = str(job.get("source_label") or "")
        suffix = f" ({source})" if source else ""
        self._log(
            "DISPLAY Parameterwrite fix9" + suffix + ": starte Bedienwertpfad "
            f"Reg {int(job['target_reg'])} -> User 0x{int(job['user_addr']):04X}, "
            f"Wert=0x{int(job['target_value']) & 0xFFFF:04X}, "
            f"Paket {int(job['block_start'])}, Maske 0x{int(job['mask']) & 0xFFFF:04X}."
        )
        self._display_user_value_start_sequence(str(job.get("variant") or "A"))

    def _display_user_value_start_next_queued(self):
        if self.display_user_value_state.get("active"):
            return
        if not self.display_user_value_queue:
            return
        job = self.display_user_value_queue.pop(0)
        self._display_user_value_start_job(job)

    def _display_user_value_complete_current(self, success: bool):
        state = dict(self.display_user_value_state or {})
        delay_ms = max(0, int(state.get("delay_ms_after", 0) or 0))
        queued = len(self.display_user_value_queue)
        source = str(state.get("source_label") or "")
        if queued:
            self._log(
                f"DISPLAY Parameterwrite fix9: {'erfolgreich' if success else 'fehlgeschlagen'}, "
                f"starte naechsten queued Write in {max(delay_ms, 150)} ms "
                f"({queued} verbleibend)."
            )
        self.display_user_value_state = {}
        if queued:
            QTimer.singleShot(max(delay_ms, 150), self._display_user_value_start_next_queued)
        elif source:
            # Kurzer Abschluss nur fuer normale Popups/Rechtsklicks; Experimente loggen ohnehin detailliert.
            self._log(f"DISPLAY Parameterwrite fix9 ({source}): {'fertig' if success else 'ohne sicheren Erfolg beendet'}.")

    def _queue_display_param_user_write_from_normal(
        self,
        addr: int,
        value: int,
        slave_addr: int,
        label: str = "",
        delay_ms: int = 0,
    ) -> bool:
        candidate = self._display_param_user_write_candidate(addr, slave_addr)
        if candidate is None:
            return False
        user_addr, block_start, mask = candidate
        if not self._ensure_display_param_blocks_loaded_once(label or f"Write {addr}", [int(block_start)], block_write=False):
            # Wichtig: True zurückgeben, damit der normale Direktwrite am Displaybus
            # NICHT versehentlich trotzdem ausgeführt wird.
            self._log(
                f"DISPLAY Parameterwrite V0.2.41 ({label or addr}): Write noch nicht gesendet, "
                "erst Parameterpaket einlesen und danach erneut starten."
            )
            return True
        job = self._display_user_value_make_job(
            int(addr),
            int(value) & 0xFFFF,
            int(user_addr),
            int(block_start),
            int(mask),
            source_label=(label or f"normaler Write {addr}"),
            preferred_variant="B",
            fallback_variants=[],
            delay_ms_after=int(delay_ms or 0),
            final_check_mode="passive",
        )
        self.display_user_value_queue.append(job)
        qpos = len(self.display_user_value_queue)
        extra = f" ({label})" if label else ""
        self._log(
            f"DISPLAY Parameterwrite fix4{extra}: normaler Write Reg {addr}=0x{int(value) & 0xFFFF:04X} "
            f"wird als Bedienwert User 0x{int(user_addr):04X} ausgefuehrt; "
            f"B (Benutzerwert + 0BC3) ohne blockierenden Abschlusscheck; Ergebnis nur passiv im Log; Queue-Position {qpos}."
        )
        self._display_user_value_start_next_queued()
        return True

    def send_display_simulated_mode(self, mode_value: int):
        self.display_sim_reg_edit.setText("1012")
        self.display_sim_value_edit.setText(str(int(mode_value)))
        self.send_display_simulated_user_value_from_fields()

    def send_display_simulated_user_value_from_fields(self):
        if self.current_backend_key() != "display_modbus":
            QMessageBox.warning(self, "Nur Modbus Display", "Display-Wert simulieren ist nur im Backend 'Modbus Display' sinnvoll.")
            return
        if self.display_user_value_state.get("active"):
            QMessageBox.information(self, "Display-Wert-Test", "Ein Display-Wert-Test läuft bereits.")
            return
        try:
            target_reg = self._parse_int_text(self.display_sim_reg_edit.text())
            target_value = self._parse_int_text(self.display_sim_value_edit.text()) & 0xFFFF
            user_addr, block_start, mask = self._display_user_variable_for_param_reg(target_reg)
        except Exception as exc:
            QMessageBox.warning(self, "Ungültiger Display-Wert", str(exc))
            return

        variant = self._display_user_write_variant()
        plan = self._display_user_write_plan(variant, target_reg, user_addr, target_value, block_start, mask)

        old_value_text = "--"
        words, source = self._display_cached_param_block_words(block_start, 90)
        if words and 0 <= (target_reg - block_start) < len(words):
            old_value = int(words[target_reg - block_start]) & 0xFFFF
            old_value_text = f"{old_value}/0x{old_value:04X} aus {source}"

        reg_info = self.regmap.get(target_reg)
        reg_name = f" - {reg_info.name}" if reg_info and reg_info.name else ""
        step_lines = []
        for step in plan:
            addr = int(step["addr"])
            value = int(step["value"]) & 0xFFFF
            frame = build_write_frame(addr, value, slave_addr=0x03)
            step_lines.append(
                f"- 0x{addr:04X} / {addr} = 0x{value:04X}  TX: {hexdump(frame, -1)}"
            )
        fallback_variants = ["B", "C"] if variant == "A" else (["C"] if variant == "B" else [])
        question = (
            "Display-Wert-Test senden?\n\n"
            "fix9 sendet ACK-gesteuert. Default A schreibt nur den 23xx-Benutzerwert; "
            "wenn das Display 0BC3 nicht selbst setzt, folgt automatisch Fallback B/C.\n\n"
            f"Variante: {self._display_user_write_variant_text(variant)}\n"
            f"Auto-Fallback: {(' -> '.join([variant] + fallback_variants)) if fallback_variants else 'aus'}\n"
            f"Ziel: Register {target_reg}{reg_name}\n"
            f"Alter Paketwert: {old_value_text}\n"
            f"Neuer Wert: {target_value}/0x{target_value:04X}\n"
            f"Benutzervariable: 0x{user_addr:04X} / {user_addr} = Register + 0x2000\n"
            f"Modified-Flag für Paket {block_start}: 0BC3H = {mask:04X}H\n\n"
            "Geplante Writes fuer die Startvariante:\n" + "\n".join(step_lines)
        )
        if not ask_yes_no(self, "Display-Wert-Test?", question, default_yes=False):
            self._log("Display-Wert-Test abgebrochen: nicht gesendet.")
            return

        job = self._display_user_value_make_job(
            target_reg, target_value, user_addr, block_start, mask,
            source_label="Display-Wert-Test",
            preferred_variant=variant,
            fallback_variants=fallback_variants,
        )
        self._display_user_value_start_job(job)

    def _display_user_value_start_sequence(self, variant: str):
        state = self.display_user_value_state
        if not state.get("active"):
            return
        variant = str(variant or "A").strip().upper()
        target_reg = int(state.get("target_reg", 0) or 0)
        user_addr = int(state.get("user_addr", 0) or 0)
        target_value = int(state.get("target_value", 0) or 0) & 0xFFFF
        block_start = int(state.get("block_start", 0) or 0)
        mask = int(state.get("mask", 0) or 0) & 0xFFFF
        plan = self._display_user_write_plan(variant, target_reg, user_addr, target_value, block_start, mask)
        seq = int(state.get("sequence_no", 0)) + 1
        state.update({
            "variant": variant,
            "plan": plan,
            "step_index": 0,
            "step_retries": 0,
            "flag_resends": 0,
            "sequence_no": seq,
            "sequence_started": time.monotonic(),
            "phase": "write_steps",
        })
        fallback_txt = " (Fallback)" if state.get("fallback_used") else ""
        self._log(
            f"DISPLAY Bedienwert fix9{fallback_txt}: starte Variante {variant} für Reg {target_reg}=0x{target_value:04X} "
            f"(User 0x{user_addr:04X}, Paket {block_start}, Maske 0x{mask:04X})."
        )
        self._display_user_value_send_current_step()

    def _display_user_value_send_current_step(self):
        state = self.display_user_value_state
        if not state.get("active"):
            return
        plan = list(state.get("plan") or [])
        idx = int(state.get("step_index", 0) or 0)
        if idx >= len(plan):
            state["phase"] = "wait_result"
            state["result_wait_started"] = time.monotonic()
            if str(state.get("final_check_mode") or "strict").lower() in {"log", "passive", "background"}:
                # V0.2.44 fix4: normale Rechtsklick-/Popup-Writes sollen nach dem
                # eigentlichen Senden/ACK nicht mehr auf Readback/Master-Read blockieren.
                # Der Abschlusscheck laeuft nur noch passiv ins Log.
                passive_state = dict(state)
                self._log(
                    "DISPLAY Bedienwert fix4: alle Writes quittiert/abgesetzt; "
                    "abschliessender 3001-/Readback-Check laeuft nur noch passiv im Log."
                )
                self._display_user_value_complete_current(True)
                QTimer.singleShot(2500, lambda st=passive_state: self._display_user_value_passive_check(st, 1))
                return
            self._log("DISPLAY Bedienwert fix9: alle Writes quittiert/abgesetzt, warte auf 3001-Flag und Master-Read.")
            QTimer.singleShot(900, self._display_user_value_check)
            return
        step = dict(plan[idx])
        retry = int(state.get("step_retries", 0) or 0) + 1
        state["step_retries"] = retry
        state["current_step_addr"] = int(step["addr"])
        state["current_step_value"] = int(step["value"]) & 0xFFFF
        state["current_step_label"] = str(step.get("label") or "")
        state["current_step_delay"] = int(step.get("delay") or 0)
        state["current_step_sent_at"] = time.monotonic()
        self._enqueue_display_fc16_single(
            int(step["addr"]),
            int(step["value"]),
            f"fix9 ACK Schritt {idx + 1}/{len(plan)} Versuch {retry}: {step.get('label') or ''}",
            post_delay_ms=0,
        )
        QTimer.singleShot(1500, self._display_user_value_check_step_ack)

    def _display_user_value_check_step_ack(self):
        state = self.display_user_value_state
        if not state.get("active") or state.get("phase") != "write_steps":
            return
        addr = int(state.get("current_step_addr", 0) or 0)
        sent_at = float(state.get("current_step_sent_at", 0.0) or 0.0)
        idx = int(state.get("step_index", 0) or 0)
        plan = list(state.get("plan") or [])
        if self._display_write_ack_seen_since(addr, sent_at):
            self._log(
                f"DISPLAY Bedienwert fix9: ACK für Schritt {idx + 1}/{len(plan)} "
                f"Addr 0x{addr:04X} gesehen."
            )
            state["step_index"] = idx + 1
            state["step_retries"] = 0
            delay = max(150, int(state.get("current_step_delay", 0) or 0))
            QTimer.singleShot(delay, self._display_user_value_send_current_step)
            return
        retry = int(state.get("step_retries", 0) or 0)
        max_retry = 4 if addr == 0x0BC3 else 3
        if retry < max_retry:
            self._log(
                f"DISPLAY Bedienwert fix9: kein ACK für Addr 0x{addr:04X}, wiederhole Schritt {idx + 1}."
            )
            self._display_user_value_send_current_step()
            return
        # Wenn nur das Flag-ACK fehlt, kann es trotzdem beim nächsten 3001-Poll sichtbar sein.
        if addr == 0x0BC3 and self._display_0bc3_value_from_3001() == int(state.get("mask", 0)):
            self._log("DISPLAY Bedienwert fix9: kein ACK für 0BC3, aber Flag ist sichtbar; warte auf Master-Read.")
            state["step_index"] = idx + 1
            state["step_retries"] = 0
            QTimer.singleShot(200, self._display_user_value_send_current_step)
            return
        self._log(f"DISPLAY Bedienwert fix9: Schritt {idx + 1} Addr 0x{addr:04X} ohne ACK fehlgeschlagen.")
        self._display_user_value_fail_or_fallback()

    def _display_user_value_passive_check(self, state_snapshot: dict[str, Any], attempt: int = 1):
        """Nur loggender Abschlusscheck fuer normale Display-Rechtsklick-/Popup-Writes."""
        try:
            block_start = int(state_snapshot.get("block_start", 0) or 0)
            target_reg = int(state_snapshot.get("target_reg", 0) or 0)
            target_value = int(state_snapshot.get("target_value", 0) or 0) & 0xFFFF
            mask = int(state_snapshot.get("mask", 0) or 0) & 0xFFFF
            sequence_started = float(state_snapshot.get("sequence_started", 0.0) or 0.0)
            flag = self._display_0bc3_value_from_3001()
            fresh_time = max(
                self._display_snapshot_time(0x03, block_start, "read-response"),
                self._display_snapshot_time(0x03, block_start, "word-frame"),
            )
            if fresh_time >= sequence_started:
                words = None
                for mode in ("read-response", "word-frame"):
                    candidate = self.display_hmi_block_snapshots.get((0x03, block_start, mode))
                    if candidate and self._display_snapshot_time(0x03, block_start, mode) >= sequence_started:
                        words = candidate
                        break
                read_value = None
                if words and 0 <= (target_reg - block_start) < len(words):
                    read_value = int(words[target_reg - block_start]) & 0xFFFF
                if read_value == target_value:
                    self._log(
                        f"DISPLAY Bedienwert fix4 PASSIV OK: Paket {block_start} frisch gesehen, "
                        f"{target_reg}=0x{read_value:04X}; 0BC3={('--' if flag is None else '0x%04X' % flag)}."
                    )
                else:
                    self._log(
                        f"DISPLAY Bedienwert fix4 PASSIV HINWEIS: Paket {block_start} frisch gesehen, "
                        f"{target_reg}={('--' if read_value is None else '0x%04X' % read_value)} statt 0x{target_value:04X}; "
                        f"0BC3={('--' if flag is None else '0x%04X' % flag)}."
                    )
                return
            if attempt < 3:
                QTimer.singleShot(3500, lambda st=dict(state_snapshot), a=attempt + 1: self._display_user_value_passive_check(st, a))
                return
            self._log(
                f"DISPLAY Bedienwert fix4 PASSIV: kein frischer Paketblock {block_start} gesehen; "
                f"0BC3={('--' if flag is None else '0x%04X' % flag)}, erwartet Maske 0x{mask:04X}."
            )
        except Exception as exc:
            self._log(f"DISPLAY Bedienwert fix4 PASSIV: Abschlusscheck uebersprungen: {exc}")

    def _display_user_value_check(self):
        state = self.display_user_value_state
        if not state.get("active"):
            return
        sequence_started = float(state.get("sequence_started", 0.0) or 0.0)
        wait_started = float(state.get("result_wait_started", sequence_started) or sequence_started)
        block_start = int(state.get("block_start", 0) or 0)
        target_reg = int(state.get("target_reg", 0) or 0)
        target_value = int(state.get("target_value", 0) or 0) & 0xFFFF
        mask = int(state.get("mask", 0) or 0) & 0xFFFF
        flag = self._display_0bc3_value_from_3001()
        fresh_time = max(
            self._display_snapshot_time(0x03, block_start, "read-response"),
            self._display_snapshot_time(0x03, block_start, "word-frame"),
        )
        if fresh_time >= sequence_started:
            words = None
            for mode in ("read-response", "word-frame"):
                candidate = self.display_hmi_block_snapshots.get((0x03, block_start, mode))
                if candidate and self._display_snapshot_time(0x03, block_start, mode) >= sequence_started:
                    words = candidate
                    break
            read_value = None
            if words and 0 <= (target_reg - block_start) < len(words):
                read_value = int(words[target_reg - block_start]) & 0xFFFF
            if read_value == target_value:
                self._log(
                    f"DISPLAY Bedienwert fix9 ERFOLG: Master/Bus hat Paket {block_start} frisch gesehen, "
                    f"{target_reg}=0x{read_value:04X}; 0BC3 aktuell {('--' if flag is None else '0x%04X' % flag)}."
                )
                self._display_user_value_complete_current(True)
                return
            self._log(
                f"DISPLAY Bedienwert fix9: Paket {block_start} wurde frisch gesehen, aber {target_reg}="
                f"{('--' if read_value is None else '0x%04X' % read_value)} statt 0x{target_value:04X}; "
                f"0BC3={('--' if flag is None else '0x%04X' % flag)}."
            )
            self._display_user_value_fail_or_fallback()
            return

        age = time.monotonic() - wait_started
        if flag == mask:
            if age < 15.0:
                self._log(
                    f"DISPLAY Bedienwert fix9: 0BC3=0x{flag:04X} sichtbar, warte auf Master-Read/Paket {block_start}."
                )
                QTimer.singleShot(1200, self._display_user_value_check)
                return
        else:
            # Wenn der naechste 3001-Poll weiterhin 0 zeigt, ist das Flag nicht angekommen.
            # Dann nicht 14s warten, sondern nur 0BC3 erneut setzen.
            # Variante A darf erst einmal abwarten: Das echte Display setzt 0BC3 oft erst
            # beim naechsten 3001-Zyklus selbst. Erst danach setzen wir das Flag als Fallback.
            resend_after = 5.5 if str(state.get("variant", "A")).upper() == "A" and int(state.get("flag_resends", 0) or 0) == 0 else 3.0
            if age >= resend_after and int(state.get("flag_resends", 0) or 0) < 4:
                state["flag_resends"] = int(state.get("flag_resends", 0) or 0) + 1
                state["phase"] = "write_steps"
                plan = [{
                    "addr": 0x0BC3,
                    "value": mask,
                    "delay": 0,
                    "label": f"fix9 Nachsetzen 0BC3=0x{mask:04X}",
                }]
                state["plan"] = plan
                state["step_index"] = 0
                state["step_retries"] = 0
                self._log(
                    f"DISPLAY Bedienwert fix9: 3001 zeigt 0BC3 nicht als 0x{mask:04X} "
                    f"({('--' if flag is None else '0x%04X' % flag)}), setze nur 0BC3 erneut."
                )
                self._display_user_value_send_current_step()
                return
            if age < 7.0:
                QTimer.singleShot(1000, self._display_user_value_check)
                return

        self._log(
            "DISPLAY Bedienwert fix9: kein frischer Paketblock gesehen. "
            f"0BC3={('--' if flag is None else '0x%04X' % flag)}."
        )
        self._display_user_value_fail_or_fallback()

    def _display_user_value_fail_or_fallback(self):
        state = self.display_user_value_state
        if not state.get("active"):
            return
        variant = str(state.get("variant", "A")).upper()
        fallbacks = list(state.get("fallback_variants") or [])
        if fallbacks:
            next_variant = str(fallbacks.pop(0)).upper()
            state["fallback_variants"] = fallbacks
            state["fallback_used"] = True
            self._log(
                f"DISPLAY Bedienwert fix9: Variante {variant} hat nicht sicher gegriffen, "
                f"starte automatisch Fallback Variante {next_variant}."
            )
            QTimer.singleShot(700, lambda v=next_variant: self._display_user_value_start_sequence(v))
            return
        self._log("DISPLAY Bedienwert fix9 FEHLGESCHLAGEN: kein sicherer Master-Read/keine Zielwert-Übernahme gesehen.")
        self._display_user_value_complete_current(False)

    def send_register_write(self, addr: int, value: int, slave_addr: int = DEFAULT_BUS_ADDR, label: str = "", delay_ms: int = 0):
        # fix9: Im Display-Backend werden bekannte Parameterpaket-Nutzwerte wie echte
        # Display-Bedienung geschrieben: Reg 1012 -> 23F4, ACK-gesteuert, ohne Extra-Dialog.
        if self._queue_display_param_user_write_from_normal(addr, value, slave_addr, label=label, delay_ms=delay_ms):
            return
        frame, wire_addr, wire_slave, note, fc_text = self._build_write_frame_for_backend(addr, value, slave_addr)
        info = self.regmap.get(addr)
        known = f" | {info.name} [{info.dtype}]" if info and info.name else ""
        extra = f" ({label})" if label else ""
        note_text = f" | {note}" if note else ""
        self._log(
            f"WRITE wird GESENDET{extra} [{self.current_backend_label()} / {fc_text}]: bus=0x{wire_slave:02X}, "
            f"addr={addr}/0x{addr:04X} -> wire={wire_addr}/0x{wire_addr:04X}, "
            f"value={value}/0x{value:04X}, signed={s16(value)}, /10={s16(value)/10.0:.1f}, "
            f"TX={hexdump(frame, -1)}{known}{note_text}"
        )
        io_worker = self._active_io_worker()
        if io_worker is None:
            self._log("WRITE nicht gesendet: keine aktive Verbindung / kein aktiver Worker.")
            return
        if label:
            self.pending_write_requests.append({
                "slave_addr": int(wire_slave),
                "requested_slave_addr": int(slave_addr),
                "addr": int(addr),
                "wire_addr": int(wire_addr),
                "quantity": 1,
                "value": int(value) & 0xFFFF,
                "label": str(label),
                "time": time.time(),
            })
            if len(self.pending_write_requests) > 100:
                del self.pending_write_requests[:len(self.pending_write_requests) - 100]
        io_worker.enqueue_write(wire_addr, value, slave_addr=wire_slave, post_delay_ms=delay_ms, write_single=self._write_single_for_backend())

    def show_write_frame(self):
        try:
            slave_addr = self._parse_int_text(self.write_bus_edit.text())
            addr = self._parse_int_text(self.write_addr_edit.text())
            value = self._parse_int_text(self.write_value_edit.text())
            frame, wire_addr, wire_slave, note, fc_text = self._build_write_frame_for_backend(addr, value, slave_addr)
            info = self.regmap.get(addr)
            known = f"\nRegister: {info.name} [{info.dtype}]" if info.name else ""
            note_text = f" | {note}" if note else ""
            self._log(
                f"WRITE Dry-Run [{self.current_backend_label()} / {fc_text}]: bus=0x{wire_slave:02X}, "
                f"addr={addr}/0x{addr:04X} -> wire={wire_addr}/0x{wire_addr:04X}, "
                f"value={value}/0x{value:04X}, signed={s16(value)}, /10={s16(value)/10.0:.1f}, "
                f"TX={hexdump(frame, -1)}{known}{note_text}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Eingabe", str(exc))

    def send_write_frame(self):
        try:
            slave_addr = self._parse_int_text(self.write_bus_edit.text())
            addr = self._parse_int_text(self.write_addr_edit.text())
            value = self._parse_int_text(self.write_value_edit.text())
            frame, wire_addr, wire_slave, note, fc_text = self._build_write_frame_for_backend(addr, value, slave_addr)
            info = self.regmap.get(addr)
            known = f"\nRegister: {info.name} [{info.dtype}]" if info.name else ""
            note_text = f"\n{note}" if note else ""

            question = (
                f"Backend: {self.current_backend_label()} / {fc_text}\n"
                f"Bus 0x{wire_slave:02X}, Register {addr} / 0x{addr:04X} wirklich schreiben?\n"
                f"Wire-Adresse: {wire_addr} / 0x{wire_addr:04X}{note_text}\n\n"
                f"Wert: {value} / 0x{value:04X} / signed={s16(value)} / /10={s16(value)/10.0:.1f}\n"
                f"Frame: {hexdump(frame, -1)}"
                f"{known}"
            )

            if not ask_yes_no(self, "ECHTEN Write senden?", question, default_yes=False):
                self._log("WRITE abgebrochen: nicht gesendet.")
                return

            self._log(
                f"WRITE wird GESENDET [{self.current_backend_label()} / {fc_text}]: bus=0x{wire_slave:02X}, "
                f"addr={addr}/0x{addr:04X} -> wire={wire_addr}/0x{wire_addr:04X}, "
                f"value={value}/0x{value:04X}, TX={hexdump(frame, -1)}"
            )
            io_worker = self._active_io_worker()
            if io_worker is None:
                self._log("WRITE nicht gesendet: keine aktive Verbindung / kein aktiver Worker.")
                return
            io_worker.enqueue_write(wire_addr, value, slave_addr=wire_slave, write_single=self._write_single_for_backend())
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Eingabe", str(exc))

    def open_timer_editor(self):
        # V0.2.41 fix5: Timer-Popup am Displaybus erst öffnen, wenn 1271ff
        # wirklich geladen ist. Sonst waren die Felder beim Öffnen noch 0 bzw.
        # ältere Defaults und Mehrfachwrites konnten falsche Partnerwerte nutzen.
        if not self._display_wait_for_param_blocks_before_popup("Timer 1-6", [1271], self.open_timer_editor):
            return
        if self.timer_dialog is None or not self.timer_dialog.isVisible():
            self.timer_dialog = TimerEditorDialog(self)
            self.timer_dialog.finished.connect(lambda _=None: setattr(self, "timer_dialog", None))
            self.timer_dialog.show()
        else:
            self.timer_dialog.load_from_live_values()
            self.timer_dialog.raise_()
            self.timer_dialog.activateWindow()

    def open_onoff_timer_editor(self):
        if not self._display_wait_for_param_blocks_before_popup("WP Ein/Aus Timer", [1181], self.open_onoff_timer_editor):
            return
        if self.onoff_timer_dialog is None or not self.onoff_timer_dialog.isVisible():
            self.onoff_timer_dialog = OnOffTimerEditorDialog(self)
            self.onoff_timer_dialog.finished.connect(lambda _=None: setattr(self, "onoff_timer_dialog", None))
            self.onoff_timer_dialog.show()
        else:
            self.onoff_timer_dialog.load_from_live_values()
            self.onoff_timer_dialog.raise_()
            self.onoff_timer_dialog.activateWindow()

    def open_silent_timer_editor(self):
        if not self._display_wait_for_param_blocks_before_popup("Silentmodus Timer", [1181], self.open_silent_timer_editor):
            return
        if self.silent_timer_dialog is None or not self.silent_timer_dialog.isVisible():
            self.silent_timer_dialog = SilentTimerDialog(self)
            self.silent_timer_dialog.finished.connect(lambda _=None: setattr(self, "silent_timer_dialog", None))
            self.silent_timer_dialog.show()
        else:
            self.silent_timer_dialog.load_from_live_values()
            self.silent_timer_dialog.raise_()
            self.silent_timer_dialog.activateWindow()

    def open_sg_editor(self):
        if not self._display_wait_for_param_blocks_before_popup("SG Ready", [1271], self.open_sg_editor):
            return
        if self.sg_dialog is None or not self.sg_dialog.isVisible():
            self.sg_dialog = SGReadyEditorDialog(self)
            self.sg_dialog.finished.connect(lambda _=None: setattr(self, "sg_dialog", None))
            self.sg_dialog.show()
        else:
            self.sg_dialog.load_from_live_values()
            self.sg_dialog.raise_()
            self.sg_dialog.activateWindow()


    def open_wp_control(self):
        # WP-Steuerung nutzt im Display-Modus u.a. 1011/1012/1016 und 1157-1159.
        # Deshalb warten wir dort auf Paket 1001ff und 1091ff; andere Backends öffnen sofort.
        if not self._display_wait_for_param_blocks_before_popup("WP-Steuerung", [1001, 1091], self.open_wp_control):
            return
        if self.wp_control_dialog is None or not self.wp_control_dialog.isVisible():
            self.wp_control_dialog = WPControlDialog(self)
            self.wp_control_dialog.finished.connect(lambda _=None: setattr(self, "wp_control_dialog", None))
            self.wp_control_dialog.show()
        else:
            self.wp_control_dialog.refresh_from_live()
            self.wp_control_dialog.raise_()
            self.wp_control_dialog.activateWindow()

    def open_at_compensation(self):
        # AT-Kompensation liegt im Paket 1181ff (1234-1236).
        if not self._display_wait_for_param_blocks_before_popup("AT-Kompensation", [1181], self.open_at_compensation):
            return
        if self.at_comp_dialog is None or not self.at_comp_dialog.isVisible():
            self.at_comp_dialog = ATCompensationDialog(self)
            self.at_comp_dialog.finished.connect(lambda _=None: setattr(self, "at_comp_dialog", None))
            self.at_comp_dialog.show()
        else:
            self.at_comp_dialog.refresh_from_live()
            self.at_comp_dialog.raise_()
            self.at_comp_dialog.activateWindow()

    def open_parameter_settings(self):
        # Parameteransicht kann alle Paketbereiche betreffen.
        if not self._display_wait_for_param_blocks_before_popup("Parameter Einstellungen", [1001, 1091, 1181, 1271, 1361, 1451, 1541], self.open_parameter_settings):
            return
        if self.parameter_dialog is None or not self.parameter_dialog.isVisible():
            self.parameter_dialog = ParameterSettingsDialog(self)
            self.parameter_dialog.finished.connect(lambda _=None: setattr(self, "parameter_dialog", None))
            self.parameter_dialog.show()
        else:
            self.parameter_dialog.refresh_table()
            self.parameter_dialog.raise_()
            self.parameter_dialog.activateWindow()

    def _display_timer_batch_plan(self, values: list[tuple[int, int, str]], slave_addr: int) -> Optional[list[dict[str, Any]]]:
        """V0.2.41 PRIVATE: Mehrfachwrites von Timer/SG/Popup-Pfaden im Displaybus planen.

        Der alte Pfad schrieb direkt 1281..1287/1323 per FC06/FC16 auf Unit 0x03.
        Am Displaybus muessen normale Parameter-/Bedienwerte jedoch als DWIN-
        Benutzervariable (Register + 0x2000) geschrieben werden. Anschliessend
        wird fuer den betroffenen 90er-Paketblock 0BC3 mit der passenden Maske
        gesetzt, damit der echte Master das Paket uebernimmt.
        """
        if self.current_backend_key() != "display_modbus":
            return None
        try:
            wire_slave = self._wire_slave_addr(slave_addr)
        except Exception:
            wire_slave = self.current_unit_id()
        if int(wire_slave) != 0x03:
            return None

        required_blocks: list[int] = []
        for addr, _value, _label in values:
            try:
                block_start = self._display_param_block_start_for_reg(int(addr))
            except Exception:
                return None
            if block_start not in required_blocks:
                required_blocks.append(block_start)
        # V0.2.41 fix5: Timer-/Popup-Schreiben nicht hart blockieren, wenn der
        # Paket-Cache noch fehlt. Die Werte kommen aus dem geöffneten Dialog. Wir
        # starten den Snapshot weiterhin als Hilfe, lassen den aktuellen Write aber
        # weiterlaufen. In V0.2.41 blieb der eigentliche Timer-Write sonst an der
        # vorgeschalteten 1271ff-Prüfung hängen.
        cache_missing = bool(self._display_missing_param_blocks(required_blocks))
        if cache_missing:
            self._log(
                "DISPLAY-INIT V0.2.41 fix5 (Timer/Popup schreiben): benötigte Parameterpakete "
                + ", ".join(f"{b}ff" for b in self._display_missing_param_blocks(required_blocks))
                + " fehlen noch. Ich starte den Snapshot einmal im Hintergrund, sende den aktuellen Dialog-Write aber trotzdem."
            )
            try:
                self.send_init_reads()
            except Exception as exc:
                self._log(f"DISPLAY-INIT V0.2.41 fix5 (Timer/Popup schreiben): automatischer Init-Start fehlgeschlagen: {exc}")

        plan: list[dict[str, Any]] = []
        skipped_unchanged_bitregs: list[str] = []
        skipped_unchanged_regs: list[str] = []
        for addr, value, label in values:
            try:
                addr_i = int(addr)
                value_i = int(value) & 0xFFFF
                user_addr, block_start, mask = self._display_user_variable_for_param_reg(addr_i)
            except Exception:
                return None

            # V0.2.41 fix5: nur noch wirklich geänderte Werte senden.
            # In V0.2.41 wurde bei Timer 1 der komplette Block 0x2501..0x2507
            # geschrieben; der Displaybus quittierte diesen Block gar nicht. Für
            # eine reine Leistungsänderung reicht z.B. 0x2507 als Einzelwert.
            cur = self._display_current_param_raw_value(addr_i)
            if cur is not None and int(cur) == value_i:
                if addr_i in (1268, 1269, 1270, 1323, 1324, 1325):
                    skipped_unchanged_bitregs.append(f"{addr_i}=0x{value_i:04X}")
                else:
                    skipped_unchanged_regs.append(f"{addr_i}=0x{value_i:04X}")
                continue

            plan.append({
                "addr": addr_i,
                "value": value_i,
                "label": str(label or f"Reg {addr}"),
                "user_addr": int(user_addr),
                "block_start": int(block_start),
                "mask": int(mask) & 0xFFFF,
                # Display-ACKs kommen auf diesem Bus nicht zuverlässig. Deshalb
                # nach Retries weiter zum 0BC3-Trigger statt hart abbrechen.
                "optional_ack": True,
            })
        if skipped_unchanged_regs:
            self._log(
                "DISPLAY Timer V0.2.41 fix5: unveränderte Timer-/Popupwerte nicht gesendet: "
                + ", ".join(skipped_unchanged_regs)
            )
        if skipped_unchanged_bitregs:
            self._log(
                "DISPLAY Timer V0.2.41 fix5: unveränderte Aktiv/Tage-Paarregister nicht gesendet: "
                + ", ".join(skipped_unchanged_bitregs)
            )
        return plan

    def _timer_write_preview_lines(self, values: list[tuple[int, int, str]], slave_addr: int) -> list[str]:
        plan = self._display_timer_batch_plan(values, slave_addr)
        if plan is not None:
            if not plan:
                return ["Display-Modbus: kein Direktwrite geplant (fehlende Paketdaten/Init läuft oder keine geänderten Werte übrig)."]
            lines = []
            seen_blocks: list[tuple[int, int]] = []
            for step in plan:
                lines.append(
                    f"{step['label']}: Reg {step['addr']}/0x{step['addr']:04X} "
                    f"-> User {step['user_addr']}/0x{step['user_addr']:04X} "
                    f"= {step['value']}/0x{step['value']:04X} FC16 "
                    f"(Display-Bedienwertpfad, Paket {step['block_start']}, 0BC3=0x{step['mask']:04X})"
                )
                bm = (int(step['block_start']), int(step['mask']))
                if bm not in seen_blocks:
                    seen_blocks.append(bm)
            for block_start, mask in seen_blocks:
                lines.append(f"Display-Flag: 0BC3/0x0BC3 = 0x{mask:04X} fuer Paket {block_start} FC16")
            return lines

        lines = []
        for addr, value, label in values:
            frame, wire_addr, wire_slave, note, fc_text = self._build_write_frame_for_backend(addr, value, slave_addr)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")
        return lines

    def _display_timer_compact_steps(self, plan: list[dict[str, Any]], title: str) -> list[dict[str, Any]]:
        """V0.2.41 fix5: mehrere Display-Timerwerte einzeln committen.

        fix1 schrieb zwar nur geänderte User-Adressen, setzte 0BC3 aber erst
        nach allen Werten. Im Log wurden bei Mehrfachänderung dadurch nicht alle
        Werte übernommen (z.B. 1283 und 1287 ja, 1284 nein). Deshalb wird jetzt
        jeder Wert als eigener Mini-Zyklus behandelt:

            Userwert schreiben -> 0BC3 fuer Paket setzen -> kurze Commit-Pause

        So bekommt der echte Display-Master jeden geänderten Wert einzeln zu
        sehen, bevor der nächste Userwert geschrieben wird.
        """
        by_block: dict[int, list[dict[str, Any]]] = {}
        block_order: list[int] = []
        for step in plan:
            block = int(step["block_start"])
            if block not in by_block:
                by_block[block] = []
                block_order.append(block)
            by_block[block].append(step)

        out: list[dict[str, Any]] = []
        for block in block_order:
            steps = sorted(by_block[block], key=lambda item: int(item["user_addr"]))
            if not steps:
                continue
            mask = int(steps[0]["mask"]) & 0xFFFF
            for item in steps:
                is_1181_block = int(block) == 1181
                out.append({
                    "kind": "single",
                    "addr": int(item["user_addr"]),
                    "qty": 1,
                    "value": int(item["value"]) & 0xFFFF,
                    "label": f"{title}: {item.get('label') or 'Timerwert'} Reg {int(item['addr'])} -> User 0x{int(item['user_addr']):04X}",
                    "block_start": int(block),
                    "mask": int(mask),
                    # PRIVATE fix5: 1181ff/KG-/WP-Ein-Aus-Timer bestaetigt
                    # 24E8..24F6 im Log nicht per ACK, obwohl die Adresse laut ASM
                    # korrekt ist. Deshalb ist der Userwert bei diesem Block weich:
                    # nach Retries folgt ein 04E8..04F6-Kommunikationswert-Fallback
                    # und erst danach 0BC3=0x0008. Fuer 1271ff bleibt der
                    # erfolgreiche striktere Userwertpfad unveraendert.
                    "optional_ack": bool(is_1181_block),
                    "post_pause_ms": 420 if is_1181_block else 260,
                    "note_no_ack": "1181ff-Useradresse ohne ACK; weiter mit Kommunikationswert-Fallback",
                })
                if is_1181_block:
                    out.append({
                        "kind": "single",
                        "addr": int(item["addr"]),
                        "qty": 1,
                        "value": int(item["value"]) & 0xFFFF,
                        "label": f"{title}: 1181ff-Fallback Kommunikationswert Reg {int(item['addr'])}=0x{int(item['value']) & 0xFFFF:04X}",
                        "block_start": int(block),
                        "mask": int(mask),
                        "optional_ack": True,
                        "is_comm_fallback": True,
                        # Ohne 0BC3 kann Four_Variable_Communication den neuen
                        # Kommunikationswert erst in den User-/Cachewert spiegeln.
                        # Danach wird 0BC3=0x0008 gesetzt, damit der Master 1181ff liest.
                        "post_pause_ms": 1700,
                        "note_no_ack": "1181ff-Kommunikationswert ohne ACK; setze trotzdem 0BC3 als weichen Trigger",
                    })
                out.append({
                    "kind": "single",
                    "addr": 0x0BC3,
                    "qty": 1,
                    "value": mask,
                    "label": f"{title}: Commit fuer {item.get('label') or 'Timerwert'} via 0BC3 Paket {block} = 0x{mask:04X}",
                    "block_start": int(block),
                    "mask": int(mask),
                    "optional_ack": True,
                    "is_trigger": True,
                    # Der Master braucht sichtbar Zeit, bis das passende Paket
                    # nach 0BC3 neu gelesen ist. 1181ff ist im Log besonders traege.
                    "post_pause_ms": 5200 if is_1181_block else 3200,
                })
        return out

    def _send_display_timer_batch(self, plan: list[dict[str, Any]], delay_ms: int, title: str) -> bool:
        if not plan:
            return False
        if self.display_timer_batch_state.get("active"):
            self._log(f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): es läuft bereits ein Display-Timer-Write; neuer Auftrag ignoriert.")
            return True
        steps = self._display_timer_compact_steps(plan, title)
        if not steps:
            self._log(f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): keine geänderten Display-Werte zum Schreiben übrig.")
            return True
        timeout_ms = max(900, min(3500, int(delay_ms or 1200) + 500))
        # PRIVATE fix5: 1181ff / WP-Ein-Aus-/Silent-Timer reagiert traeger als
        # der Betriebsart-Timer 1271ff. Etwas mehr ACK-Zeit verhindert unnoetige
        # Fehlversuche auf 0x24E8/0x24E9/...
        if any(int(item.get("block_start", 0) or 0) == 1181 for item in plan):
            timeout_ms = max(timeout_ms, 2600)
        pause_ms = 220
        self.display_timer_batch_state = {
            "active": True,
            "title": str(title),
            "steps": steps,
            "step_index": 0,
            "step_retries": 0,
            "timeout_ms": timeout_ms,
            "pause_ms": pause_ms,
            "started": time.monotonic(),
        }
        self._log(
            f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): schreibe {len(plan)} Werte ACK-gesteuert "
            f"als {len(steps)} einzelne FC16-Schritte (Timeout {timeout_ms} ms, Retry max. 3). "
            "Direkte 12xx/13xx-Fallback-Writes werden nur fuer 1181ff genutzt, wenn 24E8..24F6 kein ACK liefern. "
            "Es werden nur geänderte Userwerte plus weicher 0BC3-Trigger gesendet."
        )
        self._display_timer_batch_send_current_step()
        return True

    def _display_timer_batch_send_current_step(self) -> None:
        state = self.display_timer_batch_state
        if not state.get("active"):
            return
        steps = list(state.get("steps") or [])
        idx = int(state.get("step_index", 0) or 0)
        if idx >= len(steps):
            title = str(state.get("title") or "Timer")
            self._log(
                f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): alle FC16-Schritte quittiert/abgesetzt. "
                "0BC3-Trigger wurde weich abgesetzt. Bitte frisches passendes Parameterpaket zur Bestätigung prüfen."
            )
            self.display_timer_batch_state = {}
            return
        step = dict(steps[idx])
        retry = int(state.get("step_retries", 0) or 0) + 1
        state["step_retries"] = retry
        state["current_step"] = step
        state["current_sent_at"] = time.monotonic()
        kind = str(step.get("kind") or "single")
        label = f"V0.2.41 fix5 ACK Schritt {idx + 1}/{len(steps)} Versuch {retry}: {step.get('label') or ''}"
        if kind == "block":
            self._enqueue_display_write_block(int(step["addr"]), list(step.get("values") or []), label=label, post_delay_ms=0)
        else:
            self._enqueue_display_fc16_single(int(step["addr"]), int(step.get("value", 0)) & 0xFFFF, label=label, post_delay_ms=0)
        QTimer.singleShot(int(state.get("timeout_ms", 1700) or 1700), self._display_timer_batch_check_step_ack)

    def _display_timer_batch_check_step_ack(self) -> None:
        state = self.display_timer_batch_state
        if not state.get("active"):
            return
        step = dict(state.get("current_step") or {})
        addr = int(step.get("addr", 0) or 0)
        qty = int(step.get("qty", 1) or 1)
        sent_at = float(state.get("current_sent_at", 0.0) or 0.0)
        idx = int(state.get("step_index", 0) or 0)
        steps = list(state.get("steps") or [])
        title = str(state.get("title") or "Timer")
        if self._display_write_ack_seen_since(addr, sent_at, qty=qty, slave=0x03):
            self._log(
                f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): ACK für Schritt {idx + 1}/{len(steps)} "
                f"Addr 0x{addr:04X} qty={qty} gesehen."
            )
            state["step_index"] = idx + 1
            state["step_retries"] = 0
            next_pause = int(step.get("post_pause_ms", state.get("pause_ms", 220)) or state.get("pause_ms", 220) or 220)
            QTimer.singleShot(next_pause, self._display_timer_batch_send_current_step)
            return
        # 0BC3 kann manchmal im 3001-Poll sichtbar sein, bevor/ohne dass der ACK sauber geloggt wurde.
        if addr == 0x0BC3:
            mask = int(step.get("mask", 0) or 0) & 0xFFFF
            flag = self._display_0bc3_value_from_3001()
            if flag == mask:
                self._log(
                    f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): kein ACK für 0BC3, aber 3001 zeigt Flag 0x{mask:04X}; weiter."
                )
                state["step_index"] = idx + 1
                state["step_retries"] = 0
                next_pause = int(step.get("post_pause_ms", state.get("pause_ms", 220)) or state.get("pause_ms", 220) or 220)
                QTimer.singleShot(next_pause, self._display_timer_batch_send_current_step)
                return
        retry = int(state.get("step_retries", 0) or 0)
        max_retry = 4 if addr == 0x0BC3 else 3
        if retry < max_retry:
            self._log(
                f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): kein ACK für Schritt {idx + 1}/{len(steps)} "
                f"Addr 0x{addr:04X} qty={qty}, wiederhole."
            )
            self._display_timer_batch_send_current_step()
            return
        if bool(step.get("optional_ack")):
            extra_note = str(step.get("note_no_ack") or "Ich setze trotzdem mit 0BC3/den Folgeschritten fort")
            self._log(
                f"DISPLAY Timer/Popup V0.2.41 fix5 WARNUNG ({title}): optionaler Schritt {idx + 1}/{len(steps)} "
                f"Addr 0x{addr:04X} qty={qty} ohne ACK nach {max_retry} Versuchen. "
                f"{extra_note}; Übernahme bitte im frischen Paket prüfen."
            )
            state["step_index"] = idx + 1
            state["step_retries"] = 0
            next_pause = int(step.get("post_pause_ms", state.get("pause_ms", 220)) or state.get("pause_ms", 220) or 220)
            QTimer.singleShot(next_pause, self._display_timer_batch_send_current_step)
            return
        self._log(
            f"DISPLAY Timer/Popup V0.2.41 fix5 FEHLER ({title}): Schritt {idx + 1}/{len(steps)} "
            f"Addr 0x{addr:04X} qty={qty} ohne ACK nach {max_retry} Versuchen. Abbruch."
        )
        self.display_timer_batch_state = {}

    def send_timer_values(self, slave_addr: int, values: list[tuple[int, int, str]], delay_ms: int = 1200, title: str = "Timer"):
        if not self.connected or self._active_io_worker() is None:
            self._log("TIMER nicht gesendet: keine aktive Verbindung / kein aktiver Worker.")
            return

        display_plan = self._display_timer_batch_plan(values, slave_addr)
        if display_plan is not None and not display_plan:
            self._log(f"DISPLAY Timer/Popup V0.2.41 fix5 ({title}): Write nicht gesendet (Init/Snapshot gestartet oder keine geänderten Werte übrig).")
            return

        lines = self._timer_write_preview_lines(values, slave_addr)

        if not ask_yes_no(self, f"{title} schreiben?", f"Diese {title}-Register schreiben?\n\n" + "\n".join(lines), default_yes=False):
            self._log("TIMER Write abgebrochen: nicht gesendet.")
            return

        self._log(f"TIMER wird GESENDET ({title}):\n" + "\n".join(lines))
        if display_plan is not None:
            self._send_display_timer_batch(display_plan, delay_ms, title)
            return

        for addr, value, _label in values:
            _frame, wire_addr, wire_slave, _note, _fc_text = self._build_write_frame_for_backend(addr, value, slave_addr)
            self.worker.enqueue_write(wire_addr, value, slave_addr=wire_slave, post_delay_ms=delay_ms, write_single=self._write_single_for_backend())

    def rebuild_table_filter(self):
        self.table_rows = {}
        self.register_table.setRowCount(0)
        for reg_no in sorted(self.latest_regs):
            reg = self.latest_regs[reg_no]
            if self.known_only_cb.isChecked() and not reg.name:
                continue
            self._upsert_register_row(reg, changed=False)
        self._log("Tabellenfilter geändert. Tabelle aus gespeicherten Live-Werten neu aufgebaut.")

    def closeEvent(self, event):
        self._update_main_window_settings()
        self._save_settings()
        if self.warmlink_cloud_dialog is not None:
            try:
                setattr(self.warmlink_cloud_dialog, "_force_close", True)
                self.warmlink_cloud_dialog.stop_worker()
            except Exception:
                pass
        if hasattr(self, "live_poll_timer"):
            self.live_poll_timer.stop()
        if self.cache_save_exit_cb.isChecked():
            self.save_value_cache(silent=False)
        self.disconnect_from_device()
        self._stop_warmlink_capture("App wird beendet")
        event.accept()


def main():
    set_windows_app_id()
    app = QApplication(sys.argv)
    apply_app_theme(app, "system")
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    holder: dict[str, Any] = {}
    splash = StartupSplash()

    def show_main_window():
        if holder.get("shown"):
            return
        holder["shown"] = True
        if splash.isVisible():
            splash.close()
        window = MainWindow()
        holder["window"] = window
        window.show()

    splash.clicked.connect(show_main_window)
    splash.show()
    QTimer.singleShot(8000, show_main_window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
