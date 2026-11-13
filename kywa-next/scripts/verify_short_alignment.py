"""Opt-in Google verification in disposable private copies; originals remain read-only."""
import argparse
import copy
import json
import sys
import time
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.config import Settings
from backend.repository import SheetsRepository,google_client
from backend.sheet_sync import GoogleRows
from backend.align_short_columns import align
from backend.column_alignment import SHORT_CANONICAL
from backend.tests.test_institutions import current_record


def verify(identity,credentials,folder):
    cfg=Settings(_env_file=None,organization_id=identity,google_service_account_json=credentials)
    cfg.validate_google_identity();org=cfg.organization
    cfg.spreadsheet_id=org.storage.spreadsheet_id;cfg.sheet_name=org.storage.sheet_name
    original=GoogleRows(SheetsRepository(cfg)).snapshot()
    drive=google_client(cfg,'drive','v3')
    permissions=drive.permissions().list(fileId=folder,supportsAllDrives=True,fields='permissions(type)').execute().get('permissions',[])
    if any(p['type']=='anyone' for p in permissions):raise ValueError('업무 사본을 공개 폴더에 저장하지 않습니다.')
    copied=drive.files().copy(fileId=cfg.spreadsheet_id,body={'name':f'가운데 정렬 검증 사본 {identity} {uuid.uuid4().hex[:8]}','parents':[folder]},supportsAllDrives=True,fields='id').execute()['id']
    output=ROOT/'local-data'/'alignment-copies'/identity;output.mkdir(parents=True,exist_ok=True)
    result={'organization':identity,'passed':False}
    try:
        test=cfg.model_copy(update={'spreadsheet_id':copied})
        repo=SheetsRepository(test);initial=GoogleRows(repo);before=initial.snapshot()
        applied=align(test,True,str(output/'backup'))
        after=GoogleRows(repo).snapshot()
        assert before[:3]==after[:3]
        for row in range(1,len(before[0])):
            for col,old in enumerate(before[3][row]):
                expected=copy.deepcopy(old)
                if col in SHORT_CANONICAL and initial.layout.positions[col] is not None:
                    expected['horizontalAlignment']='CENTER'
                assert after[3][row][col]==expected,(identity,row,col)
        record=current_record(org)
        record.update(operation_id=str(uuid.uuid4()),submit_owner='alignment-copy-test',submit_hash='alignment-copy-test')
        record['before']['location']='가운데 정렬 사본 전용 시험'
        repo.apply([record],[])
        gateway=GoogleRows(repo);values,ids,_,formats=gateway.snapshot()
        row=ids[record['id']]['row']
        for col,physical in enumerate(gateway.layout.positions):
            if physical is not None:
                assert formats[row][col].get('horizontalAlignment','LEFT')==('CENTER' if col in SHORT_CANONICAL else 'LEFT'),(identity,col,'short' if col in SHORT_CANONICAL else 'narrative')
        assert GoogleRows(SheetsRepository(cfg)).snapshot()==original
        result.update(passed=True,existing_values_ids_preserved=True,other_formats_preserved=True,
            appended_row_centered=True,original_unchanged=True,records=applied['records'])
    finally:
        drive.files().update(fileId=copied,body={'trashed':True},supportsAllDrives=True).execute()
        result['copy_trashed_recoverably']=True
        (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--organization',required=True)
    p.add_argument('--credentials-file',required=True);p.add_argument('--verification-folder',required=True);a=p.parse_args()
    from googleapiclient.http import HttpRequest
    execute=HttpRequest.execute;last=0.
    def paced(request,*args,**kwargs):
        global last
        time.sleep(max(0,1.2-(time.monotonic()-last)));last=time.monotonic()
        return execute(request,*args,**kwargs)
    HttpRequest.execute=paced
    print(json.dumps(verify(a.organization,Path(a.credentials_file).read_text(encoding='utf-8-sig'),a.verification_folder),ensure_ascii=False))
