"""Persistent, server-only configuration for the flat AX distribution.

The marker exists only in the AX upload ZIP. Render/local startup is unchanged.
Environment variables supplied by the platform always take precedence.
"""
import json
import os
from pathlib import Path

from dotenv import dotenv_values

PUBLIC_DEFAULTS = {
    'APP_ENV': 'production', 'ORGANIZATION_ID': 'kywa', 'AUTH_MODE': 'pin',
    'APP_BASE_URL': 'https://ax.kywa.or.kr', 'APP_BASE_PATH': '/apps/kywa-safety',
}


def settings_env_file(root, environ=None):
    env = os.environ if environ is None else environ
    # Never pick up an old demo .env left inside an AX release directory.
    return env.get('APP_ENV_FILE') or (None if (Path(root)/'AX-BUILD.json').is_file() else Path(root)/'.env')


def configure_ax_environment(root, environ=None):
    """Load once before importing config/main; never write or rotate settings."""
    env = os.environ if environ is None else environ
    root = Path(root).resolve()
    marker = root/'AX-BUILD.json'
    if not marker.is_file():
        return False
    try:
        build = json.loads(marker.read_text(encoding='utf-8'))
        defaults = build.get('default_environment', PUBLIC_DEFAULTS)
        if (not isinstance(defaults, dict) or set(defaults) != set(PUBLIC_DEFAULTS)
                or any(not isinstance(value, str) for value in defaults.values())
                or defaults['APP_ENV'] != 'production' or defaults['AUTH_MODE'] != 'pin'
                or defaults['APP_BASE_PATH'] != build['base_path']):
            raise ValueError()
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError('AX 빌드 설정을 확인하세요. 검증된 ZIP을 다시 등록하세요.') from None
    location = env.get('APP_ENV_FILE', '')
    if not location:
        hint=build.get('default_config_file','')
        if isinstance(hint,str) and hint and Path(hint).is_absolute() and Path(hint).is_file():
            location=hint
            env['APP_ENV_FILE']=hint
    if location:
        path = Path(location)
        if not path.is_absolute() or path.resolve().is_relative_to(root):
            raise ValueError('APP_ENV_FILE은 배포 폴더 밖의 비공개 설정파일 절대 경로여야 합니다.')
        if not path.is_file():
            raise ValueError('APP_ENV_FILE 설정파일을 읽을 수 없습니다. AX 서버 경로와 읽기 권한을 확인하세요.')
        try:
            # Do not expand ${...} in API keys, JSON or PIN hashes.
            values = dotenv_values(path, encoding='utf-8-sig', interpolate=False)
        except (OSError, UnicodeError):
            raise ValueError('AX 비공개 설정파일을 UTF-8로 저장하고 읽기 권한을 확인하세요.') from None
        for key, value in values.items():
            if value is not None:
                env.setdefault(key, value)
    for key, value in defaults.items():
        env.setdefault(key, value)
    return True
