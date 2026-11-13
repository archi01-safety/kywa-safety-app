# 새 PC에서 작업 이어가기

## 2026-11-13 v1.2 작업 재개 기준

사용자 요청으로 두 GitHub 저장소의 Actions를 껐고 워크플로 및 검사 산출물을 정리했다. 새 PC 설치나 롤백을 이유로 Actions를 켜거나 YAML을 다시 만들지 않는다. 검사는 아래 수동 명령과 허용된 브라우저에서 수행한다. 최신 화면·검증은 ACTION-WORKSPACE.ko.md를 따른다.

### 기존 데이터 재개 기준

8개 Render의 현재 소스/기관 버전은 HANDOFF.md와 releases/를 먼저 확인한다. 신규 설치라는 이유로 기존 운영 시트 이관을 반복하지 않는다. 최종 구조는 일반20열/AYF18열이며 마지막 열은 개선 전 사진2다. Google 정렬 도구는 SHEET-EDITING.ko.md를 따른다. 인증값 LAW_API_OC는 기존 비공개 환경 그룹에 있으며 키 원문을 소스나 문서에 넣지 않는다. DETAILED_RISK_ENABLED=false를 유지하고 담당자 사례 검토 후 별도 활성화한다. PIN은 변경하지 않았으며 서버 재시작 후에도 절대 만료 전 세션을 복원한다. 단일 worker/instance 운영을 유지한다.

먼저 HANDOFF.md와 AGENTS.md를 읽고 현재 브랜치·배포 상태를 확인한다. 운영 데이터 변경 없이 체험 환경부터 실행한다.

AX 등록은 [AX-DEPLOYMENT.ko.md](AX-DEPLOYMENT.ko.md)를 별도로 따른다. 실행 진입점은 `python app.py`, 지정된 `PORT`와 `APP_BASE_PATH`, 소스 밖 `APP_DATA_DIR`를 사용한다. 기존 Render/root 화면은 APP_BASE_PATH를 비워 빌드한다. AX용 ZIP의 경로를 다른 슬러그로 바꾸면 화면도 재빌드해야 한다.

AYF는 현재 18열(추가 사진 포함)·시설만 수집하는 설정이다. 운영 이관을 자동 반복하지 말고 AYF-FACILITY-MIGRATION.ko.md와 최신 HANDOFF.md를 먼저 확인한다. 지원기관 PIN/해시는 별도 비공개 환경변수로 전달하며 소스 패키지에 포함하지 않는다.

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

v1.1 추가 사진 열·조치예정·복구 절차는 [PHOTO-REVIEW-V1.1.ko.md](PHOTO-REVIEW-V1.1.ko.md)를 먼저 따른다. 시트 확장은 별도 사본 검증과 운영 쓰기 점검 후 명시적으로 실행하며 앱 시작 시 자동 이관하지 않는다. 법령 API의 `LAW_API_OC`는 [신청 안내](LAW-API-SETUP.ko.md)를 따른다. `DETAILED_RISK_ENABLED`는 대표 사례 대조 전에는 false로 유지한다. 생산 PIN 세션은 숨김 관리 탭에 해시와 만료 시각을 보관하며 하나의 worker/인스턴스로 운영한다.

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

E2E 실행 전 Playwright Chromium을 설치한다(`npx playwright install chromium`). Linux의 HEIC/HEIF 검사에는 Dockerfile에 지정한 libvips·libheif 및 HEVC 플러그인이 필요하다. 로컬 브라우저 접근이 제한되면 접근을 허용한 환경에서 수동 검사하고 미검증을 기록한다. Actions를 대신 활성화하지 않는다. 문단형 생성기 수정 시 소스와 `backend/assets/hwpx-semantic.cjs`를 함께 갱신한다.

## 실제 연동과 배포

`.env.example`은 키 이름·예시만 보관한다. Google 서비스 계정 JSON, Gemini/KOSHA 키, 세션 비밀값, PIN 해시는 비공개 백업 또는 기존 Render Environment에서 재설정한다. 인증정보를 GitHub·대화·로그에 출력하지 않는다. GitHub 브라우저 로그인과 Git push 인증은 별개다.

기관별 저장소 설정과 서비스 계정 편집 권한을 확인하되 기존 권한을 이유 없이 재부여하지 않는다. `APP_ENV=production`, `AUTH_MODE=pin` 등은 기존 Render 설정과 대조한다. `scripts/set_admin_pin.py`로 해시를 만들고 원문 PIN은 코드에 넣지 않는다.

2026-11-02 **AYF와 6개 지원기관**의 개별 배포·19열 이관·운영 검증을 완료했다. 재설치나 소스 복제만으로 이관을 반복하지 않는다. 후속 배포는 대상 기관을 명시한다. 로컬 자동검사와 필요한 사본 검사 후 PARTNER-ROLLOUT.ko.md의 순서대로 개별 수동 배포한다. 대상 서비스의 검증된 커밋을 개별 수동 배포하며 Blueprint 전체 동기화는 실행하지 않는다. 디자인 후속 작업은 KYWA를 포함한 8개 서비스를 대상으로 별도 승인됐다. HEAD만 보고 이미 운영 반영됐다고 판단하지 않는다. 최신 배포 SHA와 기록은 HANDOFF.md 및 artifacts/render-deployments.json을 따른다.

KYWA 행 삭제·셀 수정 기능은 SHEET-EDITING.ko.md를 따른다. `python -m backend.migrate_row_identity`는 읽기 전용 계획 확인이며 `--apply`가 있을 때만 전체 백업 후 행 식별정보를 준비한다. 현재 평가 탭은 일반20열/AYF18열이며 마지막 추가 사진 열을 보존한다. 이미 준비된 운영 파일에는 이관을 반복할 필요가 없다. Google 행 메타데이터·숨김 관리 정보·평가표·조치이력은 동일 시점의 묶음으로 복구한다.

## 이동 직전 별도 보관할 항목

- 소스 커밋, 최신 HANDOFF/CHANGELOG, 소스 ZIP과 SHA-256.
- 비공개 인증정보, Render 환경변수 복원 정보, 기관별 저장소 매핑.
- 운영 시트 값·서식·표·숨김 관리·조치이력 백업 및 실제 사진/참고 문서.
- 미완료 작업과 재현 방법, 실제 한글/Excel 검증 결과.

`.venv`, `node_modules`, `.next`, 캐시는 새 PC에서 재생성한다. 비공개 자료는 암호화된 전달 수단으로 옮기며 공개 저장소에 올리지 않는다.
