"""Back up and remove only the explicitly labelled disposable AYF browser-test row."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.config import Settings
from backend.repository import google_client, quoted


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cleanup',action='store_true');args=parser.parse_args()
    secret=ROOT.parents[1]/'secret'
    keys=list(secret.glob('*.json'))
    if len(keys)!=1:raise SystemExit('서비스 계정 JSON 파일을 하나로 지정해야 합니다.')
    cfg=Settings(_env_file=None,organization_id='ayf',google_service_account_json=keys[0].read_text(encoding='utf-8-sig'))
    cfg.validate_google_identity();cfg.spreadsheet_id=cfg.organization.storage.spreadsheet_id;cfg.sheet_name=cfg.organization.storage.sheet_name
    api=google_client(cfg,'sheets','v4').spreadsheets()
    rows=api.values().get(spreadsheetId=cfg.spreadsheet_id,range=quoted(cfg.sheet_name),valueRenderOption='UNFORMATTED_VALUE').execute().get('values',[])
    marker='V11-20261113-A'
    found=[i for i,row in enumerate(rows[1:],1) if any(marker in str(v) for v in row)]
    if not found:
        print(json.dumps({'test_rows':0,'active_rows':len(rows)-1,'cleaned':False}));return
    if len(found)!=1:raise SystemExit('시험 표시가 여러 행에 있어 정리를 중단합니다.')
    index=found[0];before=rows[index]
    result={'test_rows':1,'active_rows':len(rows)-1,'cleaned':False}
    if args.cleanup:
        snapshot=api.get(spreadsheetId=cfg.spreadsheet_id,includeGridData=True).execute()
        folder=ROOT/'local-data'/'v11-live-baseline';folder.mkdir(parents=True,exist_ok=True)
        backup=folder/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-before-cleanup.json')
        backup.write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8')
        sheet=next(s for s in snapshot['sheets'] if s['properties']['title']==cfg.sheet_name)
        fresh=api.values().get(spreadsheetId=cfg.spreadsheet_id,range=quoted(cfg.sheet_name),valueRenderOption='UNFORMATTED_VALUE').execute().get('values',[])
        if fresh!=rows or marker not in str(fresh[index]):raise SystemExit('시트가 변경되어 정리를 중단합니다.')
        api.batchUpdate(spreadsheetId=cfg.spreadsheet_id,body={'requests':[{'deleteDimension':{'range':{'sheetId':sheet['properties']['sheetId'],'dimension':'ROWS','startIndex':index,'endIndex':index+1}}}]}).execute()
        after=api.values().get(spreadsheetId=cfg.spreadsheet_id,range=quoted(cfg.sheet_name),valueRenderOption='UNFORMATTED_VALUE').execute().get('values',[])
        if after!=rows[:index]+rows[index+1:]:raise SystemExit('정리 후 기존 행 대조가 다릅니다. 백업을 확인하세요.')
        result.update(cleaned=True,active_rows=len(after)-1,backup=str(backup),backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest())
        (folder/'cleanup-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
