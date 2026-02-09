import os
import ssl
import json
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

# 3. 헤더 디자인 (이미지-홈페이지 / 타이틀-새로고침 연결)
header_col1, header_col2 = st.columns([1, 4])

with header_col1:
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
    .stButton>button { 
        width: 100% !important; border-radius: 8px; font-weight: bold; 
        background-color: #E60012; color: white; height: 3.5em; border: none; 
        transition: all 0.3s ease;
    }
    .stButton>button:hover { background-color: #C1000F !important; color: white !important; }
    
    .report-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.95em; table-layout: fixed; }
    .report-table th, .report-table td { padding: 12px; border: 1px solid #dee2e6; vertical-align: top; word-break: keep-all; line-height: 1.6; }
    .report-table th { background-color: #f1f3f5; text-align: center; font-weight: bold; }
    
    /* 화면 표시용 열 너비 설정 */
    .report-table th:nth-child(1) { width: 8%; }  /* 분류 */
    .report-table th:nth-child(2) { width: 18%; } /* 위험상황 */
    .report-table th:nth-child(3) { width: 6%; }  /* 빈도 */
    .report-table th:nth-child(4) { width: 6%; }  /* 강도 */
    .report-table th:nth-child(5) { width: 6%; }  /* 점수 */
    .report-table th:nth-child(6) { width: 8%; }  /* 등급 */
    .report-table th:nth-child(7) { width: 20%; } /* 관련근거 */
    .report-table th:nth-child(8) { width: 28%; } /* 감소대책 */
    
    .grade-high { background-color: #ffe3e3 !important; color: #b91c1c !important; font-weight: bold; text-align: center; }
    .grade-medium { background-color: #fff5dc !important; color: #92400e !important; font-weight: bold; text-align: center; }
    .grade-low { background-color: #ebfbee !important; color: #166534 !important; font-weight: bold; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

GRADE_MAP = {'high': '높음', 'medium': '보통', 'low': '낮음', 'High': '높음', 'Medium': '보통', 'Low': '낮음', '매우 높음': '높음', '약간 높음': '보통'}

# --- 엑셀 파일 생성 함수 (열 너비 최적화 포함) ---
def create_excel(data):
    if not data: return None
    df = pd.DataFrame(data)
    column_mapping = {
        'category': '분류', 'scenario': '위험상황', 'p': '빈도', 's': '강도', 
        'score': '점수', 'grade': '등급', 'law': '관련근거', 'solution': '감소대책'
    }
    df = df.rename(columns=column_mapping)
    final_cols = ['분류', '위험상황', '빈도', '강도', '점수', '등급', '관련근거', '감소대책']
    df = df[[c for c in final_cols if c in df.columns]]
    
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='위험성평가_결과')
        
        workbook  = writer.book
        worksheet = writer.sheets['위험성평가_결과']
        
        # 1. 포맷 정의
        # 텍스트가 많은 컬럼용 (양쪽 정렬 + 상단 정렬)
        wrap_format = workbook.add_format()
        wrap_format.set_text_wrap()
        wrap_format.set_align('top')

        # 짧은 텍스트 컬럼용 (가운데 정렬 + 상단 정렬)
        center_top_format = workbook.add_format()
        center_top_format.set_align('center') # 가로 가운데
        center_top_format.set_align('top')    # 세로 상단

        # 2. 열 너비 및 포맷 적용
        worksheet.set_column(0, 0, 12, center_top_format)    # 분류 (가운데/상단)
        worksheet.set_column(1, 1, 25, wrap_format)          # 위험상황 (양쪽/상단)
        worksheet.set_column(2, 4, 6, center_top_format)     # 빈도, 강도, 점수 (가운데/상단)
        worksheet.set_column(5, 5, 10, center_top_format)    # 등급 (가운데/상단)
        worksheet.set_column(6, 6, 30, wrap_format)          # 관련근거 (양쪽/상단)
        worksheet.set_column(7, 7, 40, wrap_format)          # 감소대책 (양쪽/상단)
        
    return bio.getvalue()

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL # 이름을 이걸로 변경

def create_docx(data):
    if not data: return None
    doc = Document()
    doc.add_heading('KYWA AI 위험성평가 결과 보고서', 0)
    
    table = doc.add_table(rows=1, cols=8)
    table.style = 'Table Grid'
    
    headers = ['분류', '위험상황', '빈도', '강도', '점수', '등급', '근거', '대책']
    hdr_cells = table.rows[0].cells
    for i, txt in enumerate(headers):
        hdr_cells[i].text = txt
        hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for item in data:
        row_cells = table.add_row().cells
        keys = ['category', 'scenario', 'p', 's', 'score', 'grade', 'law', 'solution']
        center_cols = [0, 2, 3, 4, 5]

        for idx, key in enumerate(keys):
            cell = row_cells[idx]
            cell.text = str(item.get(key, ''))
            
            # 수직 정렬 코드를 아래와 같이 수정 (WD_ALIGN_VERTICAL 사용)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP 
            
            if idx in center_cols:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
                
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

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

# 6. 입력 섹션 (라디오박스/드롭다운 라벨 크기 및 볼드 강조)
col1, col2 = st.columns(2)

with col1:
    # 1. 시설명 선택
    st.markdown("### **🏢 점검 대상 시설**")
    selected_facility = st.radio(
        "시설명 선택", # 가이드용 (숨겨짐)
        ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], 
        horizontal=True,
        label_visibility="collapsed" # 기본 라벨 숨김
    )
    
    st.write("") # 간격 조절

    # 2. 부서명 선택
    st.markdown("### **📂 담당 부서 선택**")
    dept_list = [
        "활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", 
        "안전경영부", "재무회계부", "디지털정보부", "미래활동부", "정책사업부", 
        "활동안전부", "활동인증부", "청소년성장지원부", "지도인력양성부", "지도인력개발부", "자회사"
    ]
    selected_dept = st.selectbox(
        "부서명 선택", 
        dept_list,
        label_visibility="collapsed"
    )
    
    st.write("") # 간격 조절

    # 3. 현장 상황 설명
    st.markdown("### **📝 현장 상황 설명**")
    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n3. 생활관 사다리 고장으로 추락 위험 등"
    user_description = st.text_area(
        "상황 설명 입력", 
        placeholder=placeholder_text, 
        height=150,
        label_visibility="collapsed"
    )

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
    if not user_description.strip() and not img_file:
        st.warning("⚠️ 분석할 내용(글 또는 사진)을 입력해 주세요.")
    else:
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

        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

# --- 8. 결과 표시 및 데이터 처리 ---
if st.session_state.analysis_results:
    st.markdown("### 📊 분석 결과")
    
    table_html = '<table class="report-table"><thead><tr><th>분류</th><th>위험상황</th><th>빈도</th><th>강도</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr></thead><tbody>'
    
processed_data = [] # 여기서 변수가 생성됩니다.
    for item in st.session_state.analysis_results:
        if isinstance(item, dict):
            # 점수(score)를 기반으로 등급을 한 번 더 정밀하게 분류 (Python 로직)
            p_val = int(item.get('p', 3))
            s_val = int(item.get('s', 3))
            score = p_val * s_val
            item['score'] = score # 계산 일치 확인
            
            if score <= 3: refined_grade = "매우 낮음"
            elif score <= 6: refined_grade = "낮음"
            elif score <= 12: refined_grade = "보통"
            else: refined_grade = "높음"
            
            item['grade'] = refined_grade
            
            # 등급별 색상 클래스 매칭
            grade_class = "grade-high" if "높음" in refined_grade else "grade-medium" if refined_grade == '보통' else "grade-low"
            sol_html = str(item.get('solution', '')).replace('\n', '<br>')
            
            table_html += f'<tr><td style="text-align:center">{item.get("category")}</td><td>{item.get("scenario")}</td>'
            table_html += f'<td style="text-align:center">{p_val}</td><td style="text-align:center">{s_val}</td>'
            table_html += f'<td style="text-align:center">{score}</td><td class="{grade_class}">{refined_grade}</td>'
            table_html += f'<td>{item.get("law")}</td><td>{sol_html}</td></tr>'
            processed_data.append(item)
    
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    
# --- 9. 최종 데이터 전송 (반드시 이 위치, 즉 if문 안으로 이동) ---
    st.write(" ") # 여백
    if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
        with st.spinner("데이터를 전송 중입니다..."):
            # 이제 processed_data를 안전하게 참조할 수 있습니다.
            for row in processed_data:
            try:
                # 폼 응답 URL
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLScGuW2xT1BU5BKas0NkmADv1BCEX6R3JtQaJ5Nm30iBwGe1rA/formResponse"
                
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
                
                if success_count > 0:
                    st.success(f"총 {success_count}건의 데이터가 KYWA 안전센터로 전송되었습니다!")
                    st.balloons()
                else:
                    st.error("전송에 실패했습니다. 응답 상태를 확인하세요.")
                    
            except Exception as e:
                st.error(f"오류 발생: {e}")


# 10. 하단 저장 섹션
if "final_processed_data" in st.session_state and st.session_state.final_processed_data:
    st.write("---")
    st.markdown("### **📂 결과 보고서 저장 (Word, Excel)**")
    
    # 세션 상태에 저장된 데이터를 가져옴
    processed_data = st.session_state.final_processed_data
    
    # 파일명 설정 (user_name 제거, 시설명과 부서명 조합)
    file_prefix = f"KYWA_안전점검_{selected_facility}_{selected_dept}"
    
    dl_col1, dl_col2 = st.columns(2)
    
    with dl_col1:
        # Word 저장
        st.download_button(
            label="📄 Word 보고서 저장", 
            data=create_docx(processed_data), 
            file_name=f"{file_prefix}.docx", 
            use_container_width=True,
            key="doc_download"
        )
        
    with dl_col2:
        # Excel 저장
        st.download_button(
            label="📊 Excel 데이터 저장", 
            data=create_excel(processed_data), 
            file_name=f"{file_prefix}.xlsx", 
            use_container_width=True,
            key="xls_download"
        )

# --- 대시보드 섹션 ---
st.write("---")

# 함수 호출 전 정의 확인
try:
    dashboard_data = load_dashboard_data()
except NameError:
    st.error("⚠️ load_dashboard_data() 함수가 정의되지 않았습니다. 코드 상단을 확인해 주세요.")
    dashboard_data = None

if dashboard_data is not None:
    # 2. 날짜 필터링 (2026년 데이터만)
    yearly_data = dashboard_data[dashboard_data['타임스탬프'].dt.year == 2026] if '타임스탬프' in dashboard_data.columns else dashboard_data

    if yearly_data.empty:
        st.warning("📅 2026년도로 기록된 데이터가 시트에 아직 없습니다. 첫 번째 데이터를 전송해 보세요!")
    else:
        st.subheader("📊 실시간 점검 데이터 현황 (2026년)")
        
        # 3. 상단 지표
        total_count = len(yearly_data)
        m1, m2 = st.columns(2)
        m1.metric("올해 누적 점검 건수", f"{total_count} 건")
        
        # '부서명' 또는 '시설명' 기준으로 참여 현황 파악 (user_name 대체)
        count_col = "시설명" 
        if count_col in yearly_data.columns:
            m2.metric("점검 참여 시설 수", f"{yearly_data[count_col].nunique()} 개소")

        # 4. 그래프 시각화
        g_col1, g_col2 = st.columns(2)
        
        with g_col1:
            # 시트의 실제 컬럼명: '유해위험요인 (분류)' 등 저장 정보 참조
            target_col_cat = "유해위험요인 (분류)" 
            if target_col_cat in yearly_data.columns:
                st.write(f"**📂 {target_col_cat} 현황**")
                fig_pie = px.pie(yearly_data, names=target_col_cat, hole=0.3)
                fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info(f"'{target_col_cat}' 데이터 분석 중...")

        with g_col2:
            target_col_fac = "시설명" 
            if target_col_fac in yearly_data.columns:
                st.write(f"**🏢 {target_col_fac}별 점검 건수**")
                fac_counts = yearly_data[target_col_fac].value_counts().reset_index()
                fac_counts.columns = [target_col_fac, '건수']
                fig_bar = px.bar(fac_counts, x=target_col_fac, y='건수', color=target_col_fac)
                fig_bar.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350, showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)










