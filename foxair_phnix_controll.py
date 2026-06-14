#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import ctypes
import json
import os
import queue
import re
import socket
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Any, Dict, Optional, BinaryIO

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
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
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
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

from foxair_phnix_core import (
    DEFAULT_BUS_ADDR,
    DecodedRegister,
    RegisterMap,
    WarmlinkSocketClient,
    ModbusSerialClient,
    build_read_frame,
    build_write_frame,
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


APP_VERSION = "0.2.29"
BUILD_DATE = "2026-06-14"
APP_EDITION = "PUBLIC"
APP_TITLE = f"FoxAir / Phnix Controll V{APP_VERSION} {APP_EDITION} - by DosOrDie"
PUBLIC_WARNING_TEXT = "Inoffizielles Tool. Register schreiben auf eigene Gefahr. Vor Änderungen Backup erstellen."
APP_ICON_FILE = "app_icon.png"
DEFAULT_HOST = ""
DEFAULT_PORT = 2001
UPDATE_REPO = "dosordie/FoxAir_Controll"
UPDATE_API_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_RELEASES_URL = f"https://github.com/{UPDATE_REPO}/releases/latest"


def app_program_dir() -> str:
    """Ordner der EXE bzw. des Scripts.

    Bei PyInstaller liegt __file__ meist unter _internal. Einstellungen sollen aber
    neben der EXE liegen, damit portable/private Versionen alles in einem Ordner halten.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))




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
        return os.path.join(root, "FoxAir Phnix Controll")
    root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(root, "FoxAir Phnix Controll")

def app_resource_dir() -> str:
    """Ordner der mitgelieferten Programmdaten.

    Im Python/ZIP-Betrieb identisch mit app_program_dir(), im PyInstaller-Build
    kann das der _internal/_MEIPASS-Ordner sein.
    """
    if hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))

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
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def app_icon() -> QIcon:
    icon_path = resource_path(APP_ICON_FILE)
    icon = QIcon(icon_path)
    return icon

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
        self.setStyleSheet("""
            QDialog { background: #111820; border: 1px solid #2d3b48; }
            QLabel#title { color: white; font-size: 24px; font-weight: bold; }
            QLabel#version { color: #d7e6f5; font-size: 14px; }
            QLabel#hint { color: #9fb2c4; font-size: 11px; }
            QLabel#brand { color: #d7e6f5; font-size: 13px; font-weight: bold; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.addStretch(1)
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 24)
        close_btn.setToolTip("Splash schließen")
        close_btn.setStyleSheet("""
            QPushButton {
                color: #d7e6f5;
                background: transparent;
                border: 1px solid #53677a;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #263747; }
        """)
        close_btn.clicked.connect(self._skip)
        top.addWidget(close_btn, 0, Qt.AlignRight | Qt.AlignTop)
        root.addLayout(top)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        pix = QPixmap(resource_path(APP_ICON_FILE))
        if not pix.isNull():
            logo_label.setPixmap(pix.scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        root.addWidget(logo_label, 0, Qt.AlignCenter)

        title = QLabel("FoxAir / Phnix Controll")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        version = QLabel(f"Version V{APP_VERSION}  •  {BUILD_DATE}")
        version.setObjectName("version")
        version.setAlignment(Qt.AlignCenter)
        root.addWidget(version)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        brand = QLabel("FoxAir Controll\nby DosOrDie")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignRight | Qt.AlignBottom)
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
    if is_block:
        font.setItalic(True)
        point_size = font.pointSize()
        if point_size and point_size > 7:
            font.setPointSize(point_size - 1)
        item.setForeground(QColor(95, 95, 95))
    else:
        font.setItalic(False)
        item.setForeground(QColor(0, 0, 0))
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
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FoxAir.PhnixControll.0.1")
    except Exception:
        pass


def parse_version_tuple(text: str) -> tuple[int, ...]:
    """Versionsvergleich fuer Tags wie v0.2.27 oder 0.2.27."""
    m = re.search(r"(\d+(?:\.\d+){0,4})", str(text or ""))
    if not m:
        return (0,)
    parts = []
    for part in m.group(1).split("."):
        try:
            parts.append(int(part))
        except Exception:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


class UpdateCheckWorker(QObject):
    result = Signal(dict)
    error = Signal(str)
    finished = Signal()

    @Slot()
    def run(self):
        try:
            req = urllib.request.Request(
                UPDATE_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"FoxAir-Phnix-Controll/{APP_VERSION}",
                },
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise RuntimeError("GitHub-Antwort war kein Objekt")
            assets = []
            for asset in data.get("assets", []) or []:
                if isinstance(asset, dict):
                    name = str(asset.get("name", "")).strip()
                    url = str(asset.get("browser_download_url", "")).strip()
                    if name and url:
                        assets.append({"name": name, "url": url})
            self.result.emit({
                "tag": str(data.get("tag_name", "")).strip(),
                "name": str(data.get("name", "")).strip(),
                "html_url": str(data.get("html_url", UPDATE_RELEASES_URL)).strip() or UPDATE_RELEASES_URL,
                "assets": assets,
            })
        except urllib.error.HTTPError as exc:
            self.error.emit(f"GitHub HTTP-Fehler {exc.code}: {exc.reason}")
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class ReaderWorker(QObject):
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)
    log = Signal(str)
    frame_decoded = Signal(object)
    raw_chunk = Signal(bytes)

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
                    if self.transport == "serial":
                        self.log.emit(f"SERIAL RX Rohdaten: {len(chunk)} Byte, HEX={hexdump(chunk, -1)}")
                    self.rx_after_last_send = True
                    self.rx_timeout_logged = False
                    self.buf.extend(chunk)
                    parsed_frames = find_frames(self.buf, max_len=512)

                    for parsed in parsed_frames:
                        frame = decode_frame(parsed, self.regmap)
                        self.frame_decoded.emit(frame)

                except socket.timeout:
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
                if kind == "read":
                    frame = build_read_frame(addr, value_or_quantity, slave_addr=slave_addr)
                    action = (
                        f"READ gesendet: bus=0x{slave_addr:02X}, "
                        f"addr={addr} / 0x{addr:04X}, anzahl={value_or_quantity}, "
                        f"TX={hexdump(frame, -1)}"
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
        self.setWindowTitle("Kontaktdecoder Register 2034 / 0x07F2")
        self.resize(1030, 560)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.value_label = QLabel("2034: --")
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

        self.table = QTableWidget(16, 5)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setHorizontalHeaderLabels(["Bit", "Wert", "Name", "Status", "Bedeutung"])
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
        try:
            slave_addr = self.main_window._parse_int_text(self.main_window.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        self.main_window.send_read_request(2034, 1, slave_addr=slave_addr, label="Kontaktdecoder 2034")

    def set_value(self, value: Optional[int]):
        if value is None:
            self.value_label.setText("2034: --")
            rows = decode_contact_bits(0)
            for bit, _bit_value, name, _state, meaning in rows:
                vals = [str(bit), "--", name, "--", meaning]
                for col, val in enumerate(vals):
                    self.table.setItem(bit, col, QTableWidgetItem(val))
            return

        self.value_label.setText(f"2034: {value} / 0x{value:04X} / bin={value:016b}")
        rows = decode_contact_bits(value)
        for bit, bit_value, name, state, meaning in rows:
            vals = [str(bit), str(bit_value), name, state, meaning]
            for col, val in enumerate(vals):
                item = self.table.item(bit, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(bit, col, item)
                item.setText(val)
                # Kontakt-/Statusbits mit 1=EIN grün markieren, alte Sxx-Schalter mit 0=ein ebenfalls grün.
                active_is_one = ("1=EIN" in meaning.upper()) or ("1=EIN" in state.upper())
                is_active = bool(bit_value) if active_is_one else (bit_value == 0 if meaning else bool(bit_value))
                item.setBackground(QColor(220, 255, 220) if is_active else QColor(245, 245, 245))


class LoadOutputDecoderDialog(QDialog):
    """Decoder fuer Register 2019 / 0x07E3 Lastausgaenge."""

    def __init__(self, parent: "MainWindow", value: Optional[int]):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Lastausgang Decoder Register 2019 / 0x07E3")
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
        ("kein Modell gewählt / Code 9", 9),
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
        # sinnvolle Defaults nur für noch unbekannte Felder
        for timer_no, fld in self.fields.items():
            base = fld["base"]
            if self.main_window.latest_regs.get(base) is None:
                self._set_time_widgets(fld["on_hour"], fld["on_min"], encode_hhmm(15, 0), force=True)
            if self.main_window.latest_regs.get(base + 1) is None:
                self._set_time_widgets(fld["off_hour"], fld["off_min"], encode_hhmm(19, 0), force=True)
            if self.main_window.latest_regs.get(base + 2) is None:
                fld["ww_temp"].setValue(55.0)
            if self.main_window.latest_regs.get(base + 3) is None:
                fld["heat_temp"].setValue(45.0)
            if self.main_window.latest_regs.get(base + 4) is None:
                fld["cool_temp"].setValue(7.0)

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
            9: "kein Modell gewählt / aktueller Modus",
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
        self.write_value_edit.setPlaceholderText("z.B. 55 oder 0x0037")
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

        form.addRow("zu schreibender Wert:", self.write_value_edit)

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
            self.write_value_edit.setText(str(value))
        finally:
            self._programmatic = False

    def _write_value_text_edited(self):
        if self._programmatic:
            return
        try:
            raw = self.main_window._parse_int_text(self.write_value_edit.text()) & 0xFFFF
        except Exception:
            if self.value_combo is not None:
                self._programmatic = True
                try:
                    self.value_combo.setCurrentIndex(0)
                finally:
                    self._programmatic = False
            return
        self._select_combo_value(raw)

    def refresh_from_live(self):
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
        self._select_combo_value(raw)
        if not self.write_value_edit.text().strip() and not self.write_value_edit.hasFocus():
            self.write_value_edit.setText(str(raw))

    def update_from_live_register(self, reg):
        if int(reg.reg) == self.reg_no:
            self.refresh_from_live()

    def read_register(self):
        try:
            self.main_window.send_read_request(self.reg_no, 1, slave_addr=self._parse_bus(), label=f"Popup Register {self.reg_no}")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Leseanforderung", str(exc))

    def write_register(self):
        try:
            value = self.main_window._parse_int_text(self.write_value_edit.text()) & 0xFFFF
            self.main_window.send_register_write(self.reg_no, value, slave_addr=self._parse_bus(), label=f"Popup Register {self.reg_no}")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültiger Schreibwert", str(exc))


class SGReadyEditorDialog(QDialog):
    SG_REGS = set(range(1334, 1342))

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self._programmatic = False
        self.setWindowTitle("SG Ready Editor")
        self.setMinimumWidth(620)
        self._build_ui()
        self.load_from_live_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("SG Ready Register 1334-1341. SG01: Aus / Einfach (1 Kontakt) / Zweifach (2 Kontakte). SG08: Elektroheizstab Ein/Aus bei Mode4. Live-Update überschreibt keine gerade bearbeiteten Felder.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        layout.addLayout(form)
        self.auto_update_cb = QCheckBox("live aktualisieren")
        self.auto_update_cb.setChecked(True)
        form.addRow("Live:", self.auto_update_cb)

        self.sg_mode_combo = QComboBox()
        self.sg_mode_combo.addItem("Aus", 0)
        self.sg_mode_combo.addItem("Einfach - 1 Kontakt", 1)
        self.sg_mode_combo.addItem("Zweifach - 2 Kontakte", 2)
        form.addRow("SG01 Funktion (1334):", self.sg_mode_combo)

        self.raw_spins: dict[int, QSpinBox] = {}
        for reg_no, label in [
            (1335, "SG02 Schlafmodus Zeit"),
            (1336, "SG03 Mode2 Verzögerung"),
            (1337, "SG04 Mode3 Verzögerung"),
            (1341, "SG08 Elektroheizstab bei Mode4"),
        ]:
            spin = QSpinBox(); spin.setRange(0, 0xFFFF)
            self.raw_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.temp_spins: dict[int, QDoubleSpinBox] = {}
        for reg_no, label in [
            (1338, "SG05 WW-Anhebung"),
            (1339, "SG06 HZ-Anhebung"),
            (1340, "SG07 Kühlen-Anhebung"),
        ]:
            spin = QDoubleSpinBox(); spin.setRange(-50.0, 25.0); spin.setDecimals(1); spin.setSingleStep(0.5); spin.setSuffix(" °C")
            self.temp_spins[reg_no] = spin
            form.addRow(f"{label} ({reg_no}):", spin)

        self.delay_ms = QSpinBox(); self.delay_ms.setRange(0, 10000); self.delay_ms.setValue(1200); self.delay_ms.setSingleStep(100); self.delay_ms.setSuffix(" ms")
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

    def update_from_live_register(self, reg, force: bool = False):
        reg_no = int(reg.reg)
        if reg_no not in self.SG_REGS:
            return
        if not force and not self.auto_update_cb.isChecked():
            return
        raw = int(reg.raw_value) & 0xFFFF
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
        finally:
            self._programmatic = False

    def sg_values(self) -> list[tuple[int, int, str]]:
        values = [(1334, int(self.sg_mode_combo.currentData()) & 0xFFFF, "SG01 Funktion")]
        for reg_no in (1335, 1336, 1337):
            values.append((reg_no, int(self.raw_spins[reg_no].value()) & 0xFFFF, f"SG Register {reg_no}"))
        for reg_no, label in ((1338, "SG05 WW-Anhebung"), (1339, "SG06 HZ-Anhebung"), (1340, "SG07 Kuehlen-Anhebung")):
            values.append((reg_no, int(round(float(self.temp_spins[reg_no].value()) * 10.0)) & 0xFFFF, label))
        values.append((1341, int(self.raw_spins[1341].value()) & 0xFFFF, "SG08 Elektroheizstab bei Mode4"))
        return values

    def read_from_wp(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.send_read_request(1334, 8, slave_addr=slave_addr, label="SG Ready 1334-1341")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige SG-Leseanforderung", str(exc))

    def send_values(self):
        try:
            slave_addr = DEFAULT_BUS_ADDR
            self.main_window.send_timer_values(slave_addr, self.sg_values(), int(self.delay_ms.value()), title="SG Ready")
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
        self.addr_edit = QLineEdit("1334")
        self.value_edit = QLineEdit("0")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 125)
        self.count_spin.setValue(1)
        form.addRow("Bus-Adresse:", self.bus_edit)
        form.addRow("Register-Adresse:", self.addr_edit)
        form.addRow("Wert:", self.value_edit)
        form.addRow("Lesen Anzahl:", self.count_spin)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.read_btn = QPushButton("FC03 lesen")
        self.dry_btn = QPushButton("Dry-Run")
        self.send_btn = QPushButton("ECHT senden")
        self.send_btn.setEnabled(False)
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.dry_btn)
        buttons.addWidget(self.send_btn)
        layout.addLayout(buttons)

        self.read_btn.clicked.connect(self.read_registers)
        self.dry_btn.clicked.connect(self.show_write_frame)
        self.send_btn.clicked.connect(self.send_write_frame)

    def _bus(self) -> int:
        return self.main_window._parse_int_text(self.bus_edit.text())

    def _addr(self) -> int:
        return self.main_window._parse_int_text(self.addr_edit.text())

    def _value(self) -> int:
        return self.main_window._parse_int_text(self.value_edit.text()) & 0xFFFF

    def set_address(self, reg_no: int, slave_addr: int = DEFAULT_BUS_ADDR):
        self.addr_edit.setText(str(int(reg_no)))
        self.bus_edit.setText(f"0x{int(slave_addr):02X}")

    def read_registers(self):
        try:
            self.main_window.send_read_request(self._addr(), int(self.count_spin.value()), slave_addr=self._bus(), label="manuelles Popup")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Leseanforderung", str(exc))

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
            self.main_window.send_register_write(self._addr(), self._value(), slave_addr=self._bus(), label="manuelles Popup")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Schreibdaten", str(exc))


class BusAddressDialog(QDialog):
    """Popup fuer gesehene Bus-Adressen."""

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Gesehene Bus-Adressen")
        self.setWindowIcon(app_icon())
        self.resize(760, 320)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Bus", "Frames", "CRC OK", "CRC BAD", "Letzter Frame", "Vermutung"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        h = self.table.horizontalHeader()
        for col in range(5):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.Stretch)
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
            values = [
                f"0x{addr:02X}", str(st.get("frames", 0)), str(st.get("crc_ok", 0)),
                str(st.get("crc_bad", 0)), str(st.get("last_frame", "")), str(st.get("guess", "")),
            ]
            for col, text in enumerate(values):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(text)
                if col in (0, 1, 2, 3):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setSortingEnabled(True)


class KnowledgeEditorDialog(QDialog):
    """Bearbeitung der getrennten Wissensdatenbank foxair_phnix_knowledge.json."""

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
            "Diese Texte werden in foxair_phnix_knowledge.json gespeichert und beim Start über das Register-Mapping gelegt. "
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
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("nach Name/App-Name/Beschreibung suchen ...")
        self.regex_cb = QCheckBox("Regex")
        self.app_name_cb = QCheckBox("App-Name anzeigen")
        self.count_label = QLabel("0 Register")
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
        self.search_edit.textChanged.connect(lambda _=None: self.refresh())
        self.regex_cb.stateChanged.connect(lambda _=None: self.refresh())
        self.app_name_cb.stateChanged.connect(lambda _=None: self.refresh())
        self.table.itemDoubleClicked.connect(lambda _=None: self.write_selected())
        self.table.currentItemChanged.connect(lambda cur, _prev=None: self._show_selected_description())
        self.write_btn.clicked.connect(self.write_selected)
        self.read_btn.clicked.connect(self.read_selected)
        self.edit_info_btn.clicked.connect(self.edit_selected_description)
        self.close_btn.clicked.connect(self.close)
        self.refresh()

    def _collect_items(self) -> list[dict[str, Any]]:
        out = []
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
            self.main_window.open_register_quick_write(reg, DEFAULT_BUS_ADDR)

    def read_selected(self):
        reg = self._selected_reg()
        if reg is not None:
            self.main_window.send_read_request(reg, 1, slave_addr=DEFAULT_BUS_ADDR, label="Offline-Browser")

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
        "T": "Temperatur",
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
        # Beim Oeffnen direkt den ersten sichtbaren Block laden, so wie die App
        # beim Aufruf einer Parametergruppe sofort Werte anzeigt.
        QTimer.singleShot(250, self._auto_read_initial_block)

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
        top.addWidget(self.app_only_cb)
        top.addWidget(self.app_name_cb)
        top.addWidget(self.live_update_cb)
        top.addWidget(self.auto_read_block_cb)
        top.addStretch(1)
        layout.addLayout(top)

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
        preferred = ["H", "A", "F", "D", "E", "C", "R", "Z", "G", "P", "SG", "KG", "T"]
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
            technical_name = self._name_without_code(item.get("name", ""))
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
            technical_name = self._name_without_code(item.get("name", ""))
            app_name = item.get("app_label") or technical_name
            name_text = app_name if self.app_name_cb.isChecked() else technical_name
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

    def _name_without_code(self, name: str) -> str:
        if "/" in name:
            return name.split("/", 1)[1].strip()
        return name

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
            "format": "FoxAir_Phnix_Controll_Parameter_Backup",
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
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("format") != "FoxAir_Phnix_Controll_Parameter_Backup":
                raise ValueError("Keine passende FoxAir/Phnix Backup-Datei.")
            self.loaded_backup = data
            self.refresh_restore_table()
            self.restore_changed_btn.setEnabled(True)
            self.restore_selected_btn.setEnabled(True)
            self.tabs.setCurrentIndex(1)
        except Exception as exc:
            QMessageBox.warning(self, "Backup laden Fehler", str(exc))

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



BACKEND_CHOICES = [
    ("warmlink_raw", "Warmlink RAW"),
    ("standard_modbus", "Standard Modbus"),
    ("display_modbus", "Display Modbus (DWIN)"),
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
        "serial_port": "COM3", "baudrate": 9600, "parity": "N", "bytesize": 8, "stopbits": 1.0,
        "unit_id": 3, "display_translate_0x2000": True,
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
        self.backend_combo.setCurrentIndex(idx if idx >= 0 else 0)

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
        self.translate_cb.setToolTip("Nur Display-Modbus: z. B. 1205 / 0x04B5 -> 9397 / 0x24B5")

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
        form.addRow("Display:", self.translate_cb)
        form.addRow("Gerät:", self.device_combo)
        form.addRow("Hinweis:", self.device_hint_label)

        self.show_warning_cb = QCheckBox("Hinweis-Banner im Hauptfenster anzeigen")
        self.show_warning_cb.setChecked(bool(main_window.settings.get("show_public_warning", True)))
        self.show_warning_cb.setToolTip("Blendet den gelben Hinweis 'inoffizielles Tool' im Hauptfenster ein/aus.")
        form.addRow("Anzeige:", self.show_warning_cb)

        self.update_btn = QPushButton("Update jetzt prüfen ...")
        self.update_btn.setToolTip("Prüft die neueste öffentliche GitHub-Release-Version.")
        form.addRow("Update:", self.update_btn)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.backend_combo.currentIndexChanged.connect(lambda _=None: self._backend_changed(load_values=True))
        self.transport_combo.currentIndexChanged.connect(lambda _=None: self._transport_changed())
        self.update_btn.clicked.connect(self.main_window.check_for_updates)
        self._backend_changed(load_values=True)

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
        self.translate_cb.setChecked(bool(cfg.get("display_translate_0x2000", backend == "display_modbus")))

    def _save_current_fields_to_selected_backend(self):
        backend = str(self.backend_combo.currentData() or "warmlink_raw")
        self.main_window._set_backend_settings(
            backend=backend,
            transport=str(self.transport_combo.currentData() or "tcp"),
            host=self.host_edit.text().strip(),
            port=int(self.port_spin.value()),
            unit_id=int(self.unit_spin.value()),
            display_translate=self.translate_cb.isChecked(),
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
        self.translate_cb.setVisible(backend == "display_modbus")
        self.unit_label.setVisible(backend in ("display_modbus", "standard_modbus"))
        self.unit_spin.setVisible(backend in ("display_modbus", "standard_modbus"))
        self._transport_changed()
        if backend == "warmlink_raw":
            self.info_label.setText("Warmlink RAW kann per TCP/ser2net oder direkt per COM-Port genutzt werden. WP-Busadresse bleibt intern 0x63.")
        elif backend == "standard_modbus":
            self.info_label.setText("Standard-Modbus nutzt FC03 lesen und FC06 schreiben. Bei deiner Anlage bestätigt: Port 10001, Unit 1.")
        else:
            self.info_label.setText("Display-Modbus nutzt DWIN/Display-Unit, typ. Unit 3. Optional werden Parameterregister 1000–1999 auf +0x2000 übersetzt.")

    def _transport_changed(self):
        is_serial = str(self.transport_combo.currentData() or "tcp") == "serial"
        for w in (self.host_label, self.host_edit, self.port_label, self.port_spin):
            w.setVisible(not is_serial)
        for w in (self.serial_port_label, self.serial_port_edit, self.baud_label, self.baud_spin,
                  self.parity_label, self.parity_combo, self.bytesize_label, self.bytesize_combo,
                  self.stopbits_label, self.stopbits_combo):
            w.setVisible(is_serial)

    def accept(self):
        self._save_current_fields_to_selected_backend()
        self.main_window.settings["show_public_warning"] = bool(self.show_warning_cb.isChecked())
        if hasattr(self.main_window, "public_warning_label"):
            self.main_window.public_warning_label.setVisible(bool(self.show_warning_cb.isChecked()))
        self.main_window.set_current_device_model(str(self.device_combo.currentData() or DEFAULT_DEVICE_MODEL))
        backend = str(self.backend_combo.currentData() or "warmlink_raw")
        self.main_window.apply_communication_settings(backend)
        super().accept()


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
        self.regmap_path = os.path.join(resource_dir, "foxair_phnix_registers.json")
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
        self.knowledge_path = os.path.join(self.user_data_dir, "foxair_phnix_knowledge.json")
        self.bundled_knowledge_path = os.path.join(resource_dir, "foxair_phnix_knowledge.json")
        self.settings = self._load_settings()
        self.knowledge_defs = self._load_knowledge_defs()
        self.regmap = RegisterMap(self.regmap_path)
        self.register_defs = self._load_register_defs()

        self.thread: Optional[QThread] = None
        self.worker: Optional[ReaderWorker] = None

        self.table_rows: Dict[int, int] = {}
        self.latest_regs: Dict[int, object] = {}
        self.last_values: Dict[int, int] = {}
        self.previous_value_texts: Dict[int, str] = {}
        self.raw_dump = bytearray()
        self.connected = False
        self.foreign_frame_count = 0
        self.bus_rows: Dict[int, int] = {}
        self.bus_stats: Dict[int, dict] = {}
        self.raw_file: Optional[BinaryIO] = None
        self.raw_file_path: Optional[str] = None
        self.cached_regs: set[int] = set()
        self.pending_read_requests: list[dict[str, Any]] = []
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
        self.parameter_dialog: Optional[ParameterSettingsDialog] = None
        self.manual_register_dialog: Optional[ManualRegisterDialog] = None
        self.bus_dialog: Optional[BusAddressDialog] = None
        self.offline_dialog: Optional[OfflineRegisterBrowserDialog] = None
        self.backup_restore_dialog: Optional[BackupRestoreDialog] = None
        self.update_thread: Optional[QThread] = None
        self.update_worker: Optional[UpdateCheckWorker] = None
        self.register_write_dialogs: Dict[tuple[int, int], RegisterQuickWriteDialog] = {}
        self.last_contact_value: Optional[int] = None
        self.last_load_output_value: Optional[int] = None
        self.init_read_queue: list[tuple[int, int, str, int]] = []
        self.init_read_active = False
        self._suppress_name_resize = False

        self._build_ui()
        self.init_read_timer = QTimer(self)
        self.init_read_timer.setSingleShot(True)
        self.init_read_timer.timeout.connect(self._send_next_init_read)
        self.cache_timer = QTimer(self)
        self.cache_timer.timeout.connect(lambda: self.save_value_cache(silent=True))
        self._apply_cache_timer_state()
        self._log(f"Register-Mapping: {self.regmap_path} ({len(self.regmap)} Einträge)")
        if self.cache_load_start_cb.isChecked():
            self.load_value_cache(silent=False)
        self._log(f"Benutzerdaten: {self.user_data_dir}")
        QTimer.singleShot(700, self._autoconnect_if_enabled)
        if APP_EDITION.upper() == "PUBLIC":
            QTimer.singleShot(2500, self.check_for_updates_on_startup)

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
        backend_saved = str(self.settings.get("backend", "warmlink_raw"))
        if backend_saved not in BACKEND_LABELS:
            backend_saved = "warmlink_raw"
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
        self.display_translate_cb.setToolTip("Nur Display-Modbus: Parameterregister 1000–1999 werden als HMI/VP-Adresse +0x2000 gelesen/geschrieben.")
        self.display_translate_cb.setChecked(bool(active_cfg.get("display_translate_0x2000", backend_saved == "display_modbus")))
        self.comm_settings_btn = QPushButton("Programm-Einstellungen ...")
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
        self.raw_log_cb = QCheckBox("Raw anzeigen")
        self.raw_file_cb = QCheckBox("Raw in Datei (nc/bin)")
        self.raw_ascii_cb = QCheckBox("Raw ASCII-Vorschau")

        top.addWidget(self.comm_settings_btn)
        top.addWidget(self.comm_summary_label)
        top.addWidget(self.connect_btn)
        top.addWidget(self.disconnect_btn)
        top.addWidget(self.autoconnect_cb)
        top.addWidget(self.known_only_cb)
        top.addWidget(self.log_changes_only_cb)
        top.addWidget(self.raw_log_cb)
        top.addWidget(self.raw_file_cb)
        top.addWidget(self.raw_ascii_cb)
        top.addStretch(1)

        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter, 1)

        upper = QSplitter(Qt.Horizontal)
        splitter.addWidget(upper)

        self.register_table = QTableWidget(0, 11)
        self.register_table.setHorizontalHeaderLabels([
            "Reg", "Code", "Name", "Typ", "Rohwert", "Letzter Wert", "Signed", "Wert", "Frame", "Bus", "Zeit"
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
        self.register_table.setSortingEnabled(False)  # wichtig: sonst werden row-Indizes beim Live-Update falsch
        self.register_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.register_table.itemDoubleClicked.connect(self.open_register_quick_write_from_table_item)
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
        self.write_dry_btn = QPushButton("Dry-Run / Frame anzeigen")
        self.write_send_btn = QPushButton("ECHT senden")
        self.write_send_btn.setEnabled(False)
        self.read_count_spin = QSpinBox()
        self.read_count_spin.setRange(1, 125)
        self.read_count_spin.setValue(1)
        self.read_btn = QPushButton("FC03 lesen")
        self.manual_register_btn = QPushButton("Register lesen/schreiben ...")
        self.init_read_btn = QPushButton("Init-Blöcke lesen")
        self.init_pause_spin = QSpinBox()
        self.init_pause_spin.setRange(100, 5000)
        self.init_pause_spin.setValue(900)
        self.init_pause_spin.setSingleStep(100)
        self.init_pause_spin.setSuffix(" ms")
        self.init_pause_spin.setMaximumWidth(95)
        self.init_pause_spin.setToolTip("Pause zwischen den Init-Leseblöcken. Höher stellen, wenn die WP/Warmlink langsam antwortet.")

        manual_layout.addWidget(self.manual_register_btn, 0, 0, 1, 4)
        manual_layout.addWidget(self.init_read_btn, 1, 0)
        manual_layout.addWidget(QLabel("Pause:"), 1, 1)
        manual_layout.addWidget(self.init_pause_spin, 1, 2)
        manual_layout.setColumnStretch(3, 1)

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
        self.load_output_popup_btn = QPushButton("Lastausgang Decoder ...")
        self.fault_popup_btn = QPushButton("Störungen / Fehler ...")
        self.sg_popup_btn = QPushButton("SG Ready Editor ...")
        self.timer_editor_btn = QPushButton("Betriebsart Timer 1-6 ...")
        self.onoff_timer_btn = QPushButton("WP Ein/Aus Timer ...")
        self.param_settings_btn = QPushButton("Parameter Einstellungen ...")
        self.offline_browser_btn = QPushButton("Offline Register-Browser ...")
        self.bus_popup_btn = QPushButton("Gesehene Bus-Adressen ...")
        self.backup_restore_btn = QPushButton("Backup / Restore ...")
        self.update_check_btn = QPushButton("Update prüfen ...")
        self.contact_value_label.setVisible(False)
        special_layout.addWidget(self.param_settings_btn, 0, 0, 1, 2)
        special_layout.addWidget(self.onoff_timer_btn, 1, 0, 1, 2)
        special_layout.addWidget(self.timer_editor_btn, 2, 0, 1, 2)
        special_layout.addWidget(self.sg_popup_btn, 3, 0, 1, 2)
        special_layout.addWidget(self.contact_popup_btn, 4, 0, 1, 2)
        special_layout.addWidget(self.load_output_popup_btn, 5, 0, 1, 2)
        special_layout.addWidget(self.fault_popup_btn, 6, 0, 1, 2)
        special_layout.addWidget(self.backup_restore_btn, 7, 0, 1, 2)
        special_layout.addWidget(self.offline_browser_btn, 8, 0, 1, 2)
        special_layout.addWidget(self.bus_popup_btn, 9, 0, 1, 2)
        special_layout.addWidget(self.update_check_btn, 10, 0, 1, 2)
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
        self.log_text.setReadOnly(True)
        splitter.addWidget(self.log_text)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([620, 240])
        self.log_text.setMinimumHeight(170)

        self.comm_settings_btn.clicked.connect(self.open_communication_settings)
        self.connect_btn.clicked.connect(self.connect_to_device)
        self.disconnect_btn.clicked.connect(self.disconnect_from_device)
        self.write_dry_btn.clicked.connect(self.show_write_frame)
        self.write_send_btn.clicked.connect(self.send_write_frame)
        self.read_btn.clicked.connect(self.send_read_from_fields)
        self.manual_register_btn.clicked.connect(self.open_manual_register_dialog)
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
        self.raw_file_cb.stateChanged.connect(lambda _=None: self.on_raw_file_checkbox_changed())
        self.contact_popup_btn.clicked.connect(self.open_contact_decoder)
        self.load_output_popup_btn.clicked.connect(self.open_load_output_decoder)
        self.fault_popup_btn.clicked.connect(self.open_fault_decoder)
        self.sg_popup_btn.clicked.connect(self.open_sg_editor)
        self.param_settings_btn.clicked.connect(self.open_parameter_settings)
        self.offline_browser_btn.clicked.connect(self.open_offline_browser)
        self.bus_popup_btn.clicked.connect(self.open_bus_addresses)
        self.backup_restore_btn.clicked.connect(self.open_backup_restore)
        self.update_check_btn.clicked.connect(self.check_for_updates)
        self.cache_toggle_btn.clicked.connect(self.toggle_cache_options)
        self.cache_load_btn.clicked.connect(lambda: self.load_value_cache(silent=False))
        self.cache_save_btn.clicked.connect(lambda: self.save_value_cache(silent=False))
        self.cache_save_cyclic_cb.stateChanged.connect(lambda _=None: self._apply_cache_timer_state())
        self.cache_interval_spin.valueChanged.connect(lambda _=None: self._apply_cache_timer_state())
        self.register_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.register_table.customContextMenuRequested.connect(self.open_register_context_menu)

        self.frame_count = 0
        self._backend_changed()

    def _load_settings(self) -> dict:
        for path in (self.settings_path, getattr(self, "old_settings_path", "")):
            try:
                if path and os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

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
        self._save_settings()
        label = DEVICE_MODEL_LABELS.get(dev, dev)
        self._log(f"Geräteauswahl für Defaultwerte: {label} ({DEVICE_MODEL_HINT})")
        if self.parameter_dialog is not None and self.parameter_dialog.isVisible():
            self.parameter_dialog.refresh_table()
        if self.offline_dialog is not None and self.offline_dialog.isVisible():
            self.offline_dialog.items = self.offline_dialog._collect_items()
            self.offline_dialog.refresh()

    def _save_settings(self):
        try:
            cfg = self._backend_settings(self.current_backend_key())
            self._set_backend_settings(
                backend=self.current_backend_key(),
                transport=str(cfg.get("transport", "tcp")),
                host=self.host_edit.text().strip(),
                port=int(self.port_edit.value()),
                unit_id=int(self.unit_spin.value()),
                display_translate=self.display_translate_cb.isChecked(),
                serial_port=str(cfg.get("serial_port", "COM3")),
                baudrate=int(cfg.get("baudrate", 9600)),
                parity=str(cfg.get("parity", "N")),
                bytesize=int(cfg.get("bytesize", 8)),
                stopbits=float(cfg.get("stopbits", 1.0)),
            )
            data = {
                "backend": self.current_backend_key(),
                "backend_settings": self.settings.get("backend_settings", {}),
                "device_model": self.current_device_model(),
                "autoconnect_on_start": self.autoconnect_cb.isChecked(),
                "cache_load_on_start": self.cache_load_start_cb.isChecked(),
                "cache_save_on_exit": self.cache_save_exit_cb.isChecked(),
                "cache_save_cyclic": self.cache_save_cyclic_cb.isChecked(),
                "cache_interval_s": int(self.cache_interval_spin.value()),
                "show_public_warning": bool(getattr(self, "public_warning_label", None).isVisible()) if hasattr(self, "public_warning_label") else bool(self.settings.get("show_public_warning", True)),
            }
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except PermissionError as exc:
            self._log(f"SETTINGS speichern fehlgeschlagen: {exc}")
            self._log(f"Hinweis: Einstellungsdatei liegt bei {self.settings_path}. Bitte Schreibrechte für diesen Ordner prüfen.")
        except Exception as exc:
            self._log(f"SETTINGS speichern fehlgeschlagen: {exc}")

    def _backend_settings(self, backend: str) -> dict:
        backend = backend if backend in BACKEND_LABELS else "warmlink_raw"
        defaults = dict(BACKEND_DEFAULTS.get(backend, BACKEND_DEFAULTS["warmlink_raw"]))
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
            "display_translate_0x2000": bool(display_translate),
        }

    def apply_communication_settings(self, backend: str):
        backend = backend if backend in BACKEND_LABELS else "warmlink_raw"
        idx = self.backend_combo.findData(backend)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        cfg = self._backend_settings(backend)
        self.host_edit.setText(str(cfg.get("host", DEFAULT_HOST)))
        self.port_edit.setValue(int(cfg.get("port", DEFAULT_PORT)))
        self.unit_spin.setValue(int(cfg.get("unit_id", DEFAULT_BUS_ADDR)))
        self.display_translate_cb.setChecked(bool(cfg.get("display_translate_0x2000", backend == "display_modbus")))
        if hasattr(self, "write_bus_edit"):
            self.write_bus_edit.setText(f"0x{int(self.unit_spin.value()):02X}")
        self._update_comm_summary()
        self._save_settings()
        self._log(f"Kommunikation eingestellt: {self._communication_summary_text()}")

    def open_communication_settings(self):
        if self.connected:
            QMessageBox.information(self, "Kommunikation", "Bitte erst trennen, bevor die Kommunikationsart geändert wird.")
            return
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
        if backend == "display_modbus" and self.display_translate_cb.isChecked():
            parts.append("+0x2000")
        parts.append("Gerät: " + DEVICE_MODEL_LABELS.get(self.current_device_model(), self.current_device_model()) + " (nur Defaults)")
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
        if dtype in ("FLOW_M3H_X100", "FLOW_X100"):
            return f"{signed / 100.0:.1f} m³/h"
        if dtype in ("FLOW_M3H_X10", "FLOW_X10"):
            return f"{signed / 10.0:.1f} m³/h"
        if dtype in ("MINUTES", "MIN"):
            return f"{signed} min"
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
                self._log(f"Werte-Cache geladen: {loaded} Register, Stand {stamp_text}. Geladene Zeilen sind grau.")
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
        self.update_worker = UpdateCheckWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.result.connect(self._update_check_finished)
        self.update_worker.error.connect(self._update_check_error)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self._update_check_cleanup)
        self.update_thread.start()

    @Slot(dict)
    def _update_check_finished(self, info: dict):
        tag = str(info.get("tag") or "").strip()
        url = str(info.get("html_url") or UPDATE_RELEASES_URL).strip()
        assets = info.get("assets") if isinstance(info.get("assets"), list) else []
        current = parse_version_tuple(APP_VERSION)
        latest = parse_version_tuple(tag)

        setup_asset = next((a for a in assets if "setup" in str(a.get("name", "")).lower() and str(a.get("url", "")).strip()), None)
        portable_asset = next((a for a in assets if "portable" in str(a.get("name", "")).lower() and str(a.get("url", "")).strip()), None)
        primary_url = str((setup_asset or portable_asset or {}).get("url") or url)

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
                webbrowser.open(primary_url)
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

    def _log(self, text: str):
        stamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{stamp}] {text}")

    def _parse_int_text(self, text: str) -> int:
        text = text.strip()
        if not text:
            raise ValueError("Leere Eingabe")
        return int(text, 0)

    def current_backend_key(self) -> str:
        if hasattr(self, "backend_combo"):
            return str(self.backend_combo.currentData() or "warmlink_raw")
        return "warmlink_raw"

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
        backend = self.current_backend_key()
        if backend == "display_modbus" and self.display_translate_cb.isChecked() and 1000 <= int(addr) <= 1999:
            wire = int(addr) + 0x2000
            return wire, f"Display-Übersetzung: {addr}/0x{addr:04X} -> {wire}/0x{wire:04X}"
        return int(addr), ""

    def _wire_slave_addr(self, requested: Optional[int] = None) -> int:
        backend = self.current_backend_key()
        if backend in ("display_modbus", "standard_modbus"):
            return self.current_unit_id()
        return int(requested if requested is not None else DEFAULT_BUS_ADDR)

    def _write_single_for_backend(self) -> bool:
        return self.current_backend_key() in ("display_modbus", "standard_modbus")

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
        self._update_comm_summary()

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
        self.worker.disconnected.connect(self.thread.quit)
        self.worker.disconnected.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_thread_refs)

        self.thread.start()

    def disconnect_from_device(self):
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
        if self.raw_file_cb.isChecked():
            self._open_raw_file()

    @Slot()
    def on_disconnected(self):
        self.connected = False
        self.status_label.setText("getrennt")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.write_send_btn.setEnabled(False)
        self._close_raw_file()

    @Slot(str)
    def on_error(self, text: str):
        self._log(f"FEHLER: {text}")

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
    def on_raw_chunk(self, chunk: bytes):
        self.raw_dump.extend(chunk)
        if self.raw_file_cb.isChecked():
            if not self.raw_file:
                self._open_raw_file()
            if self.raw_file:
                self.raw_file.write(chunk)
                self.raw_file.flush()
        if self.raw_log_cb.isChecked():
            # Anzeige ähnlich nc/tee, aber binär sicher. Optional mit ASCII-Spalte.
            if self.raw_ascii_cb.isChecked():
                self._log(f"RX {len(chunk)}B: {hex_ascii_line(chunk, -1)}")
            else:
                self._log(f"RX {len(chunk)}B: {hexdump(chunk, -1)}")

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
        self.last_crc_label.setText(
            f"0x{frame.crc_got:04X} / calc 0x{frame.crc_calc:04X} / {'OK' if frame.crc_ok else 'BAD'}"
        )
        direction = self._frame_direction_text(frame)
        self.last_bus_label.setText(f"0x{frame.slave_addr:02X}")
        self.direction_label.setText(direction)
        self._update_bus_table(frame)
        self._apply_pending_read_response(frame)

        expected_slave = self._wire_slave_addr(DEFAULT_BUS_ADDR)
        if frame.slave_addr != expected_slave:
            self.foreign_frame_count += 1
            self.foreign_count_label.setText(str(self.foreign_frame_count))
            self._log(
                f"FREMD-FRAME: addr=0x{frame.slave_addr:02X}, func=0x{frame.func:02X}, "
                f"typ=0x{frame.typ:04X}, mode={frame.mode}, crc={'OK' if frame.crc_ok else 'BAD'}, "
                f"vermutung={guess_device_name(frame.slave_addr, frame.crc_ok)}, "
                f"RAW={hexdump(frame.raw, -1)}"
            )

        if frame.mode == "read-request":
            self._log(
                f"READ/Request gesehen: bus=0x{frame.slave_addr:02X}, "
                f"addr={frame.typ} / 0x{frame.typ:04X}, anzahl={frame.length_field}"
            )
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
        elif frame.mode == "write-response":
            self._log(
                f"WRITE/ACK gesehen: bus=0x{frame.slave_addr:02X}, "
                f"addr={frame.typ} / 0x{frame.typ:04X}, anzahl={frame.length_field}"
            )

        changed_regs_for_live_search: list[int] = []
        bulk_table_update = len(frame.registers) > 10
        old_table_updates = self.register_table.updatesEnabled()
        if bulk_table_update:
            self._suppress_name_resize = True
            self.register_table.setUpdatesEnabled(False)

        for reg in frame.registers:
            if self.known_only_cb.isChecked() and not reg.name:
                continue

            old_value = self.last_values.get(reg.reg)
            changed = old_value != reg.raw_value
            was_cached = reg.reg in self.cached_regs
            if was_cached:
                self.cached_regs.discard(reg.reg)
            if changed:
                changed_regs_for_live_search.append(reg.reg)
                if old_value is None:
                    self.previous_value_texts.setdefault(reg.reg, "--")
                else:
                    self.previous_value_texts[reg.reg] = f"{old_value} / 0x{old_value:04X}"
            self.last_values[reg.reg] = reg.raw_value

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

        if bulk_table_update:
            self._suppress_name_resize = False
            self.register_table.setUpdatesEnabled(old_table_updates)
            self._resize_name_column()

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

    def _background_for_register(self, reg_no: int, changed: bool) -> QColor:
        if reg_no in self.value_search_matches:
            return QColor(255, 190, 120)
        if reg_no in self.name_search_matches:
            return QColor(225, 210, 255)
        if reg_no in self.cached_regs:
            return QColor(225, 225, 225)
        if changed:
            return QColor(255, 245, 180)
        return QColor(255, 255, 255)

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
            reg.display_value,
            f"0x{reg.frame_type:04X}",
            f"0x{getattr(reg, 'slave_addr', DEFAULT_BUS_ADDR):02X}",
            time.strftime("%H:%M:%S", time.localtime(reg.timestamp)),
        ]
        is_block_row = is_block_dtype(reg.dtype)
        self.register_table.setRowHeight(row, 19 if is_block_row else 24)

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
            item.setBackground(self._background_for_register(reg.reg, changed))

        if not getattr(self, "_suppress_name_resize", False):
            self._resize_name_column()

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
        if self.manual_register_dialog is None or not self.manual_register_dialog.isVisible():
            self.manual_register_dialog = ManualRegisterDialog(self)
            self.manual_register_dialog.finished.connect(lambda _=None: setattr(self, "manual_register_dialog", None))
            self.manual_register_dialog.show()
        else:
            self.manual_register_dialog.raise_()
            self.manual_register_dialog.activateWindow()

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

    def toggle_cache_options(self):
        visible = not self.cache_options_widget.isVisible()
        self.cache_options_widget.setVisible(visible)
        self.cache_toggle_btn.setText("Einstellungen ausblenden" if visible else "Einstellungen ...")

    def _refresh_search_highlights(self):
        # Hintergrund in allen sichtbaren Zeilen neu setzen.
        for reg_no, row in list(self.table_rows.items()):
            bg = self._background_for_register(reg_no, False)
            for col in range(self.register_table.columnCount()):
                item = self.register_table.item(row, col)
                if item is not None:
                    item.setBackground(bg)

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

    def _apply_pending_read_response(self, frame):
        if frame.mode != "read-response":
            return
        now = time.time()
        self.pending_read_requests = [r for r in self.pending_read_requests if now - float(r.get("time", now)) < 15.0]
        for req in list(self.pending_read_requests):
            if int(req["slave_addr"]) != int(frame.slave_addr):
                continue
            quantity = int(req["quantity"])
            if len(frame.payload) != quantity * 2:
                continue
            start_addr = int(req["addr"])
            frame.typ = start_addr
            frame.length_field = quantity
            frame.registers = decode_read_response_registers(frame, start_addr, self.regmap)
            self._check_endblock_signature(frame, start_addr)
            self.pending_read_requests.remove(req)
            label = f" ({req.get('label')})" if req.get("label") else ""
            self._log(f"READ/Response passt zu Anfrage{label}: {start_addr} / 0x{start_addr:04X}, {quantity} Register")
            return

    def send_read_from_fields(self):
        try:
            slave_addr = self._parse_int_text(self.write_bus_edit.text())
            addr = self._parse_int_text(self.write_addr_edit.text())
            quantity = int(self.read_count_spin.value())
            self.send_read_request(addr, quantity, slave_addr=slave_addr, label="manuell")
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Leseanforderung", str(exc))

    def send_read_request(self, addr: int, quantity: int = 1, slave_addr: int = DEFAULT_BUS_ADDR, label: str = "", delay_ms: int = 0):
        frame, wire_addr, wire_slave, note = self._build_read_frame_for_backend(addr, quantity, slave_addr)
        note_text = f", {note}" if note else ""
        self._log(
            f"READ wird GESENDET [{self.current_backend_label()}]: bus=0x{wire_slave:02X}, "
            f"addr={addr}/0x{addr:04X} -> wire={wire_addr}/0x{wire_addr:04X}, "
            f"anzahl={quantity}, TX={hexdump(frame, -1)}{note_text}"
        )
        self.pending_read_requests.append({
            "slave_addr": wire_slave,
            "addr": addr,
            "wire_addr": wire_addr,
            "quantity": quantity,
            "label": label,
            "time": time.time(),
        })
        if not self.connected or not self.worker:
            self._log("READ nicht gesendet: keine aktive Verbindung.")
            return
        self.worker.enqueue_read(wire_addr, quantity, slave_addr=wire_slave, post_delay_ms=delay_ms)

    def send_init_reads(self):
        try:
            slave_addr = self._parse_int_text(self.write_bus_edit.text())
        except Exception:
            slave_addr = DEFAULT_BUS_ADDR
        # Der Button liest jetzt bewusst alles, was frueher ueber Basis + extra + V1.3 erreichbar war.
        # Nur Lesen, kein Schreiben. Mehr Daten haben sich in der Praxis nicht nachteilig gezeigt.
        blocks = [
            (1001, 90, "Init Extra Paketkopf/Block 1001/0x03E9"),
            (1018, 73, "Init V1.3 Paket 1 Nutzdaten 1018/0x03FA"),
            (1091, 90, "Init Extra Paketkopf/Block 1091/0x0443"),
            (1101, 80, "Init V1.3 Paket 2 Nutzdaten 1101/0x044D"),
            (1181, 90, "Init Extra Paketkopf/Block 1181/0x049D"),
            (1191, 80, "Init V1.3 Paket 3 Nutzdaten 1191/0x04A7"),
            (1271, 90, "Init Parameterblock 1271/0x04F7"),
            (1361, 90, "Init Extra-Block 1361/0x0551"),
            (1451, 90, "Init Extra-Block 1451/0x05AB"),
            (1541, 90, "Init Extra-Block 1541/0x0605"),
            (2001, 90, "Init Statusblock 2001/0x07D1"),
            (2091, 90, "Init Statusblock 2091/0x082B"),
        ]

        pause_ms = int(self.init_pause_spin.value()) if getattr(self, "init_pause_spin", None) is not None else 900
        self.init_read_queue = [(addr, quantity, label, slave_addr) for addr, quantity, label in blocks]
        self.init_read_active = True
        self.init_read_btn.setEnabled(False)
        self.init_read_btn.setText("Init läuft ...")
        text = ", ".join(f"{addr}/{qty}" for addr, qty, _ in blocks)
        self._log(f"INIT-Lesen gestartet: {len(blocks)} Blöcke, Pause {pause_ms} ms / {pause_ms/1000:.1f} s: {text}")
        self._send_next_init_read()

    def _send_next_init_read(self):
        if not self.init_read_queue:
            self.init_read_active = False
            self.init_read_btn.setEnabled(True)
            self.init_read_btn.setText("Init-Blöcke lesen")
            self._log("INIT-Lesen fertig / alle Blöcke angefordert.")
            return

        total_left = len(self.init_read_queue)
        addr, quantity, label, slave_addr = self.init_read_queue.pop(0)
        already_sent = "?"
        self._log(f"INIT-Lesen Block: {label} ({addr}/{quantity}), verbleibend danach: {total_left - 1}")
        self.send_read_request(addr, quantity, slave_addr=slave_addr, label=label, delay_ms=0)

        pause_ms = int(self.init_pause_spin.value()) if getattr(self, "init_pause_spin", None) is not None else 900
        self.init_read_timer.start(pause_ms)

    def open_register_quick_write_from_table_item(self, item):
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
        self.open_register_quick_write(reg_no, slave_addr)

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

        menu = QMenu(self)
        act_quick_write = menu.addAction(f"Register {reg_no} schnell schreiben ...")
        menu.addSeparator()
        act_read_one = menu.addAction(f"Register {reg_no} lesen")
        act_read_ten = menu.addAction(f"10 Register ab {reg_no} lesen")
        act_use_write = menu.addAction("Adresse ins Schreib-/Lesefeld übernehmen")
        action = menu.exec(self.register_table.viewport().mapToGlobal(pos))
        if action == act_quick_write:
            self.open_register_quick_write(reg_no, row_slave_addr)
        elif action == act_read_one:
            self.send_read_request(reg_no, 1, slave_addr=row_slave_addr, label="Rechtsklick")
        elif action == act_read_ten:
            self.send_read_request(reg_no, 10, slave_addr=row_slave_addr, label="Rechtsklick 10er")
        elif action == act_use_write:
            self.write_addr_edit.setText(str(reg_no))

    def open_register_quick_write(self, reg_no: int, slave_addr: int = DEFAULT_BUS_ADDR):
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

    def send_register_write(self, addr: int, value: int, slave_addr: int = DEFAULT_BUS_ADDR, label: str = "", delay_ms: int = 0):
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
        if not self.connected or not self.worker:
            self._log("WRITE nicht gesendet: keine aktive Verbindung.")
            return
        self.worker.enqueue_write(wire_addr, value, slave_addr=wire_slave, post_delay_ms=delay_ms, write_single=self._write_single_for_backend())

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

            answer = QMessageBox.question(
                self,
                "ECHTEN Write senden?",
                question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                self._log("WRITE abgebrochen: nicht gesendet.")
                return

            self._log(
                f"WRITE wird GESENDET [{self.current_backend_label()} / {fc_text}]: bus=0x{wire_slave:02X}, "
                f"addr={addr}/0x{addr:04X} -> wire={wire_addr}/0x{wire_addr:04X}, "
                f"value={value}/0x{value:04X}, TX={hexdump(frame, -1)}"
            )
            if not self.connected or not self.worker:
                self._log("WRITE nicht gesendet: keine aktive Verbindung.")
                return
            self.worker.enqueue_write(wire_addr, value, slave_addr=wire_slave, write_single=self._write_single_for_backend())
        except Exception as exc:
            QMessageBox.warning(self, "Ungültige Eingabe", str(exc))

    def open_timer_editor(self):
        if self.timer_dialog is None or not self.timer_dialog.isVisible():
            self.timer_dialog = TimerEditorDialog(self)
            self.timer_dialog.finished.connect(lambda _=None: setattr(self, "timer_dialog", None))
            self.timer_dialog.show()
        else:
            self.timer_dialog.raise_()
            self.timer_dialog.activateWindow()

    def open_onoff_timer_editor(self):
        if self.onoff_timer_dialog is None or not self.onoff_timer_dialog.isVisible():
            self.onoff_timer_dialog = OnOffTimerEditorDialog(self)
            self.onoff_timer_dialog.finished.connect(lambda _=None: setattr(self, "onoff_timer_dialog", None))
            self.onoff_timer_dialog.show()
        else:
            self.onoff_timer_dialog.raise_()
            self.onoff_timer_dialog.activateWindow()

    def open_silent_timer_editor(self):
        if self.silent_timer_dialog is None or not self.silent_timer_dialog.isVisible():
            self.silent_timer_dialog = SilentTimerDialog(self)
            self.silent_timer_dialog.finished.connect(lambda _=None: setattr(self, "silent_timer_dialog", None))
            self.silent_timer_dialog.show()
        else:
            self.silent_timer_dialog.raise_()
            self.silent_timer_dialog.activateWindow()

    def open_sg_editor(self):
        if self.sg_dialog is None or not self.sg_dialog.isVisible():
            self.sg_dialog = SGReadyEditorDialog(self)
            self.sg_dialog.finished.connect(lambda _=None: setattr(self, "sg_dialog", None))
            self.sg_dialog.show()
        else:
            self.sg_dialog.raise_()
            self.sg_dialog.activateWindow()


    def open_parameter_settings(self):
        if self.parameter_dialog is None or not self.parameter_dialog.isVisible():
            self.parameter_dialog = ParameterSettingsDialog(self)
            self.parameter_dialog.finished.connect(lambda _=None: setattr(self, "parameter_dialog", None))
            self.parameter_dialog.show()
        else:
            self.parameter_dialog.refresh_table()
            self.parameter_dialog.raise_()
            self.parameter_dialog.activateWindow()

    def send_timer_values(self, slave_addr: int, values: list[tuple[int, int, str]], delay_ms: int = 1200, title: str = "Timer"):
        if not self.connected or not self.worker:
            self._log("TIMER nicht gesendet: keine aktive Verbindung.")
            return

        lines = []
        for addr, value, label in values:
            frame, wire_addr, wire_slave, note, fc_text = self._build_write_frame_for_backend(addr, value, slave_addr)
            note_text = f" ({note})" if note else ""
            lines.append(f"{label}: Reg {addr}/0x{addr:04X} -> wire {wire_addr}/0x{wire_addr:04X} = {value}/0x{value:04X} {fc_text} TX={hexdump(frame, -1)}{note_text}")

        answer = QMessageBox.question(
            self,
            f"{title} schreiben?",
            f"Diese {title}-Register schreiben?\n\n" + "\n".join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._log("TIMER Write abgebrochen: nicht gesendet.")
            return

        self._log(f"TIMER wird GESENDET ({title}):\n" + "\n".join(lines))
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
        self._save_settings()
        if self.cache_save_exit_cb.isChecked():
            self.save_value_cache(silent=False)
        self.disconnect_from_device()
        event.accept()


def main():
    set_windows_app_id()
    app = QApplication(sys.argv)
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
