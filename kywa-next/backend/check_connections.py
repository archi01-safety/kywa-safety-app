"""Explicit Google verification. No secrets or assessment contents in diagnostics."""
import argparse
import io
import json
import uuid

from .config import Settings
from .domain import HISTORY_HEADERS
from .repository import google_client, quoted, cells
from .sheet_schema import Layout, expanded_header

INSTITUTIONS = ('kywa','fowi','knps','knf','kohi','khidi','cayf')


def header_edit_allowed(sheet, start_column, end_column):
    if start_column >= end_column: return True
    for protection in sheet.get('protectedRanges',[]):
        if protection.get('warningOnly') or protection.get('requestingUserCanEdit'): continue
        area=protection.get('range',{})
        if (area.get('startRowIndex',0)==0 and area.get('endRowIndex',1)>0 and
            area.get('startColumnIndex',0)<end_column and area.get('endColumnIndex',end_column)>start_column):
            return False
    return True


def target_settings(identity=None):
    settings = Settings(**({'organization_id':identity} if identity else {}))
    storage = settings.organization.storage
    # An explicit institution selects its checked-in destination, never another service's env IDs.
    if identity or not settings.spreadsheet_id: settings.spreadsheet_id = storage.spreadsheet_id
    if identity or not settings.drive_folder_id: settings.drive_folder_id = storage.drive_folder_id
    if identity or 'sheet_name' not in settings.model_fields_set: settings.sheet_name = storage.sheet_name
    return settings


def verify_targets(settings):
    storage = settings.organization.storage
    if (not storage.spreadsheet_id or settings.spreadsheet_id != storage.spreadsheet_id or
        settings.drive_folder_id != storage.drive_folder_id or settings.sheet_name != storage.sheet_name or
        settings.sheet_name == settings.history_sheet_name):
        raise ValueError('기관 설정과 Google 저장 대상이 다릅니다.')


def inspect(settings):
    account = settings.validate_google_identity()
    verify_targets(settings)
    sheets = google_client(settings,'sheets','v4').spreadsheets()
    drive = google_client(settings,'drive','v3').files()
    meta = sheets.get(spreadsheetId=settings.spreadsheet_id,
        fields='sheets(properties,protectedRanges(range,warningOnly,requestingUserCanEdit))').execute()
    names = {s['properties']['title'] for s in meta['sheets']}
    if settings.sheet_name not in names: raise ValueError('지정된 기존 평가 탭이 없습니다.')
    rows = sheets.values().get(spreadsheetId=settings.spreadsheet_id,range=quoted(settings.sheet_name)).execute().get('values',[])
    header = expanded_header(rows, settings.organization)
    layout = Layout(header,settings.organization)
    # Parse all rows now, before any schema write. Do not include cell values in output.
    for index,row in enumerate(rows[1:],1):
        if any(str(v).strip() for v in row): layout.decode(row,index,settings.spreadsheet_id+':'+settings.sheet_name)
    history_ready = False
    if settings.history_sheet_name in names:
        history = sheets.values().get(spreadsheetId=settings.spreadsheet_id,range=quoted(settings.history_sheet_name)).execute().get('values',[])
        if history and history[0] != HISTORY_HEADERS: raise ValueError('기존 조치이력 탭의 헤더가 다릅니다.')
        history_ready = bool(history)
    sheet_file = drive.get(fileId=settings.spreadsheet_id,supportsAllDrives=True,fields='capabilities(canEdit)').execute()
    folder = drive.get(fileId=settings.drive_folder_id,supportsAllDrives=True,
                       fields='mimeType,capabilities(canAddChildren)').execute()
    if folder.get('mimeType') != 'application/vnd.google-apps.folder': raise ValueError('사진 저장 대상이 폴더가 아닙니다.')
    original_header = rows[0] if rows else []
    sheet=next(s for s in meta['sheets'] if s['properties']['title']==settings.sheet_name)
    return dict(organization=settings.organization_id, account=account, sheet_read=True,
        sheet_can_edit=sheet_file.get('capabilities',{}).get('canEdit',False),
        drive_read=True, drive_can_add=folder.get('capabilities',{}).get('canAddChildren',False),
        schema_ready=original_header==header and history_ready,
        header_edit_allowed=header_edit_allowed(sheet,len(original_header),len(header)),
        append_headers=header[len(original_header):], history_ready=history_ready,
        row_count=max(0,len(rows)-1), write_probe_verified=False)


def probe(settings):
    """Round-trip a temporary sheet tab and JPEG; remove only those objects created here."""
    result = inspect(settings)
    if not result['sheet_can_edit'] or not result['drive_can_add']:
        raise ValueError('Google에서 편집·사진 추가 권한이 확인되지 않았습니다.')
    from PIL import Image
    from googleapiclient.http import MediaIoBaseUpload
    sheets=google_client(settings,'sheets','v4').spreadsheets()
    files=google_client(settings,'drive','v3').files()
    token=uuid.uuid4().hex
    title='연동시험_'+settings.organization_id+'_'+token[:8]
    sheet_id=file_id=None
    result['cleanup_complete']=False
    try:
        reply=sheets.batchUpdate(spreadsheetId=settings.spreadsheet_id,body={'requests':[
            {'addSheet':{'properties':{'title':title,'hidden':True}}}]}).execute()
        sheet_id=reply['replies'][0]['addSheet']['properties']['sheetId']
        sheets.batchUpdate(spreadsheetId=settings.spreadsheet_id,body={'requests':[{'updateCells':{
            'start':{'sheetId':sheet_id,'rowIndex':0,'columnIndex':0},'rows':[cells([token])],
            'fields':'userEnteredValue'}}]}).execute()
        read=sheets.values().get(spreadsheetId=settings.spreadsheet_id,range=quoted(title)+'!A1').execute()
        if read.get('values') != [[token]]: raise ValueError('시험 셀의 재조회 값이 일치하지 않습니다.')
        data=io.BytesIO()
        Image.new('RGB',(16,16),(100,116,139)).save(data,format='JPEG')
        photo=data.getvalue()
        uploaded=files.create(body={'name':'connection-test_'+settings.organization_id+'_'+token+'.jpg',
            'parents':[settings.drive_folder_id],'appProperties':{'safetyOrganization':settings.organization_id,'kywaOperation':token}},
            media_body=MediaIoBaseUpload(io.BytesIO(photo),mimetype='image/jpeg'),fields='id',supportsAllDrives=True).execute()
        file_id=uploaded['id']
        downloaded=files.get_media(fileId=file_id,supportsAllDrives=True).execute()
        if downloaded != photo: raise ValueError('시험 사진의 재조회 값이 일치하지 않습니다.')
        result['write_probe_verified']=True
    finally:
        cleanup=[]
        if file_id:
            try: files.update(fileId=file_id,body={'trashed':True},supportsAllDrives=True).execute()
            except Exception: cleanup.append('Drive 시험 사진 '+file_id)
        if sheet_id is not None:
            try: sheets.batchUpdate(spreadsheetId=settings.spreadsheet_id,body={'requests':[{'deleteSheet':{'sheetId':sheet_id}}]}).execute()
            except Exception: cleanup.append('시험 탭 '+title)
        result['cleanup_complete']=not cleanup
        result['cleanup_needed']=cleanup
        if cleanup: print(json.dumps({'organization':settings.organization_id,'cleanup_needed':cleanup},ensure_ascii=False))
    return result


def main():
    parser=argparse.ArgumentParser(description='기관별 실제 Google 접근 검증. 기본은 읽기 전용.')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--organization',choices=INSTITUTIONS)
    group.add_argument('--all',action='store_true')
    parser.add_argument('--probe',action='store_true',help='시험용 탭·사진을 생성해 재조회 후 정리')
    args=parser.parse_args()
    failed=False
    for identity in INSTITUTIONS if args.all else [args.organization]:
        try:
            settings=target_settings(identity)
            result=probe(settings) if args.probe else inspect(settings)
        except ValueError as exc:
            result={'organization':identity,'verified':False,'error':str(exc)}
            failed=True
        except Exception as exc:
            result={'organization':identity,'verified':False,'error':'Google 연결 검증 실패',
                    'http_status':getattr(getattr(exc,'resp',None),'status',None)}
            failed=True
        print(json.dumps(result,ensure_ascii=False,indent=2))
    if failed: raise SystemExit(1)


if __name__=='__main__': main()
