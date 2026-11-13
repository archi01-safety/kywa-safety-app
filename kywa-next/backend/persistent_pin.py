"""One-hour PIN sessions survive free-host restarts; raw tokens stay in signed cookies."""
import hashlib
import threading
import time
from collections import OrderedDict
from .pin_auth import PinAuth,SESSION_SECONDS


class SheetsPinSessions:
    def __init__(self,repo,pin_hash):
        self.repo=repo
        self.namespace=repo.settings.organization.id+':'+hashlib.sha256(pin_hash.encode()).hexdigest()

    def key(self,token):return hashlib.sha256((self.namespace+':'+token).encode()).hexdigest()

    def get(self,token):
        from .compact_storage import metadata
        with self.repo.lock:
            entry=metadata(self.repo).get(('pin-session',self.key(token)))
            return entry[1] if entry else None

    def put(self,token,expiry,revoked=False):
        from .sheet_sync import GoogleRows
        with self.repo.lock:
            GoogleRows(self.repo).save([('pin-session',self.key(token),
                {'version':1,'expires_at':expiry,'revoked':revoked})])


class PersistentPinAuth(PinAuth):
    def __init__(self,encoded,store,clock=time.time):
        super().__init__(encoded,clock)
        self.store=store
        self.revoked=OrderedDict()
        self.operation_lock=threading.RLock()

    def login(self,pin):
        with self.operation_lock:
            token=super().login(pin)
            if not token:return None
            try:self.store.put(token,self.sessions[token])
            except BaseException:
                with self.lock:self.sessions.pop(token,None)
                raise
            return token

    def _expiry(self,token):
        if not token:return 0
        with self.lock:
            if token in self.revoked:return 0
            if token in self.sessions:return self.sessions[token]
        # Never hold the PIN lock while acquiring the repository lock.
        saved=self.store.get(token)
        expiry=saved.get('expires_at',0) if saved and not saved.get('revoked') else 0
        with self.lock:
            if token in self.revoked:return 0
            self.sessions.setdefault(token,expiry)
            while len(self.sessions)>256:self.sessions.popitem(last=False)
            return self.sessions[token]

    def valid(self,token):return self._expiry(token)>self.clock()

    def remaining(self,token):return max(0,self._expiry(token)-self.clock())

    def revoke(self,token):
        if not token:return
        with self.operation_lock:
            with self.lock:
                self.revoked[token]=True;self.sessions.pop(token,None)
                while len(self.revoked)>5000:self.revoked.popitem(last=False)
            self.store.put(token,0,revoked=True)

    def extend(self,token):
        with self.operation_lock:
            if not self.valid(token):return False
            expiry=self.clock()+SESSION_SECONDS
            self.store.put(token,expiry)
            with self.lock:
                if token in self.revoked:return False
                self.sessions[token]=expiry
            return True
