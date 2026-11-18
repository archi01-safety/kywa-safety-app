# KYWA Netlify 기동 안내 페이지 시험

## 범위와 현재 상태

2026-11-18, `pilot/kywa-entry`에서 KYWA만 별도로 시험한다. 분기 기준은 `origin/codex/kywa-next`의 `44d8f7b326d363b1bc51ca617aa99e57c5ac50d1`이다. 실제 Render 운영은 `bacadc94e3f6bf4b87428552c1fac080e2680935` / v1.3.0이며 이 안내 페이지와 독립적이다.

- Netlify 팀: `axkywa`; 실제 프로젝트 이름: `kywa-safety`.
- 실제 주소: https://kywa-safety.netlify.app/ ; 소개만 보기: https://kywa-safety.netlify.app/?preview=1 .
- 처음 `kywa-safety-start`로 생성한 뒤 사용자 요청에 따라 프로젝트명과 기본 주소를 `kywa-safety`로 변경했다. 다른 기관은 추후 `<기관ID>-safety.netlify.app` 규칙을 사용하며 각 이름의 사용 가능 여부는 생성 시 확인한다. 이번에는 다른 기관 프로젝트를 만들지 않는다.
- 정적 소스: `entry-screen/site/`. Netlify base는 `kywa-next/entry-screen`, publish는 `site`, build는 `node tools/check.mjs`.
- Render 소스·환경변수·인증·Google 데이터와 다른 7개 기관은 변경하지 않는다. Actions·예약 호출도 추가하지 않는다.

## 방문 동작

```text
새 Netlify 주소
  → GET /__render/ready (쿠키 없음·캐시 우회)
  → Netlify 외부 중계 → 기존 KYWA Render /healthz
  → HTTP200 + JSON {"status":"ok"} 확인
  → location.replace(기존 Render /#inspect)
```

650ms 이내 응답하면 소개를 표시하지 않는다. 지연되면 가상의 현장 그림과 큰 문구로 소개를 시작한다. 소개가 재생 중이어도 준비가 확인되면 즉시 이동한다. 소개가 먼저 끝나면 마지막 요약 장면을 유지한다. 평상시 하단의 ‘기존 시스템 열기’ 링크는 사용자 후속 지시에 따라 제거했다. 연결 실패 안내의 직접 접속과 JavaScript 비활성 환경의 접속 안내는 유지하며 기존 Render 주소도 계속 사용할 수 있다.

각 확인은 최대 5초, 실패 후 간격은 2초이며 동시 확인을 시작하지 않는다. 활성 화면에서 총 120초가 지나면 자동 확인을 중단하고 재시도와 직접 접속을 제공한다. 백그라운드에서는 확인·애니메이션을 중지하고 복귀 때 새 응답을 확인한다. 이전 요청의 늦은 응답은 이동을 발생시키지 않는다. 임의의 백분율·확정 남은 시간은 표시하지 않는다.

`site/_redirects`는 준비 주소 한 개만 중계한다. 다른 로그인·사진·분석·제출·다운로드 API는 중계하지 않는다. 브라우저는 GET만 사용하고, 기존 FastAPI `/healthz`도 GET만 제공한다. Netlify 자체 중계 제한과 브라우저 제한은 별개이며 클라이언트는 5초를 적용한다.

## 소개와 개인정보

차콜 바탕, KYWA 분홍·파랑, 기존 로고 원본을 사용한다. 사용자 후속 지시에 따라 상단은 로고와 연결되는 흰색 띠로 바꾸고 시스템명·상태 표시는 어두운 색으로 조정했다. 여섯 장면은 기록 → 사진·설명 → 분석 검토·전송 → 개선조치·재평가 → Excel/PDF/HWPX → 얼굴 블러·초성 변환이다. 문구는 현재 최초 사진 2장·개선 후 1장·회전·조치계획 기능에 맞춘다.

큰 화면에서는 1·3·5장면은 글 왼쪽/그림 오른쪽, 2·4·6장면은 그림 왼쪽/글 오른쪽으로 교차 배치한다. 작은 화면은 읽는 순서를 유지하면서 문구 정렬과 등장 방향을 교차한다. 방향별 등장, 사진 카드 펼침·회전 힌트, 분석 초점, 조치 단계 강조, 문서 카드·차트 움직임과 연결선은 CSS/WAAPI로 구현했다. 숨은 장면의 움직임은 중단하고 일시정지·모션 감소에서는 전체 글을 표시한다. 고정 장면에서 재생할 때 첫 장면으로 되돌아가던 미리보기 동작도 수정했다.

원본 참고 PDF·MP4는 배포하지 않는다. 그림·이름·보고서는 모두 가상 예시이며 실제 사용자 자료가 없다. 소개 페이지는 AI·Google을 호출하거나 업무 자료·쿠키·인증정보를 저장하지 않는다. 준비 확인의 기존 `/healthz`는 저장소 조회 없이 고정 상태 JSON을 반환한다.

`?preview=1`은 준비 확인과 자동 이동이 없는 정적 미리보기다. `?preview=1&scene=1`부터 `scene=6`까지 특정 장면을 정지해 확인할 수 있다. 일시정지·이전·다음·장면 선택·키보드 초점을 제공하며 모션 감소 환경에서는 자동 재생 없이 읽을 수 있다.

## 자연 기동 측정

강제 중지·재시작·배포는 하지 않는다. 첫 요청부터 정상 상태 JSON까지를 측정하며 5초 요청 한도와 2초 재시도 간격을 포함하는 방문자 관측값이다. 표본 사이에는 마지막 준비 응답부터 970초 동안 이 작업에서 서버에 요청하지 않는다. 다른 사용자의 접속이 있을 수 있으므로 단순 대기시간이나 느린 응답만으로 절전으로 분류하지 않는다.

로딩 HTML을 받지 못하고 시간 초과만 발생한 표본은 원시 기록에서 `unconfirmed`로 보존한다. Render 관리 화면의 정상 종료·새 프로세스 시작 로그와 측정 시간을 대조한 뒤 별도 증거로 자연 기동을 확정한다. 운영 로그 원문은 비공개로 보관하고 공개 측정표에는 필요한 시각만 남긴다.

세 표본의 평균에서 2초를 뺀 값을 `site/config.json`의 `storySeconds`에 저장한다. 3회가 확인되지 않으면 완료로 표시하지 않으며 임시 60초 값을 실제 측정값으로 표현하지 않는다.

## 로컬 재현

Node 22만으로 정적 검사·단위 검사가 가능하다. 앱 루트에서:

```powershell
node --test entry-screen/tests/controller.test.mjs
node entry-screen/tools/check.mjs
node entry-screen/tools/serve.mjs --port=8024 --mode=unready
```

`http://localhost:8024/?preview=1`에서 디자인을 본다. 로컬 서버는 Render로 요청을 전달하지 않는다. `--mode=html`, `--mode=hang`으로 비정상 응답도 확인할 수 있다. `--mode=ready`에서는 실제 Render로 이동하므로 자연 절전 측정 중에는 사용하지 않는다.

자연 기동 재측정은 Python/httpx와 신뢰된 로컬 CA를 사용한다. 인증키는 필요 없다.

```powershell
python entry-screen/tools/measure-startup.py --output local-data/entry/startup.json --evidence local-data/entry/cold-evidence.json
python entry-screen/tools/summarize-startup.py --samples local-data/entry/startup.json --evidence local-data/entry/cold-evidence.json --warm local-data/entry/warm.json --output entry-screen/measurements/startup-20261118.json --config entry-screen/site/config.json
```

재측정 도구는 요청한 표본만 수집하고 종료한다. 정기 실행·작업 스케줄러·Actions에 넣지 않는다. 업무 시스템을 일부러 계속 깨워 두는 도구로 사용하지 않는다.

## 검증·배포 결과

진행 중. 연결 모의14개와 실측 집계 도구4개 검사 통과. 320/390/768/1280/1440px에서 각6장면, 총30개 조합의 가로 넘침·제목 잘림을 검사했다. 일시정지 문구 숨김, 태블릿 배치, 예시 SVG 비율, 브라우저 타이머 연결을 실제 화면 검사에서 발견·수정했다. 120초 연결 중단과 재시도·장면 선택·키보드 조작도 확인했다. 실제 iPhone/Android 기기와 OS 모션 감소 설정의 실물 검사는 별도이며 반응형 화면·CSS/JS·모의검사와 구분한다.

| 실행 중 확인 | 결과 |
|---|---|
| Render 직접 상태 확인10회 | 모두 정상; 중앙값0.090초, 평균0.117초, 최댓값0.353초 |
| Netlify 중계 상태 확인10회 | 모두 정상; 중앙값0.1045초, 평균0.162초, 최댓값0.679초; 650ms이내9회 |
| 실제 브라우저 새 주소 접속10회 | 모두 Render `/#inspect`로 자동 이동 |
| 자연 기동 정상 완료3회 | 22.391초 / 23.421초 / 22.391초; 평균22.734초, 중앙값22.391초, 최댓값23.421초 |
| 제외한 시도 | 120.204초 미응답1회는 실패로 보존; 추가 대기 후0.375초 응답1회는 정상 실행 표본으로 분리 |
| 확정 소개 길이 | 정상 완료3회 평균−2초 =20.734초 |

상태 응답 시간은 전체 업무 화면 로딩 시간이 아니다. 브라우저 방문 기록의 도구 수행 시간도 네트워크/API 실측과 구분한다. 준비 확인은 Google/AI를 호출하지 않는다. 기존 앱 화면으로 이동한 이후의 원래 공개 대시보드 조회는 기존 앱의 동작이다.

정상 완료3회의 평균은 미래 기동의 최대 시간이나 가용성 보장이 아니다. 120초 미응답도 숨기지 않고 별도 기록한다. 측정 원시 시도·서버 종료/시작 대조 시각·정상 실행10회·실제 브라우저 이동10회는 [measurements](entry-screen/measurements/)에 저장한다. 3번째 정상 기동에는 실제 Netlify 주소 방문을 함께 실행했고, 준비 확인 뒤 기존 Render로 자동 이동하는 것을 확인했다. 소개 표시·즉시 이동·소개 종료 후 대기·오류·백그라운드·늦은 응답은 모의 검사와 실제 로컬 브라우저 검사로도 대조했다.

최초 정식 배포 `6afd3b86cf3c0b88a98329ac`, 소스 `f11b5b70deb36b5516f631f169beb05013e33123`의 Published를 확인했다. 당시의 잠정20.906초를 이번 정상3회 확정값20.734초로 교체하고 흰색 상단·좌우 교차·강화된 움직임·하단 링크 제거를 마지막 보정 배포에 함께 반영한다. 최종 배포 ID·소스 SHA는 Published 확인 후 추가한다. 실제 Netlify 프로젝트 ID는 `aaf53bcd-c271-45af-b802-7ef0c8c275ce`다.

Netlify 기본 설정이 Production Private라 비로그인 중계가401로 응답하는 것을 확인했다. Production만 Public, Deploy Preview는 Private로 설정하고 익명 HTTP 요청10회와 실제 자동 이동10회를 확인했다. 추가 Powered by Netlify 배지는 이 프로젝트에서만 해제했다. 이 설정 변경은 기존 두 프로젝트·Render의 인증/환경에 영향을 주지 않는다.

PC·모바일·태블릿 확인 화면은 [review](entry-screen/review/)에 보관한다. 이 폴더와 검사·측정 도구는 공개 정적 사이트 폴더 밖에 있어 초기 전송량에 포함되지 않는다.

## 배포와 복구

Netlify는 같은 저장소의 **시험 브랜치만** 연결한다. 기존 Render 브랜치나 Blueprint를 변경하지 않는다. 인증 환경변수가 필요 없는 순수 정적 배포이며 Node는 배포 전 검사에만 사용한다. Netlify의 기본 POST 등 임의 경로를 광범위하게 Render로 넘기는 wildcard 규칙을 추가하지 않는다.

정식 배포 전에 현재 무료 크레딧을 확인한다. 사용자 승인 범위는 최초 정식 1회와 필요한 보정 1회 이내이며, 이후 디자인 검토에는 로컬/정적 미리보기를 사용한다. 기존 `kywa-doc`, `kywa-safety-survey` 프로젝트는 수정하지 않는다.

2026-11-18 배포 준비 중 잔여38.3크레딧/월300, 정식17회255크레딧을 관리 화면에서 확인했다. 정식 배포는 회당15크레딧이다([공식 요금 안내](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/billing-faq-for-credit-based-plans/)). `ignore-build.mjs`는 화면·배포 설정이 달라진 경우에만 Git 자동 배포를 계속하고, 인수인계·측정 증거 등 문서 변경은 취소한다([공식 ignore 규칙](https://docs.netlify.com/build/configure-builds/ignore-builds/)). 수동 배포 버튼이나 build hook은 별도이므로 반복 사용하지 않는다.

문제 발생 시 기존 Render 주소를 계속 안내한다. Netlify에서 이 프로젝트의 Deploys → 이전 검증 배포 → Publish deploy로 정적 안내만 복구할 수 있다. 첫 배포라 이전 배포가 없으면 Git의 시험 태그/확정 소스로 정적 ZIP을 다시 배포한다. 운영 시트·사진·앱 데이터 복원은 필요하지 않다.
