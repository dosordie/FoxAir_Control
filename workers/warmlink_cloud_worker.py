# -*- coding: utf-8 -*-
"""Qt-Worker fuer WarmLink/Linked-Go Cloud Polling und Schreibtest."""

from __future__ import annotations

import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from cloud.warmlink_api import (
    ENDPOINT_AUTO_WRITE,
    ENDPOINT_WRITE_MODEL_VALUE,
    WarmLinkCloudApi,
    WarmLinkCloudError,
    WarmLinkAuthError,
    translate_cloud_error_message,
    normalize_data_values,
    normalize_device_list,
    normalize_house_devices,
    normalize_house_list,
)
from cloud.known_devices import merge_discovered_and_known_devices, merge_device_sources, select_available_device_code
from cloud.known_devices import validation_has_value


def devices_with_known_code_fallback(
    devices: list[dict[str, Any]], device_code: str | None,
) -> list[dict[str, Any]]:
    """Compatibility wrapper: merge a stored selection into any discovery."""
    result = merge_discovered_and_known_devices(devices, [device_code])
    code = str(device_code or "").strip()
    for device in result:
        if code and device.get("deviceCode") == code and device.get("discoverySource") == "manual":
            device["discoverySource"] = "stored-device-code"
    return result


def supported_codes_for_next_poll(
    requested_codes: list[str], rows: list[dict[str, Any]],
) -> list[str]:
    """Reduce a discovery request to codes actually returned by this device."""
    supported = {str(row.get("code") or "") for row in rows if row.get("supported")}
    return [code for code in requested_codes if code in supported]


def discover_cloud_devices(
    api: WarmLinkCloudApi,
    known_device_codes: list[str],
    selected_device_code: str | None = None,
    log=None,
) -> list[dict[str, Any]]:
    """Discover deviceList and House devices, isolating non-auth House errors."""
    emit = log or (lambda _message: None)
    device_response = api.get_devices()
    if api._token_expired(device_response):
        raise WarmLinkAuthError(api.message(device_response) or "WarmLink-Login abgelaufen")
    direct = normalize_device_list(device_response)
    emit(f"WarmLink Cloud: {len(direct)} Gerät(e) über deviceList gefunden")

    house_devices: list[dict[str, Any]] = []
    house_response = api.get_houses()
    if api._token_expired(house_response):
        raise WarmLinkAuthError(api.message(house_response) or "WarmLink-Login abgelaufen")
    if api.success(house_response):
        houses = normalize_house_list(house_response)
        emit(f"WarmLink Cloud: {len(houses)} House(s) gefunden")
        for house in houses:
            house_id = house["id"]
            try:
                response = api.get_house_devices(house_id)
                if api._token_expired(response):
                    raise WarmLinkAuthError(api.message(response) or "WarmLink-Login abgelaufen")
                if not api.success(response):
                    emit(f"WarmLink Cloud: House {house_id} → Fehler: {api.message(response) or 'API-Fehler'}")
                    continue
                found = normalize_house_devices(response, house)
                house_devices.extend(found)
                emit(f"WarmLink Cloud: House {house_id} → {len(found)} Gerät(e)")
            except WarmLinkAuthError:
                raise
            except Exception as exc:
                emit(f"WarmLink Cloud: House {house_id} → Fehler: {translate_cloud_error_message(str(exc))}")
    else:
        emit(f"WarmLink Cloud: House-Liste nicht verfügbar: {api.message(house_response) or 'API-Fehler'}")

    known = list(known_device_codes)
    if selected_device_code and selected_device_code not in known:
        known.append(selected_device_code)
    merged = merge_device_sources(direct, house_devices, known)
    automatic_codes = {
        str(device.get("deviceCode")) for device in [*direct, *house_devices]
        if device.get("deviceCode")
    }
    manual_added = sum(
        1 for device in merged
        if device.get("discoverySource") == "manual" and device.get("deviceCode") not in automatic_codes
    )
    emit(f"WarmLink Cloud: insgesamt {len(merged)} eindeutige Cloud-Geräte")
    emit(f"WarmLink Cloud: {manual_added} manuelle Fallback-Geräte ergänzt")
    return merged


class WarmLinkCloudDebugWorker(QObject):
    """Runs one generic authenticated cloud request outside the GUI thread."""

    result = Signal(object)
    error = Signal(str)
    token_updated = Signal(str)
    finished = Signal()

    def __init__(self, username: str, password: str, method: str, endpoint: str,
                 body: Any = None, timeout_s: float = 15.0,
                 initial_token: str | None = None,
                 preferred_login_method: str = "md5", login_fallbacks: bool = False,
                 relogin_on_401: bool = False) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.method = method
        self.endpoint = endpoint
        self.body = body
        self.timeout_s = timeout_s
        self.initial_token = initial_token
        self.preferred_login_method = preferred_login_method
        self.login_fallbacks = login_fallbacks
        self.relogin_on_401 = relogin_on_401

    @Slot()
    def run(self) -> None:
        try:
            api = WarmLinkCloudApi(
                self.username, self.password, timeout=self.timeout_s,
                initial_token=self.initial_token,
            )
            api.preferred_login_method = self.preferred_login_method
            api.use_login_fallbacks = self.login_fallbacks
            response = api.debug_request(
                self.method, self.endpoint, self.body, relogin=self.relogin_on_401,
            )
            if api.token:
                self.token_updated.emit(api.token)
            self.result.emit(response)
        except Exception as exc:
            self.error.emit(translate_cloud_error_message(str(exc)))
        finally:
            self.finished.emit()


class WarmLinkKnownDeviceValidationWorker(QObject):
    """Validate one manually entered code with a small read-only request."""

    validated = Signal(str, object)
    error = Signal(str)
    authentication_error = Signal(str)
    token_updated = Signal(str)
    finished = Signal()

    VALIDATION_CODES = ["MainBoard Version", "code_version"]

    def __init__(self, username: str, password: str, device_code: str,
                 initial_token: str | None = None,
                 preferred_login_method: str = "md5",
                 login_fallbacks: bool = False) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.device_code = str(device_code or "").strip()
        self.initial_token = initial_token
        self.preferred_login_method = preferred_login_method
        self.login_fallbacks = login_fallbacks

    @Slot()
    def run(self) -> None:
        try:
            api = WarmLinkCloudApi(
                self.username, self.password, initial_token=self.initial_token,
            )
            api.preferred_login_method = self.preferred_login_method
            api.use_login_fallbacks = self.login_fallbacks
            response = api.get_data_by_code(self.device_code, self.VALIDATION_CODES)
            if not api.success(response):
                if api._token_expired(response):
                    raise WarmLinkAuthError(api.message(response) or "WarmLink-Login abgelaufen")
                raise WarmLinkCloudError(api.message(response) or "Gerätecode konnte nicht gelesen werden")
            rows = normalize_data_values(response, self.VALIDATION_CODES)
            if not validation_has_value(rows):
                raise WarmLinkCloudError("Kein lesbarer Validierungswert empfangen")
            if api.token:
                self.token_updated.emit(api.token)
            self.validated.emit(self.device_code, rows)
        except WarmLinkAuthError as exc:
            self.authentication_error.emit(translate_cloud_error_message(str(exc)))
        except Exception as exc:
            self.error.emit(translate_cloud_error_message(str(exc)))
        finally:
            self.finished.emit()


class WarmLinkCloudReadWorker(QObject):
    """Read requested codes using the selected device, without discovery."""

    log = Signal(str)
    data = Signal(list)
    error = Signal(str)
    token_updated = Signal(str)
    login_method = Signal(str)
    finished = Signal()

    def __init__(self, username: str, password: str, device_code: str,
                 codes: list[str], initial_token: str | None = None,
                 timeout_s: float = 15.0, preferred_login_method: str = "md5",
                 login_fallbacks: bool = False) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.device_code = str(device_code or "").strip()
        self.codes = list(dict.fromkeys(codes))
        self.initial_token = initial_token
        self.timeout_s = timeout_s
        self.preferred_login_method = preferred_login_method
        self.login_fallbacks = login_fallbacks

    @Slot()
    def run(self) -> None:
        try:
            if not self.device_code:
                raise WarmLinkCloudError("Kein Cloud-Gerät ausgewählt (deviceCode fehlt).")
            if not self.codes:
                raise WarmLinkCloudError("Keine Cloud-Codes angefordert.")
            api = WarmLinkCloudApi(self.username, self.password, timeout=self.timeout_s,
                                   initial_token=self.initial_token)
            api.preferred_login_method = self.preferred_login_method
            api.use_login_fallbacks = self.login_fallbacks
            self.log.emit("WarmLink Cloud Einzelread: " + ", ".join(self.codes))
            # The existing request mechanism reuses tokens and retries expired auth.
            response = api.get_data_by_code(self.device_code, self.codes)
            if not api.success(response):
                raise WarmLinkCloudError(api.message(response) or "Cloud-Abfrage fehlgeschlagen")
            rows = normalize_data_values(response, self.codes)
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            for row in rows:
                row.update(lastFetch=now, stale=False)
            self.data.emit(rows)
            if api.token:
                self.token_updated.emit(api.token)
            if api.last_login_method:
                self.login_method.emit(api.last_login_method)
                self.log.emit(f"WarmLink Cloud Einzelread: Login via {api.last_login_method}")
        except Exception as exc:
            self.error.emit(translate_cloud_error_message(str(exc)))
        finally:
            self.finished.emit()


class WarmLinkCloudWorker(QObject):
    log = Signal(str)
    status = Signal(str)
    devices = Signal(list)
    data = Signal(list)
    error = Signal(str)
    login_method = Signal(str)
    token_updated = Signal(str)
    finished = Signal()

    def __init__(
        self,
        username: str,
        password: str,
        codes: list[str],
        interval_s: int = 60,
        device_code: str | None = None,
        known_device_codes: list[str] | None = None,
        poll_once: bool = False,
        timeout_s: float = 15.0,
        preferred_login_method: str | None = "md5",
        login_fallbacks: bool = False,
        initial_token: str | None = None,
        initial_login_at: float | None = None,
    ) -> None:
        super().__init__()
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.codes = list(codes)
        self.interval_s = max(60, int(interval_s or 60))
        self.device_code = str(device_code or "").strip() or None
        self.known_device_codes = list(known_device_codes or [])
        self.poll_once = bool(poll_once)
        self.timeout_s = float(timeout_s)
        self.preferred_login_method = str(preferred_login_method or "md5").strip() or "md5"
        self.login_fallbacks = bool(login_fallbacks)
        self.initial_token = str(initial_token or "").strip() or None
        self.initial_login_at = float(initial_login_at or 0.0)
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
        api: WarmLinkCloudApi | None = None
        try:
            api = WarmLinkCloudApi(
                self.username,
                self.password,
                timeout=self.timeout_s,
                initial_token=self.initial_token,
                initial_login_at=self.initial_login_at,
            )
            api.preferred_login_method = self.preferred_login_method
            api.use_login_fallbacks = self.login_fallbacks
            self.status.emit("verbunden" if api.has_fresh_token() else "Login ...")
            if not api.has_fresh_token():
                self.log.emit("WarmLink Cloud: Login wird versucht ...")

            devs = discover_cloud_devices(
                api, self.known_device_codes, self.device_code, self.log.emit,
            )
            if api.reused_initial_token and not api.last_login_method:
                self.log.emit("WarmLink Cloud: gespeicherten Token verwendet")
            if api.last_login_method:
                self.preferred_login_method = api.last_login_method
                self.login_method.emit(api.last_login_method)
                self.log.emit(f"WarmLink Cloud: Login OK via {api.last_login_method}")
            if api.token:
                self.token_updated.emit(api.token)
            self.status.emit("verbunden")
            if not devs:
                self.devices.emit([])
                self.error.emit("Keine Geräte über deviceList, House/Residence oder bekannte Gerätecodes gefunden.")
                return
            self.devices.emit(devs)

            self.device_code = select_available_device_code(devs, self.device_code)
            if not self.device_code:
                self.error.emit("Ausgewähltes Gerät hat keinen deviceCode")
                self.finished.emit()
                return

            while not self._stop_event.is_set():
                started = time.time()
                try:
                    response = api.get_data_by_code_batched(self.device_code, self.codes)
                    batch_failures = response.get("batchFailures", [])
                    if batch_failures:
                        failed_codes = sum(len(item.get("codes", [])) for item in batch_failures)
                        self.log.emit(
                            f"WarmLink Cloud: {failed_codes} Code(s) vom Gerät/API abgelehnt; "
                            "übrige Blöcke wurden weiter ausgewertet"
                        )
                    if api.token:
                        self.token_updated.emit(api.token)
                    rows_raw = normalize_data_values(response, self.codes)
                    next_poll_codes = supported_codes_for_next_poll(self.codes, rows_raw)
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
                    if next_poll_codes != self.codes:
                        removed = len(self.codes) - len(next_poll_codes)
                        self.codes = next_poll_codes
                        self.log.emit(
                            f"WarmLink Cloud: Discovery abgeschlossen; Folge-Polls verwenden "
                            f"{len(self.codes)} unterstützte Codes ({removed} entfernt)"
                        )
                    backoff_s = 5.0
                    if self.poll_once:
                        break
                    if not self.codes:
                        self.error.emit("Discovery lieferte keine unterstützten Codes; Dauer-Poll beendet")
                        break
                    elapsed = time.time() - started
                    if self._sleep_interruptible(max(1.0, self.interval_s - elapsed)):
                        break
                except (WarmLinkAuthError, WarmLinkCloudError, Exception) as exc:
                    msg = f"WarmLink Cloud: Poll Fehler: {exc}"
                    self.error.emit(translate_cloud_error_message(str(exc)))
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
        except Exception as exc:
            msg = translate_cloud_error_message(str(exc))
            self.error.emit(msg)
            self.status.emit("Fehler: " + msg)
            self.log.emit("WarmLink Cloud: Login/Start Fehler: " + msg)
            if api is not None and getattr(api, "last_login_attempts", None):
                attempts = "; ".join(
                    f"{a.get('attempt')}={a.get('error_code') or a.get('http_status') or a.get('message') or 'fail'}"
                    for a in api.last_login_attempts
                )
                if attempts:
                    self.log.emit("WarmLink Cloud: Login-Versuche: " + attempts)
            if not self.login_fallbacks:
                self.log.emit("WarmLink Cloud: Login-Fallbacks deaktiviert")
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
        initial_token: str | None = None,
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
        self.initial_token = str(initial_token or "").strip() or None

    @Slot()
    def run(self) -> None:
        try:
            api = WarmLinkCloudApi(self.username, self.password, timeout=self.timeout_s, initial_token=self.initial_token)
            if self.initial_token:
                self.log.emit("WarmLink Cloud schreiben: gespeicherten/vorhandenen Token verwendet")
            else:
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
            self.error.emit(translate_cloud_error_message(str(exc)))
        finally:
            self.finished.emit()
