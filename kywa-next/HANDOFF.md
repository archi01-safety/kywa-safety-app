# KYWA 개발·운영 인수인계

최종 갱신: 2026-11-02. 이 문서는 새 PC와 새 대화에서 가장 먼저 읽는 현재 상태 문서다. 과거 날짜가 적힌 DEPLOYMENT-NOTES.md 등의 기록과 충돌하면 현재 상태를 실제 서비스에서 확인한다.

## 작업 위치와 운영 원칙

- 저장소: https://github.com/archi01-safety/kywa-safety-app
- 작업 브랜치: `codex/kywa-next`, 앱 폴더: `kywa-next`, PR: https://github.com/archi01-safety/kywa-safety-app/pull/1
- KYWA: https://kywa-safety.onrender.com/ — Render의 KYWA 서비스만 수동 배포한다.
- Next.js 정적 화면과 FastAPI를 하나의 무료 Docker 웹서비스에서 구동한다. 첫 접속 대기를 수용하며 절전 방지 주기 호출은 추가하지 않는다.
- 기관별 독립 서비스·Google 저장소·평가표·색상을 유지한다. KYWA 검토 전 다른 7개 기관은 기존 배포 `b618db5`를 유지한다. AYF는 전용 시트 제공 전 준비 모드다.
- 브랜치 최신 코드와 실제 배포는 다를 수 있다. 2026-11-02 KYWA 배포 커밋은 `3afbcc746a8df1f9a361435413d321ca99f5c156`, Render 배포는 `dep-dbjtvd2jnfac7391mmt0`(Live)이다. 이후 문서 갱신만으로 운영 코드가 바뀌지는 않는다.

## 현재 개선과 검증 상태

| 항목 | 현재 상태 |
|---|---|
| 평가표 24/20열 → 19열 이관 | 사본 검사 후 운영 이관 완료. 관리 5열을 숨김 탭으로 이전하고 평가 탭에서 실제 삭제. 기존 평가 138건·조치이력 3건의 값과 연결 일치. 검증 중 신규 앱 쓰기를 중지하고 완료 후 재개 |
| 날짜·서식·표 범위 | 운영 Asia/Seoul·ko_KR, 실제 날짜값·한국어 표시, Roboto 10pt·열별 서식·Form_Responses 표 자동 확장 확인. 실제 신규 시험 값은 `2026. 11. 2 오전 9:59:26`으로 표시 |
| 로그인 연장·문구·전송 버튼 | PC·모바일의 연장·만료·재로그인 초안 복원 검사 통과 |
| Excel | 열 정리·정수·성명 변환·A3 가로·페이지 나누기 보기·사진 앵커 자동 검사 완료. 실제 Excel 인쇄 화면에서 활성 시트·단면·한 부씩·A3 가로·보통 여백·가로 1페이지 설정 확인 |
| 문단형 HWPX | 일반 문단·실제 표·셀 사진 생성 및 1·2·3·16·30건 구조 검사 완료. 한글 2020에서 16건 9쪽·30건 16쪽 출력, 문단·표·사진 편집 → 저장 → 닫기/재열기 → PDF 출력 확인 |
| 보고서 총평 | PDF/HWPX 동일 모델·사진 캐시, 오류 분류와 사실 검증 1회 자동 수정 구현 |
| 백엔드 | 2026-11-02 로컬 180개 검사 통과 |
| GitHub/Render | 소스 34개 파일 대조 완료. CI [41369256020](https://github.com/archi01-safety/kywa-safety-app/actions/runs/41369256020)에서 백엔드 180개·프런트 단위 13개·빌드·PC/모바일·기관 테마·Docker 통과. KYWA 3afbcc7 배포 완료. 다른 기관 배포 금지 |
| 운영 제출·재평가 | 실제 사진 탐지/모자이크 → 분석 → 제출 → Drive 사진 바이트 대조 → 재평가/조치 → 동일 요청 재시도 검사 통과. 시험 기록·조치·사진만 정리하고 기존 138건·3건 보존. 운영 UI에서 문구와 로그인 연장 60:00 확인 |
| 운영 보고서 | 평창 실제 16건으로 PDF 9쪽·문단형 HWPX·Excel 다운로드 완료. 제목·본문/붙임·제외 항목·HWPX 일반 문단/실제 표·Excel 21열/정수/A3 가로/페이지 나누기 보기 확인 |

## 중요한 결정과 파일

- `backend/organizations/`, `backend/policies/`: 기관별 시설·부서·성명 설정과 서버 점수표. KYWA 6등급 및 15점 '높음' 유지.
- `backend/prompts.py`의 `kywa_prompt`: KYWA 분석 지침. 과거 등급은 새 기준으로 재계산하지 않는다.
- `backend/compact_storage.py`, `migrate_compact.py`, `sheet_format.py`: 평가 탭 A:R + S 제출자 성명, `_시스템관리`에 평가ID·평가기준버전·처리상태·수정버전·시스템데이터 및 요청 관리. 조치이력 탭 유지. 운영 탭 수동 행 이동·삭제·정렬은 동시 운영 지원 밖이다.
- `backend/report_model.py`, `report_semantic.py`, `report_layout.py`, `report_jobs.py`: 집계·검증된 총평·PDF/HWPX 공통 모델 및 작업 API.
- `backend/excel_kywa.py`, `chart_colors.py`: KYWA Excel 출력과 고정 분류/시설 색상.
- `tools/hwpx/`: 문단형 HWPX 생성 소스·의존성·라이선스. 실행 파일은 `backend/assets/hwpx-semantic.cjs`.
- `frontend/app/session-clock.tsx`, `page.tsx`: 로그인 만료/연장·초안 보존·기관별 UI.
- 실명 입력은 브라우저 메모리에서만 보유하고 성+초성 변환값만 제출한다. 분석·재평가에 성명 필드를 보내지 않는다.
- 사진 얼굴 탐지 → 모자이크 → 처리 사진으로 분석. 실패 시 원본으로 분석/제출을 진행하지 않는다.

## 다음 작업과 검증 범위

1. KYWA 사용자 검토 결과에 따라 후속 수정한다. 다른 기관 적용은 사용자가 결정한 뒤 기관별 기준을 보존하며 진행한다.
2. 현재 운영 평가표는 19열이다. 새 PC에서 예전 24열 이관 계획을 보고 재이관하거나 기존 데이터를 되돌리지 않는다. 변경 전 실제 헤더·배포 커밋을 재확인한다.
3. 한글 2020의 문단·표·사진 편집/저장/재열기/PDF 출력은 완료했다. 30건 검사는 배치 검증용 복제 자료로 16쪽을 확인했으며, 실제 30건 총평 정확성 검사와 구분한다. 한글 2014와 실제 모바일 기기의 물리적 진동은 미검증이다.
4. 단면·한 부씩 인쇄는 검증 PC에서 확인했으며 다른 PC의 프린터 드라이버 설정은 다시 확인한다.

## 운영 백업·검증 근거(비공개)

운영 변경 전 공유 드라이브에 파일 전체 사본을 만들고, 로컬 값·서식·표·조치이력 및 숨김 백업 탭을 보관했다. 복구 절차는 KYWA-UPGRADE.ko.md를 따른다. 아래 자료는 GitHub에 업로드하지 않는다.

- `local-data/production-migration-result.json`, `production-cloud-backup.json`: 운영 이관 결과와 공유 드라이브 백업 위치.
- `local-data/migration-backups/kywa-compact-20261102-095758-e8ca32.json` 및 같은 접두어의 `-latest-values.json`: 이관 직전 전체 백업과 최종 값.
- `local-data/live-followup/verification.json`: 실제 제출·재평가·중복 재시도·시험 자료 정리 증거.
- `local-data/live-followup-reports/verification.json`, `structure-verification.json`: 운영 16건의 PDF/HWPX/Excel 및 구조 검증. 같은 폴더에 실제 출력물을 비공개 보관.
- `local-data/semantic-live/native-validation.json`, 한글 PDF·편집본·Excel 인쇄 화면: 실제 앱 검증 근거.
- `local-data/ci-final/`, `ci-success-nov2.png`, `render-live-nov2.png`: CI 및 배포 확인 화면.

## 새 PC와 이동 전 백업

새 PC 실행 절차는 SETUP.md를 따른다. GitHub에는 소스·설명서·검증 요약을 보관한다. 인증정보와 실제 데이터는 접근이 제한된 별도 저장소로 이전한다. 기존 PC의 `secret`, `local-data` 및 업무 보고서는 공개 저장소에 포함하지 않는다.

이동 직전에는 당시 HEAD·배포 커밋·시트 구조·남은 작업을 다시 확정하고 소스 패키지 해시와 비공개 백업 목록을 기록한다. 지금은 최종 이동 백업을 수행하지 않는다. 대화 전문 대신 결정 이유·검증 근거·미완료 사항을 유지한다.
