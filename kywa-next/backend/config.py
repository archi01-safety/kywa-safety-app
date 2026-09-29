import json
from urllib.parse import urlparse
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    app_env: str = 'demo'
    app_base_url: str = 'http://localhost:8000'
    session_secret: str = 'local-demo-only-change-this-before-real-deployment'
    google_client_id: str = ''
    google_client_secret: str = ''
    google_service_account_json: str = ''
    spreadsheet_id: str = ''
    drive_folder_id: str = ''
    sheet_name: str = '설문지 응답 시트1'
    history_sheet_name: str = '조치이력'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3.6-flash'
    kosha_api_key: str = ''
    access_accounts_json: str = '{}'
    demo_data_path: str = str(ROOT / 'local-data' / 'demo.json')
    allow_legacy_writes: bool = False
    report_max_rows: int = 100
    google_delegate_email: str = ''
    local_workspace: bool = False
    auth_mode: str = 'google'
    admin_pin_hash: str = ''

    @property
    def demo(self):
        return self.app_env == 'demo'

    @property
    def accounts(self):
        return json.loads(self.access_accounts_json)

    def validate_runtime(self):
        if self.auth_mode not in {'google', 'pin'}:
            raise ValueError('AUTH_MODE는 google 또는 pin이어야 합니다.')
        if self.auth_mode == 'pin':
            from .pin_auth import parse_pin_hash
            parse_pin_hash(self.admin_pin_hash)
        if self.app_env not in {'demo', 'development', 'production'}:
            raise ValueError('APP_ENV must be demo, development or production')
        base = urlparse(self.app_base_url)
        if base.scheme not in {'http', 'https'} or not base.netloc or base.path not in {'', '/'} or base.query or base.fragment:
            raise ValueError('APP_BASE_URL에는 경로 없는 웹앱 주소를 입력하세요.')
        if not 1 <= self.report_max_rows <= 100:
            raise ValueError('REPORT_MAX_ROWS는 1~100 사이여야 합니다.')
        if self.local_workspace:
            if not self.demo or base.hostname not in {'localhost', '127.0.0.1', '::1'}:
                raise ValueError('운영 사본 시험 공간은 로컬 체험 모드에서만 사용할 수 있습니다.')
            data_path = Path(self.demo_data_path).resolve()
            if not data_path.is_relative_to((ROOT / 'local-data').resolve()) or not data_path.is_file():
                raise ValueError('프로젝트 local-data에 준비된 운영 사본 data.json이 필요합니다.')
        if base.scheme == 'https' and (len(self.session_secret) < 32 or self.session_secret.startswith('local-demo')):
            raise ValueError('배포 환경의 SESSION_SECRET은 별도의 32자 이상 난수여야 합니다.')
        if not self.demo:
            required = ('google_service_account_json', 'spreadsheet_id', 'drive_folder_id', 'gemini_api_key', 'kosha_api_key')
            if self.auth_mode == 'google':
                required += ('google_client_id', 'google_client_secret')
            missing = [key.upper() for key in required if not getattr(self, key)]
            if missing:
                raise ValueError('필수 서버 설정 누락: ' + ', '.join(missing))
            if len(self.session_secret) < 32 or self.session_secret.startswith('local-demo'):
                raise ValueError('SESSION_SECRET에는 별도의 32자 이상 난수를 설정하세요.')
            if not self.app_base_url.startswith('https://'):
                raise ValueError('실제 연동 환경은 HTTPS APP_BASE_URL이 필요합니다.')
            if self.auth_mode == 'google' and not self.accounts:
                raise ValueError('담당자/관리자 계정을 ACCESS_ACCOUNTS_JSON에 등록하세요.')
            from .domain import FACILITIES
            if not isinstance(self.accounts, dict):
                raise ValueError('ACCESS_ACCOUNTS_JSON은 이메일을 키로 하는 객체여야 합니다.')
            for email, account in self.accounts.items():
                if (not isinstance(email, str) or email != email.lower() or '@' not in email
                    or not isinstance(account, dict) or set(account) != {'role', 'facilities'}
                    or account['role'] not in {'admin', 'staff'} or not isinstance(account['facilities'], list)
                    or any(f not in FACILITIES for f in account['facilities'])
                    or account['role'] == 'staff' and not account['facilities']):
                    raise ValueError('승인 계정의 이메일, role, facilities 설정을 확인하세요.')
            # The supplied legacy apps share these live resources. Never use them accidentally.
            legacy_sheet = '1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q'
            legacy_folder = '13RYVnDB7rrqLQYzB5Wa9WdWr0CHjm_MW'
            if (self.spreadsheet_id == legacy_sheet or self.drive_folder_id == legacy_folder):
                if self.app_env != 'production' or not self.allow_legacy_writes:
                    raise ValueError('기존 운영 저장소입니다. 개발용 시트/폴더를 별도로 지정하세요.')


@lru_cache
def get_settings():
    return Settings()
