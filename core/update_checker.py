"""GitHub release update checking helpers."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import webbrowser

from PySide6.QtCore import QObject, Signal, Slot


UPDATE_REPO = "dosordie/FoxAir_Control"
UPDATE_API_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_RELEASES_URL = f"https://github.com/{UPDATE_REPO}/releases/latest"


def parse_version_tuple(text: str) -> tuple[int, ...]:
    """Versionsvergleich fuer Tags wie v0.2.30 oder 0.2.30."""
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


def open_update_url(url: str) -> None:
    """Open an update URL in the system browser."""
    webbrowser.open(url)


class UpdateCheckWorker(QObject):
    result = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(self, app_version: str):
        super().__init__()
        self.app_version = app_version

    @Slot()
    def run(self):
        try:
            req = urllib.request.Request(
                UPDATE_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"FoxAir-Phnix-Control/{self.app_version}",
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
