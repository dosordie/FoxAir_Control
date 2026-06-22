# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import time
from typing import Any, Optional

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from cloud.warmlink_api import (
    ENDPOINT_AUTO_WRITE, ENDPOINT_WRITE_MODEL_VALUE, translate_cloud_error_message,
)
from cloud.token_store import (
    KEYRING_SERVICE, delete_password, delete_token, get_password, get_token,
    set_password, set_token,
)
from cloud.warmlink_codes import (
    DEFAULT_WARMLINK_CLOUD_CODES, WARMLINK_CLOUD_WRITE_TEST_CODES, cloud_hint,
    cloud_modbus_register, WARMLINK_CLOUD_CREDIT, code_confidence,
    code_display_name, code_unit,
)
from dialogs.cloud_table_helpers import (
    compare_source_rows, compare_table_values, data_table_values, device_combo_label,
    device_table_value, filtered_cloud_rows, finder_cloud_row, finder_code_label,
    local_display_value, mask_cloud_value, try_float, value_finder_matches,
)
from workers.warmlink_cloud_worker import WarmLinkCloudWorker, WarmLinkCloudCommandWorker
from core.settings_manager import ensure_warmlink_cloud_defaults

class WarmLinkCloudDialog(QDialog):
    """Optionale WarmLink/Linked-Go Cloud-Anbindung mit Overlay/Compare.

    Standard bleibt lesend. Der Schreibtest ist getrennt, deaktiviert und nur
    fuer wenige erlaubte Codes vorgesehen.
    """

    DEVICE_COLUMNS = [
        "deviceNickName", "model", "custModel", "deviceStatus", "isFault", "is_fault",
        "dtuSoftwareCode", "dtuSoftwareVer", "dtuSignalIntensity", "productId",
        "productionCode", "deviceId", "deviceCode", "sn", "dtuIccid",
        "wifiSoftwareCode", "wifiSoftwareVer",
    ]
    SENSITIVE_DEVICE_FIELDS = {"deviceCode", "dtuIccid", "sn", "deviceId"}
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
        self.devices: list[dict[str, Any]] = []
        self.data_rows: list[dict[str, Any]] = []
        self._cloud_token: str | None = None
        self._cloud_token_login_at: float = 0.0
        self._cloud_token_username: str = ""
        self._loading_settings = False
        self._build_ui()
        self._load_settings()

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
        self.interval_spin.setRange(60, 86400)
        self.interval_spin.setValue(60)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setToolTip("Default 60s. Kürzere Intervalle sind bewusst gesperrt, um API-Limits zu schonen.")
        self.ids_cb = QCheckBox("IDs anzeigen")
        self.ids_cb.setToolTip("Sensible Felder wie deviceCode, deviceId, SN und ICCID im UI anzeigen.")
        self.overlay_cb = QCheckBox("Cloud im Hauptfenster anzeigen")
        self.overlay_cb.setToolTip("Gemappte Cloud-Werte als Zusatzspalten/Cloud-only-Zeilen in der Haupttabelle anzeigen.")
        self.auto_start_cb = QCheckBox("Cloud-Polling beim App-Start")
        self.auto_start_cb.setToolTip("Startet Cloud-Polling im Hintergrund nach Programmstart, wenn Zugangsdaten gespeichert sind.")
        self.cloud_only_cb = QCheckBox("Cloud-only-Zeilen")
        self.cloud_only_cb.setToolTip("Gemappte Cloud-Werte auch dann als Zeile zeigen, wenn lokal noch kein Registerwert gelesen wurde.")
        self.login_fallbacks_cb = QCheckBox("Login-Fallbacks erlauben")
        self.login_fallbacks_cb.setToolTip("Wenn MD5 bzw. die gespeicherte Methode fehlschlägt, weitere Hash-/App-Login-Varianten testen.")
        self.save_token_cb = QCheckBox("Cloud-Token verwenden/speichern")
        self.save_token_cb.setToolTip("Verwendet gespeicherte Cloud-Token beim Start und speichert neue Token sicher im OS-Keyring, nicht in settings.json. Standard: aktiv.")
        self.test_btn = QPushButton("Login testen")
        self.save_btn = QPushButton("Zugang speichern")
        self.delete_btn = QPushButton("Zugang löschen")
        self.poll_once_btn = QPushButton("Jetzt abrufen")
        self.start_poll_btn = QPushButton("Polling starten")
        self.stop_poll_btn = QPushButton("Polling stoppen")
        self.stop_poll_btn.setEnabled(False)
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(360)

        login.addWidget(QLabel("Benutzername:"), 0, 0)
        login.addWidget(self.username_edit, 0, 1, 1, 3)
        login.addWidget(QLabel("Passwort:"), 1, 0)
        login.addWidget(self.password_edit, 1, 1, 1, 3)
        login.addWidget(QLabel("Polling-Intervall:"), 2, 0)
        login.addWidget(self.interval_spin, 2, 1)
        login.addWidget(QLabel("Gerät:"), 2, 2)
        login.addWidget(self.device_combo, 2, 3)
        login.addWidget(QLabel("Status:"), 3, 0)
        login.addWidget(self.status_label, 3, 1, 1, 3)
        btn_row = QHBoxLayout()
        for b in (self.test_btn, self.save_btn, self.delete_btn, self.poll_once_btn, self.start_poll_btn, self.stop_poll_btn, self.ids_cb, self.overlay_cb, self.auto_start_cb, self.cloud_only_cb, self.login_fallbacks_cb, self.save_token_cb):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        login.addLayout(btn_row, 4, 0, 1, 4)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        dev_tab = QWidget()
        dev_layout = QVBoxLayout(dev_tab)
        self.device_table = QTableWidget(0, len(self.DEVICE_COLUMNS))
        self.device_table.setHorizontalHeaderLabels(self.DEVICE_COLUMNS)
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.device_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        dev_layout.addWidget(self.device_table)
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
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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
        self.export_mapping_candidates_btn = QPushButton("Mapping-Kandidaten exportieren")
        self.export_mapping_candidates_btn.setToolTip("Exportiert alle aktuellen Cloud-Daten mit bekannten lokalen Mappings und optionalen Wertefinder-Kandidaten als CSV.")
        compare_btn_row.addStretch(1)
        compare_btn_row.addWidget(self.export_mapping_candidates_btn)
        compare_layout.addLayout(compare_btn_row)
        self.compare_table = QTableWidget(0, len(self.COMPARE_COLUMNS))
        self.compare_table.setHorizontalHeaderLabels(self.COMPARE_COLUMNS)
        self.compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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
        self.codes_edit.setPlainText("\n".join(DEFAULT_WARMLINK_CLOUD_CODES))
        self.codes_edit.setToolTip("Ein Code pro Zeile oder kommasepariert. Initial werden alle bekannten dump_all-Codes abgefragt.")
        codes_layout.addWidget(QLabel("Code-Liste für getDataByCode:"))
        codes_layout.addWidget(self.codes_edit, 1)
        self.tabs.addTab(codes_tab, "Codes / Mapping")

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
        self.save_btn.clicked.connect(self.save_credentials)
        self.delete_btn.clicked.connect(self.delete_credentials)
        self.ids_cb.toggled.connect(lambda _=None: self.refresh_devices())
        self.auto_start_cb.toggled.connect(lambda _=None: self._save_settings())
        self.overlay_cb.toggled.connect(self._overlay_toggled)
        self.cloud_only_cb.toggled.connect(lambda _=None: self._apply_overlay_to_main())
        self.login_fallbacks_cb.toggled.connect(lambda _=None: self._save_settings())
        self.save_token_cb.toggled.connect(self._save_token_toggled)
        self.device_combo.currentIndexChanged.connect(lambda _=None: self._save_settings())
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
        self.close_btn.clicked.connect(self.close)
        self._refresh_write_values()

    def _load_settings(self):
        cfg = self._cloud_settings()
        signal_widgets = (
            self.ids_cb,
            self.overlay_cb,
            self.auto_start_cb,
            self.cloud_only_cb,
            self.login_fallbacks_cb,
            self.save_token_cb,
            self.interval_spin,
            self.device_combo,
        )
        previous_signal_states = [widget.blockSignals(True) for widget in signal_widgets]
        self._loading_settings = True
        try:
            self.username_edit.setText(str(cfg.get("username", "")))
            self.interval_spin.setValue(max(60, int(cfg.get("poll_interval_s", 60) or 60)))
            self.ids_cb.setChecked(bool(cfg.get("show_ids", False)))
            self.overlay_cb.setChecked(bool(cfg.get("overlay_enabled", True)))
            self.auto_start_cb.setChecked(bool(cfg.get("auto_start_polling", False)))
            self.cloud_only_cb.setChecked(bool(cfg.get("show_cloud_only", True)))
            self.login_fallbacks_cb.setChecked(bool(cfg.get("login_fallbacks", False)))
            self.save_token_cb.setChecked(bool(cfg.get("save_token", True)))
            selected = str(cfg.get("selected_device_code", ""))
            if selected:
                self.device_combo.addItem(f"gespeichert: {self._mask(selected)}", selected)
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
        cfg["username"] = self.username_edit.text().strip()
        cfg["poll_interval_s"] = int(self.interval_spin.value())
        cfg["show_ids"] = bool(self.ids_cb.isChecked())
        cfg["overlay_enabled"] = bool(self.overlay_cb.isChecked())
        cfg["auto_start_polling"] = bool(self.auto_start_cb.isChecked())
        cfg["show_cloud_only"] = bool(self.cloud_only_cb.isChecked())
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
            try:
                delete_token(user)
            except Exception as exc:
                self.main_window._log("WarmLink Cloud: Token konnte nicht gelöscht werden: " + str(exc))
        self._cloud_token = None
        self._cloud_token_login_at = 0.0
        self._cloud_token_username = ""

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
        return out or list(DEFAULT_WARMLINK_CLOUD_CODES)

    def _password(self) -> str | None:
        user = self.username_edit.text().strip()
        pw = self.password_edit.text()
        if pw:
            return pw
        if not user:
            return None
        try:
            return get_password(user)
        except Exception as exc:
            QMessageBox.warning(self, "Keyring fehlt", str(exc))
            return None

    def save_credentials(self):
        user = self.username_edit.text().strip()
        pw = self.password_edit.text()
        if not user:
            QMessageBox.warning(self, "WarmLink Cloud", "Benutzername fehlt.")
            return
        if pw:
            try:
                set_password(user, pw)
            except Exception as exc:
                QMessageBox.warning(self, "Keyring fehlt", str(exc))
                return
            self.password_edit.clear()
            self.password_edit.setPlaceholderText("Passwort im OS-Keyring gespeichert")
        self._save_settings()
        self.status_label.setText(f"Zugang gespeichert. Passwort liegt im OS-Keyring-Service {KEYRING_SERVICE}.")
        self.main_window._log("WarmLink Cloud: Zugang gespeichert (E-Mail in Settings, Passwort im OS-Keyring).")

    def delete_credentials(self):
        user = self.username_edit.text().strip()
        if user:
            try:
                delete_password(user)
                delete_token(user)
            except Exception as exc:
                QMessageBox.warning(self, "Keyring", str(exc))
                return
        cfg = self._cloud_settings()
        for key in ("username", "selected_device_code"):
            cfg.pop(key, None)
        self.main_window._save_settings(sync_main_fields=False)
        self.password_edit.clear()
        self._cloud_token = None
        self._cloud_token_login_at = 0.0
        self._cloud_token_username = ""
        self.status_label.setText("Zugang gelöscht.")
        self.main_window._log("WarmLink Cloud: Zugang gelöscht.")

    def _selected_device_code(self) -> str | None:
        data = self.device_combo.currentData()
        return str(data).strip() if data else None

    def _start_worker(self, poll_once: bool, just_login: bool = False):
        if self.cloud_thread is not None:
            QMessageBox.information(self, "WarmLink Cloud", "Cloud-Worker läuft bereits.")
            return
        user = self.username_edit.text().strip()
        pw = self._password()
        if not user or not pw:
            QMessageBox.warning(self, "WarmLink Cloud", "Benutzername/Passwort fehlt. Passwort ggf. zuerst speichern oder eingeben.")
            return
        self._save_settings()
        cfg = self._cloud_settings()
        initial_token = None
        initial_login_at = 0.0
        if bool(cfg.get("save_token", True)):
            if self._cloud_token_username == user and self._cloud_token:
                initial_token = self._cloud_token
                initial_login_at = self._cloud_token_login_at
            else:
                try:
                    initial_token = get_token(user)
                    initial_login_at = time.time() if initial_token else 0.0
                except Exception as exc:
                    self.main_window._log("WarmLink Cloud: Token-Keyring nicht verfügbar: " + str(exc))
        preferred_login_method = str(cfg.get("login_method") or "md5").strip() or "md5"
        login_fallbacks = bool(cfg.get("login_fallbacks", False))
        self.status_label.setText("starte ...")
        self.test_btn.setEnabled(False)
        self.poll_once_btn.setEnabled(False)
        self.start_poll_btn.setEnabled(False)
        self.stop_poll_btn.setEnabled(True)
        self.cloud_thread = QThread(self)
        self.cloud_worker = WarmLinkCloudWorker(
            username=user,
            password=pw,
            codes=self._codes(),
            interval_s=int(self.interval_spin.value()),
            device_code=self._selected_device_code(),
            poll_once=bool(poll_once or just_login),
            preferred_login_method=preferred_login_method,
            login_fallbacks=login_fallbacks,
            initial_token=initial_token,
            initial_login_at=initial_login_at,
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
        self.cloud_worker.finished.connect(self.cloud_thread.quit)
        self.cloud_worker.finished.connect(self.cloud_worker.deleteLater)
        self.cloud_thread.finished.connect(self._worker_finished)
        self.cloud_thread.start()

    def stop_worker(self):
        if self.cloud_worker is not None:
            self.cloud_worker.stop()
            self.status_label.setText("Stop angefordert ...")

    def _worker_finished(self):
        if self.cloud_thread is not None:
            self.cloud_thread.deleteLater()
        self.cloud_thread = None
        self.cloud_worker = None
        self.test_btn.setEnabled(True)
        self.poll_once_btn.setEnabled(True)
        self.start_poll_btn.setEnabled(True)
        self.stop_poll_btn.setEnabled(False)
        if "Stop" in self.status_label.text():
            self.status_label.setText("gestoppt")

    def _on_worker_log(self, text: str):
        self.main_window._log(str(text))

    def _on_token_updated(self, token: str):
        token = str(token or "").strip()
        if not token:
            return
        user = self.username_edit.text().strip()
        self._cloud_token = token
        self._cloud_token_login_at = time.time()
        self._cloud_token_username = user
        if self.save_token_cb.isChecked():
            try:
                set_token(user, token)
            except Exception as exc:
                self.main_window._log("WarmLink Cloud: Token konnte nicht gespeichert werden: " + str(exc))

    def _on_login_method(self, method: str):
        method = str(method or "").strip()
        if not method:
            return
        cfg = self._cloud_settings()
        if cfg.get("login_method") != method:
            cfg["login_method"] = method
            self.main_window._save_settings(sync_main_fields=False)

    def _on_worker_status(self, text: str):
        self.status_label.setText(str(text))

    def _on_worker_error(self, text: str):
        text = translate_cloud_error_message(str(text))
        self.status_label.setText("Fehler: " + text)
        self.main_window._log("WarmLink Cloud Fehler: " + text)
        lower = text.lower()
        if "401" in lower or "-100" in lower or "please login again" in lower or "login" in lower:
            user = self.username_edit.text().strip()
            self._cloud_token = None
            self._cloud_token_login_at = 0.0
            self._cloud_token_username = ""
            if user:
                try:
                    delete_token(user)
                except Exception as exc:
                    self.main_window._log("WarmLink Cloud: Token konnte nicht gelöscht werden: " + str(exc))

    def _on_devices(self, devices: list):
        self.devices = [d for d in devices if isinstance(d, dict)]
        self.refresh_devices()
        self._save_settings()

    def _on_data(self, rows: list):
        self.data_rows = [r for r in rows if isinstance(r, dict)]
        self.refresh_data()
        self.refresh_compare()
        self.refresh_finder_codes()
        self._apply_overlay_to_main()

    def _mask(self, value: Any) -> str:
        return mask_cloud_value(value, show_ids=self.ids_cb.isChecked())

    def refresh_devices(self):
        current = str(self.device_combo.currentData() or "")
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for dev in self.devices:
            label, code = device_combo_label(dev, show_ids=self.ids_cb.isChecked())
            self.device_combo.addItem(label, code)
        idx = self.device_combo.findData(current)
        if idx < 0:
            saved = str(self._cloud_settings().get("selected_device_code", ""))
            idx = self.device_combo.findData(saved)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(False)

        self.device_table.setRowCount(len(self.devices))
        for row, dev in enumerate(self.devices):
            for col, key in enumerate(self.DEVICE_COLUMNS):
                val = device_table_value(dev, key, self.SENSITIVE_DEVICE_FIELDS, show_ids=self.ids_cb.isChecked())
                self.device_table.setItem(row, col, QTableWidgetItem(val))
        self.device_table.resizeColumnsToContents()

    def refresh_data(self):
        rows = filtered_cloud_rows(
            self.data_rows,
            self.filter_edit.text(),
            self.unsupported_only_cb.isChecked(),
        )
        if self.mapping_issues_only_cb.isChecked():
            rows = [row for row in rows if self._mapping_status(str(row.get("code", "")))["mapping_status"] != "OK"]
        self.data_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals, status = data_table_values(row, mapping_status=self._mapping_status(str(row.get("code", "")))["mapping_status"])
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if status != "OK":
                    item.setToolTip(status)
                self.data_table.setItem(r, c, item)
        self.data_table.resizeColumnsToContents()

    def refresh_compare(self):
        rows = compare_source_rows(self.data_rows)
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
                item = QTableWidgetItem(str(val))
                if status not in ("OK", ""):
                    item.setToolTip(status)
                self.compare_table.setItem(r, c, item)
        self.compare_table.resizeColumnsToContents()

    def refresh_finder_codes(self):
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
        QApplication.processEvents()
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
            self.main_window.clear_cloud_overlay()

    def _apply_overlay_to_main(self):
        self._save_settings()
        if self.overlay_cb.isChecked():
            self.main_window.apply_cloud_rows_to_main(self.data_rows, show_cloud_only=bool(self.cloud_only_cb.isChecked()))
        else:
            self.main_window.clear_cloud_overlay()

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
        if not user or not pw or not dev or not code:
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
        self.command_worker = WarmLinkCloudCommandWorker(user, pw, dev, code, value, endpoint=endpoint, dry_run=dry_run)
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

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "WarmLink Cloud CSV exportieren", self.main_window.user_data_dir, "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(self.DATA_COLUMNS)
            for row in self.data_rows:
                code = str(row.get("code", ""))
                hint = cloud_hint(code)
                reg = cloud_modbus_register(code)
                w.writerow([
                    code, code_display_name(code), row.get("value", ""), row.get("dataType") or hint.get("dataType", ""),
                    row.get("rangeStart", ""), row.get("rangeEnd", ""), row.get("lastFetch", ""),
                    "OK" if row.get("supported") else "leer/unsupported", str(reg) if reg is not None else hint.get("confidence", ""),
                    self._mapping_status(code)["mapping_status"], hint.get("note", ""),
                ])
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
        reg = hint.get("modbus_register")
        if reg in (None, ""):
            return {"mapping_status": "Cloud-only" if not hint else "Kein Register", "modbus_register": "", "local_code_hint": local_code_hint, "register_json_code": "", "confidence": confidence, "write_allowed": write_allowed}
        try:
            reg_no = int(reg)
        except Exception:
            return {"mapping_status": "Kein Register", "modbus_register": str(reg), "local_code_hint": local_code_hint, "register_json_code": "", "confidence": confidence, "write_allowed": write_allowed}
        register_json_code = ""
        if reg_no in getattr(self.main_window.regmap, "items", {}):
            register_json_code = self.main_window._code_for_register(reg_no)
        if confidence != "confirmed":
            status = "Nicht bestätigt"
        elif not register_json_code:
            status = "Kein Register"
        elif not self.main_window._is_safe_cloud_local_mapping(code, register_json_code, hint):
            status = "Code-Mismatch"
        else:
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
        return [
            code,
            code_display_name(code),
            row.get("value", ""),
            row.get("dataType") or hint.get("dataType") or hint.get("cloud_dataType", ""),
            code_unit(code) or hint.get("unit", ""),
            row.get("rangeStart", hint.get("rangeStart", "")),
            row.get("rangeEnd", hint.get("rangeEnd", "")),
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
                reg_no = cloud_modbus_register(code)
                if reg_no is not None:
                    writer.writerow(
                        cloud_values
                        + self._mapping_candidate_local_values(reg_no, row.get("value", ""))
                        + [code_confidence(code), hint.get("note", "")]
                    )
                    exported_rows += 1
                    continue
                matches = self._unknown_mapping_candidates(row)
                if matches:
                    for match in matches:
                        candidate_reg = int(match[2])
                        note = str(hint.get("note", "") or "")
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
                        + [code_confidence(code) or str(hint.get("confidence") or "unknown"), hint.get("note", "")]
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

