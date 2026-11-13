"""Build a flat AX upload ZIP from the source allowlist and a verified static export."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--frontend',type=Path,default=root/'frontend/out')
    args=parser.parse_args()
    static=args.frontend.resolve()
    config=json.loads((static/'build-config.json').read_text(encoding='utf-8'))
    assert (static/'index.html').is_file()
    subprocess.run([sys.executable,str(root/'scripts/package_source.py')],check=True,capture_output=True)
    destination=root/'artifacts/kywa-safety-ax.zip'
    entries={}
    with zipfile.ZipFile(root/'artifacts/kywa-safety-source.zip') as source:
        for item in source.infolist():
            if item.filename.startswith('kywa-next/'):
                name=item.filename[len('kywa-next/'):]
                if name.startswith('artifacts/'): continue
                entries[name]=source.read(item)
    for path in static.rglob('*'):
        if path.is_file():
            entries['frontend/out/'+path.relative_to(static).as_posix()]=path.read_bytes()
    entries['AX-BUILD.json']=(json.dumps({'format':1,'base_path':config['basePath'],
        'entrypoint':'python app.py','source_layout':'flat','requires_external_secrets':True},indent=2)+'\n').encode()
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
