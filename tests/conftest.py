"""Stable Qt lifetime and isolated OS credential storage for functional tests."""
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def isolated_os_keyring():
    from cloud import token_store
    passwords = {}
    backend = SimpleNamespace(
        get_password=lambda service, username: passwords.get((service, username)),
        set_password=lambda service, username, value: passwords.__setitem__((service, username), value),
        delete_password=lambda service, username: passwords.pop((service, username), None),
    )
    patch = pytest.MonkeyPatch()
    patch.setattr(token_store, "_keyring_module", lambda: backend)
    yield passwords
    token_store._keyring_executor.submit(lambda: None).result(timeout=5)
    patch.undo()


@pytest.fixture(autouse=True)
def clean_keyring_state(isolated_os_keyring):
    from cloud import token_store
    token_store._keyring_executor.submit(lambda: None).result(timeout=5)
    isolated_os_keyring.clear()
    yield
    token_store._keyring_executor.submit(lambda: None).result(timeout=5)


@pytest.fixture(scope="session", autouse=True)
def qt_application_session(isolated_os_keyring):
    from PySide6.QtWidgets import QApplication
    from cloud import token_store
    application = QApplication.instance() or QApplication([])
    yield application
    token_store._keyring_executor.submit(lambda: None).result(timeout=5)
    application.processEvents()
