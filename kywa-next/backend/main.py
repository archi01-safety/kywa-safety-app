import base64
import copy
import hmac
import logging
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date
from urllib.parse import quote

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import Settings, ROOT
from .domain import (FACILITIES, DEPARTMENTS, CATEGORIES, POLICY, now, risk, digest,
                     SubmitRequest, ActionRequest, StateRequest, ReportRequest)
from .repository import DemoRepository, SheetsRepository, DriveStore, RepositoryError
from .services import Drafts, RateLimiter, AIService, ServiceError, prepare_image, kosha_search
from . import reports
from .pin_auth import PinAuth, PinLocked, SESSION_SECONDS
from .overview import summarize, guide_keywords

log = logging.getLogger('kywa')


class BodySizeLimit:
    """Enforce the limit on received bytes as well as the declared Content-Length."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        size = 0
        async def limited_receive():
            nonlocal size
            message = await receive()
            if message['type'] == 'http.request':
                size += len(message.get('body', b''))
                if size > 11 * 1024 * 1024:
                    raise HTTPException(413, '요청 크기가 11MB를 초과했습니다.')
            return message
        await self.app(scope, limited_receive if scope['type'] == 'http' else receive, send)


def create_app(settings=None, repo=None, drive=None, ai=None):
    cfg = settings or Settings()
    cfg.validate_runtime()
    repo = repo or (DemoRepository(cfg.demo_data_path) if cfg.demo else SheetsRepository(cfg))
    drive = drive or DriveStore(cfg)
    ai = ai or AIService(cfg)
    drafts, limits = Drafts(), RateLimiter()
    overview_cache, overview_lock = {}, threading.Lock()
    pin_auth = PinAuth(cfg.admin_pin_hash) if cfg.auth_mode == 'pin' else None
    expensive, memory_lock = threading.BoundedSemaphore(2), threading.BoundedSemaphore(1)
    app = FastAPI(title='KYWA Safety API', docs_url='/api/docs' if cfg.demo else None, redoc_url=None,
                  openapi_url='/api/openapi.json' if cfg.demo else None)
    app.state.repo, app.state.drafts, app.state.settings = repo, drafts, cfg
    app.state.pin_auth = pin_auth
    app.add_middleware(SessionMiddleware, secret_key=cfg.session_secret, session_cookie='kywa_session',
                       max_age=SESSION_SECONDS if pin_auth else 28800, same_site='lax', https_only=cfg.app_base_url.startswith('https://'))
    app.add_middleware(BodySizeLimit)
    oauth = OAuth()
    oauth.register(name='google', client_id=cfg.google_client_id, client_secret=cfg.google_client_secret,
                   server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                   client_kwargs={'scope': 'openid email profile', 'code_challenge_method': 'S256'})

    @app.middleware('http')
    async def security_headers(request, call_next):
        if cfg.local_workspace and (not request.client or request.client.host not in {'127.0.0.1', '::1'}):
            return JSONResponse({'detail': '로컬 시험 공간은 이 PC에서만 접근할 수 있습니다.'}, status_code=403)
        # Reject oversized multipart bodies before python-multipart can spool to disk.
        length = request.headers.get('content-length')
        if length and (not length.isdigit() or int(length) > 11 * 1024 * 1024):
            return JSONResponse({'detail': '요청 크기가 11MB를 초과했습니다.'}, status_code=413)
        if request.method == 'POST' and request.url.path == '/api/photos/prepare' and not length:
            return JSONResponse({'detail': 'Content-Length가 필요합니다.'}, status_code=411)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.url.path.startswith('/api/') or request.url.path == '/healthz':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.exception_handler(RepositoryError)
    async def repository_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        # Provider exceptions may include keys/URLs. Never echo them into HTML or logs.
        log.error('Request failed: %s %s (%s)', request.method, request.url.path, type(exc).__name__)
        return JSONResponse({'detail': '처리 결과를 확인하지 못했습니다. 입력은 유지됩니다. 같은 요청으로 재시도하세요.'}, status_code=503)

    def session(request):
        if 'owner' not in request.session:
            request.session['owner'] = secrets.token_urlsafe(24)
            request.session['csrf'] = secrets.token_urlsafe(24)
        return request.session['owner']

    def mutation(request):
        session(request)
        if request.headers.get('origin', '').rstrip('/') != cfg.app_base_url.rstrip('/'):
            raise HTTPException(403, '허용되지 않은 요청 출처입니다.')
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), request.session['csrf']):
            raise HTTPException(403, '세션을 새로고침한 뒤 다시 시도하세요.')

    def user(request, admin=False):
        if pin_auth:
            if not pin_auth.valid(request.session.get('pin_session', '')):
                raise HTTPException(401, '관리자 비밀번호를 입력하세요. 로그인은 1시간 동안 유지됩니다.')
            # Shared PIN does not establish ownership of a Google email address.
            return {'email': 'pin-admin', 'name': '전체 시설 관리자', 'role': 'admin', 'facilities': FACILITIES}
        email = request.session.get('email', '')
        if cfg.demo and email.startswith('demo-'):
            role = 'admin' if email == 'demo-admin@kywa.local' else 'staff'
            account = {'role': role, 'facilities': FACILITIES if role == 'admin' else ['중앙']}
        else:
            account = cfg.accounts.get(email)
        if not account or account.get('role') not in {'admin', 'staff'}:
            raise HTTPException(401, '승인된 담당자 또는 관리자 계정으로 로그인하세요.')
        if admin and account['role'] != 'admin':
            raise HTTPException(403, '관리자 권한이 필요합니다.')
        return {'email': email, 'name': request.session.get('name', email.split('@')[0]), **account}

    def can_view(account, record):
        return account['role'] == 'admin' or record['facility'] in account.get('facilities', [])

    def get_record(request, record_id):
        account = user(request)
        record = next((r for r in repo.records() if r['id'] == record_id), None)
        if not record or not can_view(account, record):
            raise HTTPException(404, '평가를 찾을 수 없거나 접근 권한이 없습니다.')
        return record, account

    def public_record(record):
        r = copy.deepcopy(record)
        for key in ('submit_hash', 'operation_id', 'submit_owner', 'legacy_values'):
            r.pop(key, None)
        b = r['before']
        try:
            r['current_risk'] = risk(b['p'], b['s'])
        except ValueError:
            r['current_risk'] = None
        for target in [r, r.get('after') or {}]:
            fid = target.get('photo_id')
            target['photo_url'] = f"/api/assessments/{r['id']}/photos/{fid}" if fid else ''
        return r

    def filtered(request, facility='', department='', status='', start='', end=''):
        account = user(request)
        try:
            if start: date.fromisoformat(start)
            if end: date.fromisoformat(end)
            if start and end and start > end: raise ValueError()
        except ValueError:
            raise HTTPException(422, '조회 기간을 확인하세요.')
        def match(r):
            day = r['created_at'][:10]
            return (can_view(account, r) and (not facility or r['facility'] == facility)
                    and (not department or r['department'] == department) and (not status or r['status'] == status)
                    and (not start or day >= start) and (not end or day <= end))
        return [r for r in repo.records() if match(r)]

    def guard_ai(request):
        if not limits.allow('ai-total', 60, 3600) or not limits.allow('ai:' + session(request), 10, 600):
            raise HTTPException(429, '분석 요청이 많습니다. 잠시 후 다시 시도하세요.')
        if not expensive.acquire(blocking=False):
            raise HTTPException(429, '다른 분석을 처리 중입니다. 잠시 후 다시 시도하세요.')

    @app.get('/healthz')
    async def health():
        return {'status': 'ok'}

    @app.get('/api/bootstrap')
    def bootstrap(request: Request):
        session(request)
        try:
            account = user(request)
        except HTTPException:
            account = None
        return {'mode': cfg.app_env, 'local_workspace': cfg.local_workspace, 'auth_mode': cfg.auth_mode,
                'csrf': request.session['csrf'], 'user': account,
                'facilities': FACILITIES, 'departments': DEPARTMENTS, 'categories': CATEGORIES,
                'policy': POLICY, 'report_max_rows': cfg.report_max_rows}

    @app.get('/api/overview')
    def overview(request: Request, year: int | None = None):
        year = int(now()[:4]) if year is None else year
        if not 2000 <= year <= 2100:
            raise HTTPException(422, '조회 연도를 확인하세요.')
        if not limits.allow('overview:' + session(request), 30, 60):
            raise HTTPException(429, '잠시 후 다시 조회하세요.')
        with overview_lock:
            if time.monotonic() >= overview_cache.get('expires', 0):
                records = repo.records()
                years = {year} | {int(r['created_at'][:4]) for r in records
                                 if str(r.get('created_at', ''))[:4].isdigit()}
                overview_cache['data'] = {y: summarize(records, y) for y in years}
                overview_cache['expires'] = time.monotonic() + 30
            return overview_cache['data'].get(year, dict(summarize([], year), years=sorted(
                set(overview_cache['data']) | {year}, reverse=True)))

    @app.get('/api/auth/google')
    async def login(request: Request):
        if pin_auth:
            raise HTTPException(404)
        if cfg.demo:
            raise HTTPException(400, '체험 모드에서는 체험 계정을 사용하세요.')
        return await oauth.google.authorize_redirect(request, cfg.app_base_url.rstrip('/') + '/api/auth/google/callback')

    @app.get('/api/auth/google/callback')
    async def callback(request: Request):
        if pin_auth:
            raise HTTPException(404)
        try:
            token = await oauth.google.authorize_access_token(request)
            info = token.get('userinfo', {})
            email = info.get('email', '').lower()
            if not info.get('email_verified') or email not in cfg.accounts:
                raise ValueError('Unapproved account')
            request.session.clear()
            session(request)
            request.session.update(email=email, name=info.get('name', email))
            return RedirectResponse('/#actions')
        except Exception:
            return RedirectResponse('/?login_error=1')

    @app.post('/api/auth/demo')
    def demo_login(request: Request, role: str = Form('admin')):
        mutation(request)
        if pin_auth or not cfg.demo or role not in {'admin', 'staff'}:
            raise HTTPException(404)
        request.session['email'] = f'demo-{role}@kywa.local'
        request.session['name'] = '체험 관리자' if role == 'admin' else '중앙 담당자'
        return {'ok': True}

    @app.post('/api/auth/pin')
    def pin_login(request: Request, pin: str = Form(..., max_length=64)):
        mutation(request)
        if not pin_auth:
            raise HTTPException(404)
        try:
            token = pin_auth.login(pin)
        except PinLocked as exc:
            raise HTTPException(429, '비밀번호 입력 오류가 반복되어 잠시 잠겼습니다. 15분 후 다시 시도하세요.',
                                headers={'Retry-After': str(exc.seconds)}) from None
        if not token:
            raise HTTPException(401, '비밀번호가 올바르지 않습니다.')
        pin_auth.revoke(request.session.get('pin_session', ''))
        request.session.clear()
        session(request)
        request.session['pin_session'] = token
        return {'ok': True}

    @app.post('/api/auth/logout')
    def logout(request: Request):
        mutation(request)
        if pin_auth:
            pin_auth.revoke(request.session.get('pin_session', ''))
        request.session.clear()
        return {'ok': True}

    @app.post('/api/photos/prepare')
    def prepare(request: Request, photo: UploadFile = File(...)):
        mutation(request)
        if not limits.allow('photo:' + session(request), 20, 600):
            raise HTTPException(429, '사진 처리 요청이 많습니다.')
        if not memory_lock.acquire(blocking=False):
            raise HTTPException(429, '다른 사진 또는 보고서를 처리 중입니다. 잠시 후 다시 시도하세요.')
        try:
            raw = photo.file.read(10*1024*1024+1)
            data = prepare_image(raw)
            key = drafts.put(session(request), {'type': 'photo', 'photo': data})
            return {'id': key, 'url': f'/api/drafts/{key}/photo',
                    'notice': '자동 얼굴 처리에는 누락이 있을 수 있습니다. 미리보기에서 얼굴·개인정보를 확인하세요.'}
        finally:
            photo.file.close()
            memory_lock.release()

    @app.get('/api/drafts/{key}/photo')
    def draft_photo(request: Request, key: str):
        draft = drafts.get(session(request), key)
        if not draft.get('photo'):
            raise HTTPException(404)
        return Response(draft['photo'], media_type='image/jpeg')

    def selected_photo(request, key):
        if not key:
            return None
        draft = drafts.get(session(request), key)
        if draft['type'] != 'photo':
            raise HTTPException(422, '사진 초안이 아닙니다.')
        return draft['photo']

    @app.post('/api/analyses')
    def analyze(request: Request, facility: str = Form(...), department: str = Form(...),
                description: str = Form(''), photo_id: str = Form('')):
        mutation(request)
        if facility not in FACILITIES or department not in DEPARTMENTS:
            raise HTTPException(422, '시설과 부서를 확인하세요.')
        if len(description) > 6000 or (not description.strip() and not photo_id):
            raise HTTPException(422, '사진 또는 6,000자 이하의 상황 설명을 입력하세요.')
        photo = selected_photo(request, photo_id)
        guard_ai(request)
        try:
            results = [dict(item, **risk(item['p'], item['s'])) for item in ai.analyze(facility, department, description, photo)]
            value = {'type': 'initial', 'facility': facility, 'department': department, 'description': description,
                     'items': results, 'photo': photo}
            key = drafts.put(session(request), value)
            return {'draft_id': key, 'items': results, 'guide_keywords': guide_keywords(results),
                    'photo_url': f'/api/drafts/{key}/photo' if photo else ''}
        finally:
            expensive.release()

    @app.post('/api/assessments')
    def submit(request: Request, data: SubmitRequest):
        mutation(request)
        body_hash = digest(data.model_dump())
        with repo.lock:
            previous = [r for r in repo.records() if r.get('operation_id') == data.request_id]
            if previous:
                if any(r.get('submit_hash') != body_hash or r.get('submit_owner') != digest(session(request)) for r in previous):
                    raise HTTPException(409, '같은 제출번호로 다른 내용을 저장할 수 없습니다.')
                return {'ids': [r['id'] for r in previous], 'replayed': True}
            draft = drafts.get(session(request), data.draft_id)
            if draft['type'] != 'initial':
                raise HTTPException(422)
            indexes = [x.index for x in data.items]
            if len(set(indexes)) != len(indexes) or max(indexes) >= len(draft['items']):
                raise HTTPException(422, '제출 항목을 확인하세요.')
            photo_id = drive.put(draft['photo'], data.request_id)
            records = []
            for item in data.items:
                before = dict(draft['items'][item.index])
                before.update(item.model_dump(exclude={'index'}))
                records.append(dict(id=str(uuid.uuid5(uuid.UUID(data.request_id), str(item.index))),
                    created_at=now(), facility=draft['facility'], department=draft['department'], before=before,
                    photo_id=photo_id, after=None, policy=POLICY, status='접수', revision=1,
                    operation_id=data.request_id, submit_hash=body_hash, submit_owner=digest(session(request))))
            repo.apply(records, [])
            overview_cache['expires'] = 0
            return {'ids': [r['id'] for r in records], 'replayed': False}

    @app.get('/api/assessments')
    def listing(request: Request, facility: str = '', department: str = '', status: str = '', start: str = '', end: str = ''):
        records = filtered(request, facility, department, status, start, end)
        records.sort(key=lambda r: r['created_at'], reverse=True)
        return {'items': [public_record(r) for r in records]}

    @app.get('/api/assessments/{record_id}/history')
    def history(request: Request, record_id: str):
        get_record(request, record_id)
        return {'items': [{k:v for k,v in e.items() if k != 'body_hash'} for e in repo.events(record_id)]}

    @app.get('/api/assessments/{record_id}/photos/{file_id}')
    def stored_photo(request: Request, record_id: str, file_id: str):
        record, _ = get_record(request, record_id)
        allowed = {record.get('photo_id'), (record.get('after') or {}).get('photo_id')}
        allowed.update((e.get('after') or {}).get('photo_id') for e in repo.events(record_id))
        if file_id not in allowed:
            raise HTTPException(404)
        data = drive.get(file_id)
        if not data:
            raise HTTPException(404, '사진을 불러오지 못했습니다.')
        return Response(data, media_type='image/jpeg')

    @app.post('/api/assessments/{record_id}/reassess')
    def reassess(request: Request, record_id: str, text: str = Form(...), photo_id: str = Form('')):
        mutation(request)
        record, _ = get_record(request, record_id)
        if record['status'] == '완료':
            raise HTTPException(409, '완료 건은 다시 열기 후 추가 조치하세요.')
        if not text.strip() or len(text) > 6000:
            raise HTTPException(422, '6,000자 이하의 개선조치 내용을 입력하세요.')
        photo = selected_photo(request, photo_id)
        guard_ai(request)
        try:
            result = ai.reassess(record, text, photo)
            result.update(risk(result['p'], result['s']))
            draft_id = drafts.put(session(request), dict(type='after', record_id=record_id,
                                revision=record['revision'], text=text, photo=photo, result=result))
            return {'draft_id': draft_id, 'revision': record['revision'], **result}
        finally:
            expensive.release()

    @app.post('/api/assessments/{record_id}/actions')
    def action(request: Request, record_id: str, data: ActionRequest):
        mutation(request)
        body_hash = digest(data.model_dump())
        with repo.lock:
            record, account = get_record(request, record_id)
            saved = next((e for e in repo.events(record_id) if e['id'] == data.request_id), None)
            if saved:
                if saved['body_hash'] != body_hash:
                    raise HTTPException(409, '같은 요청번호로 다른 내용을 저장할 수 없습니다.')
                return {'item': public_record(record), 'replayed': True}
            draft = drafts.get(session(request), data.draft_id)
            if draft['type'] != 'after' or draft['record_id'] != record_id:
                raise HTTPException(422, '다른 평가의 초안입니다.')
            if record['revision'] != data.revision or draft['revision'] != data.revision or record['status'] == '완료':
                raise HTTPException(409, '평가가 변경되었습니다. 목록을 새로고침하고 다시 분석하세요.')
            after = dict(**risk(data.p, data.s), text=draft['text'],
                         photo_id=drive.put(draft['photo'], data.request_id), actor=account['email'], created_at=now(),
                         policy=POLICY, rationale=draft['result']['rationale'], ai_result=draft['result'])
            record.update(after=after, status='완료' if data.complete else '조치 중', revision=record['revision']+1)
            event = dict(id=data.request_id, record_id=record_id, at=now(), actor=account['email'],
                         kind='완료' if data.complete else '조치 저장', text=draft['text'], after=after, body_hash=body_hash)
            repo.apply([record], [event])
            overview_cache['expires'] = 0
            return {'item': public_record(record), 'replayed': False}

    @app.post('/api/assessments/{record_id}/state')
    def state(request: Request, record_id: str, data: StateRequest):
        mutation(request)
        with repo.lock:
            record, account = get_record(request, record_id)
            saved = next((e for e in repo.events(record_id) if e['id'] == data.request_id), None)
            if saved:
                if saved['body_hash'] != digest(data.model_dump()):
                    raise HTTPException(409, '요청 내용이 다릅니다.')
                return {'item': public_record(record)}
            if data.revision != record['revision']:
                raise HTTPException(409, '다른 담당자가 변경했습니다. 새로고침하세요.')
            record.update(status=data.status, revision=record['revision']+1)
            event = dict(id=data.request_id, record_id=record_id, at=now(), actor=account['email'],
                         kind='상태 변경', text=data.status, body_hash=digest(data.model_dump()))
            repo.apply([record], [event])
            overview_cache['expires'] = 0
            return {'item': public_record(record)}

    @app.get('/api/guides')
    def guides(request: Request, keyword: str):
        if not keyword.strip() or len(keyword) > 80:
            raise HTTPException(422, '검색어는 1~80자로 입력하세요.')
        if not limits.allow('guides:' + session(request), 30, 600):
            raise HTTPException(429, '검색 요청이 많습니다.')
        return kosha_search(cfg, keyword.strip())

    @app.post('/api/reports')
    def report(request: Request, data: ReportRequest):
        mutation(request)
        user(request, admin=True)
        records = filtered(request, **data.model_dump(exclude={'format'}))
        if not records:
            raise HTTPException(422, '선택한 조건에 데이터가 없습니다.')
        if len(records) > cfg.report_max_rows:
            raise HTTPException(422, f'한 번에 {cfg.report_max_rows}건까지 출력합니다. 기간이나 시설을 좁혀주세요.')
        if not memory_lock.acquire(blocking=False):
            raise HTTPException(429, '다른 사진 또는 보고서를 처리 중입니다. 잠시 후 다시 시도하세요.')
        try:
            output = reports.excel(records, drive) if data.format == 'xlsx' else reports.pdf(records, drive)
            mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if data.format == 'xlsx' else 'application/pdf'
            filename = f'KYWA_위험성평가_{now()[:10]}.{data.format}'
            return Response(output, media_type=mime, headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"})
        finally:
            memory_lock.release()

    static = ROOT / 'frontend' / 'out'
    if static.exists():
        app.mount('/', StaticFiles(directory=static, html=True), name='frontend')
    else:
        @app.get('/')
        def build_required():
            return {'message': 'frontend에서 npm ci && npm run build 실행 후 서버를 재시작하세요.'}
    return app


app = create_app()
