"""Functional shutdown guarantees for the existing Cloud worker owners."""
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QThread

from dialogs.cloud_dialog import WarmLinkCloudDialog
from test_cloud_single_read_and_values import application
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window


class GatedThread(QThread):
    def __init__(self, parent, gate):
        super().__init__(parent)
        self.gate = gate

    def run(self):
        self.gate.wait(5)


def track_close(window, monkeypatch):
    calls = []
    original = window.close
    def close():
        calls.append(True)
        return original()
    monkeypatch.setattr(window, "close", close)
    window.show()
    return calls


@pytest.mark.parametrize("kind", ["read", "write"])
def test_owner_cleanup_consumes_close_marker_once(window, monkeypatch, kind):
    calls = []
    monkeypatch.setattr(window, "close", lambda: calls.append("close"))
    setattr(window, f"_close_after_cloud_{kind}", True)
    cleanup = getattr(window, f"_cloud_{kind}_finished")
    cleanup()
    cleanup()
    assert calls == ["close"]
    assert not getattr(window, f"_close_after_cloud_{kind}")
    assert getattr(window, f"cloud_{kind}_thread") is None


def test_poll_shutdown_waits_for_owner_cleanup_and_resumes_once(window, monkeypatch):
    gate = threading.Event()
    dialog = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    stops = []
    dialog.cloud_worker = SimpleNamespace(stop=lambda: stops.append(True))
    job = dialog.cloud_thread = GatedThread(dialog, gate)
    job.finished.connect(dialog._worker_finished)
    calls = track_close(window, monkeypatch)
    job.start()
    try:
        window.close(); window.close()
        assert window.isVisible() and job.isRunning()
        assert stops == [True, True]
        assert window._close_after_cloud_poll
        gate.set()
        wait_for(lambda: not window.isVisible())
        assert calls == [True, True, True]
        assert dialog.cloud_thread is None and dialog.cloud_worker is None
        assert not window._close_after_cloud_poll
    finally:
        gate.set()
        wait_for(lambda: not job.isRunning())
        window.warmlink_cloud_dialog = None


def test_poll_finished_before_close_still_resumes_after_queued_cleanup(window, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    dialog = window.warmlink_cloud_dialog = WarmLinkCloudDialog(window)
    gate = threading.Event(); gate.set()
    job = dialog.cloud_thread = GatedThread(dialog, gate)
    job.start(); assert job.wait(1000)
    # Native thread ended, but its GUI cleanup has not yet cleared the slot.
    dialog.cloud_worker = SimpleNamespace(stop=lambda: None)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted() and window._close_after_cloud_poll
    calls = []
    monkeypatch.setattr(window, "close", lambda: calls.append("close"))
    dialog._worker_finished()
    assert calls == ["close"] and not window._close_after_cloud_poll
    assert dialog.cloud_thread is None
    window.warmlink_cloud_dialog = None


@pytest.mark.parametrize("job_name", ["debug_thread", "sim_thread"])
def test_repeated_close_does_not_duplicate_auxiliary_completion_callbacks(window, monkeypatch, job_name):
    gate = threading.Event()
    dialog = WarmLinkCloudDialog(window)
    job = GatedThread(dialog, gate)
    setattr(dialog, job_name, job)
    job.finished.connect(lambda: setattr(dialog, job_name, None))
    calls = track_close(window, monkeypatch)
    job.start()
    dialog.close()
    try:
        for _ in range(3):
            window.close()
        assert window.isVisible() and job.isRunning()
        gate.set()
        wait_for(lambda: not window.isVisible())
        assert calls == [True] * 4
        assert getattr(dialog, job_name) is None
        assert not window._close_after_cloud_read and not window._close_after_cloud_poll
    finally:
        gate.set()
        wait_for(lambda: not job.isRunning())


@pytest.mark.parametrize("job_name", ["debug_thread", "sim_thread"])
def test_finished_auxiliary_thread_does_not_block_close(window, monkeypatch, job_name):
    dialog = WarmLinkCloudDialog(window)
    gate = threading.Event(); gate.set()
    job = GatedThread(dialog, gate)
    setattr(dialog, job_name, job)
    job.start(); assert job.wait(1000)
    calls = track_close(window, monkeypatch)
    window.close()
    assert not window.isVisible() and calls == [True]
    assert not window._close_after_cloud_read and not window._close_after_cloud_poll
    setattr(dialog, job_name, None)
    job.deleteLater()
