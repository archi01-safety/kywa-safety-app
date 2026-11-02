import copy
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
from PIL import Image

from backend.config import Settings
from backend.domain import sheet_row
from backend.filenames import photo_filename, report_filename
from backend.photo_privacy import FaceBox, blur_heads, deidentify_photo, FaceDetection
from backend.repository import DriveStore, SheetsRepository, google_client
from backend.tests.test_system import context, login


def pattern():
    im=Image.new('RGB',(300,240))
    im.putdata([(255*(x%2),255*(y%2),255*((x+y)%2)) for y in range(240) for x in range(300)])
    return im


@pytest.mark.parametrize('bounds',[(300,250,650,850),(0,0,180,450),(880,600,1000,1000),(480,450,520,520)])
def test_oval_blur_changes_face_but_preserves_surroundings(bounds):
    x0,y0,x1,y1=bounds
    box=FaceBox(x_min=x0,y_min=y0,x_max=x1,y_max=y1)
    source=pattern();out=blur_heads(source.copy(),[box])
    cx=int((x0+x1)*source.width/2000);cy=int((y0+y1)*source.height/2000)
    assert out.getpixel((cx,cy))!=source.getpixel((cx,cy))
    # A distant point stays byte-for-byte unchanged before JPEG encoding.
    far=(299 if cx<150 else 0,239 if cy<120 else 0)
    assert out.getpixel(far)==source.getpixel(far)
    assert all(70<v<185 for v in out.getpixel((cx,cy)))


def test_multiple_faces_no_faces_and_invalid_detector_fail_closed():
    im=pattern();boxes=[FaceBox(x_min=80,y_min=100,x_max=300,y_max=600),FaceBox(x_min=650,y_min=200,x_max=900,y_max=900)]
    result=blur_heads(im.copy(),boxes)
    for p in [(57,84),(232,132)]:assert result.getpixel(p)!=im.getpixel(p)
    assert blur_heads(im.copy(),[]).tobytes()==im.tobytes()
    raw=io.BytesIO();im.save(raw,'JPEG')
    class AI:
        settings=SimpleNamespace(demo=False)
        def _generate(self,prompt,*args):
            assert '목, 어깨' in prompt
            return FaceDetection(faces=[])
    assert Image.open(io.BytesIO(deidentify_photo(AI(),raw.getvalue()))).size==im.size


@pytest.mark.parametrize('format',['pdf','xlsx','hwpx'])
def test_report_names_use_explicit_filter_and_korea_creation_date(format):
    assert report_filename('우주',format,'2026-11-02T15:01:00+00:00')==f'우주_위험성평가_20261103.{format}'
    assert report_filename('',format,'2026-11-02T14:59:00+00:00')==f'KYWA_위험성평가_20261102.{format}'
    assert photo_filename('우주','2026-11-02T00:46:55+00:00')=='우주_20261102_094655.jpg'
    assert photo_filename('우주','2026-11-02T09:46:55+09:00',True)=='우주_개선후_20261102_094655.jpg'


def test_drive_retry_keeps_name_time_link_and_distinguishes_identical_names(monkeypatch):
    items=[]
    class Files:
        def list(self,**kw):
            return SimpleNamespace(execute=lambda:{'files':[copy.deepcopy(i) for i in items if i['appProperties']['kywaOperation'] in kw['q']]})
        def create(self,**kw):
            i=copy.deepcopy(kw['body']);i.update(id=str(len(items)+1),webViewLink=f"https://drive.google.com/file/d/{len(items)+1}/view?usp=drivesdk")
            items.append(i);return SimpleNamespace(execute=lambda:copy.deepcopy(i))
    files=Files();monkeypatch.setattr('backend.repository.google_client',lambda *_:SimpleNamespace(files=lambda:files))
    cfg=Settings(_env_file=None,app_env='production',organization_id='kywa')
    store=DriveStore(cfg);at='2026-11-02T09:46:55+09:00'
    first=store.put_photo(b'jpeg','request-a','우주',at)
    assert store.put_photo(b'jpeg','request-a','우주','2026-11-03T10:00:00+09:00')==first
    second=store.put_photo(b'jpeg','request-b','우주',at)
    assert first['id']!=second['id'] and items[0]['name']==items[1]['name']=='우주_20261102_094655.jpg'
    assert first['created_at']==at and first['view_url'].endswith('?usp=drivesdk')


def test_google_clients_reused_per_thread_and_credentials_only_for_kywa(monkeypatch):
    built=[]
    monkeypatch.setattr('backend.repository.google_credentials',lambda _:object())
    def build(*args,**kw):
        value=object();built.append(value);return value
    monkeypatch.setattr('googleapiclient.discovery.build',build)
    cfg=SimpleNamespace(organization_id='kywa',google_service_account_json='cache-test-credential',google_delegate_email='')
    main=google_client(cfg,'sheets','v4');assert google_client(cfg,'sheets','v4') is main
    with ThreadPoolExecutor(max_workers=1) as pool:
        other=pool.submit(google_client,cfg,'sheets','v4').result()
        assert other is not main
        assert pool.submit(google_client,cfg,'sheets','v4').result() is other
    cfg.google_service_account_json='changed-credential';assert google_client(cfg,'sheets','v4') is not main
    cfg.organization_id='fowi';assert google_client(cfg,'sheets','v4') is not google_client(cfg,'sheets','v4')


def test_store_cache_is_request_scoped_and_fast_apply_skips_global_rows(monkeypatch):
    cfg=Settings(_env_file=None,organization_id='kywa');repo=SheetsRepository(cfg);repo._row_sync_enabled=True
    created=[]
    class Store:
        def __init__(self,repo):created.append(self)
        def append(self,records):return None
    monkeypatch.setattr('backend.sheet_sync.Store',Store)
    monkeypatch.setattr(repo,'_rows',lambda:pytest.fail('redundant entire sheet read'))
    with repo.operation():
        first=repo.sync_store();assert repo.sync_store() is first;repo.apply([{}],[])
    with repo.operation():assert repo.sync_store() is not first
    assert len(created)==2


def test_completed_job_filename_remains_fixed_after_midnight(context,monkeypatch):
    client,app,repo,cfg=context;login(client)
    monkeypatch.setattr('backend.report_jobs.now',lambda:'2026-11-02T23:59:59+09:00')
    job=client.post('/api/report-jobs',json={'format':'xlsx','facility':'우주'}).json()['id']
    for _ in range(150):
        if client.get('/api/report-jobs/'+job).json()['state']=='complete':break
        time.sleep(.02)
    path=f'/api/report-jobs/{job}/download'
    first=client.get(path);assert first.status_code==200
    assert '우주_위험성평가_20261102.xlsx' in unquote(first.headers['content-disposition'])
    monkeypatch.setattr('backend.report_jobs.now',lambda:'2026-11-03T00:01:00+09:00')
    assert client.post('/api/report-jobs',json={'format':'xlsx','facility':'우주'}).json()['id']==job
    assert client.get(path).headers['content-disposition']==first.headers['content-disposition']


def test_appended_photo_has_explicit_canonical_hyperlink():
    from backend.tests.test_sheet_sync import Rows, Store
    from backend.organization import load_organization
    from backend.tests.test_institutions import current_record
    import uuid
    org=load_organization('kywa');g=Rows();captured=[];batch=g.batch
    def capture(requests):
        captured.extend(copy.deepcopy(requests));return batch(requests)
    g.batch=capture
    r=current_record(org);r.update(operation_id=str(uuid.uuid4()),photo_id='file-id',photo_view_url='https://drive.google.com/file/d/file-id/view?usp=drivesdk')
    Store(SimpleNamespace(settings=SimpleNamespace(organization=org)),g).append([r])
    row=next(x['appendCells']['rows'][0] for x in captured if 'appendCells' in x)
    cell=row['values'][12]
    assert cell['userEnteredValue']['stringValue']==r['photo_view_url']
    assert cell['userEnteredFormat']['textFormat']['link']['uri']==r['photo_view_url']
    assert cell['userEnteredFormat']['textFormat']['fontFamily']=='Roboto'
