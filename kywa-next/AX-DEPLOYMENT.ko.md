# AX 플랫폼 등록 안내

2026-11-13 갱신. 복수 사진·조치예정·법령 연결·세션·단답형 정렬 개선과 인수인계서를 포함하는 ZIP이다. 실제 Render 배포 상태는 HANDOFF.md를 따르며 AX 서버 설정은 변경하지 않았다. 이 안내는 앱 소스·등록 ZIP에 관한 것으로 Apache/systemd/AX 관리 서버를 설치하거나 수정하는 스크립트를 포함하지 않는다. 검증 결과는 AX-VERIFICATION.ko.md를 함께 확인한다.

## 앱 유형과 실행 구조

- **Python / FastAPI 웹앱**으로 등록한다. Streamlit 앱이나 정적 사이트로 등록하면 분석·저장이 동작하지 않는다.
- Next.js 화면은 미리 빌드한 정적 파일이고 Python이 API와 화면을 같은 포트로 제공한다. 운영 중 Next.js 개발/서버 프로세스는 필요하지 않다.
- Python **3.12**, Node.js **22**. Node는 화면 빌드와 실행 중 HWPX 생성에 필요하다. Python 의존성은 `backend/requirements.lock`, 화면 의존성은 `frontend/package-lock.json`에 고정되어 있다.
- Linux에서 libvips와 HEVC 디코더가 포함된 libheif, 한글 글꼴(NanumGothic 또는 기존 보고서 코드가 인식하는 글꼴)이 필요하다. 준비된 Docker 이미지는 Debian 환경이다. Rocky Linux의 패키지 이름·저장소·SELinux 정책은 실제 AX 환경에서 확인해야 하며 임의로 변경하지 않는다.
- 실행 계정은 일반 사용자다. `sudo`/root가 필요한 앱 동작은 없다. 의존성 설치·화면 빌드는 읽기 전용 격리 실행 **이전** 준비 단계에서 수행한다.

## ZIP 최상위와 실행 명령

`kywa-safety-ax.zip`은 한 단계 상위 폴더 없이 다음 파일이 바로 들어 있다.

```text
app.py
AX-BUILD.json
AX-DEPLOYMENT.ko.md
backend/                # API, 기관별 정책, 문단형 HWPX 생성기와 라이선스
frontend/out/           # 등록 경로로 빌드한 화면
frontend/app/           # 수정·재빌드를 위한 전체 화면 소스
frontend/package*.json
frontend/scripts/
scripts/
Dockerfile
.env.example            # 비밀값 없는 참고 파일
```

권장 실행 명령(앱 폴더를 작업 디렉터리로 선택):

```sh
/path/to/python3.12 app.py
```

AX가 주입한 `PORT`를 그대로 사용한다. 환경변수 미지정 시 로컬 기본값은 8000이며 8503·8505 등 특정 할당 포트를 고정하지 않는다. 기본 바인딩은 `127.0.0.1`, Docker 내부는 명시적으로 `HOST=0.0.0.0`이다. 앱 프로세스 실행과 systemd 실행에서 같은 명령을 사용한다. 포트·사용자·서비스 등록은 AX의 기존 관리 절차를 사용한다.

기존 Uvicorn 실행 명령을 사용하는 경우에도 환경변수 `APP_BASE_PATH`가 적용되지만, 빌드 경로 검증과 접근 로그 제한이 적용된 `app.py` 진입점을 권장한다. 초안·임시 사진·보고서 작업과 Google 쓰기 직렬화 때문에 **단일 워커**를 유지한다. PIN 세션은 토큰 해시와 절대 만료 시각을 숨김 관리에 보관해 서버 재시작 후 복원한다. 작성 중 임시 작업의 재시작 복원과는 별개다.

## 경로와 빌드

ZIP에 들어 있는 빌드의 경로는 `AX-BUILD.json`의 `base_path` 값이다. 제공 예시 슬러그는 `kywa-safety`, 경로는 `/apps/kywa-safety`다. **AX에 이 슬러그가 등록됐다는 뜻은 아니다.** 등록한 실제 슬러그가 다르면 아래와 같이 다시 빌드하고 ZIP을 만든다.

```sh
export APP_BASE_PATH=/apps/actual-slug
export NEXT_TELEMETRY_DISABLED=1
cd frontend
npm ci
npm run build
cd ..
python scripts/package_ax.py
```

Python 의존성 설치: `python -m pip install -r backend/requirements.lock`. 검증 의존성은 운영 실행에 불필요하다.

서버에도 같은 `APP_BASE_PATH`를 설정한다. 시작 시 `frontend/out/build-config.json`과 비교하여 잘못된 경로의 화면 배포를 차단한다. 원래 Render/root 배포는 빈 값으로 빌드한다. 현재 디자인·메뉴는 유지하고 주소는 `/apps/actual-slug/#inspect`, `#actions`, `#reports`를 사용한다.

[Next.js basePath는 빌드 시 포함되므로 슬러그 변경 시 재빌드가 필요하다.](https://nextjs.org/docs/pages/api-reference/config/next-config-js/basePath) FastAPI의 `root_path`는 [프록시 하위 경로 방식](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)을 사용한다. 프록시가 접두 경로를 제거하거나 유지하는 두 요청 형태를 검사한다. 앱은 `X-Forwarded-Prefix`를 신뢰해 경로를 임의 변경하지 않는다. WebSocket·SSE는 사용하지 않고 일반 HTTP로 보고서 작업 상태를 조회한다.

## 등록 시 환경변수

아래 이름이 AX에서 **자동 주입된다고 가정하지 않는다.** AX 등록 화면의 환경변수 기능 또는 플랫폼이 승인한 외부 환경파일에 설정한다. `.env`나 인증 JSON을 등록 ZIP/GitHub에 넣지 않는다.

| 변수 | AX 설정 |
|---|---|
| `PORT` | AX가 할당하는 8500~8599 중 실제 값 |
| `HOST` | 일반 프로세스는 `127.0.0.1`; 플랫폼 네트워크 구조상 필요한 주소만 지정 |
| `APP_BASE_URL` | `https://ax.kywa.or.kr` **경로 없이** |
| `APP_BASE_PATH` | `/apps/실제-슬러그` (끝 `/` 없이, 빌드와 동일) |
| `APP_DATA_DIR` | 앱 계정만 쓸 수 있는 앱별 **절대 경로**, 소스 밖 예: `/var/lib/ax-apps/actual-slug` |
| `APP_UPLOAD_DIR` | 선택. 기본은 `APP_DATA_DIR/tmp`; multipart 임시 업로드 영역 |
| `APP_LOG_DIR` | 선택. 폴더 권한 점검만 수행하며 개인정보가 담긴 파일 로그를 만들지 않음. 표준 오류는 AX/journald에서 수집 |
| `APP_ENV_FILE` | 선택. 플랫폼이 허용하는 소스 밖 비공개 환경파일의 절대 경로 |
| `FORWARDED_ALLOW_IPS` | 기본 `127.0.0.1`. 실제 신뢰 프록시 IP만 지정, `*`는 거부 |
| `REQUIRE_FRONTEND` | `app.py`는 기본 true. 빌드와 실행 경로 일치 검사 |
| `ORGANIZATION_ID` | kywa/fowi/knps/knf/kohi/khidi/cayf/ayf 중 해당 기관 |
| `APP_ENV` | 초기 독립 시험은 demo, 실제 연동은 development 또는 production |
| `SESSION_SECRET` | 32자 이상 앱별 비밀 난수; 다른 AX 앱과 공유하지 않음 |
| `AUTH_MODE`, `ADMIN_PIN_HASH` | 현재 PIN 방식이면 pin 및 기존 승인된 해시 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 지정 서비스 계정의 JSON 전체, 서버 비밀설정 |
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `KOSHA_API_KEY` | 현재 승인된 서버 API 설정 |
| `SPREADSHEET_ID`, `SHEET_NAME`, `DRIVE_FOLDER_ID`, `HISTORY_SHEET_NAME` | 해당 기관의 준비된 저장소. 설정 파일 기본값도 유지 |
| `ALLOW_LEGACY_WRITES` | 운영 저장소는 백업·준비 확인 후 true. 임의 시험 쓰기 방지 유지 |
| `REPORT_NODE` | Node가 PATH에 없을 때 Node22 실행파일 절대 경로 |

Google 계정 로그인 방식을 선택하면 기존 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ACCESS_ACCOUNTS_JSON`도 필요하고 OAuth 승인 리디렉션 URI는 `https://ax.kywa.or.kr/apps/실제-슬러그/api/auth/google/callback`이다. PIN 방식에는 OAuth 리디렉션 등록이 필요하지 않다. 기존 Google 편집 권한과 API 사용 정책을 유지한다.

## 쓰기 위치·재배포·중지·재시작

- `APP_DATA_DIR`는 배포 버전 폴더와 분리해 유지하고 다른 기관과 공유하지 않는다. 일반 사용자에게 해당 폴더의 쓰기 권한이 필요하다. 설정한 폴더의 실제 쓰기 가능 여부를 시작 시 검사한다.
- 실제 운영 평가·사진은 기존 Google 시트/Drive에 저장한다. demo 파일·사진은 지정된 데이터 폴더 안에 저장한다. `DEMO_DATA_PATH`를 별도로 설정하면 그 값이 우선하므로 AX에서는 생략하거나 같은 외부 데이터 영역에 둔다.
- 업로드 원본은 multipart 임시파일/메모리에서 처리하며 사용자가 준 파일명을 저장 경로로 사용하지 않는다. 얼굴 처리 후 확정된 사진만 기존 저장 절차로 전달한다.
- 소스 디렉터리에는 실행 중 파일을 쓰지 않으며 Python bytecode 생성을 끈다. 로그는 요청 본문·이름·키를 기록하지 않으며 Uvicorn 접근 로그를 끈다.
- 앱을 멈출 때는 AX 중지 기능의 정상 종료(SIGTERM)를 사용한다. 생성 중인 문서가 있으면 종료가 지연될 수 있으므로 실행 관리자의 종료 대기 정책은 운영자가 확인한다. 재시작 시 임시 초안·PIN 세션·미다운로드 보고서 작업은 사라져 재로그인·재생성이 필요하다. 저장된 Google 기록과 외부 데이터 디렉터리는 유지된다.
- AX로 운영을 전환하기 전 기존 Render와 같은 운영 시트에 **동시에 두 신규 앱 인스턴스가 쓰지 않도록** 전환 일정을 정한다. Streamlit 동시 행 추가 지원과 별개로 신규 앱 간 동시 관리 쓰기는 이번 호환 검사 범위가 아니다. 이번 작업은 기존 Render를 중지하거나 이전하지 않았다.

## 등록 후 점검

1. `AX-BUILD.json`과 실제 슬러그, 공개 origin, 할당 포트, 데이터 권한을 대조한다.
2. `/apps/슬러그/healthz`에서 `{"status":"ok"}` 응답을 확인한다. 정상 작동 확인용이며 절전 방지 호출을 추가하지 않는다.
3. 홈·직접 `#reports` 접속·새로고침·로고 초기화·로고/CSS/JS 로딩을 확인한다.
4. 별도 시험 저장소에서 사진→블러→분석→제출→재조회·조치·세 보고서 다운로드를 확인한다. demo 성공을 실제 Google/AI 연동 성공으로 처리하지 않는다.
5. 로그인·시간 연장·만료, 다른 AX 앱과 쿠키 분리, 관리자 사진 접근을 확인한다.
6. AX의 중지·재시작·재배포에서 포트가 유지되고 저장된 데이터가 보존되는지 확인한다.

외부 통신은 Google API/OAuth, AI API, data.go.kr 및 기존 Google Fonts를 사용한다. 폰트 통신이 차단되면 기존 CSS의 시스템 글꼴로 대체된다. AX 방화벽·프록시 업로드 한도·응답 타임아웃·인증서·서비스 승인 설정은 플랫폼 운영자가 확인해야 하며 이 패키지는 변경하지 않는다.
