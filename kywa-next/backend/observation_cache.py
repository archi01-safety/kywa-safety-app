"""Process-local, bounded observation reuse. Keys include the owner and rule versions."""
import copy
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future


class ObservationCache:
    def __init__(self, size=64, ttl=1800):
        self.size, self.ttl = size, ttl
        self.entries = OrderedDict()
        self.pending = {}
        self.lock = threading.RLock()

    def resolve(self, key, generate):
        with self.lock:
            entry = self.entries.get(key)
            if entry and time.monotonic()-entry[0] < self.ttl:
                self.entries.move_to_end(key)
                return copy.deepcopy(entry[1])
            pending=self.pending.get(key)
            creator=pending is None
            if creator:pending=self.pending[key]=Future()
        if not creator:return copy.deepcopy(pending.result(timeout=210))
        try:
            value=generate()
            with self.lock:
                self.entries[key]=(time.monotonic(),copy.deepcopy(value))
                while len(self.entries)>self.size:self.entries.popitem(last=False)
                pending.set_result(copy.deepcopy(value))
            return value
        except BaseException as error:
            pending.set_exception(error)
            raise
        finally:
            with self.lock:
                if self.pending.get(key) is pending:del self.pending[key]
