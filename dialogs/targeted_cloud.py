"""Dialog lifecycle for targeted reads through the existing Cloud worker."""
import time

from PySide6.QtCore import QTimer

from cloud.snapshot_request import CloudSnapshotRequest
from cloud.warmlink_value_translator import parse_cloud_word


def fresh_cloud_row(row):
    return (row.get("supported") and row.get("value") not in (None, "")
            and not any(row.get(flag) for flag in ("cached", "stale", "currentEmpty")))


class TargetedCloudDialogMixin:
    """Users provide CLOUD_REGISTERS, CLOUD_PURPOSE and snapshot/source hooks."""

    def _init_cloud_snapshot(self):
        self._control_identity = self.main_window.control_context()
        self.cloud_request = None
        self.cloud_read_timer = QTimer(self)
        self.cloud_read_timer.setSingleShot(True)
        self.cloud_read_timer.timeout.connect(self._cloud_timeout)
        self.initial_read_timer = QTimer(self)
        self.initial_read_timer.setSingleShot(True)
        self.initial_read_timer.timeout.connect(self._autoload_cloud)
        self.finished.connect(self._close_cloud_dialog)
        self.initial_read_timer.start(250)

    def _close_cloud_dialog(self, *_args):
        self.initial_read_timer.stop()
        self._cancel_cloud_read()
        poll = getattr(self, "poll_timer", None)
        if poll is not None:
            poll.stop()
        owner = self.main_window
        if getattr(owner, "_control_cloud_write_dialog", None) is self:
            owner._control_cloud_write_cancelled.set()

    def closeEvent(self, event):
        self._close_cloud_dialog()
        super().closeEvent(event)

    def _cancel_cloud_read(self):
        self.cloud_read_timer.stop()
        if self.cloud_request is not None:
            self.cloud_request.cancelled.set()
        self.cloud_request = None

    def connection_changed(self):
        context = self.main_window.control_context()
        if context != self._control_identity:
            self._cancel_cloud_read()
            self._control_identity = context
            self._reset_cloud_source()
            self.status_label.setText("Verbindung/Gerät geändert; bitte frisch lesen.")
            if self.isVisible() and context.transport == "cloud":
                self.initial_read_timer.start(250)

    def _autoload_cloud(self):
        if not self.isVisible() or self.main_window.control_transport() != "cloud":
            return
        if self.main_window._control_cloud_busy():
            self.initial_read_timer.start(250)
            return
        self.read_cloud_snapshot()

    def read_cloud_snapshot(self):
        self.connection_changed()
        if not self.isVisible() or self.cloud_request is not None:
            return
        owner = self.main_window
        capability = owner.control_can_read(*self.CLOUD_REGISTERS)
        if not capability:
            self.status_label.setText(capability.reason)
            return
        context = owner.control_context()
        if context.transport != "cloud":
            return
        # Owner generation survives closing/reopening a dialog.
        owner._targeted_cloud_generation = getattr(owner, "_targeted_cloud_generation", 0) + 1
        self.initial_read_timer.stop()
        codes = tuple(self.CLOUD_REGISTERS.values())
        request = self.cloud_request = CloudSnapshotRequest(owner._targeted_cloud_generation, codes,
            time.monotonic() + 60, context.username, context.device_code, purpose=self.CLOUD_PURPOSE)
        self.cloud_read_timer.start(60000)
        self.status_label.setText("Lese frische Cloudwerte …")
        error = owner.control_request_snapshot(request)
        if error:
            self.cloud_read_finished(request.cycle_id, [], error)

    def _cloud_timeout(self):
        self._cancel_cloud_read()
        self._apply_cloud_snapshot({})
        self.status_label.setText("Cloud-Timeout / keine frische Antwort; Daten unvollständig.")

    def cloud_read_finished(self, cycle_id, rows, error):
        request = self.cloud_request
        if request is None or cycle_id != request.cycle_id:
            return
        if not self.isVisible() or self.main_window.control_context() != self._control_identity:
            self.connection_changed()
            self._cancel_cloud_read()
            return
        if request.expired():
            self._cloud_timeout()
            return
        self._cancel_cloud_read()
        mapping = {code: register for register, code in self.CLOUD_REGISTERS.items()}
        fresh = [row for row in rows if row.get("code") in mapping and fresh_cloud_row(row)] if not error else []
        values = {mapping[row["code"]]: parse_cloud_word(row["value"], row) for row in fresh}
        values = self._validated_cloud_values(values)
        self._apply_cloud_snapshot(values)
        self.main_window.apply_cloud_rows_to_main([row for row in fresh if mapping[row["code"]] in values])
        count = len(values)
        self.status_label.setText(f"Cloud: {count}/{len(mapping)} Werte · " + (
            str(error) if error else "erfolgreich gelesen" if count == len(mapping) else "Daten unvollständig"))

    def _validated_cloud_values(self, values):
        return {register: value for register, value in values.items() if value is not None}
