"""Opt-in real Google workflow test, isolated in temporary tabs in each target sheet.

AI is synthetic. Uses the real API handlers, repository, Drive and report exporters.
Existing evaluation rows are never used as mutation targets.
"""
import argparse
import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from .check_connections import INSTITUTIONS, target_settings, inspect
from .domain import HISTORY_HEADERS
from .main import create_app
from .repository import SheetsRepository, DriveStore, google_client, quoted, cells
from .sheet_schema import Layout, expanded_header, base_keys, LABELS


def verify(cfg):
    from fastapi.testclient import TestClient
    from PIL import Image
    from openpyxl import load_workbook
    from pypdf import PdfReader
    readiness=inspect(cfg)
    if not readiness['sheet_can_edit'] or not readiness['drive_can_add']:
        raise ValueError('기관 저장소의 편집 권한이 없습니다.')
    org=cfg.organization
    sheets=google_client(cfg,'sheets','v4').spreadsheets()
    files=google_client(cfg,'drive','v3').files()
    token=uuid.uuid4().hex[:12]
    names=[f'흐름시험_{org.id}_{token}',f'이력시험_{org.id}_{token}']
    sheet_ids=[]
    photo_ids=set()
    result={'organization':org.id,'workflow_verified':False,'ai':'synthetic','isolation':'temporary Google tabs'}
    try:
        response=sheets.batchUpdate(spreadsheetId=cfg.spreadsheet_id,body={'requests':[
            {'addSheet':{'properties':{'title':name,'hidden':True}}} for name in names]}).execute()
        sheet_ids=[r['addSheet']['properties']['sheetId'] for r in response['replies']]
        real_header=sheets.values().get(spreadsheetId=cfg.spreadsheet_id,range=quoted(cfg.sheet_name)+'!1:1').execute().get('values',[])
        header=expanded_header(real_header,org)
        layout=Layout(header,org)
        sheets.batchUpdate(spreadsheetId=cfg.spreadsheet_id,body={'requests':[
            {'updateCells':{'start':{'sheetId':sid,'rowIndex':0,'columnIndex':0},'rows':[cells(h)],'fields':'userEnteredValue'}}
            for sid,h in zip(sheet_ids,[header,HISTORY_HEADERS])]}).execute()
        live=cfg.model_copy(update={'sheet_name':names[0],'history_sheet_name':names[1],'app_env':'production'})
        local=live.model_copy(update={'app_env':'demo','auth_mode':'google','app_base_url':'http://testserver','local_workspace':False})
        repo=SheetsRepository(live)
        class TrackedDrive(DriveStore):
            def put(self,data,key):
                fid=super().put(data,key)
                if fid: photo_ids.add(fid)
                return fid
        drive=TrackedDrive(live)
        app=create_app(local,repo=repo,drive=drive)
        raw={k:'' for k in base_keys(org)}
        raw.update(created_at='2026-10-29 12:00:00',facility=org.facilities[0],department=org.departments[0],
            location='연동시험 임시행',category=org.categories[0],scenario='시험용 내용',p=5,s=3,score=15,
            grade='보통',solution='시험',law='시험',photo='사진 없음',submitter_name='홍길동')
        def old_append():
            # Match the source Streamlit writer exactly: A1, USER_ENTERED, INSERT_ROWS, base columns only.
            google_client(live,'sheets','v4').spreadsheets().values().append(spreadsheetId=cfg.spreadsheet_id,
                range=quoted(names[0])+'!A1',valueInputOption='USER_ENTERED',insertDataOption='INSERT_ROWS',
                body={'values':[[raw[k] for k in base_keys(org)]]}).execute()
        old_append()
        original_first=sheets.values().get(spreadsheetId=cfg.spreadsheet_id,range=quoted(names[0])+'!2:2').execute()['values'][0]
        first_legacy_id=repo.records()[0]['id']
        with TestClient(app) as client:
            boot=client.get('/api/bootstrap').json()
            client.headers.update({'Origin':local.app_base_url,'X-CSRF-Token':boot['csrf']})
            image=io.BytesIO()
            Image.new('RGB',(80,80),(100,116,139)).save(image,format='JPEG')
            prepared=client.post('/api/photos/prepare',files={'photo':('test.jpg',image.getvalue(),'image/jpeg')})
            if prepared.status_code!=200: raise ValueError('사진 준비 시험 실패')
            draft=client.post('/api/analyses',data={'facility':org.facilities[0],'department':org.departments[0],
                'description':'연동시험용 난간 손상','photo_id':prepared.json()['id']})
            if draft.status_code!=200: raise ValueError('가상 분석 시험 실패')
            body=dict(request_id=str(uuid.uuid4()),draft_id=draft.json()['draft_id'],submitter_name='홍㉠㉢',
                items=[dict(index=0,location='연동시험',scenario='시험용 내용',solution='시험용 조치')])
            with ThreadPoolExecutor(max_workers=2) as pool:
                older=pool.submit(old_append)
                submitted=client.post('/api/assessments',json=body)
                older.result()
            if submitted.status_code!=200: raise ValueError('실제 Google 시험 제출 실패')
            replay=client.post('/api/assessments',json=body)
            if not replay.json().get('replayed') or len(repo.records())!=3: raise ValueError('중복 재시도 또는 동시 제출 시험 실패')
            client.post('/api/auth/demo',data={'role':'admin'})
            listing=client.get('/api/assessments')
            if listing.status_code!=200 or '홍길동' in listing.text: raise ValueError('조회 또는 성명 변환 시험 실패')
            current=next(r for r in listing.json()['items'] if r['id'] in submitted.json()['ids'])
            photo=client.get(current['photo_url'])
            if photo.status_code!=200: raise ValueError('기관 권한에 따른 사진 재조회 실패')
            old=next(r for r in listing.json()['items'] if r['id']==first_legacy_id)
            after=client.post('/api/assessments/'+old['id']+'/reassess',data={'text':'시험용 보수'})
            if after.status_code!=200: raise ValueError('기존 행 재평가 시험 실패')
            payload=dict(request_id=str(uuid.uuid4()),draft_id=after.json()['draft_id'],revision=after.json()['revision'],p=1,s=1)
            saved=client.post('/api/assessments/'+old['id']+'/actions',json=payload)
            if saved.status_code!=200 or saved.json()['item']['after']['policy']!=org.policy.version:
                raise ValueError('기존 행 관리 셀 저장 시험 실패')
            values=sheets.values().get(spreadsheetId=cfg.spreadsheet_id,range=quoted(names[0])).execute()['values']
            old_actual=next(row for row in values[1:] if layout.value(row,'id')==old['id'])
            if any(layout.value(old_actual,k)!=layout.value(original_first,k) for k in base_keys(org)):
                raise ValueError('기존 값 보존 확인 실패')
            for extension in ('xlsx','pdf'):
                exported=client.post('/api/reports',json={'format':extension})
                if exported.status_code!=200: raise ValueError('보고서 출력 시험 실패')
                if extension=='xlsx':
                    ws=load_workbook(io.BytesIO(exported.content)).active
                    text=' '.join(str(cell.value) for row in ws for cell in row)
                else: text=''.join(page.extract_text() for page in PdfReader(io.BytesIO(exported.content)).pages)
                if '홍길동' in text or '홍㉠㉢' not in text: raise ValueError('보고서 성명 시험 실패')
            result.update(workflow_verified=True,concurrent_append_verified=True,idempotency_verified=True,
                legacy_action_verified=True,photo_verified=True,reports_verified=True,masked_name_verified=True)
    finally:
        cleanup=[]
        for fid in photo_ids:
            try: files.update(fileId=fid,body={'trashed':True},supportsAllDrives=True).execute()
            except Exception: cleanup.append('Drive 시험 사진 '+fid)
        if sheet_ids:
            try: sheets.batchUpdate(spreadsheetId=cfg.spreadsheet_id,
                body={'requests':[{'deleteSheet':{'sheetId':sid}} for sid in sheet_ids]}).execute()
            except Exception: cleanup.extend(names)
        result.update(cleanup_complete=not cleanup,cleanup_needed=cleanup)
        if cleanup: print(json.dumps({'organization':org.id,'cleanup_needed':cleanup},ensure_ascii=False))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--organization',choices=INSTITUTIONS,required=True)
    parser.add_argument('--run',action='store_true',required=True,help='실제 Google 임시 탭·사진을 생성하고 검증 후 정리')
    args=parser.parse_args()
    try: print(json.dumps(verify(target_settings(args.organization)),ensure_ascii=False,indent=2))
    except ValueError as exc: raise SystemExit(str(exc)) from None
    except Exception: raise SystemExit('Google 흐름 검증 실패. 시험 항목 정리 상태를 확인하세요.') from None


if __name__=='__main__': main()
