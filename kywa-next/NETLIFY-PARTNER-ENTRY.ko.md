# 기관별 Netlify 기동 안내

한국산림복지진흥원(FoWI) 시범에 이어 2026-11-19에 AYF·KHIDI·KNPS·KNF·KOHI·CAYF의 안내 페이지를 게시했다. 7개 안내 페이지에서 각 기관의 기존 Render 업무 화면으로 연결한다.

| 항목 | 값 |
| --- | --- |
| Netlify 팀 / 프로젝트 | `axkywa` / `fowi-safety` |
| 정식 진입 | https://fowi-safety.netlify.app/ |
| 자동 이동 없는 소개 | https://fowi-safety.netlify.app/?preview=1 |
| 사진 등록 장면 고정 | https://fowi-safety.netlify.app/?preview=1&scene=2 |
| 게시 확인 | [배포 6afd6ddc7a8f9db5a980215e](https://app.netlify.com/projects/fowi-safety/deploys/6afd6ddc7a8f9db5a980215e) · 2026-11-18 Published |
| 소스와 복구 기준 | `pilot/partner-entry`의 `abf6680d492585ec2b1b1a4afd194d5873fe533c` · `fowi-entry/v0.1.0` |
| 정적 패키지 | [fowi-entry-static.zip](artifacts/fowi-entry-static.zip) · 20,303바이트 · [매니페스트](artifacts/fowi-entry-static.manifest.json) |

이 브랜치는 공통 운영 소스 `44d8f7b`에서 시작해 KYWA 안내 소스 `7d40271`의 여섯 장면을 가져왔다. KYWA 안내는 독립 `pilot/kywa-entry`에서 관리한다.

## 2026-11-19 게시 주소

| 기관 | 안내 페이지 | Netlify 배포 | 복구 버전과 패키지 |
| --- | --- | --- | --- |
| 안양시청소년재단 (AYF) | [접속](https://ayf-safety.netlify.app/) · [미리보기](https://ayf-safety.netlify.app/?preview=1) | [Published](https://app.netlify.com/projects/ayf-safety/deploys/6afe4b6a8955c60c03b18e50) | [ayf-entry/v0.1.0](entry-screen/releases/ayf.json) · [ZIP](artifacts/ayf-entry-static.zip) |
| 한국보건산업진흥원 (KHIDI) | [접속](https://khidi-safety.netlify.app/) · [미리보기](https://khidi-safety.netlify.app/?preview=1) | [Published](https://app.netlify.com/projects/khidi-safety/deploys/6afe4bad8763c83e3f102ab0) | [khidi-entry/v0.1.0](entry-screen/releases/khidi.json) · [ZIP](artifacts/khidi-entry-static.zip) |
| 국립공원공단 (KNPS) | [접속](https://knps-safety.netlify.app/) · [미리보기](https://knps-safety.netlify.app/?preview=1) | [Published](https://app.netlify.com/projects/knps-safety/deploys/6afe4be971ea762024a20e39) | [knps-entry/v0.1.0](entry-screen/releases/knps.json) · [ZIP](artifacts/knps-entry-static.zip) |
| 한전원자력연료 (KNF) | [접속](https://knf-safety.netlify.app/) · [미리보기](https://knf-safety.netlify.app/?preview=1) | [Published](https://app.netlify.com/projects/knf-safety/deploys/6afe4c1b088b2eb329842e3f) | [knf-entry/v0.1.0](entry-screen/releases/knf.json) · [ZIP](artifacts/knf-entry-static.zip) |
| 한국보건복지인재원 (KOHI) | [접속](https://kohi-safety.netlify.app/) · [미리보기](https://kohi-safety.netlify.app/?preview=1) | [Published](https://app.netlify.com/projects/kohi-safety/deploys/6afe4c3055b347c93f3f6130) | [kohi-entry/v0.1.0](entry-screen/releases/kohi.json) · [ZIP](artifacts/kohi-entry-static.zip) |
| 천안시청소년재단 (CAYF) | [접속](https://cayf-safety.netlify.app/) · [미리보기](https://cayf-safety.netlify.app/?preview=1) | [Published](https://app.netlify.com/projects/cayf-safety/deploys/6afe4c3dec900c3b85c8883f) | [cayf-entry/v0.1.0](entry-screen/releases/cayf.json) · [ZIP](artifacts/cayf-entry-static.zip) |

6개 신규 게시의 패키지 기준 소스는 `c2e5b6f312964e92d0f2297df64fa8bc0433a426`이다. 최초 배포 전 사용 가능 크레딧은 940이었으며, 정식 게시 6회 기준 90크레딧이다.

## 화면과 연결

FoWI 업무 화면과 같은 공동 기관명 헤더를 사용한다. PC에서는 한국산림복지진흥원 / × / 한국청소년활동진흥원 세 줄, 모바일에서는 기관명과 ‘× 한국청소년활동진흥원’ 두 줄로 배치한다. 오른쪽 안내는 서버 연결 상태를 표시한다. 녹색 `#129F4A`와 하늘색 `#59C2E0`을 강조에 적용한다.

템플릿은 기존 기관 프로필에서 공개 기관명, 약칭, 색상과 성명 입력 여부만 읽는다. FoWI는 초성 변환을 안내하고 성명 미수집 기관인 AYF는 제출 전 사진 확인으로 바꾼다. 사이트마다 `/__render/ready`를 해당 기관의 `/healthz`로만 중계한다. 정상 JSON이 확인되면 같은 기관의 `/#inspect`로 이동한다.

기존과 같이 650ms 이후 소개를 시작하며 개별 요청 5초, 재시도 간격 2초, 활성 화면에서 총 120초의 한도를 적용한다. 소개 길이 20.734초는 KYWA 시범판과 같은 연출 기준이다. FoWI의 기동 시간을 별도로 실측한 값으로 사용하지 않는다. 미리보기는 Render 연결 확인 없이 소개를 재생한다. 연결 지연 시에는 재시도와 해당 기관의 원래 주소를 제공한다.

## 재생성, 게시 및 복구

앱 루트에서 Node 22, Python 3으로 실행한다.

```powershell
node --test entry-screen/tests/build.test.mjs entry-screen/tests/controller.test.mjs
node entry-screen/tools/build.mjs --org=fowi
python entry-screen/tools/package-static.py --org=fowi
node entry-screen/tools/serve.mjs --org=fowi --port=8026 --mode=html
```

로컬 `http://localhost:8026/?preview=1&scene=2`에서 화면을 확인한다. `--mode=html`은 로딩 HTML을 반환하는 모의 서버다. 배포 ZIP의 최상위 `netlify.toml`은 검사한 `site/`만 게시하도록 지정한다. 첫 ZIP 업로드가 Hugo로 감지돼 실패한 뒤, 이 설정을 넣어 같은 프로젝트에서 정식 게시했다.

업데이트할 때는 기존 Netlify 프로젝트의 **Deploys → browse files to upload**에서 기관에 맞는 ZIP을 올린다. 팀, 프로젝트명, 정적 패키지의 기관 ID를 먼저 대조한다. Production은 Public, Deploy Preview는 Private다. 사용자 화면의 소개 미리보기는 정식 주소에 `?preview=1`을 붙여 사용한다. 이 프로젝트는 Git 자동 배포 대신 파일을 수동 게시한다.

문제가 생기면 기존 Render 주소를 안내한다. Netlify에 이전에 검증한 성공 배포가 있으면 그 배포를 다시 Publish한다. 성공 배포가 하나뿐이라면 기록한 태그의 ZIP과 매니페스트로 정적 안내를 복구한다.

## 검증과 확대

- Node 검사 19개에서 기관별 주소, 브랜드, AYF 성명 안내, 준비 판정, 실패와 재시도를 확인했다.
- 브라우저에서 다섯 화면 크기와 여섯 장면을 검사했다. [PC](entry-screen/review/fowi-desktop.jpg)와 [모바일](entry-screen/review/fowi-mobile.jpg)은 실제 게시 주소를 캡처했다.
- 공개 파일 6개를 ZIP과 대조하고 정상 JSON 응답과 FoWI Render로의 브라우저 자동 이동을 확인했다. 상세 결과는 [배포 확인](entry-screen/review/fowi-public-checks.json)과 [릴리스 기록](entry-screen/releases/fowi.json)에 있다.
- 추가 6개 기관에서 실제 공개 파일을 ZIP과 6개씩 대조했다. 기관별 준비 상태 응답과 브라우저 자동 이동을 확인했다. 390·820·1280px 너비의 사진 장면에서 가로 넘침과 공동 기관명 겹침을 검사했다. AYF의 개인정보 장면은 성명 안내 없이 사진 확인을 안내한다. [브라우저 검증](entry-screen/review/partner-rollout-20261119-browser.json) · [AYF PC](entry-screen/review/ayf-desktop.jpg) · [CAYF 모바일](entry-screen/review/cayf-mobile.jpg)
- 추가 6개 기관에는 KYWA 시범판의 20.734초 소개 구성을 공통 적용했다. 확인 기록은 정상 연결과 실제 자동 이동 1회씩의 결과이며, 기관별 자연 절전 기동 시간 통계는 포함하지 않는다.
