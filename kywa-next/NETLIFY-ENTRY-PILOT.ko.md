# KYWA Netlify 기동 안내 페이지 시험

## 범위와 현재 상태

2026-11-18, `pilot/kywa-entry`에서 KYWA만 별도로 시험한다. 분기 기준은 `origin/codex/kywa-next`의 `44d8f7b326d363b1bc51ca617aa99e57c5ac50d1`이다. 실제 Render 운영은 `bacadc94e3f6bf4b87428552c1fac080e2680935` / v1.3.0이며 이 안내 페이지와 독립적이다.

- Netlify 팀: `axkywa`; 프로젝트 예정 이름: `kywa-safety-start`.
- 시험 주소·실제 배포 ID·기동 시간 최종값: **검증·배포 후 아래 결과에 확정**한다.
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

650ms 이내 응답하면 소개를 표시하지 않는다. 지연되면 가상의 현장 그림과 큰 문구로 소개를 시작한다. 소개가 재생 중이어도 준비가 확인되면 즉시 이동한다. 소개가 먼저 끝나면 마지막 요약 장면을 유지한다. 기존 Render 주소 직접 접속도 계속 가능하다.

각 확인은 최대 5초, 실패 후 간격은 2초이며 동시 확인을 시작하지 않는다. 활성 화면에서 총 120초가 지나면 자동 확인을 중단하고 재시도와 직접 접속을 제공한다. 백그라운드에서는 확인·애니메이션을 중지하고 복귀 때 새 응답을 확인한다. 이전 요청의 늦은 응답은 이동을 발생시키지 않는다. 임의의 백분율·확정 남은 시간은 표시하지 않는다.

`site/_redirects`는 준비 주소 한 개만 중계한다. 다른 로그인·사진·분석·제출·다운로드 API는 중계하지 않는다. 브라우저는 GET만 사용하고, 기존 FastAPI `/healthz`도 GET만 제공한다. Netlify 자체 중계 제한과 브라우저 제한은 별개이며 클라이언트는 5초를 적용한다.

## 소개와 개인정보

차콜 바탕, KYWA 분홍·파랑, 기존 로고 원본을 사용한다. 여섯 장면은 기록 → 사진·설명 → 분석 검토·전송 → 개선조치·재평가 → Excel/PDF/HWPX → 얼굴 블러·초성 변환이다. 문구는 현재 최초 사진 2장·개선 후 1장·회전·조치계획 기능에 맞춘다.

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

작성 중. 로컬 13개 연결 모의검사 통과; 좁은 화면에서 발견한 가로 넘침·일시정지 문구 숨김·예시 보고서 그림 비율을 수정했다. 최종 PC/태블릿/모바일 검사, 3회 자연 기동·10회 실행 중 측정, 실제 중계·자동 이동, 잔여 크레딧·배포 ID와 ZIP 해시는 완료 시 확정한다.

## 배포와 복구

Netlify는 같은 저장소의 **시험 브랜치만** 연결한다. 기존 Render 브랜치나 Blueprint를 변경하지 않는다. 인증 환경변수가 필요 없는 순수 정적 배포이며 Node는 배포 전 검사에만 사용한다. Netlify의 기본 POST 등 임의 경로를 광범위하게 Render로 넘기는 wildcard 규칙을 추가하지 않는다.

정식 배포 전에 현재 무료 크레딧을 확인한다. 사용자 승인 범위는 최초 정식 1회와 필요한 보정 1회 이내이며, 이후 디자인 검토에는 로컬/정적 미리보기를 사용한다. 기존 `kywa-doc`, `kywa-safety-survey` 프로젝트는 수정하지 않는다.

2026-11-18 배포 준비 중 잔여38.3크레딧/월300, 정식17회255크레딧을 관리 화면에서 확인했다. 정식 배포는 회당15크레딧이다([공식 요금 안내](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/billing-faq-for-credit-based-plans/)). `ignore-build.mjs`는 화면·배포 설정이 달라진 경우에만 Git 자동 배포를 계속하고, 인수인계·측정 증거 등 문서 변경은 취소한다([공식 ignore 규칙](https://docs.netlify.com/build/configure-builds/ignore-builds/)). 수동 배포 버튼이나 build hook은 별도이므로 반복 사용하지 않는다.

문제 발생 시 기존 Render 주소를 계속 안내한다. Netlify에서 이 프로젝트의 Deploys → 이전 검증 배포 → Publish deploy로 정적 안내만 복구할 수 있다. 첫 배포라 이전 배포가 없으면 Git의 시험 태그/확정 소스로 정적 ZIP을 다시 배포한다. 운영 시트·사진·앱 데이터 복원은 필요하지 않다.
