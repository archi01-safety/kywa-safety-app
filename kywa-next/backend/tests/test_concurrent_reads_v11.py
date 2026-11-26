import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from backend.repository import SheetsRepository
from backend.observation_cache import ObservationCache


def test_only_inflight_listing_is_shared_and_each_result_is_isolated():
    repo=SheetsRepository(SimpleNamespace())
    entered=threading.Event();release=threading.Event();calls=[]
    def fetch():
        calls.append(1);entered.set();assert release.wait(5)
        return ([{'id':'one','before':{'score':1}}],[])
    repo._listing_snapshot=fetch
    with ThreadPoolExecutor(max_workers=3) as pool:
        first=pool.submit(repo.listing_snapshot);assert entered.wait(5)
        others=[pool.submit(repo.listing_snapshot) for _ in range(2)]
        # The source remains gated while all callers join the same pending future.
        time.sleep(.05);assert len(calls)==1
        release.set();results=[future.result(5) for future in [first,*others]]
    results[0][0][0]['before']['score']=20
    assert all(result[0][0]['before']['score']==1 for result in results[1:])
    assert repo.listing_snapshot()[0][0]['before']['score']==1 and len(calls)==2


def test_same_observation_inputs_share_generation_but_not_mutable_results():
    cache=ObservationCache();entered=threading.Event();release=threading.Event();calls=[]
    def generate():
        calls.append(1);entered.set();assert release.wait(5)
        return [{'location':'same','consequence':'minor'}]
    with ThreadPoolExecutor(max_workers=3) as pool:
        a=pool.submit(cache.resolve,'institution-owner-version-image',generate);assert entered.wait(5)
        b=pool.submit(cache.resolve,'institution-owner-version-image',generate)
        time.sleep(.05);release.set();one,two=a.result(5),b.result(5)
    one[0]['consequence']='fatal'
    assert two[0]['consequence']=='minor' and len(calls)==1
    assert cache.resolve('institution-owner-version-image',generate)==two
    cache.resolve('different-owner-version-image',generate)
    assert len(calls)==2
