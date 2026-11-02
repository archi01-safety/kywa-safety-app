# 새 PC에서 작업 이어가기

먼저 HANDOFF.md와 AGENTS.md를 읽고 현재 브랜치·배포 상태를 확인한다. 운영 데이터 변경 없이 체험 환경부터 실행한다.

## 소스와 개발 환경

Git, Python 3.12, Node.js 22를 준비한다. Windows에서 한글 출력 검증은 한글 2020, Excel 인쇄 검증은 Microsoft Excel을 별도로 사용한다. 한글 2014 호환은 별도 검증 대상이다.

```powershell
git clone --branch codex/kywa-next https://github.com/archi01-safety/kywa-safety-app.git
cd kywa-safety-app/kywa-next
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock -r backend/requirements-dev.txt
Copy-Item .env.example .env
cd frontend
npm ci
npm run build
cd ..
```

`.env`는 `APP_ENV=demo`, `ORGANIZATION_ID=kywa`, `AUTH_MODE=google`, `APP_BASE_URL=http://localhost:8000`으로 시작한다. demo에서는 Google/API 연결 성공을 의미하지 않는다. 실제 API 키를 넣기 전에 테스트용 시트와 폴더를 지정한다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

http://localhost:8000 에서 열고 Origin 검증 때문에 localhost와 127.0.0.1을 섞지 않는다. UI 변경 후 frontend에서 다시 빌드한다.

## 검사와 HWPX 재빌드

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
cd frontend
npm run test:unit
npm run build
$env:KYWA_TEST_PYTHON=(Resolve-Path '..\.venv\Scripts\python.exe').Path
npm run test:e2e
cd ..
Expand-Archive backend/assets/hwpx-semantic-source.zip -DestinationPath tools/hwpx -Force
cd tools/hwpx
npm ci
npm run build
cd ../..
```

E2E 실행 전 Playwright Chromium을 설치한다(`npx playwright install chromium`). Linux의 HEIC/HEIF 검사에는 Dockerfile과 deploy/ci.yml에 지정한 libvips·libheif 및 HEVC 플러그인이 필요하다. 로컬 브라우저 접근이 제한되면 승인된 GitHub Actions CI로 검사하고 미검증을 기록한다. 문단형 생성기 수정 시 소스와 `backend/assets/hwpx-semantic.cjs`를 함께 갱신한다.

## 실제 연동과 배포

`.env.example`은 키 이름·예시만 보관한다. Google 서비스 계정 JSON, Gemini/KOSHA 키, 세션 비밀값, PIN 해시는 비공개 백업 또는 기존 Render Environment에서 재설정한다. 인증정보를 GitHub·대화·로그에 출력하지 않는다. GitHub 브라우저 로그인과 Git push 인증은 별개다.

기관별 저장소 설정과 서비스 계정 편집 권한을 확인하되 기존 권한을 이유 없이 재부여하지 않는다. `APP_ENV=production`, `AUTH_MODE=pin` 등은 기존 Render 설정과 대조한다. `scripts/set_admin_pin.py`로 해시를 만들고 원문 PIN은 코드에 넣지 않는다.

2026-11-02 **AYF와 6개 지원기관**의 개별 배포·19열 이관·운영 검증을 완료했다. 재설치나 소스 복제만으로 이관을 반복하지 않는다. 후속 배포는 대상 기관을 명시한다. GitHub Actions와 사본 검사 후 PARTNER-ROLLOUT.ko.md의 순서대로 개별 수동 배포한다. KYWA 서비스와 Blueprint 전체 동기화는 실행하지 않는다. HEAD만 보고 이미 운영 반영됐다고 판단하지 않는다.

KYWA 행 삭제·셀 수정 기능은 SHEET-EDITING.ko.md를 따른다. `python -m backend.migrate_row_identity`는 읽기 전용 계획 확인이며 `--apply`가 있을 때만 전체 백업 후 행 식별정보를 준비한다. 평가 탭 19열은 그대로 유지한다. 이미 준비된 운영 파일에는 이관을 반복할 필요가 없다. Google 행 메타데이터·숨김 관리 정보·평가표·조치이력은 동일 시점의 묶음으로 복구한다.

## 이동 직전 별도 보관할 항목

- 소스 커밋, 최신 HANDOFF/CHANGELOG, 소스 ZIP과 SHA-256.
- 비공개 인증정보, Render 환경변수 복원 정보, 기관별 저장소 매핑.
- 운영 시트 값·서식·표·숨김 관리·조치이력 백업 및 실제 사진/참고 문서.
- 미완료 작업과 재현 방법, 실제 한글/Excel 검증 결과.

`.venv`, `node_modules`, `.next`, 캐시는 새 PC에서 재생성한다. 비공개 자료는 암호화된 전달 수단으로 옮기며 공개 저장소에 올리지 않는다.
