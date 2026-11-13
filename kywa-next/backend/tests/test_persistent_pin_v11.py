import copy
import hashlib
from types import SimpleNamespace
import pytest
from backend.pin_auth import make_pin_hash,SESSION_SECONDS
from backend.persistent_pin import PersistentPinAuth,SheetsPinSessions


class Store:
    def __init__(self):self.items={};self.reads=0;self.writes=0
    def get(self,token):self.reads+=1;return copy.deepcopy(self.items.get(token))
    def put(self,token,expiry,revoked=False):self.writes+=1;self.items[token]={'expires_at':expiry,'revoked':revoked}


def test_restart_preserves_remaining_time_and_repeated_reads_are_local():
    encoded=make_pin_hash('2468');store=Store();clock=[1000000.]
    first=PersistentPinAuth(encoded,store,lambda:clock[0]);token=first.login('2468')
    clock[0]+=600
    restarted=PersistentPinAuth(encoded,store,lambda:clock[0])
    assert restarted.valid(token) and restarted.remaining(token)==3000
    for _ in range(10):assert restarted.valid(token)
    assert store.reads==1 and store.writes==1
    assert restarted.extend(token) and restarted.remaining(token)==SESSION_SECONDS
    clock[0]+=3601
    again=PersistentPinAuth(encoded,store,lambda:clock[0]);assert not again.valid(token) and not again.extend(token)


def test_logout_revocation_survives_restart_and_missing_store_fails_closed():
    encoded=make_pin_hash('2468');store=Store()
    auth=PersistentPinAuth(encoded,store,lambda:1000000.)
    token=auth.login('2468');auth.revoke(token)
    assert not PersistentPinAuth(encoded,store,lambda:1000001.).valid(token)
    class Unavailable(Store):
        def get(self,token):raise TimeoutError()
    with pytest.raises(TimeoutError):PersistentPinAuth(encoded,Unavailable()).valid(token)


def test_sheet_session_keys_are_institution_and_pin_bound_hashes():
    a=SimpleNamespace(settings=SimpleNamespace(organization=SimpleNamespace(id='ayf')))
    b=SimpleNamespace(settings=SimpleNamespace(organization=SimpleNamespace(id='kywa')))
    key=SheetsPinSessions(a,'test-hash').key('raw-token')
    assert len(key)==64 and 'raw-token' not in key
    assert key!=SheetsPinSessions(b,'test-hash').key('raw-token')
    assert key!=SheetsPinSessions(a,'changed-hash').key('raw-token')
