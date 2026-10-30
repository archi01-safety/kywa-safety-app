"""Bounded in-memory, administrator-session-owned report jobs."""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from .domain import digest
from .report_model import VERSION, compose
from . import reports, report_layout
from .services import ServiceError

MIMES={'pdf':'application/pdf','hwpx':'application/hwp+zip',
       'xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}


class ReportJobs:
    def __init__(self,ai,drive,org,memory_lock):
        self.ai,self.drive,self.org,self.memory_lock=ai,drive,org,memory_lock
        self.jobs={}; self.cache={}; self.lock=threading.RLock()
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='report')

    def start(self,owner,records,format,filters):
        with self.lock:
            cutoff=time.monotonic()-1800
            self.jobs={k:v for k,v in self.jobs.items() if v['at']>cutoff and v.get('state')!='expired'}
            self.cache={k:v for k,v in self.cache.items() if v['at']>cutoff}
            key=digest([owner,VERSION,filters,records])
            for job_id,job in self.jobs.items():
                if job['owner']==owner and job['key']==key and job['format']==format and job['state']!='failed':
                    return job_id
            if sum(j['state'] in ('queued','running') for j in self.jobs.values())>=3:
                raise ServiceError('보고서 작업이 많습니다. 잠시 후 다시 시도해 주세요.')
            completed=sorted((j for j in self.jobs if self.jobs[j]['state'] in ('complete','failed')),key=lambda j:self.jobs[j]['at'])
            while len(self.jobs)>=6 and completed:
                self.jobs.pop(completed.pop(0))
            job_id=str(uuid.uuid4())
            self.jobs[job_id]=dict(owner=owner,key=key,format=format,state='queued',stage='보고서 생성 대기 중',at=time.monotonic())
            self.executor.submit(self._run,job_id,records)
            return job_id

    def get(self,owner,key):
        with self.lock:
            job=self.jobs.get(key)
            if not job or job['owner']!=owner or time.monotonic()-job['at']>1800:
                raise ServiceError('보고서 작업이 만료되었거나 서버가 재시작되었습니다. 다시 생성해 주세요.')
            return dict(job)

    def _run(self,job_id,records):
        job=self.jobs[job_id]
        def stage(value):
            with self.lock: job.update(state='running',stage=value)
        try:
            with self.memory_lock:
                if job['format']=='xlsx':
                    stage('상세 내역과 사진을 Excel에 배치 중')
                    output=reports.excel(records,self.drive,self.org)
                else:
                    cached=self.cache.get(job['key'])
                    if cached:
                        pages=cached['pages']
                    else:
                        model=compose(records,self.ai,stage)
                        stage('집계와 사진을 보고서 서식에 배치 중')
                        pages=report_layout.build(model,records,self.drive)
                        if len(self.cache)>=2: self.cache.pop(next(iter(self.cache)))
                        self.cache[job['key']]={'at':time.monotonic(),'pages':pages}
                    stage('편집 가능한 한글 문서 생성 중' if job['format']=='hwpx' else 'PDF 문서 생성 중')
                    output=report_layout.hwpx(pages) if job['format']=='hwpx' else report_layout.pdf(pages)
                with self.lock: job.update(state='complete',stage='보고서가 준비되었습니다',output=output)
        except Exception as exc:
            # Provider details and submitted content never become error messages/logs.
            message=str(exc) if isinstance(exc,ServiceError) else '보고서를 만들지 못했습니다. 다시 생성해 주세요.'
            with self.lock: job.update(state='failed',stage=message)
