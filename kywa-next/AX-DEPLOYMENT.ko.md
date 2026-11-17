# AX 플랫폼 등록·업데이트 안내

2026-11-17. 이미 등록된 **KYWA AI 위험성평가 시스템(test ver.)**, https://ax.kywa.or.kr/apps/kywa-safety/ 대상이다. 기존8개 Render 운영 소스·설정·데이터는 변경하지 않는다. 검증 범위는 [AX-VERIFICATION.ko.md](AX-VERIFICATION.ko.md)를 따른다.

## 등록 파일과 실행 설정

`artifacts/kywa-safety-ax.zip`을 기존 앱의 **소스관리**에서 등록한다. ZIP 최상위에는 `app.py`, `requirements.txt`, `AX-BUILD.json`, `backend/`, `frontend/out/`이 바로 있다. 상위 폴더를 추가하지 않는다. 썸네일·설명은 앱 상세관리에서 별도로 저장한다.

| 항목 | 설정 |
|---|---|
| 앱 유형 / 슬러그 | Python / FastAPI / `kywa-safety` 유지 |
| 실행 파일 / ASGI | `app.py` / `app:app`. AX의 `python -m uvicorn app:app` import 지원 |
| 직접 실행 | 앱 폴더에서 `python app.py` |
| Python | AX용 잠금 파일은 **3.11 이상** 대응. Render는 기존3.12 잠금 파일 유지 |
| 설치 | `python -m pip install -r requirements.txt` → `backend/requirements-ax.lock` |
| 포트 / 바인딩 | **AX가 배정한 PORT** / 기본127.0.0.1. Render의10000을 복사하지 않음 |
| 프로세스 수 | **단일 worker/instance**, 임시 사진·초안·보고서 작업은 프로세스 귀속 |
| 공개 주소 | `APP_BASE_URL=https://ax.kywa.or.kr`, 경로 제외 |
| 접두 경로 | `APP_BASE_PATH=/apps/kywa-safety`, 정적 빌드와 일치 |
| 실제 연동 | `APP_ENV=production`, `AUTH_MODE=pin`, `ORGANIZATION_ID=kywa` |
| 외부 설정 파일 | 기본 `/var/lib/ax-apps/kywa-safety/ax.env`, 소스 폴더 **밖** |
| 데이터 폴더 | `APP_DATA_DIR=/var/lib/ax-apps/kywa-safety`, 앱 실행 계정에 쓰기 허용 |

Node22는 HWPX 생성 시 필요하다. PATH에 없으면 `REPORT_NODE`로 절대 경로를 지정한다. Linux HEIC/HEIF에는 libvips·libheif/HEVC 디코더, PDF에는 코드가 지원하는 한글 글꼴이 필요하다. AX의 Python3.11은 실제 등록 소스의 운영 안내에서 확인했으나 이번 PC에는3.11/Linux 환경이 없으므로 새 패키지의 해당 환경 검사는 서버에서 수행한다. [NumPy2.4.6은 Python3.11 이상](https://pypi.org/project/numpy/2.4.6/), [2.5.3은3.12 이상](https://pypi.org/project/numpy/2.5.3/)이어서 AX 잠금 파일만 조건부 버전을 사용한다.

## 최초1회: 비공개 연동 설정 설치

**AX 소스 업로드만으로 Render의 환경변수는 복사되지 않는다.** 현재 앱 상세관리/소스관리에는 비밀 환경변수 입력 기능이 확인되지 않았다. 서버 운영자가 승인된 비공개 경로에 설정을 한 번 설치해야 한다. 공개 소스에 키를 넣거나 브라우저용 설정 API로 대신하지 않는다.

준비된 로컬 파일은 작업 공간의 **`secret/ax-kywa.env`**다. Google 서비스 계정 JSON·기존 KYWA 저장소·AI/KOSHA/법령 API·기존 KYWA PIN 해시와 AX 전용 세션 키를 포함한다. 이 파일은 공개 GitHub·등록 ZIP·AX 소스관리·메일 본문에 올리지 않는다. 승인된 비공개 수단으로 서버 운영자에게 전달한다.

서버 운영자 작업:

1. 파일을 `/var/lib/ax-apps/kywa-safety/ax.env`에 설치한다. 앱 실행 계정만 읽게 하고(예:0600), 데이터 폴더에는 앱 쓰기 권한을 준다. 기존 파일이 있으면 백업·대조하고 덮어쓰지 않는다.
2. ZIP의 `AX-BUILD.json`이 이 경로를 가리키므로 **별도 서비스 환경변수 추가 없이 자동으로 읽는다**. 다른 승인 경로는 `APP_ENV_FILE`에 외부 파일 절대 경로를 지정한다.
3. 플랫폼 환경변수가 파일보다 우선한다. 예전 `APP_ENV=demo`가 서비스에 명시되어 있으면 제거하거나 `production`으로 바꾼다. AX 할당 PORT는 유지한다.
4. 앱의 서버 환경에서 아래 점검을 실행한다. 키·응답 원문은 공유하지 않고 안전한 결과 JSON만 남긴다.

```sh
python scripts/check_ax_integrations.py --config /var/lib/ax-apps/kywa-safety/ax.env
```

점검은 Google 탭/헤더 조회와 편집·폴더 업로드 **권한**, AI 최소 응답, KOSHA 검색, 법령 검증을 수행한다. AI 소량 호출 비용이 발생할 수 있다. 평가·사진을 저장하거나 권한을 바꾸지 않으며 실제 업로드 성공을 대신하지 않는다. PC에서 실행한 결과는 AX 서버 출발 검증으로 기록하지 않는다.

## 설정값과 업데이트 유지 계약

샘플은 `deploy/ax.production.env.example`이다. 실제값은 외부 파일/플랫폼 비밀설정에만 둔다.

| 용도 | 변수 |
|---|---|
| Google 서버 인증 | `GOOGLE_SERVICE_ACCOUNT_JSON` |
| KYWA 저장 대상 | `SPREADSHEET_ID`, `SHEET_NAME`, `DRIVE_FOLDER_ID`, `HISTORY_SHEET_NAME` |
| AI | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| KOSHA / 법제처 | `KOSHA_API_KEY`, `LAW_API_OC` |
| 관리자 인증 | `AUTH_MODE=pin`, `ADMIN_PIN_HASH`, AX 전용 `SESSION_SECRET` |
| 기존 저장소 사용 | `ALLOW_LEGACY_WRITES=true`, 확인된 KYWA 저장소에만 적용 |
| 내부 세부 판정 | `DETAILED_RISK_ENABLED=true`, 기존 기관 기준 유지 |
| 선택 설정 | `APP_UPLOAD_DIR`, `APP_LOG_DIR`, `REPORT_NODE`, 명시한 프록시 IP의 `FORWARDED_ALLOW_IPS` |

- ZIP 교체 때 **외부 ax.env·데이터 폴더·플랫폼 환경변수를 보존**한다. 코드는 설정을 읽기만 하며 키·PIN·세션 키를 재생성하거나 파일을 덮어쓰지 않는다.
- AX marker가 있는 ZIP은 비밀설정 누락 시 운영 시작을 거부한다. 오래된 소스 폴더의 `.env`를 읽어 체험 모드로 조용히 전환하지 않는다. 합성 시험만 명시적 `APP_ENV=demo`를 사용한다.
- 서버 이전·키 만료·외부 API 정책 변경까지 소스 업데이트가 자동으로 해결하지는 않는다. 경로/정책 변경은 운영자가 조정한다.
- 예전 파일이 남는 부분 병합에서도 `AX-BUILD.json`, `app.py`, 백엔드·정적 화면·AX 잠금 파일은 **같은 ZIP**을 사용한다. 변경 전 기존 소스와 외부 설정을 비공개 백업한다.
- PIN 세션은 숨김 관리에서 만료 전 재시작 복원을 지원한다. 임시 사진·분석 초안·보고서 작업은 재시작 시 다시 해야 한다.

## 법령 API의 AX 주소 승인

이번 PC의 실제 호출에서 Google·AI·KOSHA는 통과했다. 법령 API는 기존 KYWA Render 주소로 확인됐지만 **AX 주소를 사용한 요청에서는 원문 검증이 실패**했다. AX 주소의 공동활용 추가 신청/승인과 AX 서버 재점검이 필요하다. 같은 OC를 유지하고 Render 주소를 가장해 요청하지 않는다.

같은 계정으로 국가법령정보 공동활용 추가 신청을 진행한다. 시스템 URL은 `https://ax.kywa.or.kr/apps/kywa-safety/`, 활용 목적은 `사진·설명 기반 위험성평가 결과의 관련 법령·조항 확인 및 원문 연결`이다. 인터넷·모바일, 법령 목록·본문/조문의 XML/JSON 등 필요한 항목을 확인한다. 최종 동의·신청은 명의자가 수행한다. [LAW-API-SETUP.ko.md](LAW-API-SETUP.ko.md)의 절차를 따른다. 승인 전/장애 시 기존 법령 검색 링크로 대체하며, 미확인 조항을 공식 검증으로 표시하지 않는다.

## 등록·실제 동작 확인 순서

1. 외부 설정 설치와 AX 법령 신청을 준비한다. 기존 Render는 중지/변경하지 않는다.
2. AX → **앱등록 및 관리 → 해당 test ver. 앱 → 소스관리**에서 새 `kywa-safety-ax.zip`으로 교체한다. FastAPI/슬러그/할당 포트는 유지하고 AX의 기존 배포 절차로 재시작한다. 이번 작업에서 소스 등록·배포 버튼은 대신 누르지 않았다.
3. `/apps/kywa-safety/healthz`, 첫 화면의 **운영 환경**, 관리자 로그인/연장, `/api/bootstrap`의 기관·모드를 확인한다. 인증값이 응답에 포함되지 않아야 한다.
4. 서버 연동 점검 후 별도 시험 저장소에서 사진→블러→분석→제출→재조회→조치→Excel/PDF/HWPX를 확인한다. 현재 비공개 설정은 **기존 KYWA 운영 저장소**를 가리키므로 업무 검증 전 시험 대상·정리 방법을 정한다. 이번 PC 점검에서는 업무 행/사진을 추가하지 않았다.
5. 썸네일 `artwork/kywa-safety-thumbnail-v1.png`은4:3, 브라우저 아이콘 `frontend/public/kywa-safety-icon-v1*.png/.ico`는 정사각형이다. 2026-11-17 설명80자와 썸네일을 AX 상세관리에서 저장했다. 브라우저 아이콘은 새 소스 배포 후 KYWA bootstrap 완료 시 적용되며 다른 기관 아이콘은 바꾸지 않는다.

AX와 Render가 같은 시트/Drive를 사용하면 기록은 함께 보인다. **두 신규 앱이 같은 평가를 동시에 관리·수정하는 것은 검증 범위가 아니므로** 시험/전환 시 관리자 작업을 조정한다. 이 패키지는 Apache·systemd·보안정책·포트·방화벽·업로드 한도·SSL을 변경하지 않는다.

## 다음 업데이트의 빌드·패키징

```sh
python scripts/build_ax_requirements.py
cd frontend
APP_BASE_PATH=/apps/kywa-safety npm run build -- --webpack
cd ..
python scripts/package_ax.py --frontend frontend/out
```

Render는 APP_BASE_PATH를 비워 별도로 빌드한다. 다른 AX 슬러그는 같은 경로로 재빌드하고 `package_ax.py --base-path /apps/실제슬러그`를 지정한다. Render 화면을 AX ZIP에 넣으면 패키저가 거부한다. 의존성 변경 시 AX3.11 호환성을 재검사한다. 소스/AX ZIP·매니페스트·검증·인수인계서를 함께 갱신하고 Actions는 활성화하지 않는다.
