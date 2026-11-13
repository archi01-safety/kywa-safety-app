# AX 호환 변경·검증 기록

## 2026-11-13 v1.1.2 갱신

소스 329f2f8384c6c94f3cdbe360dfadfbb41b9c024a의 [CI](https://github.com/archi01-safety/kywa-safety-app/actions/runs/43378019457) verify/ax가 성공했다. 백엔드337·프런트단위15·8개기관 PC/모바일과 root/AX, 비root·읽기전용·재시작 Docker를 통과했다. 최신 소스와 /apps/kywa-safety 정적 화면으로 ZIP을 재생성했다. 실제 AX 플랫폼 등록·AX 출발 외부 연동·한글2014·실제 모바일 진동·Google 시트 호버 미리보기는 계속 미검증이다. 실제 한글2020 문단·표·사진 편집/저장/재열기·공식 링크 열기·16건9쪽/30건16쪽 PDF 출력은 별도 통과했다. 아래 날짜가 이전인 검증 표는 당시 기록이다.

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
| Linux 의존성 설치·전체 회귀·기존 기관 PC/모바일 | PASS | CI 41415666818 verify 및 ax 모두 성공, root Docker 빌드 포함 |
| AX 하위 경로 PC/모바일 전체 입력·다운로드 | PASS | CI 41415666818 ax 작업, 두 화면 캡처 확인 |
| 비root·읽기 전용·SIGTERM·재시작 | PASS | CI ax 작업, UID10001·PORT8507·외부 볼륨·정상 종료 코드0·데이터/사진 보존 |
| 등록 ZIP을 푼 뒤 직접 실행 | PASS | Windows PORT8508, 홈/정적 경로/API, 소스 변경 없음 |
| 실제 AX Rocky/Apache/systemd 등록·재배포·승인 정책 | NOT TESTED | 실제 AX 서버 접근·등록 설정 미제공 |
| AX 출발 Google/AI/KOSHA 실연동 | NOT TESTED | AX 네트워크·서버 비밀설정 필요. 기존 Render의 7개 기관 실연동은 별도 완료 |
| 실제 Google 시트 호버 미리보기 | NOT TESTED | 기존 브라우저 사이트 접근 제한 유지 |

검사를 실행한 뒤 실패한 경우 수정 후 재검사 결과를 기록한다. 환경이 없는 항목을 PASS로 처리하지 않는다. 이 작업에서는 AX 업로드 한도/프록시 타임아웃/서비스 계정/보안 정책을 임의 수정하지 않았다.

초기 CI에서 Linux의 마이크로초 시계 차이로 세션 연장 검사의 동등 비교가 실패해 1초 허용 오차로 수정했다. 뒤이어 브라우저의 같은 문서 내 `#reports` 주소 변경을 화면에 반영하지 못하는 문제를 발견하여 `hashchange` 감지를 추가했고 AX 화면 검사를 통과했다. 숨기거나 건너뛴 실패 항목은 없다.

## 최종 디자인 포함 재검증

디자인 최종 커밋 `eee38a37f4bcd072f02d5c9d5ce5be19810c7704`의 CI 41420384220에서 백엔드 264개, 프런트 단위 15개, 8개 기관 PC/태블릿/모바일·다크/라이트 및 root/AX Docker를 통과했다. AX 비root·읽기 전용·외부 볼륨·정상 종료·재시작 검사도 다시 통과했다. AX 등록 ZIP에는 이 디자인과 최신 인수인계서를 포함한다. 실제 AX 등록과 외부 연동 미검증 범위는 위 표와 같다.


## 2026-11-03 KYWA 보정·AYF 시설 중심 버전

검증 커밋 `939dbe4cdca9967766b6440610cd269100ee4f5b`의 [CI 41568061328](https://github.com/archi01-safety/kywa-safety-app/actions/runs/41568061328) verify/ax 모두 통과. Linux 백엔드 268개, 프런트 단위 15개, 기관별 화면과 root/AX Docker·비root·읽기 전용·재시작 검사를 통과했다. 로컬 AX 정적 export도 `/apps/kywa-safety`로 재빌드했다. 새 ZIP은 `artifacts/kywa-safety-ax.zip`, 해시·크기·파일 개수는 `artifacts/ax-package.json`을 따른다. PIN 원문/해시와 비공개 백업은 포함하지 않는다.

KYWA 흰 헤더/분석 버튼 복원 및 AYF 부서·성명 제거를 포함한다. Render 배포의 최종 결과는 HANDOFF.md에 별도로 기록한다. 실제 AX 등록은 수행하지 않았다.
