"""Cancellable targeted read, serialized by the existing WarmLink worker."""
from dataclasses import dataclass, field
import threading
import time


@dataclass
class CloudSnapshotRequest:
    cycle_id: int
    codes: tuple[str, ...]
    deadline: float
    username: str
    device_code: str
    cancelled: threading.Event = field(default_factory=threading.Event)
    purpose: str = "csv_logger"

    def expired(self):
        return self.cancelled.is_set() or time.monotonic() >= self.deadline
