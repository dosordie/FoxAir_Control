# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Any


def ensure_warmlink_cloud_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    """Ensure WarmLink cloud settings exist with stable defaults."""
    cfg = settings.setdefault("warmlink_cloud", {})
    if not isinstance(cfg, dict):
        cfg = {}
        settings["warmlink_cloud"] = cfg
    cfg.setdefault("show_cloud_only", True)
    cfg.setdefault("login_method", "md5")
    cfg.setdefault("login_fallbacks", False)
    cfg.setdefault("save_token", True)
    cfg.setdefault("overlay_enabled", True)
    try:
        cfg["poll_interval_s"] = max(60, int(cfg.get("poll_interval_s", 60) or 60))
    except Exception:
        cfg["poll_interval_s"] = 60
    return cfg


def ensure_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    """Ensure persisted settings have the same defaults the UI expects."""
    if not isinstance(settings, dict):
        settings = {}
    settings.setdefault("backend_settings", {})
    settings.setdefault("device_model", "foxair_green_gl9_1")
    settings.setdefault("cache_load_on_start", False)
    settings.setdefault("cache_save_on_exit", True)
    settings.setdefault("cache_save_cyclic", False)
    settings.setdefault("cache_interval_s", 60)
    settings.setdefault("show_public_warning", True)
    settings.setdefault("theme", "system")
    settings.setdefault("update_asset_mode", "auto")
    settings.setdefault("auto_read_init_on_startup", False)
    settings.setdefault("auto_poll_live_values", False)
    settings.setdefault("live_poll_interval_s", 30)
    settings.setdefault("tab_auto_poll", False)
    settings.setdefault("tab_poll_interval_s", 30)
    settings.setdefault("display_write_mode", "fc16")
    settings.setdefault("show_dual_logger_button_display", False)
    settings.setdefault("log_level", 2)
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
