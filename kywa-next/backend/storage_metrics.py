"""Content-free submission timings. Context is local to the current request thread."""
import json
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar

current = ContextVar('storage_metrics', default=None)
stage = ContextVar('storage_stage', default='storage')


@contextmanager
def phase(name):
    token = stage.set(name)
    try:
        yield
    finally:
        stage.reset(token)


@contextmanager
def submission_metrics(enabled=True):
    if not enabled:
        yield
        return
    value = {'calls': 0, 'api_ms': 0, 'phases': defaultdict(lambda: {'calls': 0, 'api_ms': 0})}
    token = current.set(value)
    start = time.monotonic()
    success = False
    try:
        yield
        success = True
    finally:
        current.reset(token)
        value.update(elapsed_ms=round((time.monotonic()-start)*1000), success=success)
        logging.getLogger('kywa').warning('storage_timing %s', json.dumps(value, sort_keys=True))


def request_builder(*args, **kwargs):
    from googleapiclient.http import HttpRequest
    class MeasuredRequest(HttpRequest):
        def execute(self, *a, **kw):
            start = time.monotonic()
            try:
                return super().execute(*a, **kw)
            finally:
                value = current.get()
                if value is not None:
                    elapsed = round((time.monotonic()-start)*1000)
                    value['calls'] += 1
                    value['api_ms'] += elapsed
                    group = value['phases'][stage.get()]
                    group['calls'] += 1
                    group['api_ms'] += elapsed
    return MeasuredRequest(*args, **kwargs)
