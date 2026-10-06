"""A cancellable one-shot request, serialized by the existing Cloud worker."""
from dataclasses import dataclass, field
import threading
import time


@dataclass
class CloudLoggerSnapshotRequest:
    cycle_id: int
    codes: tuple[str, ...]
    deadline: float
    username: str
    device_code: str
    cancelled: threading.Event = field(default_factory=threading.Event)

    def expired(self):
        return self.cancelled.is_set() or time.monotonic() >= self.deadline
