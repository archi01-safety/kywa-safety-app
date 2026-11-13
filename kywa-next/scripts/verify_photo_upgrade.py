"""Explicit real-Google verification in disposable copies; never mutate the original."""
import argparse
import copy
import io
import json
import sys
import time
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.config import Settings
from backend.repository import SheetsRepository,DriveStore,google_client
from backend.sheet_sync import GoogleRows
from backend.migrate_photos import migrate
from backend.persistent_pin import PersistentPinAuth,SheetsPinSessions
from backend.pin_auth import make_pin_hash
from backend.main import create_app
from backend.domain import digest
from backend.rollback_photo_schema import rollback


def verify(identity,credentials,verification_folder=''):
    from fastapi.testclient import TestClient
    from PIL import Image
    cfg=Settings(_env_file=None,organization_id=identity,google_service_account_json=credentials)
    cfg.validate_google_identity();org=cfg.organization
    cfg.spreadsheet_id=org.storage.spreadsheet_id;cfg.drive_folder_id=org.storage.drive_folder_id;cfg.sheet_name=org.storage.sheet_name
    original_repo=SheetsRepository(cfg)
    source=GoogleRows(original_repo);before=source.snapshot()[:3]
    files=google_client(cfg,'drive','v3').files()
    parents=[verification_folder] if verification_folder else files.get(fileId=cfg.spreadsheet_id,fields='parents',supportsAllDrives=True).execute().get('parents',[])
    if not parents:raise ValueError('원본의 상위 폴더에 접근할 수 없습니다. 기존 비공개 검증 폴더를 --verification-folder로 지정하세요.')
    permissions=google_client(cfg,'drive','v3').permissions().list(fileId=parents[0],supportsAllDrives=True,fields='permissions(type)').execute().get('permissions',[])
    if any(p['type']=='anyone' for p in permissions):raise ValueError('공개 폴더에 업무 사본을 만들 수 없습니다.')
    copied=files.copy(fileId=cfg.spreadsheet_id,body={'name':f'복수사진 v1.1 검증용 사본 {identity} {uuid.uuid4().hex[:8]}','parents':parents},supportsAllDrives=True,fields='id').execute()['id']
    folder=ROOT/'local-data'/'v11-google'/identity;folder.mkdir(parents=True,exist_ok=True)
    (folder/'copy.json').write_text(json.dumps({'id':copied,'original_id':cfg.spreadsheet_id}),encoding='utf-8')
    uploaded=[];result={'organization':identity,'ai':'synthetic','original_mutated':False,'passed':False}
    try:
        test=cfg.model_copy(update={'spreadsheet_id':copied,'demo_data_path':str(folder/'demo.json')})
        planned=migrate(test)
        applied=migrate(test,True,str(folder/'backup'))
        assert migrate(test,True).get('already_applied')
        repo=SheetsRepository(test);baseline,issues=repo.snapshot()
        assert not issues,'사본의 기존 확인 필요 행을 먼저 정리해야 합니다.'
        existing={r['id']:copy.deepcopy(r) for r in baseline}
        # Use real Drive IO with deterministic test images, not model/network analysis.
        live_drive_cfg=test.model_copy(update={'app_env':'development'})
        class TrackedDrive(DriveStore):
            def put_photo(self,*args,**kwargs):
                item=super().put_photo(*args,**kwargs)
                if item['id'] and item['id'] not in uploaded:uploaded.append(item['id'])
                return item
        drive=TrackedDrive(live_drive_cfg)
        app=create_app(test,repo=repo,drive=drive)
        with TestClient(app,base_url=test.app_base_url) as c:
            bootstrap=c.get('/api/bootstrap').json();c.headers.update({'Origin':test.app_base_url,'X-CSRF-Token':bootstrap['csrf']})
            def picture(color):
                stream=io.BytesIO();Image.new('RGB',(400,240),color).save(stream,'WEBP')
                prepared=c.post('/api/photos/prepare',files={'photo':('content-webp.jpg',stream.getvalue(),'image/jpeg')});assert prepared.status_code==200,prepared.text
                protected=c.post('/api/photos/'+prepared.json()['id']+'/deidentify',json={});assert protected.status_code==200,protected.text
                return protected.json()['id']
            p1,p2=picture('blue'),picture('green')
            analyzed=c.post('/api/analyses',data={'facility':org.facilities[0],'department':org.departments[0] if org.departments else '',
                'description':'명시적 사본 시험: 통로 케이블 걸림','photo_ids':[p1,p2]})
            assert analyzed.status_code==200,analyzed.text
            body={'request_id':str(uuid.uuid4()),'draft_id':analyzed.json()['draft_id'],'submitter_name':'' if identity=='ayf' else '홍㉠㉢',
                'items':[{'index':0,'location':'v1.1 사본 전용 시험','scenario':'통로 케이블 걸림','solution':'배선 정리'}]}
            response=c.post('/api/assessments',json=body);assert response.status_code==200,response.text
            key=response.json()['ids'][0]
            assert c.post('/api/assessments',json=body).json()['replayed'] and len(uploaded)==2
            c.post('/api/auth/demo',data={'role':'admin'})
            bootstrap=c.get('/api/bootstrap').json();c.headers['X-CSRF-Token']=bootstrap['csrf']
            def current():
                r=c.get('/api/assessments');assert r.status_code==200,r.text
                return next(item for item in r.json()['items'] if item['id']==key)
            item=current();assert len(item['photo_urls'])==2
            assert all(c.get(url).status_code==200 for url in item['photo_urls'])
            plan={'request_id':str(uuid.uuid4()),'revision':item['revision'],'text':'배선을 정리할 예정','due_date':'2026-12-01'}
            response=c.post(f'/api/assessments/{key}/plan',json=plan);assert response.status_code==200,response.text
            assert c.post(f'/api/assessments/{key}/plan',json=plan).json()['replayed']
            item=current();assert item['status']=='조치예정'
            after=c.post(f'/api/assessments/{key}/reassess',data={'text':'배선을 정리하고 고정했습니다.','photo_id':picture('gray')});assert after.status_code==200,after.text
            action={'request_id':str(uuid.uuid4()),'draft_id':after.json()['draft_id'],'revision':after.json()['revision'],'p':1,'s':1,'complete':True}
            response=c.post(f'/api/assessments/{key}/actions',json=action);assert response.status_code==200,response.text
            assert c.post(f'/api/assessments/{key}/actions',json=action).json()['replayed']
            assert current()['status']=='완료' and len(uploaded)==3
            from backend.report_semantic import Photos,hwpx
            from backend.report_model import compose
            from backend.report_layout import build,pdf
            from backend.excel_kywa import create_excel
            from backend.services import AIService
            from pypdf import PdfReader
            from openpyxl import load_workbook
            saved=next(r for r in repo.records() if r['id']==key)
            photos=Photos([saved],drive);model=compose([saved],AIService(test),org=org)
            outputs={'pdf':pdf(build(model,[saved],photos)),'hwpx':hwpx(model,photos),'xlsx':create_excel([saved],photos,org)}
            assert len(PdfReader(io.BytesIO(outputs['pdf'])).pages)==2
            assert len(load_workbook(io.BytesIO(outputs['xlsx']))['위험성평가']._images)==3
            for extension,data in outputs.items():(folder/('three-photos.'+extension)).write_bytes(data)
        # A fresh authentication object reads the same hidden session after restart.
        encoded=make_pin_hash('2468');store=SheetsPinSessions(repo,encoded)
        auth=PersistentPinAuth(encoded,store);token=auth.login('2468')
        resumed=PersistentPinAuth(encoded,SheetsPinSessions(SheetsRepository(test),encoded))
        assert resumed.valid(token) and resumed.extend(token)
        resumed.revoke(token);assert not PersistentPinAuth(encoded,store).valid(token)
        # Delete one test row only, then prove an identical new submission appends safely.
        g=GoogleRows(repo);rows,ids,_,_=g.snapshot();index=ids[key]['row']
        g.batch([{'deleteDimension':{'range':{'sheetId':g.sheet_id,'dimension':'ROWS','startIndex':index,'endIndex':index+1}}}])
        with TestClient(app,base_url=test.app_base_url) as c:
            bootstrap=c.get('/api/bootstrap').json();c.headers.update({'Origin':test.app_base_url,'X-CSRF-Token':bootstrap['csrf']})
            d=c.post('/api/analyses',data={'facility':org.facilities[0],'department':org.departments[0] if org.departments else '',
                'description':'삭제 후 사본 시험'});assert d.status_code==200,d.text
            body.update(request_id=str(uuid.uuid4()),draft_id=d.json()['draft_id'])
            response=c.post('/api/assessments',json=body);assert response.status_code==200,response.text
        final,issues=repo.snapshot();assert not issues
        final_by_id={r['id']:r for r in final}
        assert key not in final_by_id and len(final)==len(existing)+1
        for key,value in existing.items():assert final_by_id[key]==value,'사본 내 기존 기록이 변경되었습니다.'
        # Downgrade only the schema/extensions, preserving records submitted later
        # than the registered baseline and all native row identities.
        rollback_plan=rollback(test)
        rolled=rollback(test,True,str(folder/'rollback-backup'))
        assert rolled['applied'] and rolled['columns']==planned['old_columns']
        after_downgrade,issues=SheetsRepository(test).snapshot();assert not issues
        assert {r['id'] for r in after_downgrade}==set(final_by_id)
        assert rollback(test).get('already_baseline')
        assert GoogleRows(original_repo).snapshot()[:3]==before,'외부 편집 여부를 포함한 원본 재대조가 다릅니다.'
        result.update(passed=True,existing_records=len(existing),columns=applied['new_columns'],photos=3,session_restart=True,
            idempotent=True,plan_without_ai=True,delete_then_append=True,three_photo_exports=True,downgrade_preserves_newer_records=True,source_hash=digest(before))
    finally:
        # Recoverable trash; existing files and original spreadsheet never deleted.
        for fid in uploaded:
            files.update(fileId=fid,body={'trashed':True},supportsAllDrives=True).execute()
        files.update(fileId=copied,body={'trashed':True},supportsAllDrives=True).execute()
        result['disposable_files_trashed']=True
        (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--organization',required=True,choices=['kywa','ayf','fowi','khidi','knps','knf','kohi','cayf']);p.add_argument('--credentials-file',required=True);p.add_argument('--verification-folder',default='')
    a=p.parse_args()
    # QA uses the shared service-account quota too; pace this runner, never app traffic.
    from googleapiclient.http import HttpRequest
    original_execute=HttpRequest.execute;last_call=0.
    def paced(request,*args,**kwargs):
        global last_call
        time.sleep(max(0,1.2-(time.monotonic()-last_call)));last_call=time.monotonic()
        return original_execute(request,*args,**kwargs)
    HttpRequest.execute=paced
    print(json.dumps(verify(a.organization,Path(a.credentials_file).read_text(encoding='utf-8-sig'),a.verification_folder),ensure_ascii=False))
