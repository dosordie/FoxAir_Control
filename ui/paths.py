# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys


def app_program_dir(anchor_file: str) -> str:
    """Return the installed program/script directory for portable resources."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(anchor_file))


def app_resource_dir(anchor_file: str) -> str:
    """Return the bundled resource directory, honoring PyInstaller _MEIPASS."""
    if hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(anchor_file))


def resource_path(relative_path: str, anchor_file: str) -> str:
    """Resolve a resource for normal execution and PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(anchor_file)))
    return os.path.join(base_path, relative_path)
