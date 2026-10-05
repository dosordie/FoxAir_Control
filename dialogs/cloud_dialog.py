# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import time
import urllib.parse
from typing import Any, Optional

from PySide6.QtCore import QThread, QTimer, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar,
)

from cloud.warmlink_api import (
    ENDPOINT_AUTO_WRITE, ENDPOINT_WRITE_MODEL_VALUE, translate_cloud_error_message,
)
from cloud.metadata import resolve_cloud_range
from cloud.polling import CloudSession
from cloud.token_store import (
    AsyncKeyringStore, KEYRING_SERVICE, delete_password, delete_token,
    set_password, set_token,
)
from cloud.warmlink_codes import (
    WARMLINK_644_DISCOVERY_CODES, WARMLINK_CLOUD_WRITE_TEST_CODES, cloud_hint,
    cloud_modbus_register, WARMLINK_CLOUD_CREDIT, code_confidence,
    code_display_name, code_unit,
)
from dialogs.cloud_table_helpers import (
    compare_source_rows, compare_table_values, data_table_values, device_combo_label,
    filtered_cloud_rows, finder_cloud_row, finder_code_label,
    local_display_value, mask_cloud_value, try_float, value_finder_matches,
)
from workers.warmlink_cloud_worker import (
    WarmLinkCloudWorker, WarmLinkCloudCommandWorker, WarmLinkCloudDebugWorker,
)
from cloud.device_metadata import cached_device_metadata
from core.settings_manager import ensure_warmlink_cloud_defaults

class WarmLinkCloudDialog(QDialog):
    """Optionale WarmLink/Linked-Go Cloud-Anbindung mit Overlay/Compare.

    Standard bleibt lesend. Der Schreibtest ist getrennt, deaktiviert und nur
    fuer wenige erlaubte Codes vorgesehen.
    """

    DEVICE_COLUMNS = [
        "deviceNickName", "deviceName", "model", "custModel", "deviceStatus", "isFault",
        "dtuSoftwareVer", "dtuSignalIntensity", "isShared", "houseName", "houseRoleType", "discoverySource",
    ]
    DATA_COLUMNS = ["code", "name", "value", "dataType", "rangeStart", "rangeEnd", "letzter Abruf", "Status", "Mapping", "Mapping-Status", "Hinweis"]
    COMPARE_COLUMNS = ["Cloud-Code", "Reg", "Code", "Name", "Lokal", "Cloud", "Diff", "Einheit", "Confidence", "Status", "Hinweis"]
    FINDER_COLUMNS = ["Cloud-Code", "Cloud-Wert", "Reg", "Code", "Name", "Lokal", "Match", "Hinweis"]

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("WarmLink Cloud / LTE")
        self.setWindowIcon(main_window.windowIcon())
        self.resize(1240, 820)
        self.cloud_thread: Optional[QThread] = None
        self.cloud_worker: Optional[WarmLinkCloudWorker] = None
        self.command_thread: Optional[QThread] = None
        self.command_worker: Optional[WarmLinkCloudCommandWorker] = None
        self.debug_thread: Optional[QThread] = None
        self.debug_worker: Optional[WarmLinkCloudDebugWorker] = None
        self.devices: list[dict[str, Any]] = []
        self.data_rows: list[dict[str, Any]] = []
        credentials = getattr(main_window, "cloud_credentials_cache", {})
        self._cloud_token = credentials.get("token")
        self._cloud_token_login_at = credentials.get("login_at", 0.0)
        self._cloud_token_username = credentials.get("token_user", "")
        self._loading_settings = False
        self._session_password = credentials.get("session_password")
        if not hasattr(main_window, "cloud_session"):
            main_window.cloud_session = CloudSession()
        self._keyring = getattr(main_window, "_cloud_keyring_store", None)
        if self._keyring is None:
            self._keyring = main_window._cloud_keyring_store = AsyncKeyringStore(main_window)
        self._cached_password = credentials.get("password", "")
        self._credentials_username = credentials.get("password_user", "")
        self._compare_dirty = self._finder_dirty = True
        self._data_codes = []
        self._rendered_data = {}
        self._mapping_cache = {}
        self._pending_overlay = {}
        self._overlay_structure_changed = False
        self._overlay_timer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.timeout.connect(self._flush_overlay_chunk)
        self._pending_data_rows = []
        self._data_render_timer = QTimer(self)
        self._data_render_timer.setSingleShot(True)
        self._data_render_timer.timeout.connect(self._render_data_chunk)
        self._data_resize_pending = False
        self._stopping = False
        self._build_ui()
        self._load_settings()

    @property
    def session(self):
        return self.main_window.cloud_session

    @session.setter
    def session(self, session):
        self.main_window.cloud_session = session

    def _remember_credentials(self):
        # Credentials stay in memory/keyring; device metadata has a separate safe cache.
        self.main_window.cloud_credentials_cache = {
            "token": self._cloud_token, "login_at": self._cloud_token_login_at,
            "token_user": self._cloud_token_username, "password": self._cached_password,
            "password_user": self._credentials_username, "session_password": self._session_password,
        }

    def _cloud_settings(self) -> dict[str, Any]:
        return ensure_warmlink_cloud_defaults(self.main_window.settings)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Optionale WarmLink/Linked-Go Cloud/LTE-Anbindung. Lesen per getDataByCode. "
            "Cloud-Werte koennen als Zusatzspalten im Hauptfenster angezeigt und mit lokalen Registern verglichen werden. "
            "Passwort wird nicht in config.json gespeichert, sondern im OS-Keyring."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        login_box = QGroupBox("Login / Status")
        layout.addWidget(login_box)
        login = QGridLayout(login_box)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("E-Mail / WarmLink Login")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("leer lassen = gespeichertes Keyring-Passwort verwenden")
        self.status_label = QLabel("nicht verbunden")
        self.status_label.setWordWrap(True)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 3600)
        self.interval_spin.setValue(30)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setToolTip("Livewerte alle 30 s; einstellbar von 10 bis 3600 s. Konfiguration wird separat geladen.")
        self.overlay_cb = QCheckBox("Cloud im Hauptfenster anzeigen")
        self.overlay_cb.setToolTip("Gemappte Cloud-Werte als Zusatzspalten/Cloud-only-Zeilen in der Haupttabelle anzeigen.")
        self.auto_start_cb = QCheckBox("Cloud-Polling beim App-Start")
        self.auto_start_cb.setToolTip("Startet Cloud-Polling im Hintergrund nach Programmstart, wenn Zugangsdaten gespeichert sind.")
        self.login_fallbacks_cb = QCheckBox("Login-Fallbacks erlauben")
        self.login_fallbacks_cb.setToolTip("Wenn MD5 bzw. die gespeicherte Methode fehlschlägt, weitere Hash-/App-Login-Varianten testen.")
        self.save_token_cb = QCheckBox("Cloud-Token im Keyring speichern")
        self.save_token_cb.setToolTip("Lädt und speichert Token im OS-Keyring. Der Token der aktuellen Sitzung bleibt auch ohne Speicherung im Arbeitsspeicher verfügbar.")
        self.test_btn = QPushButton("Login testen")
        self.save_btn = QPushButton("Zugang speichern")
        self.delete_btn = QPushButton("Zugang löschen")
        self.poll_once_btn = QPushButton("Jetzt abrufen")
        self.start_poll_btn = QPushButton("Polling starten")
        self.reload_static_btn = QPushButton("Konfigurationswerte neu laden")
        self.rediscover_btn = QPushButton("Geräte neu suchen")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Bereit")
        self.stop_poll_btn = QPushButton("Polling stoppen")
        self.stop_poll_btn.setEnabled(False)
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(360)
        self.device_combo.setToolTip("Gerätewechsel nur bei gestopptem Cloud-Polling möglich.")

        login.addWidget(QLabel("Benutzername:"), 0, 0)
        login.addWidget(self.username_edit, 0, 1, 1, 3)
        login.addWidget(QLabel("Passwort:"), 1, 0)
        login.addWidget(self.password_edit, 1, 1, 1, 3)
        login.addWidget(QLabel("Polling-Intervall:"), 2, 0)
        login.addWidget(self.interval_spin, 2, 1)
        login.addWidget(QLabel("Gerät:"), 2, 2)
        login.addWidget(self.device_combo, 2, 3)
        device_buttons = QHBoxLayout()
        device_buttons.addWidget(self.rediscover_btn)
        device_buttons.addStretch(1)
        login.addLayout(device_buttons, 3, 3)
        login.addWidget(QLabel("Status:"), 3, 0)
        login.addWidget(self.status_label, 3, 1, 1, 2)
        btn_row = QHBoxLayout()
        for b in (self.test_btn, self.save_btn, self.delete_btn, self.poll_once_btn, self.start_poll_btn, self.stop_poll_btn, self.overlay_cb, self.auto_start_cb, self.login_fallbacks_cb, self.save_token_cb):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        login.addLayout(btn_row, 4, 0, 1, 4)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.reload_static_btn)
        login.addLayout(progress_row, 5, 0, 1, 4)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        dev_tab = QWidget()
        dev_layout = QVBoxLayout(dev_tab)
        self.device_table = QTableWidget(0, len(self.DEVICE_COLUMNS))
        self.device_table.setHorizontalHeaderLabels(self.DEVICE_COLUMNS)
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.device_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        dev_layout.addWidget(self.device_table, 1)
        self.device_table.itemSelectionChanged.connect(self._device_table_selection_changed)
        self.tabs.addTab(dev_tab, "Geräte")

        data_tab = QWidget()
        data_layout = QVBoxLayout(data_tab)
        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter/Suche in code/name/value ...")
        self.unsupported_only_cb = QCheckBox("nur leer/unsupported")
        self.mapping_issues_only_cb = QCheckBox("Nur ungemappte / unsichere anzeigen")
        self.export_csv_btn = QPushButton("CSV Export")
        self.export_mapping_check_btn = QPushButton("Mapping-Prüfliste exportieren")
        self.export_json_btn = QPushButton("JSON Export")
        filter_row.addWidget(QLabel("Filter:"))
        filter_row.addWidget(self.filter_edit, 1)
        filter_row.addWidget(self.unsupported_only_cb)
        filter_row.addWidget(self.mapping_issues_only_cb)
        filter_row.addWidget(self.export_csv_btn)
        filter_row.addWidget(self.export_mapping_check_btn)
        filter_row.addWidget(self.export_json_btn)
        data_layout.addLayout(filter_row)
        self.data_table = QTableWidget(0, len(self.DATA_COLUMNS))
        self.data_table.setHorizontalHeaderLabels(self.DATA_COLUMNS)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        data_layout.addWidget(self.data_table, 1)
        self.tabs.addTab(data_tab, "Daten")

        compare_tab = QWidget()
        compare_layout = QVBoxLayout(compare_tab)
        compare_hint = QLabel("Vergleicht gemappte Cloud-Codes mit lokalen Registerwerten. Unknown/Candidate bleibt sichtbar, damit neue Register gefunden werden können.")
        compare_hint.setWordWrap(True)
        compare_layout.addWidget(compare_hint)
        compare_btn_row = QHBoxLayout()
        self.compare_refresh_btn = QPushButton("Vergleich aktualisieren")
        self.compare_refresh_btn.clicked.connect(self.refresh_compare)
        compare_btn_row.addWidget(self.compare_refresh_btn)
        self.export_mapping_candidates_btn = QPushButton("Mapping-Kandidaten exportieren")
        self.export_mapping_candidates_btn.setToolTip("Exportiert alle aktuellen Cloud-Daten mit bekannten lokalen Mappings und optionalen Wertefinder-Kandidaten als CSV.")
        compare_btn_row.addStretch(1)
        compare_btn_row.addWidget(self.export_mapping_candidates_btn)
        compare_layout.addLayout(compare_btn_row)
        self.compare_table = QTableWidget(0, len(self.COMPARE_COLUMNS))
        self.compare_table.setHorizontalHeaderLabels(self.COMPARE_COLUMNS)
        self.compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.compare_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.compare_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        compare_layout.addWidget(self.compare_table, 1)
        self.tabs.addTab(compare_tab, "Cloud ↔ Lokal")

        finder_tab = QWidget()
        finder_layout = QVBoxLayout(finder_tab)
        finder_hint = QLabel("Wertefinder: sucht den ausgewählten Cloud-Wert in den aktuell bekannten lokalen Modbus-/Display-Werten. Gut für SG Status oder andere noch unbekannte Cloud-Codes.")
        finder_hint.setWordWrap(True)
        finder_layout.addWidget(finder_hint)
        finder_controls = QHBoxLayout()
        self.finder_code_combo = QComboBox()
        self.finder_code_combo.setMinimumWidth(280)
        self.finder_tolerance_spin = QDoubleSpinBox()
        self.finder_tolerance_spin.setRange(0.0, 99999.0)
        self.finder_tolerance_spin.setDecimals(3)
        self.finder_tolerance_spin.setValue(0.0)
        self.finder_nonzero_cb = QCheckBox("0-Werte ausblenden")
        self.finder_nonzero_cb.setChecked(True)
        self.finder_btn = QPushButton("lokale Kandidaten suchen")
        finder_controls.addWidget(QLabel("Cloud-Code:"))
        finder_controls.addWidget(self.finder_code_combo, 1)
        finder_controls.addWidget(QLabel("Toleranz:"))
        finder_controls.addWidget(self.finder_tolerance_spin)
        finder_controls.addWidget(self.finder_nonzero_cb)
        finder_controls.addWidget(self.finder_btn)
        finder_layout.addLayout(finder_controls)
        self.finder_table = QTableWidget(0, len(self.FINDER_COLUMNS))
        self.finder_table.setHorizontalHeaderLabels(self.FINDER_COLUMNS)
        self.finder_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.finder_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.finder_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        finder_layout.addWidget(self.finder_table, 1)
        self.tabs.addTab(finder_tab, "Wertefinder")

        write_tab = QWidget()
        write_layout = QGridLayout(write_tab)
        write_info = QLabel("Schreibtest: standardmäßig Dry-Run. Erst 'wirklich senden' aktivieren + Dialog bestätigen. Nur erlaubte Testcodes sind verfügbar.")
        write_info.setWordWrap(True)
        self.write_enable_cb = QCheckBox("Schreibtest freischalten")
        self.write_send_cb = QCheckBox("wirklich senden (kein Dry-Run)")
        self.write_code_combo = QComboBox()
        for code, meta in WARMLINK_CLOUD_WRITE_TEST_CODES.items():
            self.write_code_combo.addItem(f"{code} - {meta.get('name', code)}", code)
        self.write_value_combo = QComboBox()
        self.write_endpoint_edit = QLineEdit(ENDPOINT_AUTO_WRITE)
        self.write_btn = QPushButton("Schreibtest ausführen")
        self.write_btn.setEnabled(False)
        self.write_result = QTextEdit()
        self.write_result.setReadOnly(True)
        write_layout.addWidget(write_info, 0, 0, 1, 3)
        write_layout.addWidget(self.write_enable_cb, 1, 0)
        write_layout.addWidget(self.write_send_cb, 1, 1)
        write_layout.addWidget(QLabel("Code:"), 2, 0)
        write_layout.addWidget(self.write_code_combo, 2, 1, 1, 2)
        write_layout.addWidget(QLabel("Wert:"), 3, 0)
        write_layout.addWidget(self.write_value_combo, 3, 1, 1, 2)
        write_layout.addWidget(QLabel("Endpoint:"), 4, 0)
        write_layout.addWidget(self.write_endpoint_edit, 4, 1, 1, 2)
        write_layout.addWidget(self.write_btn, 5, 0, 1, 3)
        write_layout.addWidget(self.write_result, 6, 0, 1, 3)
        write_layout.setRowStretch(6, 1)
        self.tabs.addTab(write_tab, "Schreibtest")

        codes_tab = QWidget()
        codes_layout = QVBoxLayout(codes_tab)
        self.codes_edit = QTextEdit()
        self.codes_edit.setPlainText("\n".join(WARMLINK_644_DISCOVERY_CODES))
        self.codes_edit.setToolTip("Familie 644: bestätigte Cloud-Codes plus read-only App-Kandidaten; unbekannte Codes sind erlaubt.")
        codes_layout.addWidget(QLabel("Code-Liste für getDataByCode:"))
        codes_layout.addWidget(self.codes_edit, 1)
        self.tabs.addTab(codes_tab, "Codes / Mapping")

        debug_tab = QWidget()
        debug_layout = QGridLayout(debug_tab)
        debug_hint = QLabel(
            "Generischer API-Debugger. Nutzt Host, Anmeldung und Token der bestehenden Cloud-Anbindung; "
            "es sind ausschließlich relative API-Pfade erlaubt."
        )
        debug_hint.setWordWrap(True)
        self.debug_method_combo = QComboBox()
        self.debug_method_combo.addItems(["GET", "POST", "PUT", "DELETE"])
        self.debug_path_edit = QLineEdit()
        self.debug_path_edit.setPlaceholderText("cloudservice/api/device/ota/searchSoftwareCode")
        self.debug_body_edit = QTextEdit()
        self.debug_body_edit.setPlaceholderText('Optionaler JSON-Body, z. B. {"deviceCode": "..."}')
        self.debug_device_btn = QPushButton("Aktuellen Gerätecode einfügen")
        self.debug_template_btn = QPushButton("getDataByCode vorbereiten")
        self.debug_relogin_cb = QCheckBox("Bei 401 automatisch neu anmelden")
        self.debug_relogin_cb.setChecked(False)
        self.debug_send_btn = QPushButton("Senden")
        self.debug_result_edit = QTextEdit()
        self.debug_result_edit.setReadOnly(True)
        debug_layout.addWidget(debug_hint, 0, 0, 1, 3)
        debug_layout.addWidget(QLabel("Methode:"), 1, 0)
        debug_layout.addWidget(self.debug_method_combo, 1, 1)
        debug_layout.addWidget(QLabel("Relativer API-Pfad:"), 2, 0)
        debug_layout.addWidget(self.debug_path_edit, 2, 1, 1, 2)
        debug_layout.addWidget(QLabel("JSON-Body:"), 3, 0)
        debug_layout.addWidget(self.debug_body_edit, 3, 1, 1, 2)
        debug_buttons = QHBoxLayout()
        debug_buttons.addWidget(self.debug_device_btn)
        debug_buttons.addWidget(self.debug_template_btn)
        debug_buttons.addStretch(1)
        debug_layout.addLayout(debug_buttons, 4, 1, 1, 2)
        debug_layout.addWidget(self.debug_relogin_cb, 5, 1, 1, 2)
        debug_layout.addWidget(self.debug_send_btn, 6, 0, 1, 3)
        debug_layout.addWidget(QLabel("Antwort:"), 7, 0)
        debug_layout.addWidget(self.debug_result_edit, 7, 1, 1, 2)
        debug_layout.setRowStretch(3, 1)
        debug_layout.setRowStretch(7, 2)
        self.tabs.addTab(debug_tab, "API-Debugger")

        credit = QLabel(WARMLINK_CLOUD_CREDIT)
        credit.setWordWrap(True)
        credit.setStyleSheet("color: #666666;")
        layout.addWidget(credit)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.close_btn = QPushButton("Schließen")
        close_row.addWidget(self.close_btn)
        layout.addLayout(close_row)

        self.test_btn.clicked.connect(lambda: self._start_worker(poll_once=True, just_login=False))
        self.poll_once_btn.clicked.connect(lambda: self._start_worker(poll_once=True, just_login=False))
        self.start_poll_btn.clicked.connect(lambda: self._start_worker(poll_once=False, just_login=False))
        self.stop_poll_btn.clicked.connect(self.stop_worker)
        self.reload_static_btn.clicked.connect(self.reload_static_values)
        self.rediscover_btn.clicked.connect(lambda: self._start_worker(True, discovery_only=True))
        self.tabs.currentChanged.connect(self._tab_changed)
        self.save_btn.clicked.connect(self.save_credentials)
        self.delete_btn.clicked.connect(self.delete_credentials)
        self.auto_start_cb.toggled.connect(lambda _=None: self._save_settings())
        self.overlay_cb.toggled.connect(self._overlay_toggled)
        self.login_fallbacks_cb.toggled.connect(lambda _=None: self._save_settings())
        self.save_token_cb.toggled.connect(self._save_token_toggled)
        self.username_edit.editingFinished.connect(self._save_settings)
        self.device_combo.currentIndexChanged.connect(self._device_selection_changed)
        self.filter_edit.textChanged.connect(lambda _=None: self.refresh_data())
        self.unsupported_only_cb.toggled.connect(lambda _=None: self.refresh_data())
        self.mapping_issues_only_cb.toggled.connect(lambda _=None: self.refresh_data())
        self.export_csv_btn.clicked.connect(self.export_csv)
        self.export_mapping_check_btn.clicked.connect(self.export_mapping_check_csv)
        self.export_json_btn.clicked.connect(self.export_json)
        self.export_mapping_candidates_btn.clicked.connect(self.export_mapping_candidates_csv)
        self.write_enable_cb.toggled.connect(self._update_write_controls)
        self.write_code_combo.currentIndexChanged.connect(lambda _=None: self._refresh_write_values())
        self.write_btn.clicked.connect(self.run_write_test)
        self.finder_btn.clicked.connect(self.run_value_finder)
        self.debug_send_btn.clicked.connect(self.run_debug_request)
        self.debug_device_btn.clicked.connect(self._insert_debug_device_code)
        self.debug_template_btn.clicked.connect(self._prepare_debug_get_data)
        self.close_btn.clicked.connect(self.close)
        self._refresh_write_values()

    def _initial_token_for_user(self, user: str) -> str | None:
        if self._cloud_token_username == user and self._cloud_token:
            return self._cloud_token
        return None

    def _load_settings(self):
        cfg = self._cloud_settings()
        signal_widgets = (
            self.overlay_cb,
            self.auto_start_cb,
            self.login_fallbacks_cb,
            self.save_token_cb,
            self.interval_spin,
            self.device_combo,
        )
        previous_signal_states = [widget.blockSignals(True) for widget in signal_widgets]
        self._loading_settings = True
        try:
            self.username_edit.setText(str(cfg.get("username", "")))
            self.interval_spin.setValue(min(3600, max(10, int(cfg.get("poll_interval_s", 30) or 30))))
            self.overlay_cb.setChecked(bool(cfg.get("overlay_enabled", True)))
            self.auto_start_cb.setChecked(bool(cfg.get("auto_start_polling", False)))
            self.login_fallbacks_cb.setChecked(bool(cfg.get("login_fallbacks", False)))
            self.save_token_cb.setChecked(bool(cfg.get("save_token", True)))
            selected = str(cfg.get("selected_device_code", ""))
            user = self.username_edit.text().strip()
            memory_cache = bool(user and self.session.username == user and self.session.devices)
            if memory_cache:
                self.session.devices_cached = True
                self.devices = cached_device_metadata(self.session.devices)
                self.data_rows = [dict(row) for row in self.session.rows.values()]
                if self.session.candidates:
                    self.codes_edit.setPlainText("\n".join(self.session.candidates))
            else:
                self.devices = cached_device_metadata(cfg.get("cached_devices", [])) if user and cfg.get("cached_devices_username") == user else []
                self.session = CloudSession(username=user, device_code=selected,
                    devices=list(self.devices), devices_cached=bool(self.devices))
            self._devices_username = user
            self.refresh_devices()
            if self.username_edit.text().strip():
                self.status_label.setText(f"bereit, Keyring-Service: {KEYRING_SERVICE}")
        finally:
            self._loading_settings = False
            for widget, blocked in zip(signal_widgets, previous_signal_states):
                widget.blockSignals(blocked)

    def _save_settings(self):
        if getattr(self, "_loading_settings", False):
            return
        cfg = self._cloud_settings()
        user = self.username_edit.text().strip()
        if user != self._devices_username:
            self.devices = []
            self.data_rows = []
            self._pending_overlay.clear()
            self._pending_data_rows.clear()
            self._data_render_timer.stop()
            self._devices_username = user
            self.session = CloudSession(username=user)
            cfg["cached_devices"] = []
            cfg["cached_devices_username"] = user
            cfg.pop("selected_device_code", None)
            self.refresh_devices()
            self.refresh_data()
            self.main_window.set_cloud_connection_state(False)
            if hasattr(self.main_window, "clear_cloud_device_values"):
                self.main_window.clear_cloud_device_values()
        cfg["username"] = user
        cfg["poll_interval_s"] = int(self.interval_spin.value())
        cfg["overlay_enabled"] = bool(self.overlay_cb.isChecked())
        cfg["auto_start_polling"] = bool(self.auto_start_cb.isChecked())
        cfg["show_cloud_only"] = True
        cfg["login_method"] = str(cfg.get("login_method") or "md5").strip() or "md5"
        cfg["login_fallbacks"] = bool(self.login_fallbacks_cb.isChecked())
        cfg["save_token"] = bool(self.save_token_cb.isChecked())
        if self.device_combo.currentData():
            cfg["selected_device_code"] = str(self.device_combo.currentData())
        self.main_window._save_settings(sync_main_fields=False)


    def _save_token_toggled(self, checked: bool) -> None:
        self._save_settings()
        if checked:
            return
        user = self.username_edit.text().strip()
        if user:
            self._keyring.submit(lambda: delete_token(user))
        self._cloud_token = None
        self._cloud_token_login_at = 0.0
        self._cloud_token_username = ""
        self._remember_credentials()

    def _codes(self) -> list[str]:
        text = self.codes_edit.toPlainText().replace(",", "\n").replace(";", "\n")
        out: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            code = line.strip()
            if not code or code.startswith("#"):
                continue
            if code not in seen:
                out.append(code)
                seen.add(code)
        return out or list(WARMLINK_644_DISCOVERY_CODES)

    def _password(self) -> str | None:
        # Only in-memory data here. Workers load an absent password from the OS.
        user = self.username_edit.text().strip()
        return self.password_edit.text() or (self._cached_password if self._credentials_username == user else "")

    @Slot(str, str)
    def _on_credentials_loaded(self, user, password):
        self._credentials_username, self._cached_password = user, password
        self._remember_credentials()


    def save_credentials(self):
        user = self.username_edit.text().strip()
        pw = self.password_edit.text()
        if not user:
            QMessageBox.warning(self, "WarmLink Cloud", "Benutzername fehlt.")
            return
        if pw:
            self._cached_password, self._credentials_username = pw, user
            self._remember_credentials()
            self.status_label.setText("Zugang wird gespeichert ...")
            def saved(_value, error):
                if error:
                    self.status_label.setText("Keyring: Speichern fehlgeschlagen")
                    return
                if self.username_edit.text().strip() == user and self.password_edit.text() == pw:
                    self.password_edit.clear()
                self.status_label.setText("Zugang im OS-Keyring gespeichert.")
                self.main_window._log("WarmLink Cloud: Zugang im OS-Keyring gespeichert.")
            self._keyring.submit(lambda: set_password(user, pw), saved)
        self._save_settings()
        if not pw:
            self.status_label.setText("Einstellungen gespeichert.")

    def delete_credentials(self):
        user = self.username_edit.text().strip()
        if user:
            self._keyring.submit(lambda: (delete_password(user), delete_token(user)))
        self._cached_password = ""
        self._credentials_username = ""
        self.session = CloudSession()
        self.stop_worker()
        cfg = self._cloud_settings()
        for key in ("username", "selected_device_code", "cached_devices", "cached_devices_username"):
            cfg.pop(key, None)
        self.main_window._save_settings(sync_main_fields=False)
        self.devices = []
        self.data_rows = []
        self._pending_overlay.clear()
        self._pending_data_rows.clear()
        self._data_render_timer.stop()
        if hasattr(self.main_window, "clear_cloud_device_values"):
            self.main_window.clear_cloud_device_values()
        self.username_edit.clear()
        self._devices_username = ""
        self.refresh_devices()
        self.refresh_data()
        self.password_edit.clear()
        self._cloud_token = None
        self._cloud_token_login_at = 0.0
        self._cloud_token_username = ""
        self._session_password = None
        self._remember_credentials()
        self.main_window.set_cloud_connection_state(False)
        self.status_label.setText("Zugang gelöscht.")
        self.main_window._log("WarmLink Cloud: Zugang gelöscht.")

    def _selected_device_code(self) -> str | None:
        data = self.device_combo.currentData()
        return str(data).strip() if data else None

    def _device_selection_changed(self, _index: int | None = None) -> None:
        if not self._loading_settings and self.session.device_code and self.session.device_code != self._selected_device_code():
            self.session = CloudSession(username=self.username_edit.text().strip(),
                device_code=self._selected_device_code() or "", devices=list(self.devices), devices_cached=bool(self.devices))
            self.data_rows = []
            self._pending_overlay.clear()
            self._pending_data_rows.clear()
            self._data_render_timer.stop()
            self._compare_dirty = self._finder_dirty = True
            self.refresh_data()
            if hasattr(self.main_window, "clear_cloud_device_values"):
                self.main_window.clear_cloud_device_values()
            elif hasattr(self.main_window, "clear_cloud_overlay"):
                self.main_window.clear_cloud_overlay()
        self._update_device_controls()
        self._save_settings()
        if getattr(self.main_window, "cloud_session_authenticated", False):
            self.main_window.set_cloud_connection_state(True, self._selected_device_code())
        if not self._loading_settings and self._selected_device_code():
            self.main_window._log(f"WarmLink Cloud: Gerät ausgewählt: {self._mask(self._selected_device_code())}")

    def _update_device_controls(self) -> None:
        """Keep device mutation locked to a stopped cloud polling session."""
        running = self.cloud_thread is not None
        self.device_combo.setEnabled(not running)
        self.rediscover_btn.setEnabled(not running)
        self.username_edit.setEnabled(not running)
        self.password_edit.setEnabled(not running)
        self.delete_btn.setEnabled(not running)
        self.interval_spin.setEnabled(not running)
        self.reload_static_btn.setEnabled(bool(self.session.scanned and self.session.static_codes) and not self._stopping)

    def _start_worker(self, poll_once: bool, just_login: bool = False, *, force_discovery=False, reload_static=False, discovery_only=False, full_scan=False):
        if self.cloud_thread is not None:
            QMessageBox.information(self, "WarmLink Cloud", "Cloud-Worker läuft bereits.")
            return
        user = self.username_edit.text().strip()
        pw = self._password()
        if not user:
            QMessageBox.warning(self, "WarmLink Cloud", "Benutzername fehlt.")
            return
        self._save_settings()
        cfg = self._cloud_settings()
        credentials_changed = bool(self.password_edit.text() and self.password_edit.text() != self._session_password)
        if credentials_changed:
            self.session = CloudSession(username=user, device_code=self._selected_device_code() or "",
                devices=list(self.devices), devices_cached=bool(self.devices))
        self._session_password = self.password_edit.text() or self._session_password
        self._remember_credentials()
        initial_token = None if credentials_changed else self._initial_token_for_user(user)
        initial_login_at = self._cloud_token_login_at if initial_token else 0.0
        if self.session.username != user or self.session.device_code != self._selected_device_code():
            self.session = CloudSession(username=user, device_code=self._selected_device_code() or "",
                devices=list(self.devices) if self._devices_username == user else [],
                devices_cached=bool(self.devices and self._devices_username == user))
            self.data_rows = []
            self._pending_overlay.clear()
            self._pending_data_rows.clear()
            self._data_render_timer.stop()
            self._compare_dirty = self._finder_dirty = True
            self.refresh_data()
            if hasattr(self.main_window, "clear_cloud_device_values"):
                self.main_window.clear_cloud_device_values()
            elif hasattr(self.main_window, "clear_cloud_overlay"):
                self.main_window.clear_cloud_overlay()
        self._stopping = False
        self._on_progress("CONNECTING", 0, 0)
        self._on_connection_state("CONNECTING")
        preferred_login_method = str(cfg.get("login_method") or "md5").strip() or "md5"
        login_fallbacks = bool(cfg.get("login_fallbacks", False))
        self.status_label.setText("starte ...")
        self.main_window._log("WarmLink Cloud: Login gestartet")
        self.test_btn.setEnabled(False)
        self.poll_once_btn.setEnabled(False)
        self.start_poll_btn.setEnabled(False)
        self.stop_poll_btn.setEnabled(True)
        self.cloud_thread = QThread(self)
        self._update_device_controls()
        self.cloud_worker = WarmLinkCloudWorker(
            username=user,
            password=pw,
            codes=list(WARMLINK_644_DISCOVERY_CODES) if full_scan else self._codes(),
            interval_s=int(self.interval_spin.value()),
            device_code=self._selected_device_code(),
            poll_once=bool(poll_once or just_login),
            preferred_login_method=preferred_login_method,
            login_fallbacks=login_fallbacks,
            initial_token=initial_token,
            initial_login_at=initial_login_at,
            session=self.session, force_discovery=force_discovery, reload_static=reload_static,
            discovery_only=discovery_only, full_scan=full_scan,
            load_credentials=True, use_saved_token=bool(cfg.get("save_token", True)) and not credentials_changed,
        )
        self.cloud_worker.moveToThread(self.cloud_thread)
        self.cloud_thread.started.connect(self.cloud_worker.run)
        self.cloud_worker.log.connect(self._on_worker_log)
        self.cloud_worker.status.connect(self._on_worker_status)
        self.cloud_worker.devices.connect(self._on_devices)
        self.cloud_worker.data.connect(self._on_data)
        self.cloud_worker.error.connect(self._on_worker_error)
        self.cloud_worker.login_method.connect(self._on_login_method)
        self.cloud_worker.token_updated.connect(self._on_token_updated)
        self.cloud_worker.progress.connect(self._on_progress)
        self.cloud_worker.session_updated.connect(self._on_session_updated)
        self.cloud_worker.credentials_loaded.connect(self._on_credentials_loaded)
        self.cloud_worker.connection_state.connect(self._on_connection_state)
        self.cloud_worker.timing_updated.connect(self._on_timing_updated)
        self.cloud_worker.finished.connect(self.cloud_thread.quit)
        self.cloud_worker.finished.connect(self.cloud_worker.deleteLater)
        self.cloud_thread.finished.connect(self._worker_finished)
        self.cloud_thread.start()
        if not poll_once and not just_login:
            self.main_window._log("WarmLink Cloud: Polling gestartet")

    def stop_worker(self):
        if self.cloud_worker is not None:
            self._stopping = True
            self._update_device_controls()
            self.cloud_worker.stop()
            self.status_label.setText("Stop angefordert ...")
            self.main_window._log("WarmLink Cloud: Polling gestoppt")

    @Slot()
    def _worker_finished(self):
        if self.cloud_thread is not None:
            self.cloud_thread.deleteLater()
        self.cloud_thread = None
        self.cloud_worker = None
        self.test_btn.setEnabled(True)
        self.poll_once_btn.setEnabled(True)
        self.start_poll_btn.setEnabled(True)
        self.stop_poll_btn.setEnabled(False)
        was_stopping = self._stopping
        self._stopping = False
        self._update_device_controls()
        if getattr(self.main_window, "cloud_session_authenticated", False):
            self._on_connection_state("CONNECTED")
        elif self._cloud_token is None and getattr(self.main_window, "cloud_ui_state", "") != "ERROR":
            self._on_connection_state("DISCONNECTED")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        if was_stopping:
            self.status_label.setText("gestoppt")
            self.progress_bar.setFormat("Polling gestoppt")
        elif getattr(self.main_window, "cloud_ui_state", "") == "CONNECTED":
            self.progress_bar.setFormat("Cloud verbunden")

    @Slot(str)
    def _on_worker_log(self, text: str):
        self.main_window._log(str(text))

    @Slot(str)
    def _on_token_updated(self, token: str):
        token = str(token or "").strip()
        if not token:
            return
        user = self.username_edit.text().strip()
        if self._cloud_token_username == user and self._cloud_token == token:
            return
        self._cloud_token = token
        self._cloud_token_login_at = time.time()
        self._cloud_token_username = user
        self._remember_credentials()
        if self.save_token_cb.isChecked():
            self._keyring.submit(lambda: set_token(user, token))

    @Slot(str)
    def _on_login_method(self, method: str):
        method = str(method or "").strip()
        if not method:
            return
        cfg = self._cloud_settings()
        if cfg.get("login_method") != method:
            cfg["login_method"] = method
            self.main_window._save_settings(sync_main_fields=False)

    @Slot(str)
    def _on_worker_status(self, text: str):
        self.status_label.setText(str(text))

    @Slot(str)
    def _on_worker_error(self, text: str):
        text = translate_cloud_error_message(str(text))
        self.status_label.setText("Fehler: " + text)
        self.main_window._log("WarmLink Cloud Fehler: " + text)
        lower = text.lower()
        if "401" in lower or "-100" in lower or "please login again" in lower or "login" in lower:
            self.main_window.set_cloud_connection_state(False)
            self._on_connection_state("ERROR")
            user = self.username_edit.text().strip()
            self._cloud_token = None
            self._cloud_token_login_at = 0.0
            self._cloud_token_username = ""
            self._remember_credentials()
            if user:
                self._keyring.submit(lambda: delete_token(user))

    @Slot(list)
    def _on_devices(self, devices: list):
        self.devices = cached_device_metadata(devices)
        self._devices_username = self.username_edit.text().strip()
        cfg = self._cloud_settings()
        cfg["cached_devices_username"] = self._devices_username
        cfg["cached_devices"] = list(self.devices)
        self.session.devices = list(self.devices)
        self.session.devices_cached = bool(self.devices)
        self.refresh_devices()
        selected = self.device_combo.findData(self.session.device_code)
        if selected >= 0:
            blocked = self.device_combo.blockSignals(True)
            self.device_combo.setCurrentIndex(selected)
            self.device_combo.blockSignals(blocked)
            blocked = self.device_table.blockSignals(True)
            self.device_table.selectRow(selected)
            self.device_table.blockSignals(blocked)
        self._save_settings()
        if self.session.validated or getattr(self.main_window, "cloud_session_authenticated", False):
            self.main_window.set_cloud_connection_state(True, self._selected_device_code())

    @Slot(object)
    def _on_session_updated(self, session):
        device_changed = bool(self.session.device_code and (
            self.session.username != session.username or self.session.device_code != session.device_code))
        if device_changed or (self.session.scanned and not session.scanned and not session.validated):
            self.data_rows = []
            self._pending_overlay.clear()
            self._pending_data_rows.clear()
            self._data_render_timer.stop()
            self._compare_dirty = self._finder_dirty = True
            self.refresh_data()
            if hasattr(self.main_window, "clear_cloud_device_values"):
                self.main_window.clear_cloud_device_values()
            elif hasattr(self.main_window, "clear_cloud_overlay"):
                self.main_window.clear_cloud_overlay()
        # External single reads may have arrived while a live HTTP batch ran.
        for row in self.data_rows:
            code = str(row.get("code"))
            if str(row.get("lastFetch") or "") >= str(session.rows.get(code, {}).get("lastFetch") or ""):
                session.merge([row])
        self.session = session
        self._update_device_controls()

    @Slot(str)
    def _on_connection_state(self, state):
        if self._stopping and state == "POLLING":
            state = "CONNECTED"
        device = next((d for d in self.devices if d.get("deviceCode") == self._selected_device_code()), {})
        name = str(device.get("deviceNickName") or device.get("model") or "")
        setter = getattr(self.main_window, "set_cloud_ui_state", None)
        if setter:
            if state == "ERROR":
                self.main_window.set_cloud_connection_state(False)
            elif state in ("CONNECTED", "POLLING"):
                self.main_window.set_cloud_connection_state(True, self._selected_device_code())
            setter(state, device_name=name)

    @Slot(object)
    def _on_timing_updated(self, state):
        setter = getattr(self.main_window, "set_cloud_timing_state", None)
        if setter:
            setter(state)

    @Slot(str, int, int)
    def _on_progress(self, phase, done, total):
        labels = {"CONNECTING": "Cloud-Verbindung wird aufgebaut ...", "LOADING_TOKEN": "Token wird geladen ...",
                  "DISCOVERING": "Geräte werden gesucht ...", "READING_INITIAL": "Cloudwerte werden gelesen",
                  "READING_STATIC": "Konfigurationswerte werden gelesen", "READING_LIVE": "Livewerte werden gelesen",
                  "POLLING": "Polling aktiv", "CONNECTED": "Cloud verbunden", "ERROR": "Cloud-Verbindungsfehler"}
        self.progress_bar.setRange(0, total if total else (0 if phase in ("CONNECTING", "LOADING_TOKEN", "DISCOVERING") else 1))
        self.progress_bar.setValue(done if total else 1)
        count = f" · {len(self.session.supported_codes)} unterstützte Werte" if phase in ("CONNECTED", "POLLING") and self.session.scanned else ""
        self.progress_bar.setFormat(labels.get(phase, phase) + (f" {done}/{total}" if total else count))
        if not self._stopping:
            self.status_label.setText(labels.get(phase, phase))

    def reload_all_values(self):
        """Recheck all catalogue candidates through the existing polling worker."""
        if self._stopping:
            self.status_label.setText("Cloud-Worker wird beendet; bitte danach erneut lesen.")
            return
        if self.cloud_worker:
            self.cloud_worker.request_full_scan(WARMLINK_644_DISCOVERY_CODES)
        else:
            self._start_worker(True, full_scan=True)

    def reload_static_values(self):
        if self.cloud_worker:
            self.cloud_worker.request_static_reload()
        else:
            self._start_worker(True, reload_static=True)

    @Slot(list)
    def _on_data(self, rows: list):
        started = time.perf_counter()
        existing = {str(row.get("code")): row for row in self.data_rows}
        delta = []
        for row in rows:
            if isinstance(row, dict) and row.get("code"):
                code = str(row["code"])
                merged = {**existing.get(code, {}), **row}
                if existing.get(code) != merged:
                    delta.append(merged)
                existing[code] = merged
        self.data_rows = list(existing.values())
        self.session.merge(rows)
        self._compare_dirty = self._finder_dirty = True
        self._tab_changed(self.tabs.currentIndex())
        self._apply_overlay_to_main(delta)
        good = [r for r in rows if r.get("supported") and not r.get("stale")]
        if good:
            setter = getattr(self.main_window, "set_cloud_ui_state", None)
            if setter:
                setter(getattr(self.main_window, "cloud_ui_state", "CONNECTED"), last_success_at=time.time())
        self.main_window._log(f"WarmLink Cloud: GUI-Teilupdate {len(delta)} Werte in {(time.perf_counter()-started)*1000:.1f} ms")

    def _tab_changed(self, index):
        if not self.isVisible():
            return
        if index == 1:
            self.refresh_data()
        elif index == 2 and self._compare_dirty:
            self.refresh_compare()
        elif index == 3 and self._finder_dirty:
            self.refresh_finder_codes()

    def showEvent(self, event):
        super().showEvent(event)
        self._tab_changed(self.tabs.currentIndex())

    def _mask(self, value: Any) -> str:
        return mask_cloud_value(value, show_ids=False)

    def refresh_devices(self):
        current = str(self.device_combo.currentData() or "")
        self.devices = cached_device_metadata(self.devices)
        blocked = self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for dev in self.devices:
            label, code = device_combo_label(dev, show_ids=True)
            self.device_combo.addItem(label, code)
        idx = self.device_combo.findData(current)
        if idx < 0:
            idx = self.device_combo.findData(str(self._cloud_settings().get("selected_device_code", "")))
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(blocked)

        keys = set().union(*(device.keys() for device in self.devices))
        self.device_columns = list(self.DEVICE_COLUMNS) + sorted(keys.difference(self.DEVICE_COLUMNS))
        blocked = self.device_table.blockSignals(True)
        self.device_table.setColumnCount(len(self.device_columns))
        self.device_table.setHorizontalHeaderLabels(self.device_columns)
        self.device_table.setRowCount(len(self.devices))
        for row, dev in enumerate(self.devices):
            for col, key in enumerate(self.device_columns):
                value = dev.get(key)
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                text = "—" if value is None or value == "" else str(value)
                self.device_table.setItem(row, col, QTableWidgetItem(text))
        self.device_table.selectRow(self.device_combo.currentIndex())
        self.device_table.blockSignals(blocked)
        self.device_table.resizeColumnsToContents()
        if self.session.username == self.username_edit.text().strip():
            self.session.devices = list(self.devices)
        self._update_device_controls()

    def _device_table_selection_changed(self):
        row = self.device_table.currentRow()
        if self.cloud_thread is None and 0 <= row < len(self.devices):
            index = self.device_combo.findData(self.devices[row].get("deviceCode"))
            if index >= 0:
                self.device_combo.setCurrentIndex(index)

    def refresh_data(self):
        rows = filtered_cloud_rows(
            self.data_rows,
            self.filter_edit.text(),
            self.unsupported_only_cb.isChecked(),
        )
        if self.mapping_issues_only_cb.isChecked():
            rows = [row for row in rows if self._mapping_status(str(row.get("code", "")))["mapping_status"] != "OK"]
        codes = [str(row.get("code", "")) for row in rows]
        structural = codes != self._data_codes
        if structural:
            self.data_table.setRowCount(len(rows))
            self._rendered_data.clear()
            self._data_codes = codes
        self._pending_data_rows = [(r, row) for r, row in enumerate(rows)
                                   if self._rendered_data.get(codes[r]) != row]
        self._data_resize_pending = self._data_resize_pending or structural
        self._render_data_chunk()

    @Slot()
    def _render_data_chunk(self):
        batch, self._pending_data_rows = self._pending_data_rows[:40], self._pending_data_rows[40:]
        self.data_table.setUpdatesEnabled(False)
        try:
            for r, row in batch:
                code = str(row.get("code", ""))
                mapping = self._mapping_cache.get(code)
                if mapping is None:
                    mapping = self._mapping_cache[code] = self._mapping_status(code)["mapping_status"]
                vals, status = data_table_values(row, mapping_status=mapping)
                bounds = resolve_cloud_range(code, cloud_hint(code), row)
                for c, val in enumerate(vals):
                    item = self.data_table.item(r, c)
                    if item is None:
                        item = QTableWidgetItem()
                        self.data_table.setItem(r, c, item)
                    if item.text() != str(val):
                        item.setText(str(val))
                    tooltip = bounds.description if c in (4, 5) else (status if status != "OK" else "")
                    if item.toolTip() != tooltip:
                        item.setToolTip(tooltip)
                self._rendered_data[code] = dict(row)
        finally:
            self.data_table.setUpdatesEnabled(True)
        if self._pending_data_rows:
            self._data_render_timer.start(0)
        elif self._data_resize_pending:
            self._data_resize_pending = False
            self.data_table.resizeColumnsToContents()

    def refresh_compare(self):
        self._compare_dirty = False
        rows = compare_source_rows(self.data_rows)
        codes = [str(row[0].get("code")) for row in rows]
        structural = codes != getattr(self, "_compare_codes", [])
        self._compare_codes = codes
        if structural:
            self.compare_table.setRowCount(len(rows))
        for r, (row, reg_no) in enumerate(rows):
            vals, status = compare_table_values(
                row,
                reg_no,
                latest_regs=self.main_window.latest_regs,
                regmap=self.main_window.regmap,
                display_parts_for_register=self.main_window._display_parts_for_register,
                cloud_display_text=self.main_window._cloud_display_text,
            )
            for c, val in enumerate(vals):
                item = self.compare_table.item(r, c)
                if item is None:
                    item = QTableWidgetItem()
                    self.compare_table.setItem(r, c, item)
                if item.text() != str(val):
                    item.setText(str(val))
                item.setToolTip(status if status not in ("OK", "") else "")
        if structural:
            self.compare_table.resizeColumnsToContents()

    def refresh_finder_codes(self):
        self._finder_dirty = False
        current = str(self.finder_code_combo.currentData() or self.finder_code_combo.currentText() or "") if hasattr(self, "finder_code_combo") else ""
        self.finder_code_combo.blockSignals(True)
        self.finder_code_combo.clear()
        for row in sorted(self.data_rows, key=lambda r: str(r.get("code", ""))):
            code = str(row.get("code", ""))
            if not code:
                continue
            label_code = finder_code_label(row)
            if label_code is None:
                continue
            label, code = label_code
            self.finder_code_combo.addItem(label, code)
        idx = self.finder_code_combo.findData(current)
        if idx >= 0:
            self.finder_code_combo.setCurrentIndex(idx)
        self.finder_code_combo.blockSignals(False)

    def _finder_cloud_row(self, code: str) -> dict[str, Any] | None:
        return finder_cloud_row(self.data_rows, code)

    def run_value_finder(self):
        # V0.2.44 fix4: Button sofort deaktivieren und Suche per Timer starten,
        # damit Qt den Klick/Status rendern kann und nicht wie "keine Rueckmeldung" wirkt.
        if not self.finder_btn.isEnabled():
            return
        self.finder_btn.setEnabled(False)
        self.finder_btn.setText("suche ...")
        self.main_window.statusBar().showMessage("WarmLink Cloud Wertefinder: Suche läuft ...", 5000)
        QTimer.singleShot(0, self._run_value_finder_now)

    def _run_value_finder_now(self):
        try:
            code = str(self.finder_code_combo.currentData() or "")
            row = self._finder_cloud_row(code)
            if not code or row is None:
                QMessageBox.information(self, "Wertefinder", "Kein Cloud-Code ausgewählt oder noch keine Cloud-Daten vorhanden.")
                return
            cloud_raw = row.get("value", "")
            tolerance = float(self.finder_tolerance_spin.value())
            hide_zero = bool(self.finder_nonzero_cb.isChecked())
            regs_snapshot = list(sorted(self.main_window.latest_regs.items()))
            matches = value_finder_matches(
                code=code,
                cloud_raw=cloud_raw,
                latest_regs_items=regs_snapshot,
                regmap=self.main_window.regmap,
                display_parts_for_register=self.main_window._display_parts_for_register,
                tolerance=tolerance,
                hide_zero=hide_zero,
            )
            self.finder_table.setSortingEnabled(False)
            self.finder_table.setRowCount(len(matches))
            for r, vals in enumerate(matches):
                for c, val in enumerate(vals):
                    self.finder_table.setItem(r, c, QTableWidgetItem(str(val)))
            self.finder_table.setSortingEnabled(True)
            self.finder_table.resizeColumnsToContents()
            self.main_window._log(f"WarmLink Cloud Wertefinder: {len(matches)} Kandidat(en) für {code}={cloud_raw}")
            self.main_window.statusBar().showMessage(f"Wertefinder fertig: {len(matches)} Kandidat(en)", 5000)
        finally:
            self.finder_btn.setText("lokale Kandidaten suchen")
            self.finder_btn.setEnabled(True)

    def _overlay_toggled(self):
        self._save_settings()
        if self.overlay_cb.isChecked():
            self._apply_overlay_to_main()
        else:
            self._pending_overlay.clear()
            self.main_window.clear_cloud_overlay()

    def _apply_overlay_to_main(self, rows=None):
        if not self.overlay_cb.isChecked():
            self._pending_overlay.clear()
            self.main_window.clear_cloud_overlay()
            return
        for row in self.data_rows if rows is None else rows:
            self._pending_overlay[str(row.get("code"))] = row
        self._flush_overlay_chunk()

    @Slot()
    def _flush_overlay_chunk(self):
        if not self.overlay_cb.isChecked():
            self._pending_overlay.clear()
            return
        codes = list(self._pending_overlay)[:40]
        batch = [self._pending_overlay.pop(code) for code in codes]
        if batch:
            main = self.main_window
            old_suppress = getattr(main, "_suppress_name_resize", False)
            old_count = main.register_table.rowCount()
            main._suppress_name_resize = True
            try:
                main.apply_cloud_rows_to_main(batch, show_cloud_only=True)
            finally:
                main._suppress_name_resize = old_suppress
            self._overlay_structure_changed |= main.register_table.rowCount() != old_count
        if self._pending_overlay:
            self._overlay_timer.start(0)
        elif self._overlay_structure_changed:
            self._overlay_structure_changed = False
            self.main_window._resize_name_column()

    def _refresh_write_values(self):
        self.write_value_combo.clear()
        code = str(self.write_code_combo.currentData() or "")
        meta = WARMLINK_CLOUD_WRITE_TEST_CODES.get(code, {})
        vals = meta.get("values") or {}
        if isinstance(vals, dict):
            for val, label in vals.items():
                self.write_value_combo.addItem(f"{val} - {label}", str(val))
        self._update_write_controls()

    def _update_write_controls(self):
        enabled = bool(self.write_enable_cb.isChecked())
        self.write_send_cb.setEnabled(enabled)
        self.write_code_combo.setEnabled(enabled)
        self.write_value_combo.setEnabled(enabled)
        self.write_endpoint_edit.setEnabled(enabled)
        self.write_btn.setEnabled(enabled and self.command_thread is None)

    def run_write_test(self):
        if self.command_thread is not None:
            QMessageBox.information(self, "WarmLink Cloud", "Schreibtest läuft bereits.")
            return
        if not self.write_enable_cb.isChecked():
            return
        user = self.username_edit.text().strip()
        pw = self._password()
        dev = self._selected_device_code()
        code = str(self.write_code_combo.currentData() or "")
        value = str(self.write_value_combo.currentData() or "")
        endpoint = self.write_endpoint_edit.text().strip() or ENDPOINT_AUTO_WRITE
        dry_run = not self.write_send_cb.isChecked()
        if not user or not dev or not code:
            QMessageBox.warning(self, "WarmLink Cloud", "Benutzername/Passwort/Gerät/Code fehlt.")
            return
        if not dry_run:
            ret = QMessageBox.warning(
                self,
                "Cloud-Schreibtest wirklich senden?",
                f"Wirklich an die Cloud senden?\n\nDevice: {self._mask(dev)}\nEndpoint: {endpoint}\nCode: {code}\nWert: {value}\n\nDas ist ein Test und kann die Wärmepumpe umschalten.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
        self.write_btn.setEnabled(False)
        self.write_result.append(f"Starte {'Dry-Run' if dry_run else 'SENDEN'}: {code}={value} via {endpoint}")
        self.command_thread = QThread(self)
        self.command_worker = WarmLinkCloudCommandWorker(
            user, pw, dev, code, value, endpoint=endpoint, dry_run=dry_run, load_credentials=True,
            initial_token=self._initial_token_for_user(user),
            use_saved_token=bool(self._cloud_settings().get("save_token", True)),
        )
        self.command_worker.moveToThread(self.command_thread)
        self.command_thread.started.connect(self.command_worker.run)
        self.command_worker.log.connect(self._on_command_log)
        self.command_worker.result.connect(self._on_command_result)
        self.command_worker.error.connect(self._on_command_error)
        self.command_worker.finished.connect(self.command_thread.quit)
        self.command_worker.finished.connect(self.command_worker.deleteLater)
        self.command_thread.finished.connect(self._command_finished)
        self.command_thread.start()

    def _on_command_log(self, text: str):
        text = str(text)
        self.write_result.append(text)
        self.main_window._log(text)

    def _on_command_result(self, data: dict):
        text = json.dumps(data, ensure_ascii=False, indent=2)
        self.write_result.append(text)
        self.main_window._log("WarmLink Cloud Schreibtest Antwort: " + text[:500].replace("\n", " "))
        readback = data.get("readback")
        if isinstance(readback, dict) and readback.get("supported"):
            self._on_data([{**readback, "lastFetch": time.strftime("%Y-%m-%d %H:%M:%S"), "stale": False}])

    def _on_command_error(self, text: str):
        text = translate_cloud_error_message(str(text))
        self.write_result.append("FEHLER: " + text)
        self.main_window._log("WarmLink Cloud Schreibtest Fehler: " + text)

    def _command_finished(self):
        if self.command_thread is not None:
            self.command_thread.deleteLater()
        self.command_thread = None
        self.command_worker = None
        self._update_write_controls()

    def run_debug_request(self):
        if self.debug_thread is not None:
            QMessageBox.information(self, "WarmLink Cloud", "API-Anfrage läuft bereits.")
            return
        user = self.username_edit.text().strip()
        path = self.debug_path_edit.text().strip()
        token = self._initial_token_for_user(user)
        pw = self._password() if not token else (self.password_edit.text() or "")
        if not user:
            QMessageBox.warning(self, "WarmLink Cloud", "Benutzername sowie vorhandener Token oder Passwort fehlen.")
            return
        if not path:
            QMessageBox.warning(self, "Cloud API Debugger", "Relativer API-Pfad fehlt.")
            return
        body_text = self.debug_body_edit.toPlainText().strip()
        try:
            body = json.loads(body_text) if body_text else None
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "Cloud API Debugger", f"Ungültiger JSON-Body: {exc}")
            return

        method = self.debug_method_combo.currentText()
        cfg = self._cloud_settings()
        self.debug_result_edit.setPlainText(
            f"REQUEST\n{method} {path}\n\nJSON-BODY\n{json.dumps(body, ensure_ascii=False, indent=2) if body is not None else '(leer)'}\n\nSende ..."
        )
        self.debug_send_btn.setEnabled(False)
        self.debug_thread = QThread(self)
        self.debug_worker = WarmLinkCloudDebugWorker(
            user, pw or "", method, path, body=body, initial_token=token,
            preferred_login_method=str(cfg.get("login_method") or "md5"),
            login_fallbacks=bool(cfg.get("login_fallbacks", False)),
            relogin_on_401=self.debug_relogin_cb.isChecked(), load_credentials=True,
            use_saved_token=bool(cfg.get("save_token", True)),
        )
        self.debug_worker.moveToThread(self.debug_thread)
        self.debug_thread.started.connect(self.debug_worker.run)
        self.debug_worker.result.connect(self._on_debug_result)
        self.debug_worker.error.connect(self._on_debug_error)
        self.debug_worker.token_updated.connect(self._on_token_updated)
        self.debug_worker.finished.connect(self.debug_thread.quit)
        self.debug_worker.finished.connect(self.debug_worker.deleteLater)
        self.debug_thread.finished.connect(self._debug_finished)
        self.debug_thread.start()

    def _on_debug_result(self, response):
        body = str(response.body or "")
        try:
            body = json.dumps(json.loads(body), ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            pass
        headers = "\n".join(f"{key}: {value}" for key, value in sorted(response.headers.items())) or "(keine)"
        request_text = self.debug_result_edit.toPlainText().split("\n\nSende ...", 1)[0]
        self.debug_result_edit.setPlainText(
            f"{request_text}\n\nHTTP-STATUS\n{response.status}\n\nRESPONSE-HEADER\n{headers}\n\nRESPONSE-BODY\n{body}"
        )
        request_path = urllib.parse.urlsplit(str(response.url or "")).path
        method = self.debug_method_combo.currentText()
        self.main_window._log(f"Cloud API Debugger: {response.status} {method} {request_path}")

    def _insert_debug_device_code(self):
        device_code = self._selected_device_code()
        if not device_code:
            QMessageBox.information(self, "Cloud API Debugger", "Kein Gerät ausgewählt.")
            return
        self.debug_body_edit.setPlainText(json.dumps({"deviceCode": device_code}, ensure_ascii=False, indent=2))

    def _prepare_debug_get_data(self):
        device_code = self._selected_device_code()
        if not device_code:
            QMessageBox.information(self, "Cloud API Debugger", "Kein Gerät ausgewählt.")
            return
        self.debug_method_combo.setCurrentText("POST")
        self.debug_path_edit.setText("app/device/getDataByCode")
        self.debug_body_edit.setPlainText(json.dumps({
            "deviceCode": device_code,
            "protocalCodes": ["T01"],
        }, ensure_ascii=False, indent=2))

    def _on_debug_error(self, text: str):
        current = self.debug_result_edit.toPlainText().split("\n\nSende ...", 1)[0]
        self.debug_result_edit.setPlainText(f"{current}\n\nFEHLER\n{translate_cloud_error_message(str(text))}")
        self.main_window._log("Cloud API Debugger Fehler: " + str(text))

    def _debug_finished(self):
        if self.debug_thread is not None:
            self.debug_thread.deleteLater()
        self.debug_thread = None
        self.debug_worker = None
        self.debug_send_btn.setEnabled(True)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "WarmLink Cloud CSV exportieren", self.main_window.user_data_dir, "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(self.DATA_COLUMNS)
            for row in self.data_rows:
                code = str(row.get("code", ""))
                values, _status = data_table_values(row, mapping_status=self._mapping_status(code)["mapping_status"])
                w.writerow(values)
        self.main_window._log(f"WarmLink Cloud: CSV exportiert: {path}")


    MAPPING_CHECK_COLUMNS = [
        "cloud_code", "cloud_name", "cloud_value", "confidence", "modbus_register",
        "local_code_hint", "register_json_code", "mapping_status", "write_allowed", "note",
    ]

    def _mapping_status(self, code: str) -> dict[str, Any]:
        code = str(code or "").strip()
        hint = cloud_hint(code)
        confidence = str(hint.get("confidence") or code_confidence(code) or "")
        local_code_hint = str(hint.get("local_code") or "")
        write_allowed = bool(hint.get("write_allowed", False))
        reg_no, register_json_code, error = self.main_window._validated_cloud_modbus_register(code, hint)
        if reg_no is None:
            return {"mapping_status": "Cloud-only" if not hint else "Kein Register", "modbus_register": "", "local_code_hint": local_code_hint, "register_json_code": "", "confidence": confidence, "write_allowed": write_allowed}
        if confidence != "confirmed":
            status = "Nicht bestätigt"
        elif error:
            status = "Kein Register"
        else:
            # Explizite bestätigte Aliase wie Power, Mode, O15/O17 oder
            # code_version dürfen auf lokale Register ohne eigenes code-Feld
            # zeigen. Der zentrale Resolver hat diese Zuordnung bereits geprüft.
            status = "OK"
        return {
            "mapping_status": status,
            "modbus_register": str(reg_no),
            "local_code_hint": local_code_hint,
            "register_json_code": register_json_code,
            "confidence": confidence,
            "write_allowed": write_allowed,
        }

    def export_mapping_check_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "WarmLink Mapping-Prüfliste exportieren",
            self.main_window.user_data_dir,
            "CSV (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(self.MAPPING_CHECK_COLUMNS)
            for row in self.data_rows:
                code = str(row.get("code", ""))
                hint = cloud_hint(code)
                status = self._mapping_status(code)
                writer.writerow([
                    code,
                    code_display_name(code),
                    row.get("value", ""),
                    status["confidence"],
                    status["modbus_register"],
                    status["local_code_hint"],
                    status["register_json_code"],
                    status["mapping_status"],
                    "1" if status["write_allowed"] else "0",
                    hint.get("note", ""),
                ])
        self.main_window._log(f"WarmLink Cloud: Mapping-Prüfliste CSV exportiert: {path}")


    MAPPING_CANDIDATE_COLUMNS = [
        "cloud_code", "cloud_name", "cloud_value", "cloud_datatype", "cloud_unit",
        "range_start", "range_end", "supported", "stale", "last_fetch",
        "mapped_register", "local_code", "local_name", "local_raw", "local_signed",
        "local_display", "diff", "confidence", "note",
    ]

    def _mapping_candidate_cloud_values(self, row: dict[str, Any]) -> list[Any]:
        code = str(row.get("code", ""))
        hint = cloud_hint(code)
        bounds = resolve_cloud_range(code, hint, row)
        return [
            code,
            code_display_name(code),
            row.get("value", ""),
            row.get("dataType") or hint.get("dataType") or hint.get("cloud_dataType", ""),
            code_unit(code, row),
            bounds.minimum,
            bounds.maximum,
            "1" if row.get("supported") else "0",
            "1" if row.get("stale") else "0",
            row.get("lastFetch", ""),
        ]

    def _mapping_candidate_local_values(self, reg_no: int | None, cloud_value: Any) -> list[Any]:
        if reg_no is None:
            return ["", "", "", "", "", "", ""]
        info = self.main_window.regmap.get(int(reg_no))
        reg = self.main_window.latest_regs.get(int(reg_no))
        local_code = ""
        local_name = str(getattr(info, "name", "") or "")
        if info is not None:
            _block, local_code, _clean = self.main_window._display_parts_for_register(int(reg_no), local_name)
        raw = getattr(reg, "raw_value", "") if reg is not None else ""
        signed = getattr(reg, "signed_value", "") if reg is not None else ""
        display = str(getattr(reg, "display_value", "") or "") if reg is not None else ""
        diff = ""
        cloud_num = try_float(cloud_value)
        local_num = None
        if reg is not None:
            local_txt, local_num = local_display_value(self.main_window.latest_regs, int(reg_no))
            display = display or local_txt
        if cloud_num is not None and local_num is not None:
            diff = f"{cloud_num - local_num:+.3g}"
        return [str(reg_no), local_code, local_name, raw, signed, display, diff]

    def _unknown_mapping_candidates(self, row: dict[str, Any]) -> list[list[str]]:
        code = str(row.get("code", ""))
        if cloud_modbus_register(code) is not None or not row.get("supported"):
            return []
        return value_finder_matches(
            code=code,
            cloud_raw=row.get("value", ""),
            latest_regs_items=list(sorted(self.main_window.latest_regs.items())),
            regmap=self.main_window.regmap,
            display_parts_for_register=self.main_window._display_parts_for_register,
            tolerance=0.0,
            hide_zero=True,
        )[:20]

    def export_mapping_candidates_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "WarmLink Mapping-Kandidaten exportieren",
            self.main_window.user_data_dir,
            "CSV (*.csv)",
        )
        if not path:
            return
        exported_rows = 0
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(self.MAPPING_CANDIDATE_COLUMNS)
            for row in self.data_rows:
                code = str(row.get("code", ""))
                hint = cloud_hint(code)
                cloud_values = self._mapping_candidate_cloud_values(row)
                metadata_note = data_table_values(row)[0][-1]
                reg_no = cloud_modbus_register(code)
                if reg_no is not None:
                    writer.writerow(
                        cloud_values
                        + self._mapping_candidate_local_values(reg_no, row.get("value", ""))
                        + [code_confidence(code), metadata_note]
                    )
                    exported_rows += 1
                    continue
                matches = self._unknown_mapping_candidates(row)
                if matches:
                    for match in matches:
                        candidate_reg = int(match[2])
                        note = str(metadata_note or "")
                        reason = str(match[6] or "")
                        if reason:
                            note = (note + "; " if note else "") + f"Wertefinder: {reason}"
                        writer.writerow(
                            cloud_values
                            + self._mapping_candidate_local_values(candidate_reg, row.get("value", ""))
                            + ["candidate", note]
                        )
                        exported_rows += 1
                else:
                    writer.writerow(
                        cloud_values
                        + self._mapping_candidate_local_values(None, row.get("value", ""))
                        + [code_confidence(code) or str(hint.get("confidence") or "unknown"), metadata_note]
                    )
                    exported_rows += 1
        self.main_window._log(f"WarmLink Cloud: Mapping-Kandidaten CSV exportiert: {path} ({exported_rows} Zeilen)")

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "WarmLink Cloud JSON exportieren", self.main_window.user_data_dir, "JSON (*.json)")
        if not path:
            return
        data = {
            "exported_at": time.time(),
            "deviceCode": self._selected_device_code(),
            "rows": self.data_rows,
            "credit": WARMLINK_CLOUD_CREDIT,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.main_window._log(f"WarmLink Cloud: JSON exportiert: {path}")

    def closeEvent(self, event):
        self._save_settings()
        if self.cloud_worker is not None and not getattr(self, "_force_close", False):
            # Dialog nur ausblenden, Polling laeuft weiter im Hintergrund.
            # Zum Beenden den Stop-Button nutzen oder die Haupt-App schliessen.
            self.hide()
            event.ignore()
            self.main_window._log("WarmLink Cloud: Dialog ausgeblendet, Polling läuft im Hintergrund weiter.")
            return
        self.stop_worker()
        super().closeEvent(event)
