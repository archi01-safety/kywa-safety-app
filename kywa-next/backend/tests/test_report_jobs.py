import threading
import time
from types import SimpleNamespace
import pytest
from backend.report_jobs import ReportJobs
from backend.services import AIService, ServiceError
from backend.tests.test_institutions import settings, current_record


def finish(jobs,owner,key):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        result=jobs.get(owner,key)
        if result['state'] in ('complete','failed'):return result
        time.sleep(.01)
    pytest.fail('report job did not finish')


def test_report_cache_shared_by_formats_but_session_owned(monkeypatch):
    cfg=settings('kywa');calls=[]
    monkeypatch.setattr('backend.report_jobs.compose',lambda records,ai,stage:calls.append(1) or {'facts':{}})
    monkeypatch.setattr('backend.report_jobs.report_layout.build',lambda *args:['pages'])
    monkeypatch.setattr('backend.report_jobs.report_layout.pdf',lambda pages:b'pdf')
    monkeypatch.setattr('backend.report_jobs.report_layout.hwpx',lambda pages:b'hwpx')
    jobs=ReportJobs(AIService(cfg),SimpleNamespace(),cfg.organization,threading.Lock())
    try:
        records=[current_record(cfg.organization)]
        first=jobs.start('admin-a',records,'pdf',{})
        assert finish(jobs,'admin-a',first)['output']==b'pdf'
        with pytest.raises(ServiceError):jobs.get('admin-b',first)
        second=jobs.start('admin-a',records,'hwpx',{})
        assert finish(jobs,'admin-a',second)['output']==b'hwpx' and len(calls)==1
        third=jobs.start('admin-b',records,'pdf',{})
        finish(jobs,'admin-b',third)
        assert len(calls)==2
        jobs.jobs[first]['at']-=1801
        with pytest.raises(ServiceError):jobs.get('admin-a',first)
    finally:jobs.executor.shutdown(wait=True)


def test_failed_report_has_no_download_and_can_retry(monkeypatch):
    cfg=settings('kywa')
    def fail(*args):raise RuntimeError('private provider detail')
    monkeypatch.setattr('backend.report_jobs.compose',fail)
    jobs=ReportJobs(AIService(cfg),SimpleNamespace(),cfg.organization,threading.Lock())
    try:
        records=[current_record(cfg.organization)]
        key=jobs.start('admin',records,'pdf',{})
        result=finish(jobs,'admin',key)
        assert result['state']=='failed' and 'output' not in result
        assert 'private' not in result['stage']
        assert jobs.start('admin',records,'pdf',{})!=key
    finally:jobs.executor.shutdown(wait=True)
