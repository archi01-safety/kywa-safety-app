"""Read-only live integration diagnostics, without credentials or evaluation data."""
import time
from concurrent.futures import ThreadPoolExecutor

from .domain import StrictModel
from .repository import google_client, quoted
from .visible_layout import VisibleLayout


class ConnectionReply(StrictModel):
    ok: bool


def google_check(cfg):
    sheets=google_client(cfg,'sheets','v4').spreadsheets()
    files=google_client(cfg,'drive','v3').files()
    metadata=sheets.get(spreadsheetId=cfg.spreadsheet_id,fields='sheets(properties(title))').execute()
    titles={tab['properties']['title'] for tab in metadata['sheets']}
    if not {cfg.sheet_name,cfg.history_sheet_name,'_시스템관리'} <= titles:
        raise ValueError('missing_storage_tabs')
    header=sheets.values().get(spreadsheetId=cfg.spreadsheet_id,range=quoted(cfg.sheet_name)+'!1:1').execute().get('values',[[]])[0]
    VisibleLayout(header,cfg.organization)
    sheet=files.get(fileId=cfg.spreadsheet_id,supportsAllDrives=True,fields='capabilities(canEdit)').execute()
    folder=files.get(fileId=cfg.drive_folder_id,supportsAllDrives=True,fields='mimeType,capabilities(canAddChildren)').execute()
    editable=sheet.get('capabilities',{}).get('canEdit',False)
    uploadable=folder.get('mimeType')=='application/vnd.google-apps.folder' and folder.get('capabilities',{}).get('canAddChildren',False)
    return {'ok':bool(editable and uploadable),'sheet_header_read':True,'sheet_edit_permission':editable,
        'drive_folder_read':True,'drive_upload_permission':bool(uploadable),'write_probe_performed':False}


def ai_check(cfg):
    from .services import AIService
    reply=AIService(cfg)._generate('연결 점검입니다. 지정된 JSON 스키마의 ok에 true를 반환하세요.',ConnectionReply,deterministic=True)
    return {'ok':reply.ok,'minimal_live_request':True}


def kosha_check(cfg):
    from .services import kosha_search
    reply=kosha_search(cfg,'사다리')
    return {'ok':isinstance(reply.get('items'),list) and not reply.get('demo',False),'live_search':True}


def law_check(cfg):
    from .law_links import LawLinks
    if not cfg.law_api_oc:
        return {'ok':False,'code':'missing_law_api_oc'}
    reply=LawLinks(cfg.law_api_oc,referer=cfg.app_base_url+cfg.app_base_path+'/').resolve_text('산업안전보건법 제37조(안전조치)')
    passed=any(item.get('verified') and '제38조' in item['label'] for item in reply['items'])
    return {'ok':passed,'official_article_verified':passed,'ax_referer_used':True,
        **({} if passed else {'code':'law_verification_unavailable','action':'AX 주소의 공동활용 승인과 API 통신을 확인하세요.'})}


def check_integrations(cfg):
    if cfg.demo or cfg.setup:
        raise ValueError('실연동 환경 설정이 필요합니다. 체험 모드 결과는 연동 검증이 아닙니다.')
    # Connectivity checks do not create runtime folders or validate server file permissions.
    validated=cfg.model_copy(update={'app_data_dir':'','app_upload_dir':'','app_log_dir':''})
    validated.validate_runtime()
    def run(name,func):
        started=time.monotonic()
        try: result=func(validated)
        except Exception:
            # Provider exception text can contain a URL with an API key or a response body.
            result={'ok':False,'code':name+'_connection_failed','action':'서버 설정·외부 통신·서비스 이용 권한을 확인하세요.'}
        return name,{**result,'elapsed_ms':round((time.monotonic()-started)*1000)}
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending=[executor.submit(run,name,func) for name,func in
                 (('google',google_check),('gemini',ai_check),('kosha',kosha_check),('law',law_check))]
        results=dict(future.result() for future in pending)
    return {'organization':validated.organization_id,'all_passed':all(r['ok'] for r in results.values()),
        'checks':results,'assessment_writes_performed':False,'filesystem_permissions_checked':False,
        'network_location':'the computer or server executing this command'}
