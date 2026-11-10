"""Read APIs for the KYWA Vercel pilot. The Render pilot owns PIN sessions."""
from datetime import date, datetime
from functools import lru_cache
from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import requests
from .config import Settings
from .overview import summarize
from .pilot_read import NeedsSync, read_records
from .record_view import public_record

ORIGIN = 'https://kywa-safety-pilot-api.onrender.com'


@lru_cache(maxsize=1)
def settings():
    cfg = Settings(_env_file=None)
    if cfg.organization_id != 'kywa' or not os.environ.get('SPREADSHEET_ID'):
        raise ValueError('시험 시트 설정을 확인하세요.')
    return cfg


class PilotReadHandler(BaseHTTPRequestHandler):
    overview = False

    def output(self, status, data, cache=False):
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','public, max-age=0' if cache else 'private, no-store')
        self.send_header('Vercel-CDN-Cache-Control','public, s-maxage=30' if cache else 'no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        params = {k:v[-1] for k,v in parse_qs(urlsplit(self.path).query).items() if v}
        try:
            if self.overview:
                raw = params.get('year',datetime.now(ZoneInfo('Asia/Seoul')).year)
                year = int(raw)
                if not 2000 <= year <= 2100:
                    raise ValueError()
            else:
                for key in ('start','end'):
                    if params.get(key):
                        date.fromisoformat(params[key])
                if params.get('end') and params.get('start','') > params['end']:
                    raise ValueError()
        except (TypeError,ValueError):
            return self.output(422,{'detail':'조회 기간을 확인하세요.'})
        headers = {'Cookie':self.headers.get('Cookie','')} if not self.overview else {}
        try:
            if not self.overview:
                session=requests.get(ORIGIN+'/api/auth/session',headers=headers,timeout=10,allow_redirects=False)
                session.raise_for_status()
                if session.json().get('active') is not True:
                    return self.output(401,{'detail':'관리자 로그인이 필요합니다.'})
            cfg=settings()
            try:
                records=read_records(cfg)
            except NeedsSync:
                endpoint='/api/overview' if self.overview else '/api/assessments'
                result=requests.get(ORIGIN+endpoint,params=params,headers=headers,timeout=45,allow_redirects=False)
                return self.output(result.status_code,result.json())
            if self.overview:
                return self.output(200,summarize(records,year,cfg.organization),cache=params.get('fresh')!='1')
            selected=[r for r in records if all(not params.get(k) or params[k]==r[k]
                       for k in ('facility','department','status')) and
                       (not params.get('start') or params['start']<=r['created_at'][:10]) and
                       (not params.get('end') or params['end']>=r['created_at'][:10])]
            selected.sort(key=lambda r:r['created_at'],reverse=True)
            return self.output(200,{'items':[public_record(r,cfg.organization,cfg) for r in selected],'issues':[]})
        except Exception:
            return self.output(503,{'detail':'시험 시트 조회를 완료하지 못했습니다.'})
