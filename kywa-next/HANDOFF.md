# KYWA 개발·운영 인수인계

최종 갱신: 2026-11-02. 이 문서는 새 PC와 새 대화에서 가장 먼저 읽는 현재 상태 문서다. 과거 날짜가 적힌 DEPLOYMENT-NOTES.md 등의 기록과 충돌하면 현재 상태를 실제 서비스에서 확인한다.

## AX 호환 준비와 다음 작업

7개 지원기관 배포를 완료한 뒤 사용자 TXT 요청에 따라 AX `/apps/{slug}/` 호환 작업을 진행했다. `app.py`가 PORT/HOST를 받아 실행하며 정적 화면과 서버의 APP_BASE_PATH를 일치시킨다. 데이터·임시 폴더는 소스 밖으로 설정할 수 있다. 백엔드 256개·프런트 단위 15개·접두 경로 빌드를 로컬에서 통과했다. Linux/PC/모바일 CI 상태와 최종 ZIP은 AX-VERIFICATION.ko.md 및 artifacts/ax-package.json을 확인한다.

AX 서버/Apache/systemd와 8개 Render 운영 서비스는 이 AX 작업에서 변경하지 않는다. GitHub 최신 코드와 운영 배포 버전은 다르다. AX 등록 시 실제 슬러그·할당 포트·쓰기 폴더·비밀설정이 필요하며 AX-DEPLOYMENT.ko.md를 따른다. 사용자가 추가한 다음 작업은 7개 기관의 지정 메인·서브 컬러 적용이며 KYWA 핑크 테마는 유지한다.

## 작업 위치와 운영 원칙

- 저장소: https://github.com/archi01-safety/kywa-safety-app
- 작업 브랜치: `codex/kywa-next`, 앱 폴더: `kywa-next`, PR: https://github.com/archi01-safety/kywa-safety-app/pull/1
- KYWA: https://kywa-safety.onrender.com/ — 현재 운영 커밋을 유지하며 이번 지원기관 배포에서 제외한다.
- Next.js 정적 화면과 FastAPI를 하나의 무료 Docker 웹서비스에서 구동한다. 첫 접속 대기를 수용하며 절전 방지 주기 호출은 추가하지 않는다.
- 기관별 독립 서비스·Google 저장소·평가표·색상을 유지한다. 승인된 후속 작업은 AYF 연결과 7개 지원기관 개선 적용이다. 배포는 AYF → FoWI → KHIDI → KNPS·KNF·KOHI·CAYF 순서로 개별 수행한다.
- 브랜치 최신 코드와 실제 배포는 다를 수 있다. 2026-11-02 KYWA 배포 커밋은 `8b396719eb84fd8badf3f1246908a00cb8391eee`, Render 배포는 `dep-dbk1ffajnfac739aj3gg`(Live)이다. 이후 문서 갱신만으로 운영 코드가 바뀌지는 않는다.

## 지원기관 개선 — 7개 기관 배포·운영 검증 완료

2026-11-02 AYF → FoWI → KHIDI → KNPS → KNF → KOHI → CAYF 순서로 커밋 `d1d195fd833bc810af8bce34562666edf9d26fe3`를 개별 배포했다. AYF는 전용 시트와 기존 공용 사진 폴더를 연결하여 production으로 전환했다. KYWA 운영 커밋·시트·서비스 설정은 변경하지 않았다. 전체 Blueprint 동기화와 절전 방지 호출은 수행하지 않았다.

| 기관 | 보존한 기존 평가 | 저장 구조 | 배포 및 운영 검증 |
|---|---:|---|---|
| [AYF](https://ayf-safety.onrender.com) | 0건 | 19열 + 숨김 관리 | 완료 |
| [FoWI](https://fowi-safety.onrender.com) | 131건 | 19열 + 숨김 관리 | 완료 |
| [KHIDI](https://khidi-safety.onrender.com) | 98건 | 19열 + 숨김 관리 | 완료 |
| [KNPS](https://knps-safety.onrender.com) | 96건 | 19열 + 숨김 관리 | 완료 |
| [KNF](https://knf-safety.onrender.com) | 13건 | 19열 + 숨김 관리 | 완료 |
| [KOHI](https://kohi-safety.onrender.com) | 125건 | 19열 + 숨김 관리 | 완료 |
| [CAYF](https://cayf-safety.onrender.com) | 6건 | 19열 + 숨김 관리 | 완료 |


기관별 전체 파일을 비공개 공유 드라이브에 백업하고 로컬 값·서식·이력 스냅샷을 남겼다. 기존 6개 기관의 관리 5열을 숨김 `_시스템관리`로 이관했고 KHIDI D열 ‘이름’을 보존했다. 공개 사진 폴더에 업무 백업을 저장하지 않았다. 이전 24열 이관 기록을 근거로 관리 열을 다시 추가하지 않는다.

`experience_version=2`로 개선 입력·홈 초기화·진행 팝업·타원형 머리 블러·수동 로그인 연장·행 삭제/수정·Excel/PDF/문단형 HWPX를 적용한다. `branding.technical_support`로 7개 기관의 공동 기관명·기술지원 안내·Powered by KYWA·개발자정보 팝업을 표시한다. 기관별 점수표·원본 프롬프트 지침·색상·사진 폴더는 유지한다. AYF는 CAYF 지침을 따른다.

[CI 41403837004](https://github.com/archi01-safety/kywa-safety-app/actions/runs/41403837004)의 백엔드·프런트 단위·Next 빌드·KYWA 회귀·7개 기관 PC/모바일 테마 및 동작·Docker 검사를 통과했다. 7개 비공개 사본에서 기존 값/이력 보존, 재이관, 직접 수정/삭제, 잘못된 행 격리, 요청 재시도, 기존 Streamlit 방식 append, 최초/개선 후 사진, 공유 폴더 기관 구분, 조치이력을 검사했다.

7개 운영 서비스에서 실제 AI 탐지/블러→분석→사진·평가 제출→동일 요청 재시도→재평가/조치→재조회와 시설/전체 각각 Excel·PDF·HWPX 총 42개 다운로드를 확인했다. 사진 바이트·공식 Drive 링크·Roboto 서식·파일명 및 기록 일치를 대조했다. 로그인 1시간 연장·로그아웃·KOSHA 조회도 통과했다. 시험 행·사진만 정리했고 기존 평가/조치/성명/사진/버전/시각은 보존했다. 삭제된 시험 요청과 감사 이력은 복구 정책상 숨김 관리에 남는다.

실제 한글 2020에서 AYF 5등급/FoWI 6등급 16건 HWPX를 각각 9쪽 PDF로 출력했다. FoWI 일반 문단을 편집·저장·닫기·재열기하여 수정 유지도 확인했다. 표/사진 편집 경로는 기존 공통 생성기의 KYWA 검증과 함께 적용한다. KHIDI Excel의 실제 인쇄 화면에서 활성 시트·한 부씩·A3 가로·보통 여백·모든 열 한 페이지를 확인했다.

미검증 범위: 저장된 브라우저 권한이 AYF 운영 화면과 Google Sheets를 차단하여 AYF 운영 UI 직접 조작 및 시트 호버 미리보기는 완료로 표시하지 않는다. 7개 기관의 PC/모바일 화면 검증은 승인된 CI에서 수행했고, 접근 가능한 운영 사이트는 기관명·지원 안내·팝업·홈 초기화를 추가 확인했다. 한글 2014·실제 모바일 진동·다른 PC 프린터 설정은 별도 확인이 필요하다. 기존 Streamlit 웹 화면 자체가 아닌 기존 append 저장 방식으로 호환을 검사했다.

현재 검증 요약은 `artifacts/partner-rollout-verification.json`, 실제 Render 배포는 `artifacts/render-deployments.json`에 기록한다. 비공개 근거는 `local-data/partner-rollout/`의 targets/extended, production/*/cloud-backup·migration·baseline·live, documents/native-verification, ci-ui에 보관하며 GitHub에 올리지 않는다. 운영·복구 절차는 PARTNER-ROLLOUT.ko.md를 따른다.

## 사진·저장 속도·다운로드 개선 — KYWA 배포 완료

새 사진의 머리 윤곽 타원 블러, 시설·한국 시각 파일명, Drive 공식 링크, 저장 작업 내 조회 재사용과 스레드별 Google 클라이언트, 서버 확정 보고서 파일명을 구현했다. 2026-11-02 이전 사진/링크는 변경하지 않는다. 최종 CI [41390527355](https://github.com/archi01-safety/kywa-safety-app/actions/runs/41390527355)의 백엔드 224개·프런트 단위 15개·PC/모바일·기관 테마·Docker 검사를 통과하고 KYWA만 배포했다. 사본에서 최초/개선 후 사진·동일 요청 재사용·같은 초의 별도 사진·공식 클릭 링크·Roboto 10pt·처리 이미지 바이트 일치를 확인했고, 행 삭제/직접 수정/잘못된 행 격리 후 신규 제출도 재검증했다. 운영에서 실제 얼굴 블러→분석→최초/개선 후 사진 저장, 사진 바이트·공식 링크 일치, 동일 요청 재사용, 시설/전체 조회의 6개 보고서 파일명과 재다운로드 고정을 확인했다. 시험 행 1건과 사진 2개만 정리하고 기존 136건의 평가·조치·사진 링크·성명·버전·시각 보존을 대조했다. 운영 배포 직후 사진 제출 1회는 14.54초였으며 사본 반복 측정과 실행 환경이 다르다. docs.google.com 브라우저 접근 제한으로 호버 미리보기는 미검증이다. 자세한 기준과 성능 비교는 [PHOTO-STORAGE.ko.md](PHOTO-STORAGE.ko.md)를 따른다.

## 시트 직접 삭제·수정 지원 — 배포·운영 검증 완료

2026-11-02 후속 작업. 행 삭제 후 과거 행 연결 오류가 신규 제출까지 막던 문제를 수정했다. KYWA 운영 시트를 전체 백업하고 135건에 Google 행 식별정보를 연결했으며, 일치하는 실제 행이 없는 관리 기록 4건은 삭제 상태로 보관했다. 평가 탭 19열·기존 값·기존 조치이력 3건은 변경하지 않았다. KYWA만 새 코드를 배포했으며 실제 제출·중복 재시도·직접 수치 수정·중간 행 삭제·삭제 후 추가·삭제된 요청 재시도 차단·오래된 보고서 차단과 Excel/PDF/HWPX 출력을 확인했다. 시험 행만 정리한 뒤 기존 135건의 ID·최초/개선 평가·사진 링크·성명·처리상태·수정 버전·시각이 모두 그대로임을 대조했다. 신규 앱 쓰기는 재개됐다.

- `backend/sheet_sync.py`, `migrate_row_identity.py`: 안정적인 행 ID, 요청별 중복 확인, 행 추가/요청 원자적 저장, 삭제·직접 수정 감지, 부분 갱신·복구.
- `frontend/app/sheet-issues.tsx`: 행별 확인 사항·현재 기준 적용. 조치 초안 보존 및 최신 보고서 확인 포함.
- CI [41382098619](https://github.com/archi01-safety/kywa-safety-app/actions/runs/41382098619): 백엔드 211개, 프런트 단위 13개, Next 빌드, PC/모바일, 다른 기관 테마 회귀, Docker 통과. PC/모바일의 확인 필요 안내 화면도 시각 검토했다. 로컬 브라우저 실행은 완료되지 않아 승인된 CI에서 검사했다.
- 공유 드라이브 사본: 첫/중간/마지막/전체 행 삭제, 마지막 A:S 지우기 후 추가, 직접 수정·15점 높음·잘못된 행 격리·과거 기준 확정·조치 저장·Streamlit 추가 검증 완료.
- 운영 시험 중 제출 1회가 일시적인 HTTP 502로 중단됐다. 숨김 요청 기록과 실제 행에 저장되지 않았음을 확인하고 새 시험을 이어갔으며, 중복 행 없이 완료했다. 테스트용 삭제 기록과 이력은 복구 정책에 따라 내부에 남고 목록·통계·보고서에는 포함되지 않는다.
- 운영 절차·범위·복구는 [SHEET-EDITING.ko.md](SHEET-EDITING.ko.md)를 따른다. 일부 열만 정렬하거나 서로 다른 평가의 셀을 섞지 않는다. 같은 셀을 앱과 시트에서 동시에 수정하지 않는다.

## 이전 개선과 검증 상태(시트 직접 편집 배포 당시)

| 항목 | 현재 상태 |
|---|---|
| 평가표 24/20열 → 19열 이관 | 사본 검사 후 운영 이관 완료. 관리 5열을 숨김 탭으로 이전하고 평가 탭에서 실제 삭제. 앞선 19열 이관 당시 평가 138건·조치이력 3건의 값과 연결 일치. 이후 관리자 삭제를 반영한 현재 활성 평가는 135건이며 위 후속 검증 완료 |
| 시트 삭제·수정 및 신규 제출 | 운영 135건 연결·기존 4건 삭제 상태 분리. 실제 신규 제출/재시도, 직접 수정 15점 높음, 중간 행 삭제 후 새 행 추가, 삭제 요청 재전송 거부 및 3종 보고서 확인 완료 |
| 날짜·서식·표 범위 | 운영 Asia/Seoul·ko_KR, 실제 날짜값·한국어 표시, Roboto 10pt·열별 서식·Form_Responses 표 자동 확장 확인. 실제 신규 시험 값은 `2026. 11. 2 오전 9:59:26`으로 표시 |
| 로그인 연장·문구·전송 버튼 | PC·모바일의 연장·만료·재로그인 초안 복원 검사 통과 |
| Excel | 열 정리·정수·성명 변환·A3 가로·페이지 나누기 보기·사진 앵커 자동 검사 완료. 실제 Excel 인쇄 화면에서 활성 시트·단면·한 부씩·A3 가로·보통 여백·가로 1페이지 설정 확인 |
| 문단형 HWPX | 일반 문단·실제 표·셀 사진 생성 및 1·2·3·16·30건 구조 검사 완료. 한글 2020에서 16건 9쪽·30건 16쪽 출력, 문단·표·사진 편집 → 저장 → 닫기/재열기 → PDF 출력 확인 |
| 보고서 총평 | PDF/HWPX 동일 모델·사진 캐시, 오류 분류와 사실 검증 1회 자동 수정 구현 |
| 백엔드 | 시트 동기화 포함 최신 CI 211개 검사 통과 |
| GitHub/Render | 이번 코드·검사 11개 파일의 로컬/원격 내용 일치 확인. CI 41382098619 통과, KYWA 2db732e 배포 완료. 다른 기관 배포 금지 |
| 앞선 운영 제출·재평가 검사 | 실제 사진 탐지/모자이크 → 분석 → 제출 → Drive 사진 바이트 대조 → 재평가/조치 → 동일 요청 재시도 검사 통과. 시험 기록·조치·사진만 정리하고 기존 138건·3건 보존. 운영 UI에서 문구와 로그인 연장 60:00 확인 |
| 앞선 운영 보고서 검사 | 평창 실제 16건으로 PDF 9쪽·문단형 HWPX·Excel 다운로드 완료. 제목·본문/붙임·제외 항목·HWPX 일반 문단/실제 표·Excel 21열/정수/A3 가로/페이지 나누기 보기 확인 |

## 중요한 결정과 파일

- `backend/organizations/`, `backend/policies/`: 기관별 시설·부서·성명 설정과 서버 점수표. KYWA 6등급 및 15점 '높음' 유지.
- `backend/prompts.py`의 `kywa_prompt`: KYWA 분석 지침. 과거 등급은 새 기준으로 재계산하지 않는다.
- `backend/compact_storage.py`, `migrate_compact.py`, `sheet_format.py`: 평가 탭 A:R + S 제출자 성명, `_시스템관리`에 평가ID·평가기준버전·처리상태·수정버전·시스템데이터 및 요청 관리. 조치이력 탭 유지. 행 직접 삭제·수정은 현재 활성화된 `sheet_sync.py`의 v2 경로로 처리한다. 이전 코드만 단독 롤백하지 않는다. SHEET-EDITING.ko.md를 확인한다.
- `backend/report_model.py`, `report_semantic.py`, `report_layout.py`, `report_jobs.py`: 집계·검증된 총평·PDF/HWPX 공통 모델 및 작업 API.
- `backend/excel_kywa.py`, `chart_colors.py`: KYWA Excel 출력과 고정 분류/시설 색상.
- `tools/hwpx/`: 문단형 HWPX 생성 소스·의존성·라이선스. 실행 파일은 `backend/assets/hwpx-semantic.cjs`.
- `frontend/app/session-clock.tsx`, `page.tsx`: 로그인 만료/연장·초안 보존·기관별 UI.
- 실명 입력은 브라우저 메모리에서만 보유하고 성+초성 변환값만 제출한다. 분석·재평가에 성명 필드를 보내지 않는다.
- 사진 머리 영역 탐지 → 타원 블러 → 처리 사진으로 분석. 실패 시 원본으로 분석/제출을 진행하지 않는다.

## 다음 작업과 검증 범위

1. 지원기관 개선은 완료됐다. 후속 수정은 대상 기관·배포 커밋·현행 시트 구조를 확인한 뒤 진행하고, KYWA 변경은 별도 요청 범위에 따른다.
2. 현재 운영 평가표는 19열이다. 새 PC에서 예전 24열 이관 계획을 보고 재이관하거나 기존 데이터를 되돌리지 않는다. 변경 전 실제 헤더·배포 커밋을 재확인한다.
3. 한글 2020의 문단·표·사진 편집/저장/재열기/PDF 출력은 완료했다. 30건 검사는 배치 검증용 복제 자료로 16쪽을 확인했으며, 실제 30건 총평 정확성 검사와 구분한다. 한글 2014와 실제 모바일 기기의 물리적 진동은 미검증이다.
4. 단면·한 부씩 인쇄는 검증 PC에서 확인했으며 다른 PC의 프린터 드라이버 설정은 다시 확인한다.

## 이번 사진 개선의 비공개 검증 근거

- `local-data/blur-production-backup.json`: 배포 전 운영 파일 전체 값·서식·메타데이터와 같은 공유 드라이브의 전체 사본 위치.
- `local-data/blur-benchmark-before.json`, `blur-benchmark-after.json`, `blur-api-count-before.json`, `blur-api-count-after.json`: 같은 사본·사진의 시간 및 호출 수 비교.
- `local-data/blur-copy-verification.json`, `blur-visual/`: 실제 Google 저장·링크·행 삭제/수정 회귀, 실제 AI 머리 탐지/블러 결과.
- `local-data/blur-remote-verification.json`, `blur-ci-final.json`, `ci-blur/`, `render-blur-live.png`: 공개 소스 일치, CI/PC·모바일 및 Render Live 증거.
- `local-data/live-blur/`: 실제 신규 사진·재평가·제출/중복 재시도·PDF/Excel/HWPX와 최종 기존 기록 대조. 업무 데이터/사진이므로 GitHub 업로드 금지.

## 운영 백업·검증 근거(비공개)

운영 변경 전 공유 드라이브에 파일 전체 사본을 만들고, 로컬 값·서식·표·조치이력 및 숨김 백업 탭을 보관했다. 복구 절차는 KYWA-UPGRADE.ko.md를 따른다. 아래 자료는 GitHub에 업로드하지 않는다.

- `local-data/row-backups/row-identity-20261102-122233.json` 및 같은 접두어 `.cloud.json`: 행 식별정보 적용 직전 전체 백업과 공유 드라이브 사본 위치.
- `local-data/row-sync-production-migration.json`: 135건 연결·4건 삭제 상태·19열·값/기존 이력 보존 결과.
- `local-data/row-sync-copy-verification.json`, `live-row-sync/verification.json`: 사본 및 실제 제출·삭제·수정·재시도·출력 검사. 실제 보고서는 같은 비공개 폴더에 보관.
- `local-data/row-sync-remote-verification.json`, `ci-row-sync/`, `row-sync-ci-success.png`, `render-row-sync-live.png`: 원격 소스 일치, PC/모바일 화면, CI/배포 근거.

- `local-data/production-migration-result.json`, `production-cloud-backup.json`: 운영 이관 결과와 공유 드라이브 백업 위치.
- `local-data/migration-backups/kywa-compact-20261102-095758-e8ca32.json` 및 같은 접두어의 `-latest-values.json`: 이관 직전 전체 백업과 최종 값.
- `local-data/live-followup/verification.json`: 실제 제출·재평가·중복 재시도·시험 자료 정리 증거.
- `local-data/live-followup-reports/verification.json`, `structure-verification.json`: 운영 16건의 PDF/HWPX/Excel 및 구조 검증. 같은 폴더에 실제 출력물을 비공개 보관.
- `local-data/semantic-live/native-validation.json`, 한글 PDF·편집본·Excel 인쇄 화면: 실제 앱 검증 근거.
- `local-data/ci-final/`, `ci-success-nov2.png`, `render-live-nov2.png`: CI 및 배포 확인 화면.

## 새 PC와 이동 전 백업

새 PC 실행 절차는 SETUP.md를 따른다. GitHub에는 소스·설명서·검증 요약을 보관한다. 인증정보와 실제 데이터는 접근이 제한된 별도 저장소로 이전한다. 기존 PC의 `secret`, `local-data` 및 업무 보고서는 공개 저장소에 포함하지 않는다.

이동 직전에는 당시 HEAD·배포 커밋·시트 구조·남은 작업을 다시 확정하고 소스 패키지 해시와 비공개 백업 목록을 기록한다. 지금은 최종 이동 백업을 수행하지 않는다. 대화 전문 대신 결정 이유·검증 근거·미완료 사항을 유지한다.
