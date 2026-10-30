from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.organization import load_organization
from backend.pin_auth import make_pin_hash


def test_ayf_configuration():
    org = load_organization('ayf')
    assert org.name == '안양시청소년재단'
    assert len(org.facilities) == 12 and len(org.departments) == 12
    assert org.departments.count('활동사업팀') == 1
    assert org.policy.risk(5, 3)['grade'] == '높음'
    assert org.submitter_name.mode == 'required'
    assert org.storage.spreadsheet_id == ''
    assert org.storage.drive_folder_id == load_organization('kywa').storage.drive_folder_id
    with pytest.raises(ValueError):
        Settings(_env_file=None, organization_id='ayf', app_env='production').validate_runtime()


def test_setup_allows_real_analysis_path_but_blocks_storage(tmp_path):
    cfg = Settings(_env_file=None, organization_id='ayf', app_env='setup',
        app_base_url='https://testserver', session_secret='s'*40, auth_mode='pin',
        admin_pin_hash=make_pin_hash('1234'), gemini_api_key='test-key', kosha_api_key='test-key',
        demo_data_path=str(tmp_path/'empty.json'))
    calls = []
    def analyze(*args):
        calls.append(args)
        return [dict(category='시설 안전', location='시험', scenario='시험 위험', solution='시험 조치', law='', p=5, s=3)]
    with TestClient(create_app(cfg, ai=SimpleNamespace(analyze=analyze)), base_url='https://testserver') as c:
        boot = c.get('/api/bootstrap').json()
        assert boot['mode'] == 'setup'
        c.headers.update({'Origin':cfg.app_base_url, 'X-CSRF-Token':boot['csrf']})
        response = c.post('/api/analyses', data=dict(facility='안전감사실',department='안전감사실',description='시험 위험'))
        assert response.status_code == 200 and len(calls) == 1
        assert response.json()['items'][0]['grade'] == '높음'
        for path in ('/api/assessments','/api/assessments/test/actions','/api/assessments/test/state','/api/reports','/api/auth/demo'):
            assert c.post(path,json={}).status_code == 503
        assert c.get('/api/overview').json()['total'] == 0
        assert c.get('/api/assessments').status_code == 401


def test_setup_refuses_existing_institution_storage():
    cfg = Settings(_env_file=None, organization_id='kywa',app_env='setup', app_base_url='https://testserver',
        session_secret='s'*40,auth_mode='pin',admin_pin_hash=make_pin_hash('1234'),gemini_api_key='test',kosha_api_key='test')
    with pytest.raises(ValueError, match='시트가 지정된'):
        cfg.validate_runtime()
