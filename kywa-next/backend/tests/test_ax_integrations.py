import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend.ax_config import PUBLIC_DEFAULTS,configure_ax_environment,settings_env_file


def marker(root,**changes):
    root.mkdir(parents=True,exist_ok=True)
    value={'base_path':'/apps/kywa-safety','default_environment':dict(PUBLIC_DEFAULTS)}
    value.update(changes)
    (root/'AX-BUILD.json').write_text(json.dumps(value),encoding='utf-8')


def test_render_has_no_ax_defaults_and_keeps_original_dotenv(tmp_path):
    env={}
    assert not configure_ax_environment(tmp_path,env)
    assert env=={}
    assert settings_env_file(tmp_path,env)==tmp_path/'.env'


def test_ax_defaults_to_real_mode_and_never_uses_release_dotenv(tmp_path):
    marker(tmp_path)
    (tmp_path/'.env').write_text('APP_ENV=demo',encoding='utf-8')
    env={}
    assert configure_ax_environment(tmp_path,env)
    assert env['APP_ENV']=='production' and env['AUTH_MODE']=='pin'
    assert settings_env_file(tmp_path,env) is None


def test_explicit_demo_is_only_an_intentional_override(tmp_path):
    marker(tmp_path);env={'APP_ENV':'demo'}
    configure_ax_environment(tmp_path,env)
    assert env['APP_ENV']=='demo'


@pytest.mark.parametrize('location',['missing','inside','relative'])
def test_configuration_must_exist_outside_release(tmp_path,location):
    root=tmp_path/'release';marker(root)
    selected=tmp_path/'missing.env' if location=='missing' else root/'inside.env' if location=='inside' else Path('relative.env')
    if location=='inside':selected.write_text('GEMINI_API_KEY=PRIVATE_SENTINEL',encoding='utf-8')
    env={'APP_ENV_FILE':str(selected)}
    with pytest.raises(ValueError) as exc:configure_ax_environment(root,env)
    assert 'PRIVATE_SENTINEL' not in str(exc.value) and 'GEMINI_API_KEY' not in env


def test_literal_settings_and_port_survive_replacing_release(tmp_path):
    external=tmp_path/'protected.env'
    content='APP_ENV=production\nSESSION_SECRET=stable-test-value\nGEMINI_API_KEY=literal-${UNCHANGED}\nADMIN_PIN_HASH=literal$600000$salt$hash\nPORT=9999\n'
    external.write_text(content,encoding='utf-8-sig')
    for release in ('one','two'):
        root=tmp_path/release;marker(root)
        env={'APP_ENV_FILE':str(external),'PORT':'8507'}
        configure_ax_environment(root,env)
        assert env['SESSION_SECRET']=='stable-test-value'
        assert env['GEMINI_API_KEY']=='literal-${UNCHANGED}'
        assert env['ADMIN_PIN_HASH']=='literal$600000$salt$hash'
        assert env['PORT']=='8507' and env['APP_BASE_PATH']=='/apps/kywa-safety'
    assert external.read_text(encoding='utf-8-sig')==content


def test_platform_environment_overrides_config_file(tmp_path):
    root=tmp_path/'release';marker(root)
    profile=tmp_path/'server.env';profile.write_text('GEMINI_MODEL=old\nSESSION_SECRET=file-secret\n',encoding='utf-8')
    env={'APP_ENV_FILE':str(profile),'GEMINI_MODEL':'platform-model','SESSION_SECRET':'existing-platform-secret'}
    configure_ax_environment(root,env)
    assert env['GEMINI_MODEL']=='platform-model' and env['SESSION_SECRET']=='existing-platform-secret'


def test_ax_can_read_the_installed_private_profile_without_service_env_changes(tmp_path):
    profile=tmp_path/'server-private'/'ax.env';profile.parent.mkdir()
    profile.write_text('SESSION_SECRET=private-stable\n',encoding='utf-8')
    for name in ('release-one','release-two'):
        root=tmp_path/name;marker(root,default_config_file=str(profile))
        env={};configure_ax_environment(root,env)
        assert env['APP_ENV_FILE']==str(profile) and env['SESSION_SECRET']=='private-stable'


def test_corrupt_marker_is_rejected_without_showing_values(tmp_path):
    marker(tmp_path,default_environment={'SESSION_SECRET':'PRIVATE_SENTINEL'})
    with pytest.raises(ValueError) as exc:configure_ax_environment(tmp_path,{})
    assert 'PRIVATE_SENTINEL' not in str(exc.value)


def test_diagnostics_refuses_demo():
    from backend.ax_integrations import check_integrations
    from backend.config import Settings
    with pytest.raises(ValueError):check_integrations(Settings(_env_file=None))


def test_diagnostics_checks_every_provider_and_redacts_failures(monkeypatch):
    from backend import ax_integrations as diag
    class Config:
        demo=False;setup=False;organization_id='kywa'
        def model_copy(self,update):return self
        def validate_runtime(self):pass
    monkeypatch.setattr(diag,'google_check',lambda _: {'ok':True,'write_probe_performed':False})
    monkeypatch.setattr(diag,'ai_check',lambda _: (_ for _ in ()).throw(RuntimeError('PRIVATE_SENTINEL')))
    monkeypatch.setattr(diag,'kosha_check',lambda _: {'ok':True})
    monkeypatch.setattr(diag,'law_check',lambda _: {'ok':True})
    result=diag.check_integrations(Config())
    assert set(result['checks'])=={'google','gemini','kosha','law'}
    assert not result['all_passed'] and not result['assessment_writes_performed']
    assert 'PRIVATE_SENTINEL' not in json.dumps(result)


def test_direct_config_import_in_ax_also_defaults_to_real_mode(tmp_path):
    root=tmp_path/'release';marker(root)
    backend=root/'backend';backend.mkdir()
    original=Path(__file__).resolve().parents[1]
    for name in ('__init__.py','config.py','ax_config.py'):
        shutil.copyfile(original/name,backend/name)
    (root/'.env').write_text('APP_ENV=demo',encoding='utf-8')
    env={k:v for k,v in os.environ.items() if not k.startswith(('APP_','AUTH_','ORGANIZATION_'))}
    env['PYTHONPATH']=str(root)
    result=subprocess.run([sys.executable,'-c','from backend.config import Settings; s=Settings(); print(s.app_env,s.auth_mode,s.app_base_path)'],
        cwd=root,env=env,capture_output=True,text=True,check=True)
    assert result.stdout.strip()=='production pin /apps/kywa-safety'


def test_ax_fastapi_import_contract(tmp_path):
    root=tmp_path/'release';marker(root)
    source=Path(__file__).resolve().parents[2]
    shutil.copyfile(source/'app.py',root/'app.py')
    backend=root/'backend';backend.mkdir()
    for file in (source/'backend').glob('*.py'):shutil.copyfile(file,backend/file.name)
    for folder in ('organizations','policies','risk_profiles'):
        shutil.copytree(source/'backend'/folder,backend/folder)
    static=root/'frontend/out';static.mkdir(parents=True)
    (static/'index.html').write_text('test',encoding='utf-8')
    (static/'build-config.json').write_text(json.dumps({'basePath':'/apps/kywa-safety'}),encoding='utf-8')
    env={k:v for k,v in os.environ.items() if not k.startswith(('APP_','AUTH_','ORGANIZATION_','REQUIRE_'))}
    env.update(PYTHONPATH=str(root),APP_ENV='demo',AUTH_MODE='google',APP_BASE_URL='http://testserver',APP_DATA_DIR=str(tmp_path/'data'))
    code='from uvicorn.importer import import_from_string; from fastapi.testclient import TestClient; app=import_from_string("app:app"); c=TestClient(app); assert c.get("/apps/kywa-safety/healthz").status_code==200; print(app.root_path)'
    result=subprocess.run([sys.executable,'-c',code],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='/apps/kywa-safety'


def test_ax_lock_preserves_other_render_dependencies():
    from scripts.build_ax_requirements import content,ROOT
    generated=content()
    original=(ROOT/'backend/requirements.lock').read_text(encoding='utf-8')
    assert 'numpy==2.4.6; python_version < "3.12"' in generated
    for line in original.splitlines():
        if not line.startswith('numpy=='):assert line in generated
