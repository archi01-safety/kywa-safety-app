"""KYWA-only, backed-up, atomic column migration. Other institutions are rejected."""
import argparse
from datetime import datetime
import json
import uuid
from .config import ROOT
from .repository import SheetsRepository, google_client, cells, quoted
from .sheet_schema import SheetSchemaError
from .domain import HEADERS, digest
from .compact_storage import TAB, HEAD, VISIBLE, compact, clean, padded, packed, META_COLUMNS


def migrate(settings, apply=False):
    from .compact_storage import PREVIOUS, metadata
    from .sheet_format import canonical, fingerprint, date_serial, format_requests
    if settings.organization.id!='kywa': raise ValueError('KYWA에서만 실행할 수 있습니다.')
    repo=SheetsRepository(settings); svc=google_client(settings,'sheets','v4').spreadsheets()
    sid=settings.spreadsheet_id; rows=repo._rows(); header=rows[0]
    if header==VISIBLE:
        return {'already_applied':True,'records':len(repo.records())}
    if header not in (HEADERS+['제출자 성명'],PREVIOUS):
        raise SheetSchemaError('기존 KYWA 헤더가 예상과 다릅니다. 자동 변경하지 않습니다.')
    if any(any(str(v).strip() for v in row[len(header):]) for row in rows):
        raise SheetSchemaError('예상 열 밖에 값이 있어 중단합니다.')
    records=repo._decoded(rows); before_events=repo.events()
    result={'records':len(records),'events':len(before_events),'removed':['평가ID','평가기준버전','처리상태','수정버전','시스템데이터'],'applied':False}
    if not apply: return result
    snapshot=svc.get(spreadsheetId=sid,includeGridData=True).execute()
    props={s['properties']['title']:s['properties'] for s in snapshot['sheets']}
    if header!=PREVIOUS and TAB in props: raise SheetSchemaError('기존 숨김 관리 탭이 있어 자동 덮어쓰지 않습니다.')
    previous_entries=metadata(repo) if header==PREVIOUS else {}
    if any(k[0]=='request' and v[1].get('state')!='committed' for k,v in previous_entries.items()):
        raise SheetSchemaError('미확정 제출 요청을 먼저 복구한 뒤 이관하세요.')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    folder=ROOT/'local-data/migration-backups'; folder.mkdir(parents=True,exist_ok=True)
    backup=folder/('kywa-compact-'+stamp+'.json')
    backup.write_text(json.dumps({'spreadsheet_id':sid,'snapshot':snapshot,'values':rows,'events':before_events},ensure_ascii=False),encoding='utf-8')
    old_id=props[settings.sheet_name]['sheetId']; new_id=max(p['sheetId'] for p in props.values())+1
    backup_title='_백업_KYWA_'+stamp
    svc.batchUpdate(spreadsheetId=sid,body={'requests':[{'duplicateSheet':{'sourceSheetId':old_id,'newSheetId':new_id,'newSheetName':backup_title}},
        {'updateSheetProperties':{'properties':{'sheetId':new_id,'hidden':True},'fields':'hidden'}}]}).execute()
    fresh=repo._rows()
    if fresh[:len(rows)]!=rows or repo.events()!=before_events:
        raise SheetSchemaError('백업 중 기존 값이 바뀌었습니다. 이관을 중단합니다.')
    rows=fresh; records=repo._decoded(rows)
    latest=folder/('kywa-compact-'+stamp+'-latest-values.json')
    latest.write_text(json.dumps({'values':rows,'events':before_events},ensure_ascii=False),encoding='utf-8')
    name_col=23 if len(header)==24 else 19
    converted=[canonical(row[:18]+[row[name_col] if len(row)>name_col else '']) for row in rows[1:]]
    hidden=[cells(HEAD)]
    for record in records:
        index=record['_sheet_row']
        value={'row':index,'hash':fingerprint(converted[index-1]),'record':clean(record)}
        hidden.append(cells(packed('record',record['id'],value)))
    for (kind,key),(_,value) in previous_entries.items():
        if kind=='request':
            value={**value,'rows':[canonical(r[:18]+[r[19]]) for r in value['rows']]}
            hidden.append(cells(packed(kind,key,value)))
    managed_id=props[TAB]['sheetId'] if TAB in props else new_id+1
    requests=[]
    if TAB not in props:
        requests.append({'addSheet':{'properties':{'sheetId':managed_id,'title':TAB,'hidden':True,'gridProperties':{'rowCount':max(1000,len(hidden)+100),'columnCount':META_COLUMNS}}}})
    else:
        requests.append({'updateCells':{'range':{'sheetId':managed_id},'fields':'userEnteredValue'}})
    requests += [
        {'updateCells':{'start':{'sheetId':managed_id,'rowIndex':0,'columnIndex':0},'rows':hidden,'fields':'userEnteredValue'}},
        {'deleteDimension':{'range':{'sheetId':old_id,'dimension':'COLUMNS','startIndex':18,'endIndex':23 if len(header)==24 else 19}}},
        {'updateSpreadsheetProperties':{'properties':{'timeZone':'Asia/Seoul','locale':'ko_KR'},'fields':'timeZone,locale'}}]
    if converted:
        requests.append({'updateCells':{'start':{'sheetId':old_id,'rowIndex':1,'columnIndex':0},'rows':[cells([r[0]]) for r in converted],'fields':'userEnteredValue'}})
    requests.extend(format_requests(svc,sid,settings.sheet_name,1,len(rows),19))
    svc.batchUpdate(spreadsheetId=sid,body={'requests':requests}).execute()
    after_rows=repo._rows(); after=repo.records()
    if after_rows[0]!=VISIBLE or [canonical(r) for r in after_rows[1:len(rows)]]!=converted:
        raise SheetSchemaError('이관 후 평가 값 대조가 다릅니다. 백업을 확인하세요.')
    expected={r['id']:clean(r) for r in records}; actual={r['id']:clean(r) for r in after}
    if any(actual.get(k)!=v for k,v in expected.items()) or repo.events()!=before_events:
        raise SheetSchemaError('평가·조치 연결 대조가 일치하지 않습니다. 백업을 확인하세요.')
    return {**result,'records':len(records),'applied':True,'backup':str(backup),'cloud_backup':backup_title}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--spreadsheet-id',required=True,help='Explicit target ID: use a verified copy first.')
    parser.add_argument('--sheet-name',default='설문지 응답 시트1')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    from .config import Settings
    settings=Settings(organization_id='kywa',spreadsheet_id=args.spreadsheet_id,sheet_name=args.sheet_name)
    print(json.dumps(migrate(settings,args.apply),ensure_ascii=False,indent=2))
