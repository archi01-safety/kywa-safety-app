"""Build a flat AX upload ZIP from the source allowlist and a verified static export."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--frontend',type=Path,default=root/'frontend/out')
    parser.add_argument('--organization',choices=('kywa','ayf','fowi','khidi','knps','knf','kohi','cayf'),default='kywa')
    parser.add_argument('--origin',default='https://ax.kywa.or.kr')
    parser.add_argument('--base-path',default='/apps/kywa-safety')
    args=parser.parse_args()
    static=args.frontend.resolve()
    config=json.loads((static/'build-config.json').read_text(encoding='utf-8'))
    assert (static/'index.html').is_file()
    if not re.fullmatch(r'(?:/[A-Za-z0-9_-]+)+',args.base_path) or config.get('basePath')!=args.base_path:
        parser.error('AX 화면을 실제 APP_BASE_PATH로 빌드한 뒤 지정하세요. Render/root 정적 화면은 AX ZIP에 넣을 수 없습니다.')
    from urllib.parse import urlsplit
    origin=urlsplit(args.origin)
    if origin.scheme!='https' or not origin.netloc or origin.path not in ('','/') or origin.query or origin.fragment or origin.username:
        parser.error('--origin에는 경로 없는 HTTPS 주소를 입력하세요.')
    subprocess.run([sys.executable,str(root/'scripts/build_ax_requirements.py')],check=True,capture_output=True)
    subprocess.run([sys.executable,str(root/'scripts/package_source.py')],check=True,capture_output=True)
    destination=root/'artifacts/kywa-safety-ax.zip'
    entries={}
    with zipfile.ZipFile(root/'artifacts/kywa-safety-source.zip') as source:
        for item in source.infolist():
            if item.filename.startswith('kywa-next/'):
                name=item.filename[len('kywa-next/'):]
                if name.startswith('artifacts/') and name!='artifacts/ax-integration-verification.json': continue
                entries[name]=source.read(item)
    for path in static.rglob('*'):
        if path.is_file():
            entries['frontend/out/'+path.relative_to(static).as_posix()]=path.read_bytes()
    entries['AX-BUILD.json']=(json.dumps({'format':2,'base_path':config['basePath'],
        'entrypoint':'python app.py','asgi_entrypoint':'app:app','python_minimum':'3.11','requirements':'requirements.txt',
        'source_layout':'flat','requires_external_secrets':True,
        'configuration_contract':1,'default_environment':{'APP_ENV':'production','ORGANIZATION_ID':args.organization,
            'AUTH_MODE':'pin','APP_BASE_URL':args.origin.rstrip('/'),'APP_BASE_PATH':config['basePath']},
        'default_config_file':'/var/lib/ax-apps/'+(config['basePath'].strip('/').split('/')[-1] or args.organization+'-safety')+'/ax.env',
        'persistent_configuration':'APP_ENV_FILE outside release directory or platform environment',
        'integration_check':'python scripts/check_ax_integrations.py --config <external-config>',
        'included_integrations':['google_sheets','google_drive','gemini','kosha','law'],
        'private_config_included':False},indent=2)+'\n').encode()
    forbidden={'.env','node_modules','.next','.venv','local-data','secret','__pycache__'}
    manifest=[]
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(entries.items()):
            assert not forbidden.intersection(Path(name).parts),name
            assert b'-----BEGIN '+b'PRIVATE KEY-----' not in data,name
            archive.writestr(name,data)
            manifest.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    with zipfile.ZipFile(destination) as archive:assert archive.testzip() is None
    (root/'artifacts/ax-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    result=dict(file=destination.name,base_path=config['basePath'],files=len(entries),bytes=destination.stat().st_size,
                sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    (root/'artifacts/ax-package.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
