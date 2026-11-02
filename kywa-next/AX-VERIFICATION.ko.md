# AX 호환 변경·검증 기록

2026-11-02. AX 운영 등록은 아직 수행하지 않았다. 실제 등록 방법은 AX-DEPLOYMENT.ko.md, 배포 ZIP의 경로와 해시는 artifacts/ax-package.json을 확인한다. 아래 상태는 이번 AX 호환 소스에 대한 것이며 완료된 7개 기관 Render 운영 검증과 구분한다.

## 파일별 변경

| 파일 | 기존 문제 | 수정 내용 | 영향 범위 |
|---|---|---|---|
| `backend/config.py` | 공개 origin만 있고 하위 경로·외부 쓰기 경로 미지정 | `APP_BASE_PATH` 및 데이터/임시/로그 절대 경로, 외부 환경파일 지원 | 서버 설정. 빈 경로는 기존 root 동작 |
| `backend/main.py` | API 사진 URL·로그인 복귀 주소가 루트, 쿠키 이름 공통 | `root_path`, 접두 URL, 경로별 쿠키, 경로 제거 후 업로드 제한 검사 | API 주소/인증 경계. 평가·저장 업무 로직 유지 |
| `backend/runtime.py`, `app.py` | 실행 명령에 바인딩 고정, 읽기 전용 소스 대비 부족 | PORT/HOST 분리, 비root 진입점, 외부 쓰기 확인, 임시 경로, 빌드 일치 확인 | 앱 실행만 변경, 플랫폼 설정 변경 없음 |
| `frontend/next.config.ts`, `frontend/scripts/write-build-config.mjs`, `frontend/package.json` | 정적 빌드가 루트 경로 전제 | build-time basePath, 서버 대조용 빌드 정보 | 정적 CSS/JS 및 클라이언트 경로 |
| `frontend/app/base-path.ts`, `frontend/app/page.tsx` | API·로고·홈·인증 링크가 루트 | 공통 경로 함수, AX 앱별 로그인 탭 알림 채널 | 기존 UI 크기·색상·흐름 유지 |
| `Dockerfile` | 고정 명령, 경로 빌드 인자 없음 | 경로 빌드 인자, 공통 진입점, 명시적 컨테이너 바인딩 | 기존 root 빌드/Free 서비스 구조 유지 |
| `backend/tests/test_ax_runtime.py` | 프록시·외부 쓰기·경로 쿠키 검사 없음 | 보존/제거 프록시, 업로드·저장·세 보고서·재시작·쿠키·설정 거부 검사 | 합성 자료만 사용 |
| `frontend/tests/ax-prefix.spec.ts`, `frontend/playwright.config.ts` | 하위 경로 화면 검사 없음 | PC/모바일 업로드·분석·제출·로그인·Excel·새로고침·홈 검사 | CI 브라우저 검사 |
| `scripts/verify_ax_container.py`, `deploy/ci.yml` | 비root·읽기 전용·재시작 확인 없음 | 단일 워커·할당 포트·읽기 전용 파일시스템·외부 볼륨·SIGTERM 검사 | CI의 임시 컨테이너에 한정 |
| `scripts/package_ax.py`, `scripts/package_source.py` | AX 등록용 평탄 ZIP 없음 | 전체 소스 + 경로 빌드 + 매니페스트·해시, 비밀/캐시 제외 | 등록 산출물 |
| `.env.example`, `AGENTS.md`, `HANDOFF.md`, `SETUP.md`, `CHANGELOG.md`, AX 안내 문서 | AX 재개·배포 방법 없음 | 환경·빌드·등록·검증·미검증 항목 기록 | 인수인계 |

## 검사 상태

| 검사 | 상태 | 근거/범위 |
|---|---|---|
| Windows 백엔드 전체 회귀 256개 | PASS | 2026-11-02 실행, AX 신규 검사 10개 포함 |
| 프런트 단위검사 15개 | PASS | 성명 변환과 다운로드 파일명 |
| `/apps/kywa-safety` 정적 빌드·TypeScript | PASS | Node22/Next16 정적 export 생성 |
| 접두 경로 보존/제거 프록시의 API·사진·세 보고서 | PASS | TestClient, 합성 자료, 원본 성명 미전송·권한·CSRF 유지 |
| PIN 세션 경로 분리·1시간 연장 | PASS | AX 쿠키가 root 앱에 전송되지 않음 |
| 잘못된 경로·포트·전체 프록시 신뢰·화면 경로 불일치 거부 | PASS | 자동검사 |
| Linux 의존성 설치·전체 회귀·PC/모바일 | NOT TESTED | CI 실행 대기 |
| 비root·읽기 전용·SIGTERM·재시작 | NOT TESTED | CI 실행 대기, Windows에 Docker 미설치 |
| 실제 AX Rocky/Apache/systemd 등록·재배포·승인 정책 | NOT TESTED | 실제 AX 서버 접근·등록 설정 미제공 |
| AX 출발 Google/AI/KOSHA 실연동 | NOT TESTED | AX 네트워크·서버 비밀설정 필요. 기존 Render의 7개 기관 실연동은 별도 완료 |
| 실제 Google 시트 호버 미리보기 | NOT TESTED | 기존 브라우저 사이트 접근 제한 유지 |

검사를 실행한 뒤 실패한 경우 수정 후 재검사 결과를 기록한다. 환경이 없는 항목을 PASS로 처리하지 않는다. 이 작업에서는 AX 업로드 한도/프록시 타임아웃/서비스 계정/보안 정책을 임의 수정하지 않았다.
