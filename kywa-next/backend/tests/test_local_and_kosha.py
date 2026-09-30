import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.repository import DemoRepository
from backend.services import kosha_search, parse_kosha_response, ServiceError


def test_kosha_singleton_empty_and_error():
    payload={'header':{'resultCode':'00'},'body':{'totalCount':1,'items':{'item':{
        'techGdlnNo':'A-G-1-2025','techGdlnNm':'추락방호망','fileDownloadUrl':'https://portal.kosha.or.kr/example'}}}}
    assert len(parse_kosha_response(payload)['items']) == 1
    assert parse_kosha_response({'header':{'resultCode':'00'},'body':{'totalCount':0,'items':''}})['items']==[]
    with pytest.raises(ValueError):
        parse_kosha_response({'header':{'resultCode':'30'},'body':{'totalCount':0}})
    payload['body']['items']['item']['fileDownloadUrl']='javascript:alert(1)'
    assert parse_kosha_response(payload)['items'][0]['url']==''


def test_kosha_does_not_hide_provider_auth_failure(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'header':{'resultCode':'30','resultMsg':'NOT_REGISTERED_SERVICE_KEY'}}
    monkeypatch.setattr('backend.services.httpx.get',lambda *a,**kw: Response())
    with pytest.raises(ServiceError,match='인증키'):
        kosha_search(SimpleNamespace(demo=False,kosha_api_key='test-only'),'추락')


def test_local_workspace_refuses_public_base_url():
    with pytest.raises(ValueError,match='로컬'):
        Settings(_env_file=None,local_workspace=True,app_base_url='https://kywa-safety.onrender.com',
                 session_secret='test-only-'*5).validate_runtime()


def test_local_workspace_refuses_remote_clients(tmp_path,monkeypatch):
    monkeypatch.setattr('backend.config.ROOT',tmp_path)
    data=tmp_path/'local-data/data.json'
    data.parent.mkdir()
    data.write_text(json.dumps({'records':[],'events':[]}),encoding='utf-8')
    cfg=Settings(_env_file=None,local_workspace=True,demo_data_path=str(data),app_base_url='http://localhost:8001')
    app=create_app(cfg)
    with TestClient(app,client=('203.0.113.10',4567)) as remote:
        assert remote.get('/api/bootstrap').status_code==403
    with TestClient(app,client=('127.0.0.1',4567)) as local:
        assert local.get('/api/bootstrap').json()['local_workspace'] is True
    assert DemoRepository(data).records()==[]
