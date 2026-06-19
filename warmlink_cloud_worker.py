# -*- coding: utf-8 -*-
"""Qt-Worker fuer WarmLink/Linked-Go Cloud Polling und Schreibtest."""

from __future__ import annotations

import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from warmlink_cloud_api import (
    ENDPOINT_AUTO_WRITE,
    ENDPOINT_WRITE_MODEL_VALUE,
    WarmLinkCloudApi,
    WarmLinkCloudError,
    WarmLinkAuthError,
    normalize_data_values,
    normalize_device_list,
)


class WarmLinkCloudWorker(QObject):
    log = Signal(str)
    status = Signal(str)
    devices = Signal(list)
    data = Signal(list)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        username: str,
        password: str,
        codes: list[str],
        interval_s: int = 60,
        device_code: str | None = None,
        poll_once: bool = False,
        timeout_s: float = 15.0,
    ) -> None:
        super().__init__()
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.codes = list(codes)
        self.interval_s = max(60, int(interval_s or 60))
        self.device_code = str(device_code or "").strip() or None
        self.poll_once = bool(poll_once)
        self.timeout_s = float(timeout_s)
        self._stop_event = threading.Event()
        self._last_good_rows: list[dict[str, Any]] = []
        self._last_good_by_code: dict[str, dict[str, Any]] = {}

    @Slot()
    def stop(self) -> None:
        self._stop_event.set()

    def _sleep_interruptible(self, seconds: float) -> bool:
        return self._stop_event.wait(max(0.1, float(seconds)))

    @Slot()
    def run(self) -> None:
        backoff_s = 5.0
        try:
            api = WarmLinkCloudApi(self.username, self.password, timeout=self.timeout_s)
            self.status.emit("Login ...")
            self.log.emit("WarmLink Cloud: Login wird versucht ...")
            api.login()
            self.status.emit("verbunden")
            self.log.emit("WarmLink Cloud: Login OK")

            devices_response = api.get_devices()
            devs = normalize_device_list(devices_response)
            self.devices.emit(devs)
            self.log.emit(f"WarmLink Cloud: {len(devs)} Gerät(e) gefunden")
            if not devs:
                self.error.emit("Keine Geräte in der Cloud gefunden")
                self.finished.emit()
                return

            selected = None
            if self.device_code:
                for dev in devs:
                    if str(dev.get("deviceCode") or "") == self.device_code:
                        selected = dev
                        break
            if selected is None:
                selected = devs[0]
                self.device_code = str(selected.get("deviceCode") or "").strip() or None
            if not self.device_code:
                self.error.emit("Ausgewähltes Gerät hat keinen deviceCode")
                self.finished.emit()
                return

            while not self._stop_event.is_set():
                started = time.time()
                try:
                    response = api.get_data_by_code(self.device_code, self.codes)
                    rows_raw = normalize_data_values(response, self.codes)
                    now_txt = time.strftime("%Y-%m-%d %H:%M:%S")
                    rows: list[dict[str, Any]] = []
                    empty_current = 0
                    for row in rows_raw:
                        code = str(row.get("code", ""))
                        r = dict(row)
                        r["lastFetch"] = now_txt
                        r["stale"] = False
                        if r.get("supported"):
                            self._last_good_by_code[code] = dict(r)
                            rows.append(r)
                        elif code in self._last_good_by_code:
                            # Leere/unsupported Cloud-Antworten ueberschreiben den
                            # letzten gueltigen Wert nicht. Fuer UI/Overlay wird der
                            # letzte gute Wert veraltet markiert.
                            cached = dict(self._last_good_by_code[code])
                            cached["stale"] = True
                            cached["cached"] = True
                            cached["currentEmpty"] = True
                            cached["lastFetch"] = cached.get("lastFetch") or now_txt
                            rows.append(cached)
                            empty_current += 1
                        else:
                            rows.append(r)
                            empty_current += 1
                    self._last_good_rows = rows
                    supported = sum(1 for r in rows if r.get("supported"))
                    unsupported = sum(1 for r in rows_raw if not r.get("supported"))

                    # Zusatzendpunkte: Status lesen; Faultdaten nur bei Hinweis auf Fehler.
                    try:
                        status_resp = api.get_device_status(self.device_code)
                        if api.success(status_resp):
                            self.log.emit("WarmLink Cloud: device/getDeviceStatus OK")
                            obj = status_resp.get("objectResult")
                            if isinstance(obj, dict) and (obj.get("isFault") or obj.get("is_fault")):
                                fault_resp = api.get_fault_data_by_device_code(self.device_code)
                                self.log.emit("WarmLink Cloud: device/getFaultDataByDeviceCode " + ("OK" if api.success(fault_resp) else "Fehler"))
                    except Exception as status_exc:
                        self.log.emit(f"WarmLink Cloud: Status/Fault Zusatzabfrage übersprungen: {status_exc}")

                    self.data.emit(rows)
                    self.status.emit(f"verbunden, letzter Abruf {now_txt}")
                    cached_txt = f", {empty_current} leer/unsupported davon Cache genutzt" if empty_current else ""
                    self.log.emit(f"WarmLink Cloud: Poll OK, {supported} Werte, {unsupported} leer/unsupported{cached_txt}")
                    backoff_s = 5.0
                    if self.poll_once:
                        break
                    elapsed = time.time() - started
                    if self._sleep_interruptible(max(1.0, self.interval_s - elapsed)):
                        break
                except (WarmLinkAuthError, WarmLinkCloudError, Exception) as exc:
                    msg = f"WarmLink Cloud: Poll Fehler: {exc}"
                    self.error.emit(str(exc))
                    self.status.emit(f"Fehler, Retry in {int(backoff_s)}s")
                    self.log.emit(msg)
                    if self._last_good_rows:
                        stale = []
                        now_txt = time.strftime("%Y-%m-%d %H:%M:%S")
                        for row in self._last_good_rows:
                            r = dict(row)
                            r["stale"] = True
                            r["lastFetch"] = r.get("lastFetch") or now_txt
                            stale.append(r)
                        self.data.emit(stale)
                    if self.poll_once:
                        break
                    if self._sleep_interruptible(backoff_s):
                        break
                    backoff_s = min(300.0, backoff_s * 2.0)
        finally:
            self.finished.emit()


class WarmLinkCloudCommandWorker(QObject):
    log = Signal(str)
    result = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        username: str,
        password: str,
        device_code: str,
        code: str,
        value: str,
        endpoint: str = ENDPOINT_AUTO_WRITE,
        dry_run: bool = True,
        timeout_s: float = 15.0,
    ) -> None:
        super().__init__()
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.device_code = str(device_code or "").strip()
        self.code = str(code or "").strip()
        self.value = str(value)
        self.endpoint = str(endpoint or ENDPOINT_WRITE_MODEL_VALUE).strip()
        self.dry_run = bool(dry_run)
        self.timeout_s = float(timeout_s)

    @Slot()
    def run(self) -> None:
        try:
            api = WarmLinkCloudApi(self.username, self.password, timeout=self.timeout_s)
            self.log.emit("WarmLink Cloud schreiben: Login ...")
            api.login()

            if not self.device_code:
                devices_response = api.get_devices()
                devs = normalize_device_list(devices_response)
                if not devs:
                    raise WarmLinkCloudError("deviceCode fehlt und keine Cloud-Geräte gefunden")
                self.device_code = str(devs[0].get("deviceCode") or "").strip()
                if not self.device_code:
                    raise WarmLinkCloudError("Erstes Cloud-Gerät hat keinen deviceCode")
                nick = str(devs[0].get("deviceNickName") or devs[0].get("deviceName") or "").strip()
                self.log.emit(f"WarmLink Cloud schreiben: kein gespeichertes Gerät, nutze erstes Gerät {nick or self.device_code}")

            self.log.emit(
                f"WarmLink Cloud schreiben: {'DRY-RUN ' if self.dry_run else ''}{self.code}={self.value} via {self.endpoint}"
            )
            data = api.write_test_code(
                device_code=self.device_code,
                code=self.code,
                value=self.value,
                endpoint=self.endpoint,
                dry_run=self.dry_run,
            )

            if (not self.dry_run) and api.success(data):
                # Kurzer Readback: App/Cloud braucht oft einen Moment, bis der neue
                # Wert wieder in getDataByCode auftaucht. Fehler hier macht den
                # eigentlichen Schreib-Erfolg nicht kaputt.
                time.sleep(2.0)
                try:
                    rb_response = api.get_data_by_code(self.device_code, [self.code])
                    rb_rows = normalize_data_values(rb_response, [self.code])
                    rb = rb_rows[0] if rb_rows else {"code": self.code, "supported": False}
                    data["readback"] = rb
                    if rb.get("supported"):
                        self.log.emit(f"WarmLink Cloud schreiben: Readback {self.code}={rb.get('value')}")
                    else:
                        self.log.emit(f"WarmLink Cloud schreiben: Readback {self.code} leer/unsupported")
                except Exception as rb_exc:
                    data["readback_error"] = str(rb_exc)
                    self.log.emit(f"WarmLink Cloud schreiben: Readback übersprungen: {rb_exc}")

            self.result.emit(data)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()
