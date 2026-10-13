"""Exclusive identity lease on the existing ReaderWorker queue, without retries.

FC03 RTU replies have no address/transaction identifier. Only one outstanding
service request is permitted; failures close this connection to quarantine late
replies before any new session. The ordinary queue remains unchanged otherwise.
"""
from __future__ import annotations

import threading
import uuid

from core.device_identity import (READ_START, READ_QUANTITY, WRITE_START,
                                  WRITE_QUANTITY, SLAVE, checked_words,
                                  decode_wifi_identity, validate_wifi_identity)


class DeviceIdentityIOMixin:
    def init_identity_io(self):
        self._identity_lock = threading.RLock()
        self._identity_token = None
        self._identity_guard = None
        self._identity_inflight = None
        self._normal_tx_busy = False

    @property
    def identity_service_active(self):
        return self._identity_token is not None

    def begin_identity_service(self, guard):
        with self._identity_lock:
            if (self._identity_token or not self.running or self.tx_blocked
                    or self._normal_tx_busy or not self.write_queue.empty() or self.buf
                    or not self.client or not self.client.is_connected() or not guard()):
                return None
            self._identity_token = uuid.uuid4().hex
            self._identity_guard = guard
            self._identity_inflight = None
            return self._identity_token

    def end_identity_service(self, token, *, abort=False):
        with self._identity_lock:
            if token != self._identity_token:
                return
            # Never let a queued or late identity reply enter normal decoding.
            if abort or self._identity_inflight or not self.write_queue.empty():
                self.stop()
                while not self.write_queue.empty():
                    self.write_queue.get_nowait()
                # Keep a privacy tombstone until this stopped worker is destroyed.
                # A recv already in progress may still return a late reply.
                self._identity_inflight = None
                return
            self._identity_token = None
            self._identity_guard = None
            self._identity_inflight = None

    def _enqueue_io(self, entry, identity_token=None):
        with self._identity_lock:
            if self._identity_token:
                if identity_token != self._identity_token or self._identity_inflight or not self.write_queue.empty():
                    return False
                kind, slave, addr, values, _, _ = entry
                if kind == "read":
                    valid = (slave, addr, values) == (SLAVE, READ_START, READ_QUANTITY)
                elif kind == "write_block":
                    checked_words(values, WRITE_QUANTITY)
                    valid = ((slave, addr) == (SLAVE, WRITE_START) and values[:2] == [0xAA, 0x5A]
                             and validate_wifi_identity(decode_wifi_identity(values[2:])))
                else:
                    valid = False
                if not valid or not self._identity_guard():
                    return False
                self.write_queue.put((*entry, identity_token))
            elif identity_token is not None:
                return False
            else:
                self.write_queue.put(entry)
            return True

    def _identity_before_send(self, token, kind):
        with self._identity_lock:
            if token != self._identity_token or not self._identity_guard() or self.tx_blocked:
                self.identity_event.emit(token, "error", None)
                return False
            self._identity_inflight = kind
            return True

    def _identity_route_frame(self, raw):
        with self._identity_lock:
            token, phase = self._identity_token, self._identity_inflight
            if not token:
                return False
            # No service raw data reaches normal logs/capture/register caches.
            if phase and raw[0] == SLAVE:
                if raw[1] in (0x83, 0x90):
                    self._identity_inflight = None
                    self.identity_event.emit(token, "error", None)
                elif phase == "read" and raw[1] == 0x03 and len(raw) != 8:
                    self._identity_inflight = None
                    self.identity_event.emit(token, "read", bytes(raw))
                elif phase == "write_block" and raw[1] == 0x10 and len(raw) == 8:
                    self._identity_inflight = None
                    self.identity_event.emit(token, "ack", bytes(raw))
            return True
