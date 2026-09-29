# KYWA Safety · Next.js 개발 앱

기존 Streamlit을 유지하면서 `Next.js 정적 화면 + FastAPI`를 하나의 Render 무료 Docker 서비스로 실행합니다. 목표 주소는 **https://kywa-safety.onrender.com**이며, `v2` 접미사는 사용하지 않습니다. 실제 주소는 Render에서 서비스 생성 후 확인해야 합니다.

## 구현 범위

- 모바일·PC 대응 화면: AI 위험성평가, 개선조치·재평가, 관리자 결과보고서.
- 사진 또는 설명 분석 → 항목 선택·내용 수정 → 제출 → 조치 기록 → 재평가 → 담당자 확인 완료 → 다시 열기 및 이력 조회.
- Gemini 구조화 응답 검증, 서버에서 점수·등급 산정, KOSHA 키워드 검색과 원문 링크.
- Google 로그인 및 승인 계정 목록. 담당자는 지정 시설만, 관리자는 전체 조회·보고서 출력.
- 개발용 Sheets/Drive 분리, 비공개 사진, CSRF 검증, 재시도 시 중복 저장 방지, 수정 버전 충돌 검사.
- Excel/PDF: 조회 조건, 최초 평가 당시 등급 집계, 최신 조치내용 및 개선 전후 사진. 전체 변경 이력은 앱에서 조회합니다.
- HWPX는 사용자가 제공할 정상 양식과 참고자료를 받은 후 연동합니다. 현재 버튼은 준비 중입니다.

`APP_ENV=demo`에서는 **가상 AI 응답과 로컬 샘플 데이터**를 사용합니다. Gemini/Google/KOSHA 연결 성공을 의미하지 않습니다. Render 무료 서비스가 재시작되면 체험 기록은 초기화될 수 있습니다.

## 로컬 실행

Python 3.12, Node.js 22가 필요합니다. 아래 명령은 `kywa-next` 폴더 기준입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Copy-Item .env.example .env
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

http://localhost:8000 에서 확인합니다. `127.0.0.1` 주소로 접속하려면 `APP_BASE_URL`도 동일하게 바꾸세요. Origin 검증 때문에 두 주소를 섞어 사용하지 않습니다. 화면 변경 후 `npm run build`, 브라우저 새로고침이 필요합니다.

이 작업 폴더에 준비된 런타임을 이용하려면 `scripts/start-local.ps1`을 실행할 수도 있습니다. `.tools` 폴더는 로컬 도구이며 GitHub에 업로드하지 않습니다.

## GitHub 반영과 Render 배포

대상 저장소: https://github.com/archi01-safety/kywa-safety-app

개발 브랜치는 `codex/kywa-next`입니다. 새 Render 서비스는 이 브랜치를 배포합니다. 기존 main의 Streamlit 및 배포 워크플로와 분리해서 검증한 다음, 운영 반영 시점에 PR을 병합하고 Render의 배포 브랜치를 조정합니다.

1. 저장소 루트에 이 `kywa-next` 폴더를 추가합니다. 기존 `app.py`, `Dockerfile`, Streamlit 설정은 그대로 둡니다. `.env`, `.venv`, `local-data`, `node_modules`, `artifacts`, `.tools`는 업로드하지 않습니다.
2. Render에서 **New → Blueprint**를 선택해 해당 저장소를 연결합니다. Blueprint 파일 경로를 `kywa-next/render.yaml`로 지정합니다.
3. 서비스 `kywa-safety`, Docker, Singapore, **Free**, `/healthz`를 확인합니다. 이름이 이미 사용 중이면 원하는 주소 생성이 불가능할 수 있으므로 임의로 유료 전환하거나 다른 이름을 확정하지 않습니다.
4. 초기 설정은 `APP_ENV=demo`, `APP_BASE_URL=https://kywa-safety.onrender.com`입니다. `SESSION_SECRET`은 Render가 생성합니다. 서비스 주소가 다르면 `APP_BASE_URL`과 OAuth 리디렉션 URI도 일치시켜야 합니다.
5. 자동 배포는 꺼져 있습니다. 검토한 커밋을 Render의 Manual Deploy로 배포합니다. 저장소 변경을 기존 Streamlit에 반영하기 전 새 앱에서 검증합니다.

Blueprint 대신 New Web Service로 만들 때도 Root Directory=`kywa-next`, Runtime=`Docker`, Dockerfile=`./Dockerfile`, Free, Health Check=`/healthz`로 설정하면 됩니다. **Next.js는 빌드할 때만 실행**하며, 운영 프로세스는 FastAPI 하나입니다.

배포 이미지의 Python 의존성은 `backend/requirements.lock`, 프런트엔드는 `frontend/package-lock.json`을 사용합니다. Python 원본 범위를 바꾸면 잠금 파일도 갱신하세요.

## 실제 API 연결 (개발 데이터부터)

Render Environment에 `.env.example`의 값을 등록합니다. 비밀값을 GitHub나 채팅에 붙여 넣지 마세요.

| 설정 | 내용 |
|---|---|
| `APP_ENV` | 실연동 테스트는 `development`, 검증 후 `production` |
| `APP_BASE_URL` | `https://kywa-safety.onrender.com` |
| `SESSION_SECRET` | 32자 이상 별도 난수. 변경하면 기존 로그인 세션이 무효화됩니다. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | 웹 애플리케이션용 Google OAuth 클라이언트 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 JSON 전체를 서버 환경변수로 등록 |
| `SPREADSHEET_ID` | 별도 개발용 스프레드시트 ID |
| `SHEET_NAME` | 기본 `설문지 응답 시트1` |
| `HISTORY_SHEET_NAME` | 기본 `조치이력` |
| `DRIVE_FOLDER_ID` | 별도 개발용 사진 폴더 ID |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | 사용 가능한 모델과 키. 기본 모델은 `gemini-2.5-flash`, 계정에서 사용 가능 여부 확인 |
| `KOSHA_API_KEY` | 안전보건공단 기술지침 API 키 |
| `ACCESS_ACCOUNTS_JSON` | 아래 형태의 승인 계정 및 시설 범위 |

```json
{"admin@example.org":{"role":"admin","facilities":[]},"staff@example.org":{"role":"staff","facilities":["중앙","평창"]}}
```

이메일은 소문자로 입력합니다. 시설은 `중앙, 평창, 우주, 바이오, 해양, 미래, 생태, 본원` 중 지정합니다. 로그인 허용 여부와 시설 범위는 매 요청마다 다시 검사합니다.

Google OAuth의 승인된 리디렉션 URI:

```text
https://kywa-safety.onrender.com/api/auth/google/callback
```

OAuth 동의 화면이 테스트 상태라면 실제 로그인할 계정을 테스트 사용자에도 등록합니다. Sheets API와 Drive API를 활성화하고 개발 시트를 서비스 계정에 편집자로 공유합니다.

**Drive 저장 위치:** 서비스 계정에는 자체 저장 용량이 없으므로 Workspace 공유 드라이브에 개발 폴더를 만들고 업로드 가능한 권한을 부여하는 구성을 권장합니다. 개인 My Drive 폴더를 공유하는 것만으로는 업로드가 실패할 수 있습니다. 조직에서 이미 도메인 전체 위임을 승인한 경우에만 `GOOGLE_DELEGATE_EMAIL`을 설정해 기존 승인 범위를 사용합니다. 새 권한 승인은 조직 관리자가 진행해야 합니다. 앱은 파일을 인터넷 전체에 공개하는 권한을 만들지 않습니다. [Google Drive 오류 안내](https://developers.google.com/workspace/drive/api/guides/handle-errors#storageQuotaExceeded)

원본 코드에 직접 들어 있던 KOSHA 키는 새 코드에 복사하지 않았습니다. 기존 저장소 공개 범위를 확인하고 해당 키는 발급처에서 교체해 환경변수로 관리하세요.

## 시트 초기화·기존 데이터 이관

웹 서버는 시트 구조를 자동으로 변경하지 않습니다. **운영 시트의 사본**에서 먼저 실행하세요. 기존 앱이 같은 시트에 쓰는 동안에는 이관하거나 새 앱을 연결하지 않습니다.

```powershell
# .env에 development와 실제 개발용 설정 등록 후
.\.venv\Scripts\python.exe -m backend.migrate
# 행 수와 오류를 확인한 후 적용
.\.venv\Scripts\python.exe -m backend.migrate --apply
```

기본 명령은 읽기 전용입니다. `--apply`는 로컬 `artifacts/migration-backups`에 백업을 저장한 다음 단일 Google batchUpdate로 실행합니다. 백업에는 업무 데이터가 들어 있으므로 GitHub에 올리지 않습니다. 대량 이관 전에는 Google Sheets 자체 사본도 별도로 보관하세요.

- 기존 A:R 값은 이관 시 건드리지 않고 S:W에 평가 ID, 기준 버전, 상태, 수정 버전, 시스템 데이터를 추가합니다.
- 과거 등급은 `LEGACY-UNKNOWN`으로 보존합니다. 기존 점수·등급을 현행 기준으로 다시 써넣지 않습니다. 현행 환산은 상세 화면의 참고값입니다.
- 기존 개선 후 값이 있으면 완료 상태로 가져오되, 기록에 없는 조치내용·담당자·시각은 만들어내지 않습니다.
- 알 수 없는 헤더, 잘못된 날짜/수치, 중복 ID 또는 이미 사용 중인 S:W 데이터가 있으면 쓰기 전에 중단합니다.
- 이후 관리 대상 열을 직접 수정하거나 정렬해서 ID와 시스템 데이터를 분리하지 마세요. 변경은 앱에서 처리합니다.
- **Render 인스턴스 1개, Uvicorn worker 1개**가 필요합니다. 시트를 직접 쓰는 다른 프로그램과 병행 운영하지 않습니다. 다중 인스턴스가 필요해지면 트랜잭션 DB로 이관해야 합니다.

기존 운영 시트/폴더 ID는 오접속 방지 대상으로 등록되어 있습니다. 운영 전환 때만 `APP_ENV=production` 및 `ALLOW_LEGACY_WRITES=true`가 허용됩니다. 기존 운영 자원을 재사용하는 것이 필수는 아닙니다. 새 저장소를 운영용으로 승격하는 방법도 가능합니다.

롤백 시 새 앱의 쓰기를 중지하고 원본 사본으로 복원한 다음 기존 Streamlit을 다시 연결합니다. 전환 후 새로 추가된 기록은 먼저 별도로 내보내야 합니다. 앱 두 개가 한 시트에 동시에 쓰지 않도록 전환 시간을 정하세요.

## 위험도 기준

빈도 1~5 × 강도 1~4. AI가 보낸 점수·등급을 신뢰해 저장하지 않고 서버에서 계산합니다.

| 점수 | 등급 |
|---|---|
| 1~3 | 매우 낮음 |
| 4~6 | 낮음 |
| 8 | 보통 |
| 9~12 | 약간 높음 |
| 15 | 높음 |
| 16~20 | 매우 높음 |

해당 곱셈 범위에서 7, 11, 13, 14, 17~19는 나오지 않습니다. 재평가 AI가 낮은 점수를 주도록 강제하지 않으며, 담당자가 빈도·강도를 조정할 수 있습니다.

## 무료 운영 및 Keep Alive

`GET /healthz`는 외부 API·Google 저장소를 호출하지 않고 즉시 작은 200 응답을 반환합니다. cron-job.org에서 URL `https://kywa-safety.onrender.com/healthz`, 5분 간격, GET, 실패 알림을 설정할 수 있습니다. 최초 기동 직후에는 수동으로 앱이 열린 것을 확인한 뒤 모니터를 켜세요. 이 저장소 안에는 계정이나 예약 작업을 자동 생성하는 코드가 없습니다.

Render 무료 서비스는 15분 유휴 후 중지될 수 있고 월 무료 서비스 시간은 워크스페이스에서 공유됩니다. 서비스 1개를 31일 유지하면 744시간입니다. 여분의 개발 서비스까지 상시 실행하면 한도에 영향을 줍니다. 무료 환경은 무중단을 보장하지 않으며 외부 요청·재시작·플랫폼 정책에 따라 지연이 생길 수 있습니다. [Render 무료 서비스 안내](https://render.com/docs/free)

기존 GitHub `*/50` 스케줄은 매시간 0분과 50분에 실행되어 50분 공백이 생깁니다. GitHub Actions를 5분 주기 Keep Alive로 바꾸기보다 외부 HTTP 모니터를 사용하세요. `deploy/health-check.yml`은 수동 점검 예제이고 예약 실행을 추가하지 않았습니다.

배포 후 7일 관찰은 별도로 필요합니다. 기록 항목: health 실패/응답시간, 첫 화면 기동시간, AI 오류·429, 사진 업로드 성공, 중복 제출 여부, 메모리 및 보고서 100건 출력. 이 관찰을 로컬 테스트로 대신했다고 판단하지 않습니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm run build
# 별도 합성 데이터 서버를 자동으로 시작하는 PC·모바일 검사
# Windows: KYWA_TEST_PYTHON에 .venv/Scripts/python.exe 절대경로 지정
npx playwright install chromium
npm run test:e2e
```

`deploy/ci.yml`을 저장소 루트의 `.github/workflows/kywa-next-ci.yml`로 추가하면 Python 테스트, Next.js 빌드, Docker 이미지 빌드를 실행합니다. `deploy/health-check.yml`도 필요한 경우 루트 `.github/workflows`에 추가합니다. 기존 워크플로는 덮어쓰지 않습니다.

실제 Google OAuth, Sheets/Drive 권한, Gemini 모델, KOSHA 키 및 Render 배포는 각 계정 연결 후 현장 샘플로 확인해야 합니다. `docs-validation.md`에 이번 로컬 검증 결과와 남은 확인 항목을 기록합니다.
