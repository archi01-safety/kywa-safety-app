# KYWA AI 위험성평가 시스템

Next.js 정적 화면과 Python/FastAPI를 기관별 독립 Render Docker 서비스로 운영합니다. 2026-11-16 배포 기록 기준 KYWA·AYF·FoWI·KHIDI·KNPS·KNF·KOHI·CAYF 모두 **v1.3.0**이며 실제 운영 소스는 `bacadc94e3f6bf4b87428552c1fac080e2680935`입니다. 공통 운영 브랜치는 `codex/kywa-next`입니다.

## 작업을 이어갈 때

1. [PROJECT-CONTEXT.ko.md](PROJECT-CONTEXT.ko.md)의 현재 상태와 이번 요청 관련 절을 읽습니다.
2. [HANDOFF.md](HANDOFF.md) 맨 위에서 마지막 작업·실제 배포·미검증 항목을 확인합니다.
3. [SETUP.md](SETUP.md)와 [CHANGELOG.md](CHANGELOG.md) 최근 항목을 필요한 만큼 확인합니다.
4. 새 대화/새 PC에는 [RESUME-PROMPT.ko.md](RESUME-PROMPT.ko.md)의 시작문을 사용합니다.

문서/패키지 HEAD가 바뀌어도 실제 서비스가 재배포된 것은 아닙니다. 실제 버전은 [Render 배포 기록](artifacts/render-deployments.json)과 기관별 `releases/<기관>/<버전>.json`, `<기관>/<버전>` 태그로 확인합니다. 과거 Streamlit 코드나 이전 작업 폴더를 최신 운영본으로 착각하지 않습니다.

## 현재 기능

- 현장 사진/설명 → AI 위험 관찰·기관별 서버 판정 → 검토/편집·선택 제출.
- 개선조치·조치계획·재평가·담당자 확인 완료와 변경 이력.
- Google Sheets/Drive 연동, 직접 행 삭제·셀 수정 반영, 요청번호 기반 중복 저장 방지.
- KOSHA 키워드 추천·원문 연결, 법제처 현행 법령 검증·제목 유일 일치 시 조문 번호 자동 보정.
- 최초 사진2장/개선후1장, 실제 형식 판별·대표 JPEG/MPO·HEIC 변환·AI 얼굴 탐지·타원형 블러·좌우90도 회전.
- 기관별 내부 세부 판정과 최대2개 선택 질문. 공개 점수는 기존 빈도1~5 × 강도1~4 및 기관별 등급을 유지.
- KYWA 등7개 기관 성명 필수·브라우저 초성 변환. **AYF는 부서·성명 미수집**.
- Excel 상세내역, PDF 및 편집 가능한 문단형 HWPX 보고서.
- 관리자 PIN 로그인·남은시간/수동연장·만료 후 초안 보존, 공통 진행/오류/사진 로딩 안내.
- 기관색·다크/라이트 테마·지원기관 KYWA 기술지원 표기. 기관별 예외는 공통 설정으로 관리.

일반 공개 시트20열, AYF18열이며 관리 정보는 숨김 탭에 보존합니다. 기존 기록을 현재 점수로 일괄 재계산하지 않습니다. 기관별 시설·부서·평가표·색상·수집 설정과 코드 위치는 PROJECT-CONTEXT에서 확인합니다.

## 로컬 실행

Python3.12와 Node22를 준비하고 앱 디렉터리 `kywa-next`에서 실행합니다. 새 PC의 상세 절차는 [SETUP.md](SETUP.md)를 따릅니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock -r backend/requirements-dev.txt
Copy-Item .env.example .env
cd frontend
npm ci
npm run build -- --webpack
cd ..
.\.venv\Scripts\python.exe app.py
```

기본 `.env.example`은 localhost:8000의 **체험 모드**입니다. 실제 Google/AI 연동 검증을 의미하지 않습니다. 실제 연동 시험은 별도 시트·사진 폴더·서버 인증정보를 사용하며 운영ID 기본값 상속에 주의합니다. 화면 수정 뒤에는 정적 빌드가 필요합니다.

현재 app.py는 Streamlit이 아니라 FastAPI 실행 진입점입니다. 운영에서 Next.js 서버를 별도로 실행하지 않습니다. Render는 Docker/PORT10000/root 경로, AX는 플랫폼 할당 PORT와 일치하는 빌드·서버 접두 경로를 사용합니다.

## 검증·배포·복구

현재 v1.3 검증 근거는 [artifacts/v1.3-verification.json](artifacts/v1.3-verification.json)에 있습니다. 백엔드483건·프런트20건·root/AX 빌드, 기관별 합성 사례/반복 분석·법령·출력을 검사했습니다. 합성 반복성을 실제 현장 판정 정확도나 모든 사진 구도의 보장으로 표현하지 않습니다.

GitHub Actions는 사용자 요청으로 **중지**했습니다. 새 PC·검증·복구를 이유로 워크플로를 되살리지 않습니다. 로컬 검사와 기관별 수동 Render 배포를 사용하며 무료 첫 접속 대기를 수용합니다. 절전 방지용 예약 호출은 추가하지 않습니다. `/healthz`는 외부 AI/Google API를 호출하지 않는 상태 확인입니다.

복구는 [기관별 버전 안내](releases/README.md)를 따릅니다. 기관별 태그/검증 SHA와 데이터 구조를 먼저 대조하고 신규 제출·사진·이력을 보존합니다. 과거 시트 사본으로 현재 데이터를 통째로 덮어쓰지 않습니다. Blueprint 전체 동기화와 기존 인증/PIN 교체를 임의 수행하지 않습니다.

## 문서와 산출물

| 용도 | 위치 |
|---|---|
| 최신 컨텍스트 / 재개 시작문 | [PROJECT-CONTEXT](PROJECT-CONTEXT.ko.md), [RESUME-PROMPT](RESUME-PROMPT.ko.md) |
| 날짜별 작업·설치 | [HANDOFF](HANDOFF.md), [SETUP](SETUP.md), [CHANGELOG](CHANGELOG.md) |
| v1.3 / 시트 직접 편집 | [법령·세부판정·회전](LEGAL-RISK-ROTATION-V1.3.ko.md), [시트 편집](SHEET-EDITING.ko.md) |
| 기관별 설정·저장소 | [기관별 설정](ORGANIZATION-SETUP.ko.md), [지원기관 전환](PARTNER-ROLLOUT.ko.md) — 현재 스키마/상태는 최신 컨텍스트 우선 |
| AX 설정·검증 한계 | [AX-DEPLOYMENT](AX-DEPLOYMENT.ko.md), [AX-VERIFICATION](AX-VERIFICATION.ko.md) |
| KYWA 앱 아이콘·4:3 썸네일 | [ARTWORK](ARTWORK.ko.md), [승인 B안](artwork/kywa-safety-icon-v1.png), [AX 썸네일](artwork/kywa-safety-thumbnail-v1.png) |
| 최신 소스 / AX 등록용 | [소스 ZIP](artifacts/kywa-safety-source.zip), [AX ZIP](artifacts/kywa-safety-ax.zip) |

API 키·인증 JSON·PIN/해시·세션 키·운영 데이터/사진·업무 백업은 공개 저장소에 포함하지 않습니다. AX test ver.의 설명·썸네일은 저장했으나 새 소스 등록/실연동은 AX 외부 비공개 설정 최초 설치와 서버 검증이 필요합니다. ZIP 업데이트 때 설정을 보존하는 절차는 AX-DEPLOYMENT를 따릅니다. 한글/기기별 검증 한계는 컨텍스트/인수인계서에서 구분합니다. 예전 구축 절차와 Streamlit 병행 이력은 HANDOFF 및 Git 이력을 참고합니다.
