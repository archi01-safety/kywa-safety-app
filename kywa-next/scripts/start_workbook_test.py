"""Start the private workbook-copy test app on this computer only."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port',type=int,default=8001)
args=parser.parse_args()
data=root/'local-data/workbook-test/data.json'
if not data.is_file():
    raise SystemExit('Run python -m backend.local_workspace --source <xlsx> first.')
secret_file = root/'local-data/auth/admin-pin.env'
if not secret_file.is_file():
    raise SystemExit('Run python scripts/set_admin_pin.py to set your administrator PIN first.')
pin_settings = dict(line.split('=', 1) for line in secret_file.read_text(encoding='utf-8').splitlines() if '=' in line)
if pin_settings.get('AUTH_MODE') != 'pin' or not pin_settings.get('ADMIN_PIN_HASH'):
    raise SystemExit('Invalid local PIN settings. Run python scripts/set_admin_pin.py again.')
environment={**os.environ,'APP_ENV':'demo','LOCAL_WORKSPACE':'true',
             'AUTH_MODE':'pin','ADMIN_PIN_HASH':pin_settings['ADMIN_PIN_HASH'],
             'APP_BASE_URL':f'http://localhost:{args.port}','DEMO_DATA_PATH':str(data)}
raise SystemExit(subprocess.call([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1',
                                 '--port',str(args.port),'--no-proxy-headers'],cwd=root,env=environment))
