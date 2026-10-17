"""One outstanding FC03 request on the Warmlink RTU stream.

Responses carry no start address. Keep the active request until a matching
response or its transport-started deadline; queued reads have no deadline yet.
"""
from __future__ import annotations

import time
from PySide6.QtCore import QObject, QTimer, Qt

WARMLINK_READ_TIMEOUT_S = 5.0
WARMLINK_READBACK_DELAY_MS = 800
WARMLINK_READBACK_TIMEOUT_S = 12.0
WARMLINK_TIMEOUT_DRAIN_MS = 500
READ_PRIORITIES = {"readback": 0, "manual": 1, "dialog": 2, "background": 3, "init": 4}


def read_priority(label):
    label = str(label).lower()
    if "readback" in label:
        return "readback"
    if label.startswith(("popup register", "rechtsklick", "manuell")):
        return "manual"
    if "init" in label or "geräte-info" in label:
        return "init"
    if label.startswith("auto-poll"):
        return "background"
    return "dialog"


class WarmlinkRequestScheduler(QObject):
    def __init__(self, parent, send, timed_out, log):
        super().__init__(parent)
        self.send = send
        self.timed_out = timed_out
        self.log = log
        self.active = None
        self.queue = []
        self.sequence = 0
        self.resume_at = 0.0
        self.unresolved = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._timeout)

    @staticmethod
    def key(request):
        return request["slave_addr"], request["wire_addr"], request["quantity"]

    def submit(self, request, priority=None, delay_ms=0):
        priority = priority or read_priority(request.get("label"))
        request.update(scheduler=True, priority=priority, time=None, sent_monotonic=None,
                       ready_at=time.monotonic() + delay_ms / 1000,
                       timeout_s=WARMLINK_READBACK_TIMEOUT_S if priority == "readback" else WARMLINK_READ_TIMEOUT_S)
        key = self.key(request)
        if priority == "readback":
            # A new acknowledged write needs a fresh read, even if an older
            # identical request is active. Never cancel that in-flight request.
            self.queue = [item for item in self.queue if self.key(item[2]) != key]
        else:
            for _rank, _sequence, queued in self.queue:
                if self.key(queued) == key:
                    if READ_PRIORITIES[priority] < READ_PRIORITIES[queued["priority"]]:
                        queued["priority"] = priority
                        self.queue = [(READ_PRIORITIES[r["priority"]], seq, r) for _, seq, r in self.queue]
                    return queued
            if self.active and self.key(self.active) == key:
                return self.active
        self.sequence += 1
        self.queue.append((READ_PRIORITIES[priority], self.sequence, request))
        self.log(f"WARMLINK READ queued: reg={request['addr']} qty={request['quantity']} priority={priority}")
        self._dispatch()
        return request

    def _dispatch(self):
        if self.active or self.unresolved or not self.queue:
            return
        quiet_remaining = self.resume_at - time.monotonic()
        if quiet_remaining > 0:
            QTimer.singleShot(max(1, int(quiet_remaining * 1000) + 1), self._dispatch)
            return
        self.queue.sort(key=lambda item: item[:2])
        request = self.queue[0][2]
        remaining = request["ready_at"] - time.monotonic()
        if remaining > 0:
            QTimer.singleShot(max(1, int(remaining * 1000) + 1), self._dispatch)
            return  # Reserve the next slot for a readback during its settle delay.
        self.queue.pop(0)
        self.active = request
        self.send(request)

    def sent(self, addr, quantity, slave):
        request = self.active
        if not request or request["sent_monotonic"] is not None or self.key(request) != (slave, addr, quantity):
            return
        request["time"] = time.time()
        request["sent_monotonic"] = time.monotonic()
        if request.get("expect_response", True):
            self.timer.start(int(request["timeout_s"] * 1000))
        else:
            self.complete(request)
        self.log(f"WARMLINK READ sent: reg={request['addr']} qty={quantity}")

    def matching(self, slave, byte_count):
        request = self.active
        if request and request["sent_monotonic"] is not None and request["slave_addr"] == slave and request["quantity"] * 2 == byte_count:
            return request
        return None

    def complete(self, request, timeout=False):
        if request is not self.active:
            return
        self.timer.stop()
        elapsed = time.monotonic() - (request["sent_monotonic"] or time.monotonic())
        self.log(f"WARMLINK READ {'timeout' if timeout else 'response'}: reg={request['addr']} qty={request['quantity']} after {elapsed*1000:.0f} ms")
        self.active = None
        if timeout:
            self.resume_at = time.monotonic() + WARMLINK_TIMEOUT_DRAIN_MS / 1000
            if request.get("sent_monotonic") is not None:
                # FC03 has no address or transaction ID. Quiet time alone cannot
                # prove a late answer is gone. Retain ownership until it arrives,
                # or until reconnect resets the stream.
                self.unresolved = request
                self.log("WARMLINK READ suspended: ausstehende Antwort nach Timeout; späte Antwort abwarten oder Verbindung neu aufbauen.")
        QTimer.singleShot(0, self._dispatch)

    def _timeout(self):
        request = self.active
        if request:
            self.timed_out(request)
            self.complete(request, timeout=True)

    def unmatched_response(self, slave=None, byte_count=None):
        if self.unresolved and (self.unresolved["slave_addr"], self.unresolved["quantity"] * 2) == (slave, byte_count):
            self.log(f"WARMLINK READ late response drained: reg={self.unresolved['addr']}")
            self.unresolved = None
        if self.active is None:
            self.resume_at = time.monotonic() + WARMLINK_TIMEOUT_DRAIN_MS / 1000
            QTimer.singleShot(WARMLINK_TIMEOUT_DRAIN_MS + 1, self._dispatch)

    def cancel(self):
        self.timer.stop()
        self.active = None
        self.resume_at = 0.0
        self.queue.clear()
        self.unresolved = None

    def cancel_labels(self, labels):
        self.queue = [item for item in self.queue if item[2].get("label") not in labels]
        # Do not release an active FC03 early: its response has no transaction ID.
