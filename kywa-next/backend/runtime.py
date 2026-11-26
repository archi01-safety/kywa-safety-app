"""App-owned runtime setup. Does not modify the proxy or service manager."""
import json
import os
from pathlib import Path
import tempfile


def prepare_runtime(cfg, static):
    if cfg.require_frontend:
        try:
            build = json.loads((static / 'build-config.json').read_text(encoding='utf-8'))
            if build['basePath'] != cfg.app_base_path or not (static / 'index.html').is_file():
                raise ValueError()
        except (OSError, ValueError, KeyError):
            raise ValueError('화면 빌드 경로가 APP_BASE_PATH와 다릅니다. 같은 APP_BASE_PATH로 frontend를 다시 빌드하세요.') from None
    paths = [Path(p) for p in (cfg.app_data_dir, cfg.app_upload_dir, cfg.app_log_dir) if p]
    if cfg.app_data_dir and not cfg.app_upload_dir:
        cfg.app_upload_dir = str(Path(cfg.app_data_dir) / 'tmp')
        paths.append(Path(cfg.app_upload_dir))
    for path in paths:
        try:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Check actual writes rather than permission bits alone.
            with tempfile.TemporaryFile(dir=path):
                pass
        except OSError:
            raise ValueError('앱 데이터·임시·로그 폴더의 쓰기 권한을 확인하세요.') from None
    if cfg.app_upload_dir:
        # Starlette's multipart spool uses Python's temporary-file directory.
        tempfile.tempdir = cfg.app_upload_dir
        os.environ['TMPDIR'] = cfg.app_upload_dir


def launch_options(environ=None):
    env = os.environ if environ is None else environ
    try:
        port = int(env.get('PORT', '8000'))
        if not 1 <= port <= 65535: raise ValueError()
    except ValueError:
        raise ValueError('PORT는 1~65535의 정수여야 합니다.') from None
    host = env.get('HOST', '127.0.0.1').strip()
    if not host: raise ValueError('HOST가 비어 있습니다.')
    trusted = env.get('FORWARDED_ALLOW_IPS', '127.0.0.1').strip()
    if trusted == '*':
        raise ValueError('FORWARDED_ALLOW_IPS에는 프록시 주소를 명시하세요. 전체 신뢰(*)는 허용하지 않습니다.')
    return dict(host=host, port=port, proxy_headers=True, forwarded_allow_ips=trusted,
                workers=1, limit_concurrency=20, timeout_keep_alive=5, access_log=False)
