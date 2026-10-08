#!/usr/bin/env python3
"""Compare cyclic cloud-table work against a chosen Git revision, without network I/O.

Run from the repository root with QT_QPA_PLATFORM=offscreen if no display exists.
Reported times are local measurements, not portable performance assertions.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import textwrap
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
import foxair_phnix_control as gui
import dialogs.cloud_dialog as cloud_dialog
from cloud.polling import classify_cloud_codes
from cloud.warmlink_codes import WARMLINK_644_DISCOVERY_CODES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="Git revision containing the full-refresh implementation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = subprocess.check_output(["git", "show", f"{args.baseline}:dialogs/cloud_dialog.py"], cwd=root, text=True)
    cls = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == "WarmLinkCloudDialog")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "refresh_data")
    namespace = dict(vars(cloud_dialog))
    exec(compile(textwrap.dedent(ast.get_source_segment(source, method)), "baseline-refresh", "exec"), namespace)
    old_refresh = namespace["refresh_data"]
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="warmlink-benchmark-") as directory:
        gui.app_user_data_dir = lambda: directory
        gui.MainWindow._autoconnect_if_enabled = lambda self: None
        gui.MainWindow._autostart_warmlink_cloud_if_enabled = lambda self: None
        gui.MainWindow.check_for_updates_on_startup = lambda self: None
        window = gui.MainWindow()
        dialog = cloud_dialog.WarmLinkCloudDialog(window)
        codes = list(WARMLINK_644_DISCOVERY_CODES)
        live = set(classify_cloud_codes(codes)["live"])
        dialog.data_rows = [{"code": code, "value": "0", "supported": True, "lastFetch": "initial"} for code in codes]
        old_refresh(dialog)  # Warm register/metadata caches equally.
        old_times, new_times, max_chunks = [], [], []
        for _ in range(5):
            started = time.perf_counter()
            old_refresh(dialog)
            old_times.append((time.perf_counter() - started) * 1000)
        dialog.refresh_data()
        while dialog._pending_data_rows:
            application.processEvents()
        for trial in range(5):
            dialog.data_rows = [{**row, "value": str(trial + 1), "lastFetch": str(trial)} if row["code"] in live else row for row in dialog.data_rows]
            started = time.perf_counter()
            dialog.refresh_data()
            chunks = [(time.perf_counter() - started) * 1000]
            while dialog._pending_data_rows:
                step = time.perf_counter()
                application.processEvents()
                chunks.append((time.perf_counter() - step) * 1000)
            new_times.append((time.perf_counter() - started) * 1000)
            max_chunks.append(max(chunks))
        print(json.dumps({"catalog": len(codes), "live": len(live),
            "old_full_refresh_median_ms": round(statistics.median(old_times), 1),
            "new_live_refresh_median_ms": round(statistics.median(new_times), 1),
            "new_largest_chunk_median_ms": round(statistics.median(max_chunks), 1)}, indent=2))
        dialog.close()
        window.close()


if __name__ == "__main__":
    main()
