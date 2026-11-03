# 운영 연결 준비 및 다음 배포 반영 기록

갱신: 2026-09-29. 사용자가 제공한 운영 정보와 첨부 원본 코드에서 확인한 사항을 구분해 기록한다. 비밀키 값은 이 문서에 저장하지 않는다.

## 현재 상태

- 공개 개발 앱: https://kywa-safety.onrender.com — 마지막 배포는 체험 모드.
- GitHub: https://github.com/archi01-safety/kywa-safety-app, 개발 브랜치 `codex/kywa-next`, 초안 PR #1.
- 이번 분석 프롬프트 보강과 이 문서는 로컬에 준비했으며 다음 코드 반영·배포 대상이다. 현재 운영 시트에 쓰거나 공유 권한을 변경하지 않았다.

## 사용자에게 확인된 정보

2026-09-29 사용자 보고: Render에 `GOOGLE_SERVICE_ACCOUNT_JSON`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `SPREADSHEET_ID`, `SHEET_NAME`, `DRIVE_FOLDER_ID`, `KOSHA_API_KEY`, `HISTORY_SHEET_NAME`, `ACCESS_ACCOUNTS_JSON` 입력을 완료하고 기존 설정을 확인했다. 실제 값·JSON 유효성·적용된 배포·외부 API 인증 성공은 아직 확인하지 않았다.

사용자 요청에 따라 원본 개발 앱처럼 숫자 4자리 관리자 비밀번호를 입력해야 개선조치·결과보고서를 볼 수 있도록 구현했다. `AUTH_MODE=pin`, `ADMIN_PIN_HASH`를 사용하며 실제 비밀번호나 해시는 문서·소스에 넣지 않는다. 요청된 초기값의 해시는 로컬 전용 `local-data/auth/admin-pin.env`에 준비했다. PIN 방식에서는 Google OAuth 클라이언트 ID·Secret이 필요하지 않다. 기존 `ACCESS_ACCOUNTS_JSON`은 Google 로그인 방식의 계정 목록으로 남겨둘 수 있으나 PIN 인증에는 사용하지 않는다.

서버가 숫자 문자열을 검증하므로 앞자리 0을 보존한다. 비밀번호 해시는 무작위 salt와 PBKDF2-SHA256 600,000회로 생성한다. 계정 전체에서 15분 안에 5회 실패하면 15분 잠그며, 쿠키·IP를 바꿔도 같은 프로세스의 제한을 공유한다. 서버 세션은 로그인 후 1시간에 만료되고 로그아웃 시 폐기한다. 재시작하면 세션과 실패 횟수가 초기화되므로 단일 프로세스에서 사용한다. 4자리 공용 비밀번호는 개인별 인증보다 추측에 약하고 작업자 개인을 식별하지 못한다. 이력의 작업자는 Google 이메일로 가장하지 않고 `pin-admin`으로 기록한다. 다중 인스턴스 운영이나 재시작을 넘어 유지되는 잠금이 필요하면 영속 인증 저장소가 필요하다.

PIN 모드에서는 체험 관리자 우회 로그인과 Google 로그인 경로를 닫았다. 기존 Google 로그인 방식은 선택 가능한 대안으로 유지한다. 새 화면·PIN 인증·푸터는 로컬 검증을 완료했으며 GitHub/Render에는 아직 반영하지 않았다. 운영 저장소 전환 전까지 `APP_ENV=demo`를 유지한다.

| 항목 | 확정 정보 | 상태 |
|---|---|---|
| 운영 스프레드시트 ID | `1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q` | 기존 제출이 계속 누적되는 운영 원본 |
| 서비스 계정 | `kywa-safety-check@gen-lang-client-0053629470.iam.gserviceaccount.com` | 사용자가 편집자 공유 및 기존 자동 저장 동작을 확인함 |
| 운영 사진 폴더 ID | `13RYVnDB7rrqLQYzB5Wa9WdWr0CHjm_MW` | 원본 코드 폴더를 현재도 사용한다고 확인함 |
| 전체 시설 관리자 | `kywa_safety@kywa.or.kr` | 사용자 확인 완료. OAuth 로그인 연결은 미완료 |
| KOSHA 서비스 기본 주소 | `https://apis.data.go.kr/B552468/koshaguide` | 사용자 제공 |
| KOSHA 일반 인증키 | 사용자 제공 완료, 값은 문서·소스에 복사하지 않음 | Render `KOSHA_API_KEY` 등록 필요 |

스프레드시트 화면에서 문서명 `KYWA 실시간 위험성평가 DB`, 탭 `설문지 응답 시트1`, gid `413707311`을 읽기 전용으로 확인했다. 전체 행의 유효성과 A:W 전체 헤더 검증은 인증 후 이관 미리보기에서 수행한다.

원본 `app.py.txt`와 `app.py(dev).txt`에 기재된 Drive 폴더를 현재도 사용한다고 사용자가 확인했다. 새 앱 인증정보 등록 후 해당 폴더 업로드를 검증한다. 이번에는 Google에 쓰지 않았다.

## 로컬 개발 공간 및 실제 KOSHA 검증

사용자 요청에 따라 현재 개발 저장소는 Google 사본 대신 프로젝트의 `local-data/workbook-test`를 사용한다. 첨부 XLSX를 그대로 복사한 `source.xlsx`, 평가 129건의 `data.json`, 시험용 사진 처리 사본과 매칭 기록을 준비했다. `pic-test`의 JPG 181장 중 정확한 시설·제출시각 파일명으로 평가 113건에 사진을 연결했다. 개선 후 사진 1건은 대응 정보를 확인할 수 없어 임의 연결하지 않았다. 원래 점수·등급·셀 값은 보존했다.

`.venv/Scripts/python.exe scripts/start_workbook_test.py`로 실행하면 `http://localhost:8001`에서 사용한다. PC의 루프백에서만 접근하도록 제한하며 새 AI 분석은 가상 응답이다. 이 폴더는 GitHub/소스 ZIP/Docker 배포에서 제외한다. Google API 연동 시험이 필요해질 때 별도 Google 시험 저장소를 준비하며, 현재 로컬 시험에는 필요하지 않다.

제공된 KOSHA 키로 실제 `/getKoshaGuide` 요청과 새 검색 함수를 검증했다. `추락` 1건, `전기` 56건, HTTP 200/응답 코드 00. 각 검색의 첫 원문 PDF도 전체 다운로드·파일 시그니처·종료 표식을 확인했다. 인증 오류 코드를 빈 결과로 숨기지 않도록 보완했다. 결과는 `artifacts/kosha-verification.json`, 키 등록 상세 안내는 [SETUP-GUIDE.ko.md](SETUP-GUIDE.ko.md)에 있다. 이번 변경은 로컬에 있으며 Render 환경변수를 변경하거나 재배포하지 않았다.

## 다음 배포에 포함할 분석 기준

기존 운영 코드의 시설·부서·사진·설명 입력, 12개 표준 분류, 원인 중심 분류 우선순위, 장소 추출, 빈도 1~5·강도 1~4, 한국어 명사형 위험상황·감소대책을 유지한다. 새 앱의 Gemini JSON은 `items` 배열 안에 `category, location, scenario, p, s, law, solution`을 받고 구조·값을 검증한다. `score, grade`는 서버에서 계산해 최종 결과에 붙인다.

- 기존 예시의 '본관 2층 테라스'를 '본관 3층 복도'로 바꾸는 오류는 계승하지 않는다.
- 특정 단어만으로 강도·점수를 제한하거나 조치했다고 무조건 점수를 낮추는 지시는 계승하지 않는다.
- 근거 법령을 실시간 확인했다고 주장하지 않는다. 불확실한 조항 번호는 생략하고 원문 확인 필요를 표시한다.
- 현행 6단계 등급은 기존 합의대로 유지하고, 과거 기록의 등급은 재계산해 덮어쓰지 않는다.
- 실제 모델이 이 기준을 준수하는지는 키 등록 후 대표 현장 사례로 확인한다. 가상 응답 테스트만으로 분석 품질을 확인했다고 판단하지 않는다.
- 첨부 운영/개발 코드 모두 `gemini-3.6-flash`를 사용한다. 새 코드 기본값과 `.env.example`을 같은 모델로 맞췄다. Google 공식 모델 목록에서 모델명과 구조화 출력 지원을 확인했으며, 3.x 샘플링 파라미터 폐기 안내에 따라 고정 `temperature=0` 전달을 제거했다. 실제 프로젝트의 모델 호출/할당량 검증은 아직 하지 않았다.

## 저장 형식 및 운영 전환

| 열 | 저장 내용 |
|---|---|
| A:M | 타임스탬프, 시설명, 담당 부서, 장소, 유해위험요인, 위험상황, 빈도, 강도, 점수, 위험등급, 감소대책, 관련근거, 사진 기록 |
| N:R | 개선 후 빈도, 강도, 점수, 위험등급, 사진 기록 |
| S:W | 평가ID, 평가기준버전, 처리상태, 수정버전, 시스템데이터 |
| 조치이력 탭 | 조치ID, 평가ID, 처리시각, 처리자, 작업, 조치내용, 시스템데이터 |

기존 시트를 그대로 연결하는 것만으로는 이력 관리가 시작되지 않는다. 현재는 로컬 사본으로 조회·조치·보고서를 시험한다. Google 연결 검증 단계에서는 별도 시험 저장소로 읽기 전용 이관 점검 → 백업 → 이관 적용 → 분석·제출·사진·조치·보고서를 검증한다. 기존 앱이 새 행을 계속 쓰는 동안 운영 원본은 새 앱으로 이관하지 않는다.

최종 전환 시 기존 앱 쓰기를 중지하고 백업·이관을 끝낸 뒤 `SPREADSHEET_ID`를 운영 ID로, `APP_ENV=production`, `ALLOW_LEGACY_WRITES=true`로 설정한다. 지금은 이 설정을 적용하지 않는다. Render 인스턴스/프로세스는 1개로 유지한다.

## Render에 입력할 정보

서비스의 Environment에서 아래 Key/Value를 등록한다. 준비 중에는 Save only를 사용하고, 전체 설정과 이관을 확인한 뒤 배포한다. `APP_ENV`를 먼저 바꾸면 필수 설정 검사 때문에 서비스가 기동하지 않는다.

| 환경변수 | 준비할 값 |
|---|---|
| `GEMINI_API_KEY` | Gemini API 키. 채팅/공개 GitHub/Next.js 클라이언트에 입력하지 않고 Render에 직접 등록 |
| `GEMINI_MODEL` | `gemini-3.6-flash` — 첨부 운영 코드와 동일. 실제 프로젝트 사용 가능 여부는 키 등록 후 확인 |
| `KOSHA_API_KEY` | 제공한 일반 인증키. 서버에서 인코딩·요청 처리 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 위 서비스 계정의 인증 JSON 전체. 이메일만으로 서버 인증 불가 |
| `AUTH_MODE` | 이번 관리자 비밀번호 방식은 `pin` |
| `ADMIN_PIN_HASH` | 로컬 비밀 설정 파일의 동명 값 전체. 비밀번호 원문을 넣지 않음 |
| `SPREADSHEET_ID` | 시험은 별도 개발 시트 ID, 운영 전환은 위 운영 ID |
| `SHEET_NAME` | `설문지 응답 시트1` |
| `HISTORY_SHEET_NAME` | `조치이력` |
| `DRIVE_FOLDER_ID` | 운영은 `13RYVnDB7rrqLQYzB5Wa9WdWr0CHjm_MW`. 로컬 시험에서는 사용하지 않음 |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | `AUTH_MODE=google`일 때만 필요. PIN 방식에서는 추가할 필요 없음 |
| `ACCESS_ACCOUNTS_JSON` | `{"kywa_safety@kywa.or.kr":{"role":"admin","facilities":[]}}` |
| `APP_BASE_URL` | `https://kywa-safety.onrender.com` |
| `SESSION_SECRET` | 기존 Render 생성값 유지. 새로 생성하거나 채팅으로 보낼 필요 없음 |

푸터는 `C:/Users/user/Desktop/app.py(dev).txt`의 저작권·운영 방침·AI 결과 검토 안내·안전경영부 연락처(`archi01@kywa.or.kr`, `02-6959-7138`)를 참고했다. 2026-09-29 사용자가 유료 Tier 2 사용 및 옵트아웃 적용 확인을 알렸으므로, 해당 확인을 근거로 AI 분석에 전송되는 입력 정보의 모델 학습 미사용 안내를 추가했다. 제공업체·모델 이름은 이용자 안내에 표시하지 않는다. 데이터 이용 목적과 외부 AI 서비스 전송 안내는 유지한다. 기관 규정 전반의 준수 여부를 별도로 확인한 것은 아니므로 포괄적인 규정 준수 보장은 추가하지 않았다. 이번 수정은 로컬 개발 앱과 배포용 소스에 반영하며 Render에는 아직 배포하지 않았다.

OAuth 승인 리디렉션 URI: `https://kywa-safety.onrender.com/api/auth/google/callback`.

현재 앱은 `GOOGLE_SERVICE_ACCOUNT_JSON`의 JSON을 직접 읽는다. 기존 Streamlit Secrets의 `[gcp_service_account]` TOML 블록을 그대로 붙여 넣는 형식이 아니다. 같은 계정의 유효한 JSON 키 파일이 있으면 재사용 가능하다. 새 키 발급이 무조건 필요한 것은 아니다. 사용자 이메일 로그인만으로 Sheets/Drive 자동 저장 자격 증명을 대신하지 않는다.

## 권한 및 운영 확인

- Sheets API와 Drive API가 해당 Google Cloud 프로젝트에서 활성화되어 있어야 한다. 배포 서버는 Render이며 Cloud Run은 필요하지 않다.
- 기존 공유가 정상이라면 같은 서비스 계정에 운영 시트 권한을 다시 줄 필요는 없다. 개발 사본/새 사진 폴더의 권한은 따로 확인한다.
- Drive는 현재 저장 구성을 우선 확인한다. Google 문서상 서비스 계정은 자체 저장 용량/파일 소유권이 없으므로 공유 드라이브 또는 사용자 권한을 통한 업로드가 필요하다. 이미 승인된 도메인 위임이 있는 경우에만 기존 범위의 `GOOGLE_DELEGATE_EMAIL` 설정을 검토한다. 새 광범위 권한을 임의로 부여하지 않는다.
- 현재 운영 시트는 로그아웃 상태에서 링크로 열람 가능했다. 원본 앱은 공개 CSV로 조회하므로, 공유를 제한하면 기존 조회에 영향이 있다. 새 앱으로 전환한 뒤 인증된 서버 조회를 검증하고 접근 범위를 조정한다. 이번 작업에서는 공유를 바꾸지 않았다.
- 실제 대표 사례의 분석 품질, 중복 제출, 사진 저장·조회, 담당자 시설 권한, 100건 보고서, 오류/사용량·비용을 확인한다. 무료 서비스 운영 관찰과 HWPX 양식 확인은 별도 항목이다.

참고: [Render 환경변수](https://render.com/docs/configure-environment-variables), [Gemini 키 관리](https://ai.google.dev/gemini-api/docs/api-key), [Drive 서비스 계정 저장 제약](https://developers.google.com/workspace/drive/api/guides/handle-errors#storageQuotaExceeded).

모델 근거: [Gemini 3.6 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash), [Gemini API 변경 이력](https://ai.google.dev/gemini-api/docs/changelog).
