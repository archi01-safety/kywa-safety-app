from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.pin_auth import make_pin_hash, PinAuth, PinLocked

# This test value differs from deployment credentials; it verifies a leading zero.
TEST_PIN = '0427'


@pytest.fixture(scope='module')
def encoded():
    return make_pin_hash(TEST_PIN)


@pytest.fixture
def pin_context(tmp_path, encoded):
    cfg = Settings(_env_file=None, auth_mode='pin', admin_pin_hash=encoded,
                   app_base_url='http://testserver', demo_data_path=str(tmp_path/'data.json'))
    app = create_app(cfg)
    with TestClient(app) as client:
        boot = client.get('/api/bootstrap').json()
        client.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':boot['csrf']})
        yield client, app, cfg


def sign_in(client):
    response = client.post('/api/auth/pin', data={'pin':TEST_PIN})
    assert response.status_code == 200, response.text
    boot = client.get('/api/bootstrap').json()
    client.headers['X-CSRF-Token'] = boot['csrf']
    return boot


def test_pin_protects_all_admin_routes_and_disables_bypasses(pin_context):
    c, app, cfg = pin_context
    boot = c.get('/api/bootstrap').json()
    assert boot['auth_mode'] == 'pin' and boot['user'] is None
    assert 'admin_pin_hash' not in boot and cfg.admin_pin_hash not in str(boot)
    assert c.get('/api/assessments').status_code == 401
    assert c.get('/api/assessments/demo-1/history').status_code == 401
    assert c.get('/api/assessments/demo-1/photos/fake').status_code == 401
    assert c.post('/api/reports',json={'format':'xlsx'}).status_code == 401
    assert c.post('/api/assessments/demo-1/reassess',data={'text':'점검'}).status_code == 401
    assert c.post('/api/auth/demo',data={'role':'admin'}).status_code == 404
    assert c.get('/api/auth/google').status_code == 404
    assert c.get('/api/auth/google/callback').status_code == 404
    assert c.post('/api/auth/pin',data={'pin':TEST_PIN},headers={'X-CSRF-Token':'wrong'}).status_code == 403
    assert c.post('/api/auth/pin',data={'pin':TEST_PIN},headers={'Origin':'https://other.example'}).status_code == 403
    assert c.post('/api/analyses',data={'facility':'중앙','department':'협력부(국립청소년시설)','description':'난간 흔들림'}).status_code == 200
    old_csrf = boot['csrf']
    boot = sign_in(c)
    assert boot['csrf'] != old_csrf
    assert boot['user']['role'] == 'admin' and boot['user']['email'] == 'pin-admin'
    assert len(c.get('/api/assessments').json()['items']) == 4
    assert c.post('/api/reports',json={'format':'xlsx'}).status_code == 200


def test_logout_revokes_copied_cookie_and_server_restart_ends_session(pin_context):
    c, app, cfg = pin_context
    sign_in(c)
    captured = c.cookies.get('kywa_session')
    assert c.post('/api/auth/logout').status_code == 200
    c.cookies.clear()
    c.cookies.set('kywa_session', captured, domain='testserver.local', path='/')
    assert c.get('/api/assessments').status_code == 401
    c.headers['X-CSRF-Token'] = c.get('/api/bootstrap').json()['csrf']
    sign_in(c)
    captured = c.cookies.get('kywa_session')
    with TestClient(create_app(cfg)) as restarted:
        restarted.cookies.set('kywa_session',captured,domain='testserver.local',path='/')
        assert restarted.get('/api/assessments').status_code == 401


def test_pin_lock_is_shared_across_cookies_and_expiration_is_absolute(pin_context):
    c, app, cfg = pin_context
    clock = [100.0]
    app.state.pin_auth.clock = lambda:clock[0]
    for attempt in range(5):
        c.cookies.clear()
        c.headers['X-CSRF-Token'] = c.get('/api/bootstrap').json()['csrf']
        response = c.post('/api/auth/pin',data={'pin':'9999'})
        assert response.status_code == (401 if attempt < 4 else 429)
    assert response.headers['retry-after'] == '900'
    assert c.post('/api/auth/pin',data={'pin':TEST_PIN},headers={'X-Forwarded-For':'198.51.100.1'}).status_code == 429
    clock[0] += 901
    sign_in(c)
    clock[0] += 3599
    assert c.get('/api/assessments').status_code == 200
    clock[0] += 2
    assert c.get('/api/assessments').status_code == 401
    assert c.get('/api/bootstrap').json()['user'] is None


def test_concurrent_attempts_cannot_skip_account_limit(encoded):
    auth = PinAuth(encoded)
    def wrong(_):
        try:
            return auth.login('9999')
        except PinLocked:
            return 'locked'
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(wrong, range(8)))
    assert results.count(None) == 4 and results.count('locked') == 4


def test_production_pin_does_not_require_google_oauth(encoded):
    cfg = Settings(_env_file=None, app_env='production', auth_mode='pin', admin_pin_hash=encoded,
                   app_base_url='https://example.org', session_secret='test-only-'*5,
                   google_service_account_json='{}',spreadsheet_id='test-sheet',drive_folder_id='test-folder',
                   gemini_api_key='test-key',kosha_api_key='test-key')
    cfg.validate_runtime()
    cfg.auth_mode = 'google'
    with pytest.raises(ValueError, match='GOOGLE_CLIENT_ID'):
        cfg.validate_runtime()
    cfg.auth_mode = 'pin'
    cfg.admin_pin_hash = TEST_PIN
    with pytest.raises(ValueError, match='ADMIN_PIN_HASH'):
        cfg.validate_runtime()


def test_pin_format_and_independent_salts():
    for invalid in ('427', '００００', 'abcd', '12345'):
        with pytest.raises(ValueError):
            make_pin_hash(invalid)
    assert make_pin_hash(TEST_PIN) != make_pin_hash(TEST_PIN)
