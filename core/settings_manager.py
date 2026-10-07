# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Any

from core.udp_diagnostics import udp_diagnostic_defaults
from cloud.known_devices import normalize_known_device_codes
from cloud.device_metadata import cached_device_metadata


def engineering_parameter_is_visible(data: dict[str, Any], settings: dict[str, Any]) -> bool:
    """Apply UI visibility only; this deliberately never changes write policy."""
    is_engineering = str(data.get("ui_visibility", "")).lower() == "engineering"
    return not is_engineering or bool(settings.get("show_engineering_parameters", False))


def ensure_warmlink_cloud_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    """Ensure WarmLink cloud settings exist with stable defaults."""
    cfg = settings.setdefault("warmlink_cloud", {})
    if not isinstance(cfg, dict):
        cfg = {}
        settings["warmlink_cloud"] = cfg
    # Compatibility key retained, but overlay now always includes projectable rows.
    cfg["show_cloud_only"] = True
    cfg.setdefault("login_method", "md5")
    cfg.setdefault("login_fallbacks", False)
    cfg.setdefault("save_token", True)
    cfg.setdefault("overlay_enabled", True)
    if "known_device_codes" in cfg:  # Legacy data remains loadable, but is not a GUI device source.
        cfg["known_device_codes"] = normalize_known_device_codes(cfg["known_device_codes"])
    cfg.setdefault("cached_devices_username", "")
    cfg["cached_devices"] = cached_device_metadata(cfg.get("cached_devices", []))
    try:
        cfg["poll_interval_s"] = min(3600, max(10, int(cfg.get("poll_interval_s", 30) or 30)))
    except Exception:
        cfg["poll_interval_s"] = 30
    return cfg


def ensure_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    """Ensure persisted settings have the same defaults the UI expects."""
    if not isinstance(settings, dict):
        settings = {}
    settings.setdefault("backend_settings", {})
    settings.setdefault("device_model", "foxair_green_gl9_1")
    settings.setdefault("show_public_warning", True)
    settings.setdefault("show_engineering_parameters", False)
    settings.setdefault("theme", "system")
    settings.setdefault("update_asset_mode", "auto")
    settings.setdefault("auto_read_init_on_startup", False)
    settings.setdefault("auto_poll_live_values", False)
    settings.setdefault("live_poll_interval_s", 30)
    settings.setdefault("tab_auto_poll", False)
    settings.setdefault("tab_poll_interval_s", 30)
    settings.setdefault("display_write_mode", "fc16")
    capture = settings.setdefault("warmlink_raw_capture", {})
    if not isinstance(capture, dict):
        capture = {}
        settings["warmlink_raw_capture"] = capture
    capture.setdefault("mode", "normal")
    capture.setdefault("prevent_standby", True)
    csv_logger = settings.setdefault("csv_logger", {})
    if not isinstance(csv_logger, dict):
        csv_logger = settings["csv_logger"] = {}
    try:
        csv_logger["interval_s"] = min(3600, max(5, int(csv_logger.get("interval_s", 30))))
    except (TypeError, ValueError):
        csv_logger["interval_s"] = 30
    csv_logger.setdefault("last_directory", "")
    settings.setdefault("manual_register_dialog", {})
    settings.setdefault("show_dual_logger_button_display", False)
    settings.setdefault("log_level", 2)
    settings["udp_diagnostic"] = udp_diagnostic_defaults(settings.get("udp_diagnostic", {}))
    main_window = settings.setdefault("main_window", {})
    if not isinstance(main_window, dict):
        main_window = {}
        settings["main_window"] = main_window
    try:
        main_window["width"] = max(900, int(main_window.get("width", 1400) or 1400))
    except Exception:
        main_window["width"] = 1400
    try:
        main_window["height"] = max(600, int(main_window.get("height", 900) or 900))
    except Exception:
        main_window["height"] = 900
    main_window["maximized"] = bool(main_window.get("maximized", False))
    if not isinstance(settings.get("main_table_column_widths"), dict):
        settings["main_table_column_widths"] = {}
    ensure_warmlink_cloud_defaults(settings)
    return settings


def load_settings(path: str) -> dict[str, Any]:
    """Load a settings JSON file; return an empty dict on failure."""
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_settings(path: str, settings: dict[str, Any]) -> dict[str, Any]:
    """Atomically save settings JSON without UI/keyring dependencies."""
    data = ensure_defaults(dict(settings or {}))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
    return data
