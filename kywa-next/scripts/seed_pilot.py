"""Create a private synthetic KYWA fixture. Never copy an operational sheet."""
import argparse
import json
import os
import secrets
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.compact_storage import HEAD, TAB, VISIBLE, packed, visible
from backend.config import Settings
from backend.domain import HISTORY_HEADERS
from backend.repository import google_client
from backend.sheet_sync import CONFIG, KEY, fingerprint


def fixture(org):
    for n in range(150):
        rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f'kywa:pilot:synthetic:{n}'))
        risk = org.policy.risk(1 + n % 5, 1 + n % 4)
        date = f'2026-{5 + n % 3:02d}-{1 + n % 27:02d}T09:00:00+09:00'
        yield dict(id=rid, organization_id='kywa', created_at=date,
                   facility=org.facilities[n % len(org.facilities)],
                   department=org.departments[n % len(org.departments)], submitter_name='',
                   policy=org.policy.version, policy_snapshot=org.policy.model_dump(),
                   before=dict(location=f'시험구역 {n+1}', category=org.categories[n % len(org.categories)],
                               scenario='합성 자료: 바닥 단차', solution='단차 정비', law='시험 자료', **risk),
                   after=dict(text='시험 조치', created_at=date, actor='시험', **org.policy.risk(1, 1)) if n % 3 else None,
                   photo_id='', revision=1, status=['접수', '조치 중', '완료'][n % 3])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--parent', required=True)
    p.add_argument('--state', required=True, type=Path)
    a = p.parse_args()
    cfg = Settings(_env_file=None, google_service_account_json=os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
    drive = google_client(cfg, 'drive', 'v3')
    sheets = google_client(cfg, 'sheets', 'v4').spreadsheets()
    state = json.loads(a.state.read_text()) if a.state.exists() else {}
    def save():
        a.state.write_text(json.dumps(state, indent=2), encoding='utf-8')
    def create(key, name, mime, parent):
        if key not in state:
            state[key] = drive.files().create(body=dict(name=name, mimeType=mime, parents=[parent],
                    appProperties={'kywa_fixture':'vercel-pilot-v1'}), supportsAllDrives=True, fields='id').execute()['id']
            save()
        existing=drive.files().get(fileId=state[key],supportsAllDrives=True,fields='appProperties,parents').execute()
        if existing.get('appProperties',{}).get('kywa_fixture')!='vercel-pilot-v1' or parent not in existing.get('parents',[]):
            raise RuntimeError('시험 저장소 식별 불일치')
        return state[key]
    folder=create('folder','KYWA Vercel 합성 시험','application/vnd.google-apps.folder',a.parent)
    if any(p['type']=='anyone' for p in drive.permissions().list(fileId=folder,supportsAllDrives=True,fields='permissions(type)').execute()['permissions']):
        raise RuntimeError('비공개 시험 폴더가 필요합니다')
    sid=create('sheet','KYWA 합성 평가 150건','application/vnd.google-apps.spreadsheet',folder)
    if 'session_secret' not in state:
        state['session_secret']=secrets.token_urlsafe(48)
        save()
    doc=sheets.get(spreadsheetId=sid,fields='sheets.properties').execute()
    props=doc['sheets'][0]['properties']
    if props['title']==cfg.sheet_name and len(doc['sheets'])==3:
        print('Existing pilot fixture retained')
        return
    if len(doc['sheets'])!=1 or sheets.values().get(spreadsheetId=sid,range=props['title']).execute().get('values'):
        raise RuntimeError('시험 시트가 비어 있지 않습니다')
    sheet_id=props['sheetId']
    hist_id=max(1,sheet_id+1)
    meta_id=hist_id+1
    records=list(fixture(cfg.organization))
    rows=[VISIBLE]; meta=[HEAD,packed(*CONFIG,dict(version=2,formats=[{}]*19))]
    req=[{'updateSpreadsheetProperties':{'properties':{'timeZone':'Asia/Seoul','locale':'ko_KR'},'fields':'timeZone,locale'}},
         {'updateSheetProperties':{'properties':{'sheetId':sheet_id,'title':cfg.sheet_name},'fields':'title'}},
         {'addSheet':{'properties':{'sheetId':hist_id,'title':cfg.history_sheet_name}}},
         {'addSheet':{'properties':{'sheetId':meta_id,'title':TAB,'hidden':True,'gridProperties':{'columnCount':64}}}}]
    for i,record in enumerate(records,1):
        row=visible(record);rows.append(row)
        meta.append(packed('record',record['id'],dict(record=record,source_values=row,row=i,hash=fingerprint(row))))
        req.append({'createDeveloperMetadata':{'developerMetadata':{'metadataKey':KEY,'metadataValue':record['id'],
              'visibility':'DOCUMENT','location':{'dimensionRange':{'sheetId':sheet_id,'dimension':'ROWS','startIndex':i,'endIndex':i+1}}}}})
    from backend.repository import cells
    for dest,data in [(sheet_id,rows),(meta_id,meta),(hist_id,[HISTORY_HEADERS])]:
        req.append({'updateCells':{'start':{'sheetId':dest,'rowIndex':0,'columnIndex':0},'rows':[cells(row) for row in data],'fields':'userEnteredValue'}})
    sheets.batchUpdate(spreadsheetId=sid,body={'requests':req}).execute()
    print('Created synthetic fixture: 150 rows, 19 columns, history and hidden management tabs')

if __name__=='__main__':
    main()
