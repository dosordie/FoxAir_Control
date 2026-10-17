"""Serialize account I/O across the existing poll, snapshot and command workers."""
from functools import wraps
import threading
from weakref import WeakValueDictionary


_locks = WeakValueDictionary()
_lock_guard = threading.Lock()


def account_io_lock(username):
    with _lock_guard:
        key = str(username).strip()
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


def serialized_cloud_io(function):
    @wraps(function)
    def serialized(self, *args, **kwargs):
        with account_io_lock(self.username):
            return function(self, *args, **kwargs)
    return serialized
