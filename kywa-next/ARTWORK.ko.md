# KYWA 앱 아이콘·AX 썸네일

2026-11-17 사용자 선택 **B안**. 차콜 바탕·분홍 방패·흰색 체크의 정사각형 앱 아이콘이다. 기관 공식 로고와 상단 로고는 변경하지 않는다.

- `artwork/kywa-safety-icon-v1.png`: 승인 원본1254×1254.
- `artwork/kywa-safety-thumbnail-v1.png`: AX용1448×1086,4:3. 좌우 검은 여백.
- `frontend/public/kywa-safety-icon-v1.ico`:16/32/48/256px 브라우저 아이콘.
- `frontend/public/kywa-safety-icon-v1-32.png`, `-180.png`, `-512.png`: 원본에서 직접 축소한 게시용 파일.

bootstrap의 `organization.id === kywa`일 때만 아이콘을 설정한다. AX 접두 경로는 공통 appPath를 사용한다. 다른7개 기관의 아이콘·기관 로고·디자인은 변경하지 않는다. AX 대표 이미지와 설명은 소스 배포와 별개로 앱 상세관리에서 저장했다.

## 생성 방식과 프롬프트

기본 내장 image_gen으로 생성/편집했다. 외부 CLI나 별도 API 키는 사용하지 않았다. A(밝은 글라스 방패),B(차콜 방패),C(체크리스트)3안을 검토한 뒤 B를 선택했다. B 원본 생성 사양은 `square safety app icon, charcoal tile, bold magenta shield with white check, subtle blue edge, no text, no official logo reproduction`이다. 다음은 썸네일 편집의 최종 프롬프트다.

```text
Use case: compositing. Asset type: exact 4:3 landscape application catalog thumbnail. Edit target: the supplied square charcoal KYWA safety app icon, with magenta shield and white check. Change ONLY the canvas: make a 4:3 landscape image by adding equal solid pure black (#000000) vertical padding on the LEFT and RIGHT of the original centered square icon. Preserve the entire original icon perfectly: all details, colors, proportions, rounded corners, its background, and its full square footprint. Do not crop, stretch, redraw, relight, add text, decorate, or add anything else. The square icon fills the full height, and the extra width is only equal black sidebars. Final composition is exactly 4:3 landscape, ideally 1600 by 1200 pixels.
```

실제 출력은1448×1086이며4:3 비율과 양끝 검은 픽셀을 확인했다. 승인 원본과 썸네일은 별도 보존한다.
