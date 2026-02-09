import requests
import io
import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
from docx import Document

# 1. 환경 설정 및 보안 우회
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정 및 세션 초기화
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# 2.5 로고 이미지 로드
logo_path = "kywa_logo.png"
logo_img = None
if os.path.exists(logo_path):
    logo_img = Image.open(logo_path)

# 3. 헤더 디자인 (수정본)
# 3. 헤더 디자인 (이미지-홈페이지 / 타이틀-새로고침 연결)
header_col1, header_col2 = st.columns([1, 4])

with header_col1:
    if logo_img:
        # 로고 이미지 표시 (너비는 적절히 조절하세요)
        st.image(logo_img, width=300) 
    else:
        # 이미지가 없을 경우 기존 텍스트 표시
        st.markdown("<h2 style='color: #E60012; margin-top: 0;'>KYWA</h2>", unsafe_allow_html=True)
    # GitHub의 Raw 이미지 경로
    raw_logo_url = "https://raw.githubusercontent.com/archi01-safety/kywa-safety-app/main/kywa_logo.png"
    
    # 로고 전용 스타일: 링크 밑줄 및 이미지 테두리 제거
    st.markdown(
        f"""
        <style>
            .logo-link {{
                text-decoration: none !important;
                border: none !important;
                outline: none !important;
            }}
            .logo-img {{
                cursor: pointer;
                border: none !important;
                outline: none !important;
                display: block; /* 이미지 하단 미세한 공백 제거 */
            }}
        </style>
        
        <a href="https://www.kywa.or.kr/main/main.jsp" target="_blank" class="logo-link">
            <img src="{raw_logo_url}" width="300" class="logo-img">
        </a>
        """,
        unsafe_allow_html=True
    )

with header_col2:
    st.title("🚨 KYWA AI 위험성평가 시스템")
    # 스타일 정의: 링크의 밑줄을 완전히 제거하고 색상을 테마에 맞춤
    st.markdown(
        """
        <style>
            .title-link {
                text-decoration: none !important; /* 밑줄 강제 제거 */
                color: inherit !important;       /* 테마 색상 상속 */
                border: none !important;         /* 테두리 제거 */
                outline: none !important;        /* 포커스 시 선 제거 */
            }
            .title-link h1 {
                text-decoration: none !important;
                margin-bottom: 0px;
                cursor: pointer;
                font-size: 2.2rem;
                font-weight: 700;
            }
            /* 마우스 올렸을 때 효과 (선택사항) */
            .title-link:hover {
                text-decoration: none !important;
                opacity: 0.8;
            }
        </style>
        
        <a href="https://kywa-safety-check.streamlit.app/" target="_self" class="title-link">
            <h1>🚨 KYWA AI 위험성평가 시스템</h1>
        </a>
        """,
        unsafe_allow_html=True
    )
    st.caption("Korea Youth Work Agency - 스마트 안전관리 플랫폼")

    
# 4. 커스텀 CSS (표 너비 최적화 반영)
st.markdown("""
    <style>
@@ -149,72 +199,155 @@
    doc.save(bio)
    return bio.getvalue()

# 5. 사이드바 및 모델 설정
with st.sidebar:
    api_key = st.text_input("Gemini API Key", type="password")
if api_key:
    genai.configure(api_key=api_key, transport='rest')
    model = genai.GenerativeModel('gemini-flash-latest')
# 5. 모델 설정 (Secrets에서 키를 안전하게 가져옴)
try:
    # Streamlit Secrets에 저장된 키를 자동으로 호출합니다.
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key, transport='rest')
        model = genai.GenerativeModel('gemini-flash-latest') # 또는 사용 중인 모델명
    else:
        st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.")
        st.stop()
except Exception as e:
    st.error(f"API 설정 오류가 발생했습니다: {e}")
    st.stop()

st.divider()
# --- 6. 입력 섹션 ---
col1, col2 = st.columns(2)

with col1:
    selected_facility = st.radio("점검 대상 시설", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    st.markdown("### **🏢 점검 대상 시설**")
    # 변수 할당(selected_facility)을 명시적으로 수행
    selected_facility = st.radio(
        "시설명 선택", 
        ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], 
        horizontal=True,
        label_visibility="collapsed",
        key="facility_val" 
    )
    
    st.write("") 

    st.markdown("### **📂 담당 부서 선택**")
    dept_list = ["활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", "안전경영부", "재무회계부", "디지털정보부", "미래활동부", "정책사업부", "활동안전부", "활동인증부", "청소년성장지원부", "지도인력양성부", "지도인력개발부", "자회사"]
    
    # 변수 할당(selected_dept)을 명시적으로 수행
    selected_dept = st.selectbox(
        "부서명 선택", 
        dept_list,
        label_visibility="collapsed",
        key="dept_val"
    )
    
    st.write("") 
    st.markdown("### **📝 현장 상황 설명**")
    user_description = st.text_area("상황 설명 입력", height=150, label_visibility="collapsed", key="user_desc")

    # 3. 현장 상황 설명
    st.markdown("### **📝 현장 상황 설명**")
    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n3. 생활관 사다리 고장으로 추락 위험 등"
    user_description = st.text_area("현장 상황 설명", placeholder=placeholder_text, height=220)
with col2:
    source_option = st.radio("사진 방식", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    img_file = st.camera_input("촬영") if "📷" in source_option else st.file_uploader("업로드") if "🖼️" in source_option else None
    user_description = st.text_area(
        "상황 설명 입력", 
        placeholder=placeholder_text, 
        height=150,
        label_visibility="collapsed"
    )

# 7. AI 분석 버튼 (변별력 강화를 위한 프롬프트 수정)
with col2:
    # 4. 사진 방식 및 입력
    st.markdown("### **📸 사진 기록 방식**")
    source_option = st.radio(
        "사진 방식 선택", 
        ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), 
        horizontal=True,
        label_visibility="collapsed"
    )
    
    # 사진 입력 위젯 (이 부분은 위젯 자체가 제목 역할을 하므로 스타일 유지)
    if "📷" in source_option:
        img_file = st.camera_input("📸 현장 사진 촬영")
    elif "🖼️" in source_option:
        img_file = st.file_uploader("🖼️ 사진 파일 업로드", type=['png', 'jpg', 'jpeg'])
    else:
        img_file = None
        
# 7. AI 분석 실행 섹션
if st.button("🚀 KYWA AI 위험요인 분석 시작", use_container_width=True):
    if not api_key: st.error("API Key를 입력하세요.")
    if not user_description.strip() and not img_file:
        st.warning("⚠️ 분석할 내용(글 또는 사진)을 입력해 주세요.")
    else:
        with st.spinner("KYWA AI가 정밀 분석 중 입니다...."):
            # 프롬프트에 등급 판정 가이드라인 추가
            prompt = f"""
            시설명: [{selected_facility}], 상황: {user_description}. 
            반드시 다음 JSON 형식을 엄수하세요.
            
        try:
            with st.spinner(f"✨ KYWA AI가 [{selected_facility}] 시설의 데이터를 분석 중입니다...🔍"):
                
                # 모든 지침을 하나의 prompt 문자열 안에 포함시킵니다.
                prompt = f"""
                당신은 한국청소년활동진흥원(KYWA)의 안전관리 전문가입니다.
                
                [시설 정보]
                - 시설명: {selected_facility}
                - 담당부서: {selected_dept}
                - 현장 상황: {user_description}

                [필수 지시사항]
                1. category(분류): 시설명이 '생태', '해양' 등이라 하더라도 이를 category에 적지 마십시오. 
                   반드시 [보행 안전, 시설 안전, 화재 안전, 작업 안전, 활동 안전, 보건 및 위생관리, 화학물질 관리, 작업특성 요인, 작업환경 요인, 작업 환경, 기계(설비)적 요인, 전기적 요인, 재난 안전] 중 상황에 가장 적합한 표준 분류를 선택하십시오.
                2. 등급 판정의 객관성: 단순 노후화나 경미한 파손(예: 보도블럭 일부 들뜸/파손)은 강도(s)를 2 이하로 설정하여 전체 score가 6점 이하가 되도록 하십시오.

                [빈도 등급 판정 가이드라인] ※1~5번 기준과 예를 근거로 하되 안전수칙 및 작업표준은 있음을 전제로 등급 판정.
                1. 빈도 5점(기준: 피해가 발생할 가능성이 매우 높음)
                2. 빈도 4점(기준: 피해가 발생할 가능성이 높음)
                3. 빈도 3점(기준: 부주의하면 피해가 발생할 가능성이 있음)
                4. 빈도 2점(기준: 피해가 발생할 가능성이 낮음)
                5. 빈도 1점(기준: 피해가 발생할 가능성이 매우 낮음)

                [강도 등급 판정 가이드라인]
                1. 강도 4점(사망 또는 영구 장애), 3점(중대한 부상/휴업 수반), 2점(응급처치 이상/비휴업), 1점(경미한 부상)

                [판정 원칙 및 예외 기준]
                1. 일상적 위험 vs 산업적 위험 구분: 단순 전도 등은 강도 1점을 원칙으로 함.
                2. 점수 조정 예시: 보도블럭 파손(빈도 2, 강도 1 -> 2점), 바닥 물기(빈도 3, 강도 1 -> 3점)

            [등급 판정 가이드라인]
            - 모든 상황을 '보통'이나 '높음'으로 판정하지 마십시오.
            - 매우 낮음(1~3점): 사고 가능성이 거의 없는 단순 정리정돈이나 가벼운 불편 사항.
            - 낮음(4~6점): 주의가 필요하나 큰 부상으로 이어지지 않는 경미한 사항.
            - 보통(8~12점): 치료가 필요한 부상 위험이 있는 경우.
            - 높음(15점 이상): 골절, 중상 등 심각한 사고 위험이 있는 경우.

            1. p(빈도), s(강도)는 1~5 정수. (경미한 사안은 p, s를 1~2로 낮게 책정)
            2. score는 p*s 결과 숫자.
            3. grade는 "매우 낮음", "낮음", "보통", "높음" 중 하나.
            4. 모든 문장은 명사형 종결.
            5. 관련근거는 법령이나 규칙 명시.
            키: category, scenario, p, s, score, grade, law, solution
            """
            content = [prompt]
            if img_file: content.append(Image.open(img_file))
            try:
                # temperature를 0.0으로 설정하여 일관성 유지
                [종합 등급 판정 가이드라인]
                - 매우 낮음(1~3점), 낮음(4~6점), 보통(8~12점), 높음(15점), 매우 높음(16~20점)
                - 모든 문장은 명사형 종결.
                - 반드시 다음 JSON 형식을 엄수하세요: 키는 category, scenario, p, s, score, grade, law, solution 이며 리스트 [] 안에 담아 출력하세요.
                """

                # 분석 데이터 준비
                content = [prompt]
                if img_file:
                    from PIL import Image
                    content.append(Image.open(img_file))
                
                # 모델 호출 및 결과 처리
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                
                # 결과 저장 및 리프레시
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.success(f"✅ [{selected_facility}] 시설 분석 완료!")
                st.rerun()
            except Exception as e: st.error(f"오류: {e}")

# 8. 결과 표시 및 데이터 처리 (점수 기반 등급 재조정 로직 추가)
        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

# --- 8. 결과 표시 및 데이터 처리 ---
if st.session_state.analysis_results:
    st.markdown("### 📊 분석 결과")

    table_html = '<table class="report-table"><thead><tr><th>분류</th><th>위험상황</th><th>빈도</th><th>강도</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr></thead><tbody>'

    processed_data = []
    # 세션 스테이트에 처리된 데이터를 저장할 리스트 준비
    current_processed_data = [] 
    
    for item in st.session_state.analysis_results:
        if isinstance(item, dict):
            # 점수(score)를 기반으로 등급을 한 번 더 정밀하게 분류 (Python 로직)
            # 점수 및 등급 재산정
            p_val = int(item.get('p', 3))
            s_val = int(item.get('s', 3))
            score = p_val * s_val
            item['score'] = score # 계산 일치 확인
            item['score'] = score 

            if score <= 3: refined_grade = "매우 낮음"
            elif score <= 6: refined_grade = "낮음"
@@ -223,82 +356,68 @@

            item['grade'] = refined_grade

            # 등급별 색상 클래스 매칭
            grade_class = "grade-high" if "높음" in refined_grade else "grade-medium" if refined_grade == '보통' else "grade-low"
            sol_html = str(item.get('solution', '')).replace('\n', '<br>')

            table_html += f'<tr><td style="text-align:center">{item.get("category")}</td><td>{item.get("scenario")}</td>'
            table_html += f'<td style="text-align:center">{p_val}</td><td style="text-align:center">{s_val}</td>'
            table_html += f'<td style="text-align:center">{score}</td><td class="{grade_class}">{refined_grade}</td>'
            table_html += f'<td>{item.get("law")}</td><td>{sol_html}</td></tr>'
            processed_data.append(item)
            
            current_processed_data.append(item)

    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    
    # 중요: 전송 및 저장을 위해 세션 스테이트에 최종 데이터 저장
    st.session_state.final_data = current_processed_data

# --- 9. 최종 데이터 전송 ---
if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
    # 위젯에서 직접 값을 가져오거나 세션에서 가져옴
    t_facility = st.session_state.facility_val
    t_dept = st.session_state.dept_val

# 9. 최종 데이터 전송 (추출된 ID 반영)
    if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
        with st.spinner("데이터를 전송 중입니다..."):
            try:
                # 폼 응답 URL
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLScGuW2xT1BU5BKas0NkmADv1BCEX6R3JtQaJ5Nm30iBwGe1rA/formResponse"
    if "final_data" in st.session_state and st.session_state.final_data:
        with st.spinner(f"[{t_dept}] 데이터를 전송 중..."):
            success_count = 0
            for row in st.session_state.final_data:
                # 쿼리 파라미터 구성
                params = {
                    "entry.1651948586": t_facility,
                    "entry.1328786382": t_dept, # 담당 부서
                    "entry.1297326802": str(row.get("category", "")),
                    "entry.1421719401": str(row.get("scenario", "")),
                    "entry.1752607260": str(row.get("grade", "")),
                    "entry.271461796": str(row.get("solution", "")),
                    "entry.956205828": str(row.get("law", "")),
                    "entry.1058871339": "사진 별도 첨부"
                }

                success_count = 0
                for row in processed_data:
                    # 추출된 ID와 데이터 매핑
                    payload = {
                        "entry.1902283977": selected_facility,      # 시설명
                        "entry.1485620273": row.get("category"),    # 유해위험요인 (분류)
                        "entry.2072170485": row.get("scenario"),    # 위험상황
                        "entry.1212734944": row.get("grade"),       # 위험등급
                        "entry.2124342735": row.get("solution"),    # 감소대책
                        "entry.543223131": row.get("law")           # 관련근거
                    }
                    
                    # 전송
                    response = requests.post(form_url, data=payload)
                    if response.status_code == 200:
                        success_count += 1
                base_url = "https://docs.google.com/forms/d/e/1FAIpQLSeBGGpZQKh62zTomgTS14hhvgWzQ0FdGNVf9-r3FTzhd6ufQQ/formResponse"

                if success_count > 0:
                    st.success(f"총 {success_count}건의 데이터가 KYWA 안전센터로 전송되었습니다!")
                    st.balloons()
                else:
                    st.error("전송에 실패했습니다. 응답 상태를 확인하세요.")
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")

    # 10. 하단 저장 섹션
    if processed_data:
        st.write("---")
        st.caption("📂 결과 보고서 저장 (Word, Excel)")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "Word 저장", 
                data=create_docx(processed_data), 
                file_name=f"KYWA_Report_{selected_facility}.docx", 
                use_container_width=True
            )
        with dl_col2:
            st.download_button(
                "Excel 저장", 
                data=create_excel(processed_data), 
                file_name=f"KYWA_Data_{selected_facility}.xlsx", 
                use_container_width=True
            )

-----------

현재까지의 코드는 이렇게 구성되어 있어.
이 상태에서 아래 내용만 바꿔서 구성하려고 해.
구글폼에서 종합하는 내용은 아래 내용이 잘 반영되면 수정할 예정이야.

1. 항목 변경
  - 변경전 : 성명/시설명/유해위험요인/위험상황/위험등급/감소대책/관련근거/사진 기록
  - 변경후 : 시설명/부서명/유해위험요인/위험상황/위험등급/감소대책/관련근거/사진 기록
2. 부서명: 드롭다운 형식으로 선택
  - 드롭다운 선택지: 활동부/협력부/청렴감사실/기획혁신부/인재경영부/홍보전략부/안전경영부/재무회계부/디지털정보부/미래활동부/정책사업부/활동안전부/활동인증부/청소년성장지원부/지도인력양성부/지도인력개발부

종합하면, '성명' 입력란은 삭제하고, 첫 선택지는 점검 대상 시설(라디오박스 유지) 이고 부서 선택(드롭다운 형식), 현장 상황 설명(텍스트 장문형으로 입력), 사진방식(카메라/갤러리/없음 중 선택 유지), 그 아래부터는 그대로 유지할거야. KYWA AI 위험요인 분석 시작 등등
                try:
                    # 전송 방식의 신뢰성을 위해 requests.get 사용 (파라미터 포함)
                    resp = requests.get(base_url, params=params)
                    if resp.status_code == 200:
                        success_count += 1
                except:
                    pass
            
            if success_count > 0:
                st.success(f"[{t_dept}] 부서로 {success_count}건 전송 완료!")
                st.balloons()
        
# --- 10. 하단 저장 섹션 ---
if "final_data" in st.session_state and st.session_state.final_data:
    st.write("---")
    # 파일명에 사용할 시설명 안전하게 가져오기
    f_name = st.session_state.get('facility_val', 'Result')
    
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button("Word 저장", data=create_docx(st.session_state.final_data), file_name=f"KYWA_{f_name}.docx", use_container_width=True)
    with dl_col2:
        st.download_button("Excel 저장", data=create_excel(st.session_state.final_data), file_name=f"KYWA_{f_name}.xlsx", use_container_width=True)
