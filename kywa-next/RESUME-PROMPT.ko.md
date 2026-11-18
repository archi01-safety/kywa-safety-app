# 새 대화·새 PC 작업 시작문

아래 시작문을 복사하고 마지막에 이번 요청만 덧붙인다. 파일 경로는 새 PC의 실제 clone 위치에 맞춘다. 비밀값이나 운영 자료는 붙여 넣지 않는다.

```text
KYWA AI 위험성평가 시스템 작업을 이어갑니다.

저장소: https://github.com/archi01-safety/kywa-safety-app
공통 운영 브랜치: codex/kywa-next
앱 디렉터리: 저장소 안 kywa-next
현재 PC 작업 폴더: C:/업무폴더/2026 업무/4. AI위험성평가/kywa-v1.1/kywa-next

먼저 AGENTS.md와 PROJECT-CONTEXT.ko.md를 읽고 HANDOFF.md 맨 위·SETUP.md·최근 CHANGELOG.md를 확인해 주세요.
Git 상태/worktree와 원격 최신 브랜치를 확인하고 다른 worktree의 브랜치를 강제로 이동하지 마세요.
문서/HEAD와 실제 배포 SHA를 구분하고, 이번 요청 관련 파일/기관 설정만 추가로 읽어 주세요.

2026-11-16 기준 KYWA·AYF·FoWI·KHIDI·KNPS·KNF·KOHI·CAYF 모두
Render 독립 무료 Docker 서비스의 v1.3.0이며 운영 소스는
bacadc94e3f6bf4b87428552c1fac080e2680935입니다.
더 최신 기록이 있으면 PROJECT-CONTEXT/HANDOFF와 기관별 releases JSON을 우선 확인하세요.

Next.js는 정적 화면, app.py는 FastAPI 실행 진입점입니다. Vercel로 운영 이전하지 않았습니다.
별도 Netlify 기동 안내 시험은 pilot/kywa-entry와 entry-screen/에 있습니다.
NETLIFY-ENTRY-PILOT.ko.md의 실제 배포/실측 상태를 먼저 확인하고 기존 Render 앱을 바꾸지 마세요.
주소는 https://kywa-safety.netlify.app/ 이며 ?preview=1은 서버를 깨우지 않는 소개 재생입니다.
정적 시험 버전 kywa-entry/v0.1.0과 기존 업무 시스템의 기관별 v1.3.0을 구분하세요.
AX test ver.는 별도 등록돼 있습니다. AX-DEPLOYMENT/AX-VERIFICATION 최신 상태를 읽고,
외부 ax.env와 플랫폼 환경변수를 ZIP 업데이트 때 보존하세요. 새 소스 등록은 사용자가 수행하며
AX 서버 설정 설치·법령 주소 승인·서버 실연동 검증은 Render 완료와 구분하세요.
일반 시트20열/AYF18열, AYF는 부서·성명 미수집입니다.
내부 세부 판정은 기본 활성화이며 공개 점수는 기존 기관별1~20점입니다.
담당자 검토표 회신은 활성화의 필수 조건이 아닙니다.
GitHub Actions와 절전 방지 예약 호출은 추가/재활성화하지 마세요.

신규 제출·사진·조치·숨김관리·행 식별 정보를 보존하고 과거 기록을 일괄 재계산하지 마세요.
인증정보/PIN/세션 키·실제 자료를 공개 저장소·로그·채팅에 출력하지 마세요.
이번 지시의 기관 범위와 기존 승인을 확인해 불필요한 재승인 요청 없이 진행하되 실제 제한/미검증은 정확히 구분해 주세요.

작업이 끝나면 PROJECT-CONTEXT.ko.md의 현재 상태와 HANDOFF/CHANGELOG를 갱신해 주세요.
실행·배포가 바뀌면 SETUP/기관별 버전·배포 기록·복구 절차·소스/AX ZIP도 맞춰 주세요.
다른 PC 이동 직전 최종 비공개 백업은 별도로 요청하기 전에는 시작하지 마세요.

이번 요청:
[여기에 작업 내용을 추가]
```

최신 상세 정보는 [PROJECT-CONTEXT.ko.md](PROJECT-CONTEXT.ko.md), 배포 근거는 `artifacts/render-deployments.json`과 `releases/<기관>/<버전>.json`에서 확인한다. 이 시작문은 현재 상태 전체를 중복 저장하는 문서가 아니므로 실제 최신 상태와 함께 사용한다.
