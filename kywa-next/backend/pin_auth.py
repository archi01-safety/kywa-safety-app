"""Server-only shared administrator PIN authentication for one app process."""
import hashlib
import hmac
import math
import re
import secrets
import threading
import time
from collections import OrderedDict, deque

ITERATIONS = 600_000
SESSION_SECONDS = 3600
LOCK_SECONDS = 900


def make_pin_hash(pin):
    if not isinstance(pin, str) or not re.fullmatch(r'[0-9]{4}', pin):
        raise ValueError('비밀번호는 숫자 4자리로 입력하세요.')
    salt = secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac('sha256', pin.encode('ascii'), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${value.hex()}'


def parse_pin_hash(value):
    try:
        scheme, rounds, salt, digest = value.split('$')
        if (scheme != 'pbkdf2_sha256' or rounds != str(ITERATIONS)
                or not re.fullmatch(r'[0-9a-f]{32}', salt)
                or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError()
        return bytes.fromhex(salt), bytes.fromhex(digest)
    except (ValueError, AttributeError):
        raise ValueError('ADMIN_PIN_HASH를 설정하세요. scripts/set_admin_pin.py로 생성할 수 있습니다.') from None


class PinLocked(Exception):
    def __init__(self, seconds):
        self.seconds = max(1, math.ceil(seconds))


class PinAuth:
    def __init__(self, encoded, clock=time.monotonic):
        self.salt, self.expected = parse_pin_hash(encoded)
        self.clock = clock
        self.lock = threading.Lock()
        self.failures = deque()
        self.blocked_until = 0
        self.sessions = OrderedDict()

    def login(self, pin):
        # Global, account-wide limit also covers fresh cookies and changing IPs.
        # A single lock serializes checks so parallel guesses cannot bypass it.
        with self.lock:
            now = self.clock()
            if now < self.blocked_until:
                raise PinLocked(self.blocked_until - now)
            while self.failures and now - self.failures[0] >= LOCK_SECONDS:
                self.failures.popleft()
            valid = bool(re.fullmatch(r'[0-9]{4}', pin))
            candidate = hashlib.pbkdf2_hmac('sha256', pin.encode('ascii'), self.salt, ITERATIONS) if valid else b''
            if not valid or not hmac.compare_digest(candidate, self.expected):
                self.failures.append(now)
                if len(self.failures) >= 5:
                    self.blocked_until = now + LOCK_SECONDS
                    self.failures.clear()
                    raise PinLocked(LOCK_SECONDS)
                return None
            self.failures.clear()
            self.sessions = OrderedDict((key, expiry) for key, expiry in self.sessions.items() if expiry > now)
            token = secrets.token_urlsafe(32)
            self.sessions[token] = now + SESSION_SECONDS
            while len(self.sessions) > 256:
                self.sessions.popitem(last=False)
            return token

    def valid(self, token):
        with self.lock:
            expiry = self.sessions.get(token, 0)
            if expiry <= self.clock():
                self.sessions.pop(token, None)
                return False
            return True

    def revoke(self, token):
        with self.lock:
            self.sessions.pop(token, None)
