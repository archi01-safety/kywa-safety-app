# KYWA 서버 인증·API 키 설정 안내

2026-09-29. 현재 Render 앱은 체험 모드이다. 키를 저장해도 `APP_ENV=demo`인 동안 실제 Gemini 분석이나 Google 저장으로 전환되지 않는다.

## 현재 선택한 관리자 로그인: 숫자 4자리 비밀번호

원본 개발 앱처럼 개선조치·결과보고서 탭 진입 시 관리자 비밀번호를 입력하는 방식을 로컬에 구현했다. 요청한 초기 비밀번호로 로컬 로그인을 확인했다. Google OAuth 설정은 이 방식에서 필요하지 않으며, 아래 Google 로그인 설명은 `AUTH_MODE=google`을 선택할 때만 적용한다. 자동 저장용 `GOOGLE_SERVICE_ACCOUNT_JSON`은 계속 필요하다.

다음 두 환경변수를 Render에 추가하고 우선 **Save only**로 저장한다.

| Key | Value |
|---|---|
| `AUTH_MODE` | `pin` |
| `ADMIN_PIN_HASH` | 프로젝트 `local-data/auth/admin-pin.env`의 `ADMIN_PIN_HASH=` 뒤 값 전체 |

해시 문자열은 `pbkdf2_sha256$600000$`로 시작한다. `$`와 나머지 문자를 모두 그대로 복사하고 바깥 따옴표는 추가하지 않는다. 이 필드에 숫자 비밀번호 원문을 넣으면 앱이 기동하지 않는다. 비밀 설정 파일 자체는 GitHub에 올리지 않는다.

새 코드가 GitHub/Render에 반영되어야 비밀번호 화면이 나타난다. 기존 배포에는 이 기능이 없으므로 환경변수만 저장해도 바로 바뀌지 않는다. 새 코드로 체험 배포해 로그인·푸터를 먼저 확인하고, 실제 운영 시트 연결은 별도 백업·이관 절차 후 진행한다.

비밀번호 재설정은 `kywa-next`에서 다음 명령으로 새 4자리 값을 두 번 입력한다.

```powershell
.\.venv\Scripts\python.exe scripts/set_admin_pin.py
```

생성된 파일의 새 해시를 Render에 입력하고 재배포한다. 로컬 앱은 다시 실행하면 적용된다. 비밀번호를 잊었을 때도 같은 방법으로 재설정한다.

로그인은 1시간 유지되고 로그아웃 시 즉시 폐기된다. 15분 내 5회 실패 시 15분간 로그인이 잠긴다. 이 제한은 하나의 서버 프로세스에서 모든 접속자가 공유하며 재시작하면 초기화된다. 공용 비밀번호를 아는 사람은 전체 시설을 관리할 수 있고, 이력에는 개인 이메일 대신 `pin-admin`이 기록된다. 초기 비밀번호를 공개 화면이나 소스에 표시하지 않는다.

## 인증 수단 구분

| 용도 | 계정 또는 설정 |
|---|---|
| 서버의 Sheets/Drive 자동 저장 | 서비스 계정 JSON |
| 현재 관리자 로그인 | `AUTH_MODE=pin`, `ADMIN_PIN_HASH` |
| 선택 가능한 Google 로그인 | `kywa_safety@kywa.or.kr`, OAuth 웹 클라이언트 |
| Gemini 분석 | `GEMINI_API_KEY` |
| KOSHA 검색 | `KOSHA_API_KEY` |

자동 저장용 계정은 `kywa-safety-check@gen-lang-client-0053629470.iam.gserviceaccount.com`이다. 기존 계정을 그대로 사용하며 새 서비스 계정을 만들 필요는 없다. 이메일에 편집자 권한을 부여한 것과 Render 서버가 그 계정으로 인증하는 것은 별도 단계이다.

## 서비스 계정 JSON 준비

기존 앱에 사용한 JSON 파일이 있으면 유효한 해당 파일을 재사용한다. 메모장으로 열어 `client_email`이 위 계정과 일치하는지 확인한다. 첫 `{`부터 마지막 `}`까지 전체를 사용한다.

파일을 찾지 못했고 새 키가 필요한 경우:

1. [Google Cloud Console 서비스 계정](https://console.cloud.google.com/iam-admin/serviceaccounts?project=gen-lang-client-0053629470)을 연다.
2. 프로젝트가 `gen-lang-client-0053629470`인지 확인한다.
3. 위 서비스 계정을 선택하고 **키(Keys)** 탭으로 이동한다.
4. **키 추가(Add key) → 새 키 만들기(Create new key)**를 선택한다.
5. **JSON → 만들기**를 선택한다. 인증 JSON이 PC로 다운로드된다.
6. 메모장으로 열어 내용을 확인한다. 이 파일을 GitHub나 채팅에 올리지 않는다.

이미 만든 키의 비밀 부분은 Console에서 다시 다운로드할 수 없다. 기존 파일이나 Streamlit Secrets에 보관된 인증정보가 있으면 먼저 확인한다. 기존 운영 앱의 키를 삭제하지 않는다. 키 생성이 막히면 프로젝트 권한·조직 정책을 관리 담당자에게 확인한다.

Streamlit Secrets의 `[gcp_service_account]`는 TOML 형식일 수 있다. 해당 블록을 JSON 환경변수에 그대로 붙여 넣으면 형식 오류가 난다. 원본 JSON 파일을 사용하면 변환이 필요 없다.

## JSON을 Render에 등록

1. [kywa-safety 환경변수 화면](https://dashboard.render.com/web/srv-datkiq6gekts73b716eg/env)을 연다.
2. **Environment Variables → Edit / Add Environment Variable**을 선택한다.
3. **Key**: `GOOGLE_SERVICE_ACCOUNT_JSON`
4. **Value**: JSON 전체. `{ }`를 포함하며 코드 블록 표시나 바깥 따옴표는 추가하지 않는다.
5. JSON 내부 `private_key`의 `\n`을 지우지 않는다. 앱이 필요한 줄바꿈을 처리한다.
6. 준비 중에는 **Save only**로 저장한다.

현재 코드는 JSON 환경변수를 읽는다. Secret Files에 파일만 올리는 방식은 이 설정을 대신하지 않는다. 동일 계정의 기존 시트·폴더 공유는 유지하면 되며, Sheets API와 Drive API 활성화 및 실제 쓰기 권한은 연결 검사에서 확인한다.

운영 전환 때 사용할 값은 아래와 같다. 각각 별도 환경변수이며 Value에는 `변수명=`을 제외한 값만 입력한다.

```text
SPREADSHEET_ID=1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q
SHEET_NAME=설문지 응답 시트1
HISTORY_SHEET_NAME=조치이력
DRIVE_FOLDER_ID=13RYVnDB7rrqLQYzB5Wa9WdWr0CHjm_MW
```

## Gemini 키를 Render에 등록

1. 기존 Streamlit Secrets의 `GEMINI_API_KEY` 또는 [Google AI Studio API Keys](https://aistudio.google.com/api-keys)에서 사용할 키를 확인한다.
2. 위 Render 화면의 **Environment Variables → Add Environment Variable**을 선택한다.
3. **Key**에 `GEMINI_API_KEY`를 입력한다.
4. **Value**에는 실제 키 문자열만 넣는다. `GEMINI_API_KEY=`나 따옴표를 붙이지 않는다.
5. 변수 하나를 더 추가해 Key를 `GEMINI_MODEL`, Value를 `gemini-3.6-flash`로 입력한다. 첨부 운영 코드와 같은 모델이다.
6. 준비 단계에서는 **Save only**로 저장한다.
7. 전체 필수 설정과 데이터 이관을 마친 뒤 **Save and deploy** 또는 최신 코드의 **Manual Deploy**로 적용한다.

`Save only`는 저장만 하고 현재 서버에는 적용하지 않는다. 체험 모드 해제는 전체 설정을 준비한 뒤 진행한다. 키를 Next.js 코드, `NEXT_PUBLIC_GEMINI_API_KEY`, 공개 `render.yaml`에 넣지 않는다.

## KOSHA 실제 검증

제공된 키로 기존 코드와 동일한 `/getKoshaGuide`, `callApiId=1050`, `techGdlnNm` 요청을 호출했다. 새 앱의 검색 함수로도 확인했다.

| 검색어 | HTTP / 응답 코드 | 전체 건수 | 원문 PDF 확인 |
|---|---|---:|---|
| 추락 | 200 / 00 | 1 | A-G-1-2025, 607,811 bytes |
| 전기 | 200 / 00 | 56 | B-E-4-2025, 367,238 bytes |

두 원문 모두 전체 응답, PDF 시그니처와 종료 표식을 확인했다. 앱은 한 번에 10건을 조회한다. 로컬 인증서 오류는 Windows 신뢰 저장소를 사용해 해결했으며 인증서 검증을 끄지 않았다. HTTP 200 안에 인증 오류 코드가 들어오면 검색 결과 없음으로 처리하지 않도록 보완했다.

Render 환경변수 `KOSHA_API_KEY`의 Value에 제공한 일반 인증키를 등록한다. 키는 문서나 소스에 복사하지 않는다. 검증 기록은 `artifacts/kosha-verification.json`에 있다.

## 선택 사항: Google 로그인으로 전환할 때

사용자가 확인한 전체 시설 관리자: `kywa_safety@kywa.or.kr`. Render `ACCESS_ACCOUNTS_JSON`의 Value:

```json
{"kywa_safety@kywa.or.kr":{"role":"admin","facilities":[]}}
```

관리자의 빈 시설 목록은 현재 코드에서 전체 시설 접근을 의미한다. 사람의 로그인을 위해 서비스 계정 JSON과 별도로 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`이 필요하다. Google Auth Platform의 웹 애플리케이션용 클라이언트에 승인된 리디렉션 URI를 등록한다.

```text
https://kywa-safety.onrender.com/api/auth/google/callback
```

외부 OAuth 앱이 테스트 상태라면 위 계정을 테스트 사용자에도 등록한다. 이메일 승인 목록만으로 OAuth 클라이언트 설정까지 완료되는 것은 아니다.

## 로컬 개발 저장 공간

Google 개발 시트 대신 `kywa-next/local-data/workbook-test`를 준비했다.

- `source.xlsx`: 첨부 원본의 바이트 단위 사본. 원본은 변경하지 않음.
- `data.json`: 평가 129건과 원래 점수·등급을 보존한 시험 저장소.
- `photos/`: `pic-test` 사진에서 원본 명명 규칙과 정확히 일치한 처리 사본.
- `import-report.json`: 매칭과 누락 기록. 사진 있는 평가 113건 연결, 오류 0건. 개선 후 사진 1건은 파일명과의 대응 정보가 없어 임의 연결하지 않음.

프로젝트 최상위 `pic-test`에는 JPG 181장이 있다. 원본 폴더를 수정하거나 Google Drive 파일을 추가 다운로드하지 않았다. 개선 후 사진은 원본 링크에 해당하는 파일이 확인되면 추가 매핑한다.

`kywa-next` 폴더에서 실행:

```powershell
.\.venv\Scripts\python.exe scripts/start_workbook_test.py
```

주소는 `http://localhost:8001`. 개선조치/보고서에서 설정한 4자리 관리자 비밀번호로 시험한다. 새 AI 분석은 가상 응답이며 변경은 이 PC의 `data.json`에만 저장된다. 실제 Google 관리자 인증 성공을 의미하지 않는다.

129건 조회와 사진 113건의 로컬 읽기를 확인했다. 본원 55건의 Excel 보고서에는 사진 47개가 포함되며 중앙 1건의 PDF도 생성했다. 한 번에 100건까지만 출력하므로 전체 129건 출력 시에는 시설이나 기간을 나누어 선택한다. 검증 과정에서 평가 데이터는 수정하지 않았다.

이 PC의 폴더를 Render 서버가 직접 읽을 수는 없다. 운영 자료·사진은 공개 GitHub/체험 앱에 올리지 않는다. 소스 ZIP과 Docker 이미지에서 `local-data`를 제외한다. 실제 운영은 Google Sheets/Drive를 사용하고 기존 앱 쓰기 중지·백업·이관 후 전환한다.

참고: [Google 서비스 계정 키](https://docs.cloud.google.com/iam/docs/keys-create-delete), [Render 환경변수](https://render.com/docs/configure-environment-variables), [Gemini 키 관리](https://ai.google.dev/gemini-api/docs/api-key).
