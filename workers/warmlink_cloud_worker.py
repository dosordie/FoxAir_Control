# -*- coding: utf-8 -*-
"""Qt-Worker fuer WarmLink/Linked-Go Cloud Polling und Schreibtest."""

from __future__ import annotations

import copy
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
from cloud.polling import CloudSession, CloudTimingState
from cloud.token_store import load_cloud_credentials


WARMLINK_APP_HEARTBEAT_SETTLE_S = 1.0


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
    progress=None,
    cancelled=None,
) -> list[dict[str, Any]]:
    """Discover deviceList and House devices, isolating non-auth House errors."""
    emit = log or (lambda _message: None)
    device_response = api.get_devices()
    if api._token_expired(device_response):
        raise WarmLinkAuthError(api.message(device_response) or "WarmLink-Login abgelaufen")
    if cancelled and cancelled():
        return []
    direct = normalize_device_list(device_response)
    emit(f"WarmLink Cloud: {len(direct)} Gerät(e) über deviceList gefunden")

    house_devices: list[dict[str, Any]] = []
    house_response = api.get_houses()
    if api._token_expired(house_response):
        raise WarmLinkAuthError(api.message(house_response) or "WarmLink-Login abgelaufen")
    if api.success(house_response):
        houses = normalize_house_list(house_response)
        emit(f"WarmLink Cloud: {len(houses)} House(s) gefunden")
        for index, house in enumerate(houses, 1):
            if cancelled and cancelled():
                break
            if progress:
                progress("DISCOVERING", index, len(houses))
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
                 relogin_on_401: bool = False, load_credentials: bool = False, use_saved_token: bool = True) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.method = method
        self.endpoint = endpoint
        self.body = body
        self.timeout_s = timeout_s
        self.load_credentials = load_credentials
        self.use_saved_token = use_saved_token
        self.initial_token = initial_token
        self.preferred_login_method = preferred_login_method
        self.login_fallbacks = login_fallbacks
        self.relogin_on_401 = relogin_on_401

    @Slot()
    def run(self) -> None:
        try:
            if self.load_credentials:
                self.password, self.initial_token = load_cloud_credentials(
                    self.username, self.password, self.initial_token,
                    use_saved_token=self.use_saved_token)
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
                 login_fallbacks: bool = False, load_credentials: bool = False, use_saved_token: bool = True) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.device_code = str(device_code or "").strip()
        self.load_credentials = load_credentials
        self.use_saved_token = use_saved_token
        self.initial_token = initial_token
        self.preferred_login_method = preferred_login_method
        self.login_fallbacks = login_fallbacks

    @Slot()
    def run(self) -> None:
        try:
            if self.load_credentials:
                self.password, self.initial_token = load_cloud_credentials(
                    self.username, self.password, self.initial_token,
                    use_saved_token=self.use_saved_token)
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
                 login_fallbacks: bool = False, load_credentials: bool = False, use_saved_token: bool = True) -> None:
        super().__init__()
        self.username = username
        self.password = password
        self.device_code = str(device_code or "").strip()
        self.codes = list(dict.fromkeys(codes))
        self.load_credentials = load_credentials
        self.use_saved_token = use_saved_token
        self.initial_token = initial_token
        self.timeout_s = timeout_s
        self.preferred_login_method = preferred_login_method
        self.login_fallbacks = login_fallbacks

    @Slot()
    def run(self) -> None:
        try:
            if self.load_credentials:
                self.password, self.initial_token = load_cloud_credentials(
                    self.username, self.password, self.initial_token,
                    use_saved_token=self.use_saved_token)
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
    progress = Signal(str, int, int)
    session_updated = Signal(object)
    credentials_loaded = Signal(str, str)
    connection_state = Signal(str)
    timing_updated = Signal(object)

    def __init__(
        self,
        username: str,
        password: str,
        codes: list[str],
        interval_s: int = 30,
        device_code: str | None = None,
        known_device_codes: list[str] | None = None,
        poll_once: bool = False,
        timeout_s: float = 15.0,
        preferred_login_method: str | None = "md5",
        login_fallbacks: bool = False,
        initial_token: str | None = None,
        initial_login_at: float | None = None,
        session: CloudSession | None = None,
        force_discovery: bool = False,
        discovery_only: bool = False,
        reload_static: bool = False,
        load_credentials: bool = False,
        use_saved_token: bool = True,
    ) -> None:
        super().__init__()
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.codes = list(dict.fromkeys(codes))
        self.interval_s = min(3600, max(10, int(interval_s or 30)))
        self.device_code = str(device_code or "").strip() or None
        self.known_device_codes = list(known_device_codes or [])
        self.poll_once = bool(poll_once)
        self.timeout_s = float(timeout_s)
        self.preferred_login_method = str(preferred_login_method or "md5").strip() or "md5"
        self.login_fallbacks = bool(login_fallbacks)
        self.initial_token = str(initial_token or "").strip() or None
        self.initial_login_at = float(initial_login_at or 0.0)
        self.session = copy.deepcopy(session) if session else CloudSession()
        self.force_discovery = force_discovery
        self.discovery_only = discovery_only
        self.reload_static = reload_static
        self.load_credentials = load_credentials
        self.use_saved_token = use_saved_token
        self._reload_event = threading.Event()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()

    @Slot()
    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def request_static_reload(self) -> None:
        self._reload_event.set()
        self._wake_event.set()

    def _sleep_interruptible(self, seconds: float) -> bool:
        self._wake_event.wait(max(0.1, seconds))
        self._wake_event.clear()
        return self._stop_event.is_set()

    def _settle_after_heartbeat(self) -> bool:
        # A static-reload wake must not shorten the DTU/cloud settle time.
        # Stop uses the same Event as the rest of this worker and wakes immediately.
        return self._stop_event.wait(WARMLINK_APP_HEARTBEAT_SETTLE_S)

    def _prepare_live_refresh(self, api) -> bool:
        if self._stop_event.is_set():
            return False
        try:
            response = api.send_app_heartbeat(self.device_code)
            if api._token_expired(response):
                raise WarmLinkAuthError(api.message(response) or "WarmLink-Login abgelaufen")
            if not api.success(response):
                raise WarmLinkCloudError(api.message(response) or "Cloud lehnt app_heartbeat ab")
        except WarmLinkAuthError:
            raise  # Keep the existing auth invalidation/retry path.
        except Exception as exc:
            if not self._stop_event.is_set():
                self.log.emit("WarmLink Cloud: Heartbeat fehlgeschlagen: " + translate_cloud_error_message(str(exc)))
            return not self._stop_event.is_set()  # Still try the normal live read.
        return not self._settle_after_heartbeat()

    def _publish_session(self):
        self.session_updated.emit(copy.deepcopy(self.session))

    def _emit_progress(self, phase, done, total):
        self.progress.emit(phase, done, total)
        phases = {"DISCOVERING": "DISCOVERY", "READING_INITIAL": "INITIAL_SCAN",
                  "READING_STATIC": "STATIC_RELOAD", "READING_LIVE": "POLL_RUNNING"}
        if phase not in ("CONNECTED", "POLLING"):
            self.timing_updated.emit(CloudTimingState(phases.get(phase, phase), done, total,
                polling_active=not self.poll_once and not self.discovery_only))

    def _emit_wait(self, phase, deadline, duration):
        self.timing_updated.emit(CloudTimingState(phase, deadline=deadline,
            duration=duration, polling_active=not self.poll_once and not self.discovery_only))

    def _discover(self, api):
        self._emit_progress("DISCOVERING", 0, 0)
        devices = discover_cloud_devices(api, self.known_device_codes, self.device_code,
            self.log.emit, self._emit_progress, self._stop_event.is_set)
        if self._stop_event.is_set():
            return False
        if not devices:
            raise WarmLinkCloudError("Keine Cloud-Geräte gefunden.")
        selection_devices = devices
        if self.discovery_only and self.device_code not in self.known_device_codes:
            automatic = [device for device in devices if device.get("discoverySource") not in ("manual", "stored-device-code")]
            if automatic:
                selection_devices = automatic
        selected = select_available_device_code(selection_devices, self.device_code)
        if not selected:
            raise WarmLinkCloudError("Ausgewähltes Gerät hat keinen deviceCode")
        self.device_code = selected
        if self.discovery_only and self.session.username == self.username and self.session.device_code == selected:
            self.session.devices = devices
        else:
            self.session = CloudSession(username=self.username, device_code=selected, devices=devices)
        if self.discovery_only:
            self.session.validated = True
        self._publish_session()
        self.devices.emit(devices)
        return True

    @Slot()
    def run(self) -> None:
        backoff_s = 5.0
        next_poll_at = None
        api = None
        try:
            self._emit_progress("CONNECTING", 0, 0)
            self.connection_state.emit("CONNECTING")
            if self.load_credentials:
                self._emit_progress("LOADING_TOKEN", 0, 0)
                self.password, self.initial_token = load_cloud_credentials(
                    self.username, self.password, self.initial_token,
                    use_saved_token=self.use_saved_token, log=self.log.emit)
                self.credentials_loaded.emit(self.username, self.password or "")
            if self._stop_event.is_set():
                return
            api = WarmLinkCloudApi(self.username, self.password, timeout=self.timeout_s,
                                   initial_token=self.initial_token,
                                   initial_login_at=self.initial_login_at)
            api.preferred_login_method = self.preferred_login_method
            api.use_login_fallbacks = self.login_fallbacks
            reuse = (not self.force_discovery and not self.discovery_only and self.session.reusable(
                self.username, self.device_code, api.token))
            if not reuse:
                if not self._discover(api):
                    return
            else:
                self.devices.emit(self.session.devices)
            if self.discovery_only:
                if api.token and api.token != self.initial_token:
                    self.session.scanned = False
                    self._publish_session()
                if api.token:
                    self.token_updated.emit(api.token)
                if api.last_login_method:
                    self.login_method.emit(api.last_login_method)
                self.connection_state.emit("CONNECTED")
                self.progress.emit("CONNECTED", 0, 0)
                self.status.emit(f"{len(self.session.devices)} Geräte gefunden")
                return
            needs_discovery = False
            if self.session.candidates != self.codes:
                self.session.scanned = False
            if api.last_login_method:
                self.login_method.emit(api.last_login_method)
            while not self._stop_event.is_set():
                if needs_discovery:
                    if not self._discover(api):
                        break
                    needs_discovery = False
                initial = not self.session.scanned
                static_reload = self.reload_static or self._reload_event.is_set()
                self.reload_static = False
                self._reload_event.clear()
                requested = self.codes if initial else (
                    self.session.static_codes if static_reload else self.session.live_codes)
                phase = "READING_INITIAL" if initial else ("READING_STATIC" if static_reload else "READING_LIVE")
                try:
                    if requested:
                        self._emit_progress(phase, 0, len(requested))
                        token_before = api.token
                        if not initial and not static_reload and not self._prepare_live_refresh(api):
                            break
                        response = api.get_data_by_code_batched(self.device_code, requested,
                            progress=lambda done, total: self._emit_progress(phase, done, total),
                            cancelled=self._stop_event.is_set)
                        if self._stop_event.is_set():
                            break
                        rows = normalize_data_values(response, requested)
                        now = time.strftime("%Y-%m-%d %H:%M:%S")
                        for row in rows:
                            row.update(lastFetch=now, stale=False)
                        self.session.merge(rows)
                        if initial:
                            self.session.classify(self.codes)
                            if not self.session.supported_codes:
                                self.session.scanned = False
                                self._publish_session()
                                self.connection_state.emit("ERROR")
                                self._emit_progress("ERROR", 0, 0)
                                self.error.emit("Keine unterstützten Werte für das ausgewählte Gerät")
                                return
                            self.log.emit(f"WarmLink Cloud: Initialscan {len(self.codes)} Kandidaten, "
                                f"{len(self.session.supported_codes)} unterstützt: "
                                f"{len(self.session.live_codes)} live, {len(self.session.static_codes)} statisch, "
                                f"{len(self.session.other_codes)} weitere")
                        self.session.validated = True
                        token_changed = bool(api.token and api.token != token_before)
                        if token_changed and not initial:
                            self.session.scanned = False
                        self._publish_session()
                        self.data.emit([dict(self.session.rows[row["code"]]) for row in rows])
                        self.connection_state.emit("CONNECTED" if self.poll_once else "POLLING")
                        self.status.emit(f"verbunden, letzter Abruf {now}")
                        self.log.emit(f"WarmLink Cloud: {phase} OK, {len(rows)} Werte")
                    if api.token:
                        self.token_updated.emit(api.token)
                    if api.last_login_method:
                        self.login_method.emit(api.last_login_method)
                    # Status is tied only to initial/live reads. Fault history stays on demand.
                    if not static_reload and not self._stop_event.is_set():
                        try:
                            status_token = api.token
                            api.get_device_status(self.device_code)
                            if api.token and api.token != status_token:
                                self.session.scanned = False
                                self._publish_session()
                                self.token_updated.emit(api.token)
                        except Exception as exc:
                            self.log.emit("WarmLink Cloud: Statusabfrage übersprungen: " + str(exc))
                    backoff_s = 5.0
                    self.progress.emit("CONNECTED" if self.poll_once else "POLLING", 0, 0)
                    if self.poll_once:
                        break
                    if not self.session.scanned:
                        continue  # A renewed login invalidates the configuration snapshot.
                    # A static reload wakes the wait, but keeps the live deadline.
                    if not static_reload or next_poll_at is None:
                        next_poll_at = time.monotonic() + self.interval_s
                    self._emit_wait("POLL_WAIT", next_poll_at, self.interval_s)
                    if self._sleep_interruptible(max(0.0, next_poll_at - time.monotonic())):
                        break
                except Exception as exc:
                    if self._stop_event.is_set():
                        break
                    if static_reload:
                        self.reload_static = True
                    auth_error = isinstance(exc, WarmLinkAuthError)
                    if auth_error:
                        self.session.validated = False
                        self.session.scanned = False
                        self._publish_session()
                        self.connection_state.emit("ERROR")
                    else:
                        self.connection_state.emit("CONNECTING")
                    lower = str(exc).lower()
                    needs_discovery = auth_error or any(marker in lower for marker in ("invalid device", "device not found", "device does not exist", "no permission", "access denied"))
                    if needs_discovery:
                        if not auth_error:
                            self.device_code = None  # An invalid saved selection must not win rediscovery.
                        self.session.validated = self.session.scanned = False
                        self._publish_session()
                    self.error.emit(translate_cloud_error_message(str(exc)))
                    self.status.emit(f"Abruf fehlgeschlagen, Retry in {int(backoff_s)}s")
                    stale = [{**self.session.rows[code], "stale": True} for code in requested
                             if code in self.session.rows]
                    if stale:
                        self.data.emit(stale)
                    if self.poll_once:
                        break
                    self._emit_wait("RETRY", time.monotonic() + backoff_s, backoff_s)
                    if self._sleep_interruptible(backoff_s):
                        break
                    backoff_s = min(300.0, backoff_s * 2)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.connection_state.emit("ERROR")
                self._emit_progress("ERROR", 0, 0)
                self.error.emit(translate_cloud_error_message(str(exc)))
        finally:
            self.timing_updated.emit(CloudTimingState())
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
        load_credentials: bool = False, use_saved_token: bool = True,
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
        self.load_credentials = load_credentials
        self.use_saved_token = use_saved_token
        self.initial_token = str(initial_token or "").strip() or None

    @Slot()
    def run(self) -> None:
        try:
            if self.load_credentials:
                self.password, self.initial_token = load_cloud_credentials(
                    self.username, self.password, self.initial_token,
                    use_saved_token=self.use_saved_token)
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
