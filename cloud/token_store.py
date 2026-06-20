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
