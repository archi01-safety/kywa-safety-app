import io
import json
import tempfile
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.config import Settings
from backend.main import create_app
from backend.runtime import launch_options, prepare_runtime
from backend.pin_auth import make_pin_hash

PREFIX = '/apps/kywa-safety'


class StripPrefix:
    """Simulates Apache removing the mount path; browser still uses public URLs."""
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope['path'].startswith(PREFIX):
            scope = dict(scope, path=scope['path'][len(PREFIX):] or '/', raw_path=scope['raw_path'][len(PREFIX):] or b'/')
        await self.app(scope, receive, send)


@pytest.mark.parametrize('strip', [False, True])
def test_proxy_upload_submit_protected_photos_all_reports_and_restart(tmp_path, monkeypatch, strip):
    monkeypatch.setattr(tempfile, 'tempdir', None)
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    cfg = Settings(_env_file=None, app_base_url='http://testserver', app_base_path=PREFIX,
                   app_data_dir=str(tmp_path/'data'), app_log_dir=str(tmp_path/'logs'))
    app = create_app(cfg)
    with TestClient(StripPrefix(app) if strip else app) as c:
        get = lambda path: c.get(PREFIX+path)
        post = lambda path, **kw: c.post(PREFIX+path, **kw)
        boot = get('/api/bootstrap')
        cookie = boot.headers['set-cookie']
        assert f'path={PREFIX}' in cookie.lower() and 'httponly' in cookie.lower() and 'kywa_session_' in cookie
        assert get('/healthz').json() == {'status':'ok'}
        assert get('/healthz').headers['cache-control'] == 'no-store'
        assert 'spreadsheet_id' not in boot.text and 'private_key' not in boot.text
        c.headers.update({'Origin':cfg.app_base_url, 'X-CSRF-Token':boot.json()['csrf']})
        assert post('/api/auth/demo', data={'role':'admin'}, headers={'Origin':'http://attacker.test'}).status_code == 403
        raw = io.BytesIO(); Image.new('RGB',(100,70),'#385a70').save(raw,'WEBP')
        photo = post('/api/photos/prepare',files={'photo':('../../private.jpg',raw.getvalue(),'image/jpeg')}).json()
        assert photo['url'].startswith(PREFIX+'/api/') and c.get(photo['url']).status_code == 200
        processed = post('/api/photos/'+photo['id']+'/deidentify',json={}).json()
        draft = post('/api/analyses',data={'facility':'우주','department':boot.json()['departments'][0],'description':'합성 검증용 난간','photo_id':processed['id']})
        assert draft.status_code == 200, draft.text
        item = draft.json()['items'][0]
        body = {'request_id':str(uuid.uuid4()),'submitter_name':'홍㉠㉢','draft_id':draft.json()['draft_id'],
                'items':[dict(index=0,location=item['location'],scenario=item['scenario'],solution=item['solution'])]}
        saved = post('/api/assessments',json=body)
        assert saved.status_code == 200, saved.text
        assert post('/api/assessments',json=body).json()['replayed']
        assert post('/api/auth/demo',data={'role':'admin'}).status_code == 200
        records = get('/api/assessments').json()['items']
        record = next(r for r in records if r['id']==saved.json()['ids'][0])
        assert record['photo_url'].startswith(PREFIX+'/api/')
        assert c.get(record['photo_url']).status_code == 200
        for format in ('xlsx','pdf','hwpx'):
            start=post('/api/report-jobs',json={'format':format,'facility':'우주'})
            assert start.status_code==200,start.text
            path='/api/report-jobs/'+start.json()['id']
            for _ in range(300):
                state=get(path).json()
                if state['state'] in ('complete','failed'):break
                time.sleep(.05)
            assert state['state']=='complete',state
            output=get(path+'/download')
            assert output.status_code==200 and 'filename*=UTF-8' in output.headers['content-disposition']
            assert output.content.startswith(b'%PDF' if format=='pdf' else b'PK')
        c.cookies.clear()
        assert c.get(record['photo_url']).status_code==401
        assert not (tmp_path/'private.jpg').exists()
        assert (tmp_path/'data/demo.json').is_file()
        assert tempfile.gettempdir()==str(tmp_path/'data/tmp')
    restarted=create_app(cfg)
    with TestClient(restarted) as c:
        assert c.get(PREFIX+'/api/overview').json()['total']==5


def test_prefix_pin_session_isolation(tmp_path):
    cfg=Settings(_env_file=None,app_base_url='http://testserver',app_base_path=PREFIX,
                 demo_data_path=str(tmp_path/'data.json'),auth_mode='pin',admin_pin_hash=make_pin_hash('0427'))
    with TestClient(create_app(cfg)) as c:
        boot=c.get(PREFIX+'/api/bootstrap')
        c.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':boot.json()['csrf']})
        assert c.post(PREFIX+'/api/auth/pin',data={'pin':'0427'}).status_code==200
        c.headers['X-CSRF-Token']=c.get(PREFIX+'/api/bootstrap').json()['csrf']
        assert c.post(PREFIX+'/api/auth/extend').json()['remaining_seconds']==3600
        assert c.get('/api/auth/session').json()['active'] is False  # scoped cookie isn't sent to root
        assert c.get(PREFIX+'/api/auth/session').json()['active'] is True


def test_build_mismatch_and_runtime_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile,'tempdir',None)
    monkeypatch.setenv('TMPDIR',str(tmp_path))
    static=tmp_path/'static';static.mkdir();(static/'index.html').write_text('test')
    (static/'build-config.json').write_text(json.dumps({'basePath':PREFIX}))
    cfg=Settings(_env_file=None,app_base_path=PREFIX,require_frontend=True,app_data_dir=str(tmp_path/'data'))
    cfg.validate_runtime();prepare_runtime(cfg,static)
    cfg.app_base_path='/apps/different'
    with pytest.raises(ValueError,match='APP_BASE_PATH'):prepare_runtime(cfg,static)
    cfg=Settings(_env_file=None,app_data_dir='relative')
    with pytest.raises(ValueError,match='절대 경로'):cfg.validate_runtime()


@pytest.mark.parametrize('prefix',['/apps/../private','//example.com','/apps/a?x=1','/apps/%2F','/apps/a\\b'])
def test_invalid_prefix_rejected(prefix):
    with pytest.raises(ValueError):Settings(_env_file=None,app_base_path=prefix).validate_runtime()


def test_launch_binding_port_and_trusted_proxy():
    assert launch_options({})['host']=='127.0.0.1'
    assert launch_options({'PORT':'8599'})['port']==8599
    assert launch_options({'PORT':'8501','HOST':'0.0.0.0'})['host']=='0.0.0.0'
    for port in ('0','65536','eight'):
        with pytest.raises(ValueError):launch_options({'PORT':port})
    with pytest.raises(ValueError):launch_options({'FORWARDED_ALLOW_IPS':'*'})
    assert launch_options({})['access_log'] is False
