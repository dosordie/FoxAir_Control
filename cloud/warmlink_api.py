# -*- coding: utf-8 -*-
"""Schlanker WarmLink/Linked-Go Cloud API Client.

WarmLink/Linked-Go API mapping inspired by srbjessen/ha-warmlink, licensed
under MIT. Original reverse engineering credited there to zyznos321/warmlink.

V0.2.46: Lesen bleibt Standard. Login ist robuster (plain, md5, md5md5,
optionale App-Payload-Felder). Schreibtests koennen mehrere bekannte Endpoint-
Varianten testen, bleiben aber im UI explizit freizuschalten.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from cloud.warmlink_codes import WARMLINK_PRODUCT_IDS

SERVICE_ROOT = "https://cloud.linked-go.com:449"
BASE_URL = SERVICE_ROOT + "/crmservice/api"
CLOUDSERVICE_API_ROOT = SERVICE_ROOT + "/cloudservice/api"

ENDPOINT_LOGIN = "app/user/login"
ENDPOINT_DEVICE_LIST = "app/device/deviceList"
ENDPOINT_GET_DATA_BY_CODE = "app/device/getDataByCode"
ENDPOINT_GET_DEVICE_STATUS = "app/device/getDeviceStatus"
ENDPOINT_GET_FAULT_DATA = "app/device/getFaultDataByDeviceCode"
ENDPOINT_DEVICE_CONTROL = "app/device/control"
ENDPOINT_DEVICE_CONTROL_LANG = "app/device/control?lang=en"

# Schreib-/Control-Endpunkte:
# Fuer normale App-Accounts ist der relevante Control-Endpunkt nach Repo-/Log-
# Abgleich app/device/control unter der crmservice/api-Base. Die cloudservice-
# Endpunkte liefern mit normalem App-Token HTTP 401 und bleiben nur als
# explizite Expert-Fallbacks erhalten.
ENDPOINT_WRITE_MODEL_VALUE = "cloudservice/api/device/updateDeviceControlModelValue"
ENDPOINT_WRITE_MODEL_DATA = "cloudservice/api/device/updateDeviceControlModelData"
ENDPOINT_WRITE_SWITCH_STATE = "cloudservice/api/device/updateDeviceControlSwithSate"
ENDPOINT_WRITE_APP_MODEL_VALUE = "app/device/updateDeviceControlModelValue"
ENDPOINT_AUTO_WRITE = "auto"

WRITE_ENDPOINT_CANDIDATES = [
    ENDPOINT_DEVICE_CONTROL_LANG,
    ENDPOINT_DEVICE_CONTROL,
]
EXPERT_WRITE_ENDPOINT_CANDIDATES = [
    ENDPOINT_WRITE_MODEL_VALUE,
    ENDPOINT_WRITE_MODEL_DATA,
    ENDPOINT_WRITE_SWITCH_STATE,
    ENDPOINT_WRITE_APP_MODEL_VALUE,
]

KEYRING_SERVICE = "warmlink_gui"


class WarmLinkCloudError(RuntimeError):
    pass


class WarmLinkAuthError(WarmLinkCloudError):
    pass


@dataclass
class WarmLinkCloudResponse:
    ok: bool
    data: dict[str, Any]
    message: str = ""


class WarmLinkCloudApi:
    def __init__(self, username: str, password: str, base_url: str = BASE_URL, timeout: float = 15.0) -> None:
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.base_url = str(base_url or BASE_URL).rstrip("/")
        self.timeout = float(timeout)
        self.token: str | None = None
        self.last_login_at: float = 0.0
        self.last_login_attempts: list[dict[str, Any]] = []
        self.last_login_method: str | None = None
        self.preferred_login_method: str | None = "md5"
        self.use_login_fallbacks: bool = True

    def _url(self, endpoint: str) -> str:
        ep = str(endpoint or "").strip()
        if ep.startswith("http://") or ep.startswith("https://"):
            return ep
        ep = ep.lstrip("/")
        if ep.startswith("cloudservice/api/") or ep.startswith("crmservice/api/"):
            return f"{SERVICE_ROOT}/{ep}"
        return f"{self.base_url}/{ep}"

    def _request_json(self, endpoint: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "FoxAir-Phnix-Control-WarmLinkCloud/0.2.46",
        }
        if token:
            headers["x-token"] = token
        req = urllib.request.Request(self._url(endpoint), data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw) if raw.strip() else {}
                if isinstance(data, dict):
                    data.setdefault("http_status", int(getattr(resp, "status", 200) or 200))
                    data.setdefault("endpoint", endpoint)
                return data
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            try:
                data = json.loads(raw) if raw.strip() else {}
            except Exception:
                data = {"error_msg": raw or str(exc)}
            if not isinstance(data, dict):
                data = {"error_msg": str(data)}
            data.setdefault("http_status", exc.code)
            data.setdefault("endpoint", endpoint)
            return data
        except urllib.error.URLError as exc:
            raise WarmLinkCloudError(f"Netzwerkfehler: {exc}") from exc
        except TimeoutError as exc:
            raise WarmLinkCloudError(f"Timeout nach {self.timeout:.0f}s") from exc
        except json.JSONDecodeError as exc:
            raise WarmLinkCloudError(f"Ungueltige JSON-Antwort: {exc}") from exc

    @staticmethod
    def success(data: dict[str, Any]) -> bool:
        # API nutzt historisch den Tippfehler isReusltSuc.
        return bool(data.get("isReusltSuc") or data.get("isResultSuc") or data.get("success"))

    @staticmethod
    def _success(data: dict[str, Any]) -> bool:
        return WarmLinkCloudApi.success(data)

    @staticmethod
    def message(data: dict[str, Any]) -> str:
        for key in ("error_msg", "message", "msg", "errorMsg", "error"):
            if data.get(key):
                return str(data.get(key))
        code = data.get("error_code") or data.get("code") or data.get("http_status")
        return "" if code in (None, "") else f"Fehlercode {code}"

    @staticmethod
    def _message(data: dict[str, Any]) -> str:
        return WarmLinkCloudApi.message(data)

    @staticmethod
    def _token_expired(data: dict[str, Any]) -> bool:
        code = str(data.get("error_code") or data.get("code") or data.get("http_status") or "")
        msg = WarmLinkCloudApi._message(data).lower()
        return code in {"401", "-100"} or ("login" in msg and "again" in msg)

    @staticmethod
    def _is_not_found(data: dict[str, Any]) -> bool:
        code = str(data.get("http_status") or data.get("status") or "")
        msg = WarmLinkCloudApi._message(data).lower()
        return code == "404" or "not found" in msg

    def _login_payload(self, password_value: str, extended: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {"userName": self.username, "password": password_value}
        if extended:
            payload.update({
                "loginSource": "app",
                "areaCode": "",
                "appId": "16",
                "type": "2",
                "lang": "en",
            })
        return payload

    def login(self, preferred_method: str | None = "md5", use_fallbacks: bool = True) -> bool:
        if not self.username:
            raise WarmLinkAuthError("Benutzername fehlt")
        if not self.password:
            raise WarmLinkAuthError("Passwort fehlt")

        self.preferred_login_method = preferred_method
        self.use_login_fallbacks = bool(use_fallbacks)
        self.last_login_method = None

        plain = self.password
        md5 = hashlib.md5(plain.encode("utf-8")).hexdigest()
        md5md5 = hashlib.md5(md5.encode("utf-8")).hexdigest()
        all_attempts: dict[str, tuple[str, bool]] = {
            "plain": (plain, False),
            "md5": (md5, False),
            "md5md5": (md5md5, False),
            "plain+app": (plain, True),
            "md5+app": (md5, True),
            "md5md5+app": (md5md5, True),
        }
        fallback_order = ["md5md5", "plain", "md5+app", "md5md5+app", "plain+app"]
        preferred = str(preferred_method or "md5").strip() or "md5"
        if preferred not in all_attempts:
            preferred = "md5"

        labels: list[str] = []
        for label in [preferred]:
            if label not in labels:
                labels.append(label)
        if use_fallbacks:
            for label in ["md5", *fallback_order]:
                if label not in labels:
                    labels.append(label)

        self.last_login_attempts = []
        last_data: dict[str, Any] = {}
        for label in labels:
            pw_value, extended = all_attempts[label]
            data = self._request_json(ENDPOINT_LOGIN, self._login_payload(pw_value, extended=extended))
            last_data = data
            self.last_login_attempts.append({
                "attempt": label,
                "ok": self._success(data),
                "http_status": data.get("http_status"),
                "error_code": data.get("error_code"),
                "message": self._message(data),
            })
            if self._success(data) and isinstance(data.get("objectResult"), dict):
                obj = data["objectResult"]
                token = obj.get("x-token") or obj.get("token") or obj.get("xToken")
                if token:
                    self.token = str(token)
                    self.last_login_at = time.time()
                    self.last_login_method = label
                    return True
        detail = "; ".join(f"{a['attempt']}={a.get('error_code') or a.get('http_status') or a.get('message') or 'fail'}" for a in self.last_login_attempts)
        fallback_txt = "" if use_fallbacks else "; Fallbacks deaktiviert"
        raise WarmLinkAuthError((self._message(last_data) or "Login fehlgeschlagen") + fallback_txt + (f" ({detail})" if detail else ""))

    def post(self, endpoint: str, payload: dict[str, Any], relogin: bool = True) -> dict[str, Any]:
        if not self.token:
            self.login(self.preferred_login_method or "md5", self.use_login_fallbacks)
        data = self._request_json(endpoint, payload, token=self.token)
        if relogin and self._token_expired(data):
            self.token = None
            self.login(self.preferred_login_method or "md5", self.use_login_fallbacks)
            data = self._request_json(endpoint, payload, token=self.token)
        if not isinstance(data, dict):
            raise WarmLinkCloudError("Ungueltige Antwortstruktur")
        return data

    def get_devices(self, product_ids: list[str] | None = None) -> dict[str, Any]:
        payload = {
            "productIds": product_ids or WARMLINK_PRODUCT_IDS,
            "pageIndex": "1",
            "pageSize": "999",
        }
        return self.post(ENDPOINT_DEVICE_LIST, payload)

    def get_data_by_code(self, device_code: str, codes: list[str]) -> dict[str, Any]:
        payload = {"deviceCode": str(device_code), "protocalCodes": list(codes)}
        return self.post(ENDPOINT_GET_DATA_BY_CODE, payload)

    def get_device_status(self, device_code: str) -> dict[str, Any]:
        payloads = [
            {"deviceCode": str(device_code)},
            {"device_code": str(device_code)},
        ]
        endpoints = [ENDPOINT_GET_DEVICE_STATUS, "cloudservice/api/device/getDeviceStatus", "cloudservice/api/device/getDeviceStatusMgsByDeviceCode", "cloudservice/api/device/getControlDetailStatusByDeviceCode"]
        return self._post_first_success(endpoints, payloads)

    def get_fault_data_by_device_code(self, device_code: str) -> dict[str, Any]:
        payloads = [
            {"deviceCode": str(device_code)},
            {"device_code": str(device_code)},
        ]
        endpoints = [ENDPOINT_GET_FAULT_DATA, "cloudservice/api/device/getFaultDataByDeviceCode", "cloudservice/api/device/queryFaultDevice", "cloudservice/api/device/v4/listAllDeviceFault"]
        return self._post_first_success(endpoints, payloads)

    def _post_first_success(self, endpoints: list[str], payloads: list[dict[str, Any]]) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        last: dict[str, Any] = {}
        for endpoint in endpoints:
            for payload in payloads:
                data = self.post(endpoint, payload)
                last = data
                attempts.append({"endpoint": endpoint, "payload": payload, "http_status": data.get("http_status"), "ok": self._success(data), "message": self._message(data), "error_code": data.get("error_code")})
                if self._success(data):
                    data.setdefault("endpoint", endpoint)
                    data.setdefault("payload", payload)
                    data.setdefault("attempts", attempts)
                    return data
                if self._token_expired(data):
                    continue
        last.setdefault("attempts", attempts)
        return last

    def _write_control_primary_payload(self, device_code: str, code: str, value: str | int | float) -> dict[str, Any]:
        """Bestaetigtes Payloadformat fuer den normalen App-Control-Endpunkt."""
        return {
            "appId": "16",
            "param": [{
                "deviceCode": str(device_code),
                "protocolCode": str(code),
                "value": str(value),
            }],
        }

    def _write_control_payload_variants(self, device_code: str, code: str, value: str | int | float, debug_fallbacks: bool = False) -> list[dict[str, Any]]:
        """Payloads fuer den normalen App-Control-Endpunkt.

        Live bestaetigt: app/device/control?lang=en, HTTP 200, error_code 0,
        mit {"appId":"16","param":[{"deviceCode", "protocolCode", "value"}]}.
        Alte Varianten bleiben nur fuer Debug-/Expert-Testlaeufe erhalten.
        """
        dc = str(device_code)
        c = str(code)
        v = str(value)
        primary = self._write_control_primary_payload(dc, c, v)
        if not debug_fallbacks:
            return [primary]
        return [
            primary,
            {"appId": "16", "param": [{"deviceCode": dc, "protocalCode": c, "value": v}]},
            {"appId": 16, "param": [{"deviceCode": dc, "protocolCode": c, "value": v}]},
            {"appId": 16, "param": [{"deviceCode": dc, "protocalCode": c, "value": v}]},
            {"deviceCode": dc, "appId": "16", "param": c, "value": v},
            {"deviceCode": dc, "appId": 16, "param": c, "value": v},
        ]

    def _write_legacy_payload_variants(self, device_code: str, code: str, value: str | int | float) -> list[dict[str, Any]]:
        """Alte/unsichere Payloads fuer Expert-Fallbacks."""
        dc = str(device_code)
        c = str(code)
        v = str(value)
        return [
            {"deviceCode": dc, "protocalCode": c, "protocolCode": c, "code": c, "value": v},
            {"deviceCode": dc, "protocalCode": c, "value": v},
            {"deviceCode": dc, "protocolCode": c, "value": v},
            {"deviceCode": dc, "code": c, "value": v},
            {"deviceCode": dc, "dataCode": c, "value": v},
            {"deviceCode": dc, "model": c, "value": v},
            {"deviceCode": dc, "controlCode": c, "controlValue": v},
        ]

    def _payloads_for_write_endpoint(self, endpoint: str, device_code: str, code: str, value: str | int | float, debug_fallbacks: bool = False) -> list[dict[str, Any]]:
        ep = str(endpoint or "").strip().lower()
        if ep.startswith("app/device/control"):
            return self._write_control_payload_variants(device_code, code, value, debug_fallbacks=debug_fallbacks)
        return self._write_legacy_payload_variants(device_code, code, value)

    def write_test_code(
        self,
        device_code: str,
        code: str,
        value: str | int | float,
        endpoint: str = ENDPOINT_AUTO_WRITE,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Expliziter Cloud-Schreibtest fuer einzelne erlaubte Codes.

        Die Linked-Go App nutzt fuer Steuerwerte nicht getDataByCode. Je App/
        Account wurden unterschiedliche Control-Endpunkte beobachtet. Bei
        endpoint='auto' nutzt nur den bestaetigten App-Control-Pfad.
        Alte Payload-Varianten werden nur mit endpoint='debug' oder 'expert' getestet.
        """
        endpoint_text = str(endpoint or "").strip() or ENDPOINT_AUTO_WRITE
        endpoint_lower = endpoint_text.lower()
        debug_fallbacks = endpoint_lower in ("debug", "debug-auto", "expert", "expert-auto")
        if endpoint_lower in ("", "auto"):
            endpoints = list(WRITE_ENDPOINT_CANDIDATES)
        elif endpoint_lower in ("debug", "debug-auto"):
            endpoints = list(WRITE_ENDPOINT_CANDIDATES)
        elif endpoint_lower in ("expert", "expert-auto"):
            endpoints = list(WRITE_ENDPOINT_CANDIDATES) + list(EXPERT_WRITE_ENDPOINT_CANDIDATES)
        else:
            endpoints = [endpoint_text]

        payloads_by_endpoint = [
            {"endpoint": ep, "payloads": self._payloads_for_write_endpoint(ep, device_code, code, value, debug_fallbacks=debug_fallbacks)}
            for ep in endpoints
        ]
        if dry_run:
            return {
                "isReusltSuc": True,
                "dryRun": True,
                "endpoint": endpoint_text,
                "endpoints": endpoints,
                "payloadsByEndpoint": payloads_by_endpoint,
            }

        attempts: list[dict[str, Any]] = []
        last: dict[str, Any] = {}
        for ep in endpoints:
            payloads = self._payloads_for_write_endpoint(ep, device_code, code, value, debug_fallbacks=debug_fallbacks)
            for payload in payloads:
                data = self.post(ep, payload)
                last = data
                attempts.append({
                    "endpoint": ep,
                    "payload": payload,
                    "http_status": data.get("http_status"),
                    "error_code": data.get("error_code"),
                    "ok": self._success(data),
                    "message": self._message(data),
                })
                if self._success(data):
                    data.setdefault("endpoint", ep)
                    data.setdefault("payload", payload)
                    data.setdefault("attempts", attempts)
                    return data
        last.setdefault("attempts", attempts)
        if endpoints:
            last.setdefault("endpoint", endpoints[-1])
        return last


def normalize_device_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    obj = response.get("objectResult")
    if isinstance(obj, list):
        return [d for d in obj if isinstance(d, dict)]
    if isinstance(obj, dict):
        for key in ("records", "list", "rows", "data"):
            val = obj.get(key)
            if isinstance(val, list):
                return [d for d in val if isinstance(d, dict)]
        if obj.get("deviceCode") or obj.get("deviceId"):
            return [obj]
    return []


def normalize_data_values(response: dict[str, Any], requested_codes: list[str]) -> list[dict[str, Any]]:
    obj = response.get("objectResult")
    raw_items: list[Any] = []
    if isinstance(obj, list):
        raw_items = obj
    elif isinstance(obj, dict):
        for key in ("data", "list", "records", "rows"):
            if isinstance(obj.get(key), list):
                raw_items = obj[key]
                break
        if not raw_items:
            raw_items = [obj]

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or item.get("protocalCode") or item.get("protocolCode") or item.get("name") or "").strip()
        if not code and len(item) == 1:
            code = str(next(iter(item.keys())))
            item = {"code": code, "value": next(iter(item.values()))}
        if not code:
            continue
        seen.add(code)
        value = item.get("value", item.get("dataValue", item.get("val", item.get("currentValue"))))
        rows.append({
            "code": code,
            "value": value,
            "dataType": item.get("dataType") or item.get("type") or "",
            "rangeStart": item.get("rangeStart", item.get("min")),
            "rangeEnd": item.get("rangeEnd", item.get("max")),
            "raw": item,
            "supported": value not in (None, ""),
        })

    for code in requested_codes:
        if code not in seen:
            rows.append({
                "code": code,
                "value": "",
                "dataType": "",
                "rangeStart": "",
                "rangeEnd": "",
                "raw": {},
                "supported": False,
            })
    return rows


def keyring_module():
    try:
        import keyring  # type: ignore
        return keyring
    except Exception as exc:
        raise WarmLinkCloudError(
            "Python keyring ist nicht installiert. Bitte installieren mit: pip install keyring"
        ) from exc


def keyring_set_password(username: str, password: str) -> None:
    kr = keyring_module()
    kr.set_password(KEYRING_SERVICE, username, password)


def keyring_get_password(username: str) -> str | None:
    kr = keyring_module()
    return kr.get_password(KEYRING_SERVICE, username)


def keyring_delete_password(username: str) -> None:
    kr = keyring_module()
    try:
        kr.delete_password(KEYRING_SERVICE, username)
    except Exception:
        # Kein gespeichertes Passwort ist kein fataler Fehler.
        pass
