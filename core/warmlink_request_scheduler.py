"""One outstanding FC03 request on the Warmlink RTU stream.

Responses carry no start address. Keep the active request until a matching
response or its transport-started deadline; queued reads have no deadline yet.
"""
from __future__ import annotations

import time
from PySide6.QtCore import QObject, QTimer

WARMLINK_READ_TIMEOUT_S = 5.0
WARMLINK_READBACK_DELAY_MS = 200
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
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)

    @staticmethod
    def key(request):
        return request["slave_addr"], request["wire_addr"], request["quantity"]

    def submit(self, request, priority=None, delay_ms=0):
        priority = priority or read_priority(request.get("label"))
        request.update(scheduler=True, priority=priority, time=None, sent_monotonic=None,
                       ready_at=time.monotonic() + delay_ms / 1000)
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
        if self.active or not self.queue:
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
        if not request or self.key(request) != (slave, addr, quantity):
            return
        request["time"] = time.time()
        request["sent_monotonic"] = time.monotonic()
        if request.get("expect_response", True):
            self.timer.start(int(WARMLINK_READ_TIMEOUT_S * 1000))
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
        QTimer.singleShot(0, self._dispatch)

    def _timeout(self):
        request = self.active
        if request:
            self.timed_out(request)
            self.complete(request, timeout=True)

    def unmatched_response(self):
        if self.active is None and self.resume_at > time.monotonic():
            self.resume_at = time.monotonic() + WARMLINK_TIMEOUT_DRAIN_MS / 1000

    def cancel(self):
        self.timer.stop()
        self.active = None
        self.resume_at = 0.0
        self.queue.clear()

    def cancel_labels(self, labels):
        self.queue = [item for item in self.queue if item[2].get("label") not in labels]
        # Do not release an active FC03 early: its response has no transaction ID.
