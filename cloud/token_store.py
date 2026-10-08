# -*- coding: utf-8 -*-
"""OS-Keyring backed storage for WarmLink credentials and tokens."""

from __future__ import annotations

KEYRING_SERVICE = "warmlink_gui"


def _keyring_module():
    try:
        import keyring  # type: ignore
        return keyring
    except Exception as exc:
        raise RuntimeError(
            "Python keyring ist nicht installiert. Bitte installieren mit: pip install keyring"
        ) from exc


def _token_key(username: str) -> str:
    return f"{str(username or '').strip()}:token"


def set_password(username: str, password: str) -> None:
    kr = _keyring_module()
    kr.set_password(KEYRING_SERVICE, username, password)


def get_password(username: str) -> str | None:
    kr = _keyring_module()
    return kr.get_password(KEYRING_SERVICE, username)


def delete_password(username: str) -> None:
    kr = _keyring_module()
    try:
        kr.delete_password(KEYRING_SERVICE, username)
    except Exception:
        # Kein gespeichertes Passwort ist kein fataler Fehler.
        pass


def set_token(username: str, token: str) -> None:
    kr = _keyring_module()
    kr.set_password(KEYRING_SERVICE, _token_key(username), token)


def get_token(username: str) -> str | None:
    kr = _keyring_module()
    return kr.get_password(KEYRING_SERVICE, _token_key(username))


def delete_token(username: str) -> None:
    kr = _keyring_module()
    try:
        kr.delete_password(KEYRING_SERVICE, _token_key(username))
    except Exception:
        # Kein gespeicherter Token ist kein fataler Fehler.
        pass


def load_cloud_credentials(username, password=None, token=None, *, use_saved_token=True, log=None):
    """Call only in a worker: OS credential providers may block for seconds."""
    emit = log or (lambda message: None)
    if use_saved_token and not token:
        try:
            token = get_token(username)
        except Exception:
            emit("WarmLink Cloud: Token-Keyring nicht verfügbar")
    if not password:
        try:
            password = get_password(username)
        except Exception:
            emit("WarmLink Cloud: Passwort-Keyring nicht verfügbar")
    if not username or not (password or token):
        raise RuntimeError("Benutzername/Passwort fehlt. Zugang bitte eingeben oder speichern.")
    return password or "", token


# Serialize credential mutations, including save/delete races, outside Qt's GUI thread.
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Slot

_keyring_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warmlink-keyring")


class AsyncKeyringStore(QObject):
    completed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.completed.connect(self._complete)

    def submit(self, operation, callback=None):
        def run():
            try:
                result, error = operation(), None
            except Exception as exc:
                result, error = None, exc
            try:
                self.completed.emit((callback, result, error))
            except RuntimeError:
                pass  # Owner was closed while an OS provider was still responding.
        return _keyring_executor.submit(run)

    @Slot(object)
    def _complete(self, result):
        callback, value, error = result
        if callback:
            callback(value, error)
