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
import plotly.express as px

# [수정 1] 페이지 설정이 무조건 가장 먼저 와야 합니다!
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

# [수정 2] 파라미터 이름을 unsafe_allow_html=True 로 변경
st.markdown("""
    <style>
    /* 모든 텍스트가 현재 테마의 글자색을 따르도록 설정 */
    html, body, [data-testid="stWidgetLabel"] p {
        color: var(--text-color);
    }
    
    /* 모바일 환경에서 표(Table)나 컨테이너의 가독성 향상 */
    .stDataFrame {
        width: 100% !important;
    }
    
    /* 이미지나 아이콘이 다크모드에서 너무 눈부시지 않게 살짝 조절 */
    img {
        max-width: 100%;
        filter: brightness(var(--image-brightness, 1));
    }
    </style>
    """, unsafe_allow_html=True)

# 1. 환경 설정 및 보안 우회 (필요한 경우)
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정 및 세션 초기화
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "final_data" not in st.session_state:
    st.session_state.final_data = None

# 3. 모델 설정 (Secrets에서 키를 안전하게 가져옴)
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key, transport='rest')
        model = genai.GenerativeModel('gemini-flash-latest')
    else:
        st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.")
        st.stop()
except Exception as e:
    st.error(f"API 설정 오류가 발생했습니다: {e}")
    st.stop()

# --- 도구 함수 (Word/Excel 생성) ---
def create_docx(data):
    doc = Document()
    doc.add_heading('KYWA AI 위험성평가 결과 보고서', 0)
    for item in data:
        doc.add_paragraph(f"분류: {item.get('category')}")
        doc.add_paragraph(f"상황: {item.get('scenario')}")
        doc.add_paragraph(f"등급: {item.get('grade')} (점수: {item.get('score')})")
        doc.add_paragraph(f"대책: {item.get('solution')}")
        doc.add_paragraph("-" * 20)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def create_excel(data):
    df = pd.DataFrame(data)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return bio.getvalue()

# --- [추가] 버튼 스타일 설정 ---
st.markdown("""
    <style>
    /* 모든 Streamlit 버튼 스타일 수정 */
    div.stButton > button {
        background-color: #ff4b4b !important; /* 기본 붉은색 */
        color: white !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
        border-radius: 0.5rem !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
    }

    /* 마우스 호버(Hover) 시 효과 */
    div.stButton > button:hover {
        background-color: #ff3333 !important; /* 마우스 올렸을 때 더 진한 빨강 */
        color: white !important;
        border: none !important;
        transform: scale(1.01); /* 아주 살짝 커지는 효과 */
    }
    
    /* Word/Excel 저장 버튼 등 일반 버튼도 동일 적용을 원치 않으시면 위 범위를 좁힐 수 있습니다 */
    </style>
""", unsafe_allow_html=True)

# --- 4. 스타일 및 헤더 디자인 (오류 방지 중괄호 처리) ---
st.markdown("""
    <style>
    /* 버튼 스타일 */
    div.stButton > button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 0.5rem !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover {
        background-color: #ff3333 !important;
        transform: scale(1.01);
    }
    /* 로고 및 타이틀 스타일 */
    .logo-img { cursor: pointer; display: block; margin-top: 10px; }
    .refresh-title { text-decoration: none !important; color: inherit !important; cursor: pointer; }
    .refresh-title:hover { color: #FF4B4B !important; }
    </style>
""", unsafe_allow_html=True)

header_col1, header_col2 = st.columns([1, 4])
raw_logo_url = "https://raw.githubusercontent.com/archi01-safety/kywa-safety-app/main/kywa_logo.png"

with header_col1:
    # f-string을 쓰지 않고 직접 삽입하여 중괄호 오류 원천 차단
    st.markdown(f'''
        <a href="https://www.kywa.or.kr/main/main.jsp" target="_blank">
            <img src="{raw_logo_url}" width="300" class="logo-img">
        </a>
    ''', unsafe_allow_html=True)

with header_col2:
    st.markdown("""
        <a href="/" target="_self" class="refresh-title">
            <h1 style='margin-bottom: 0;'>🚨 KYWA AI 위험성평가 시스템</h1>
        </a>
        <p style='color: gray; margin-top: 0;'>Korea Youth Work Agency - 스마트 안전관리 플랫폼</p>
    """, unsafe_allow_html=True)

st.divider()

# --- 5. 입력 섹션 ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### **🏢 점검 대상 정보**")
    selected_facility = st.radio("• 시설명 선택 (필수)", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    
    dept_list = ["활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", "안전경영부", "재무회계부", "디지털정보부", "자회사"]
    selected_dept = st.selectbox("• 담당 부서 선택 (필수)", dept_list)
    
    st.markdown("### **📝 현장 상황 설명**")
    placeholder_text = "<예  시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험\n  (자세히 작성할수록 정확한 결과가 나옵니다.)"
    user_description = st.text_area("• 상황 설명 입력 (권장)", placeholder=placeholder_text, height=150)

with col2:
    st.markdown("### **📸 사진 기록 방식**")
    source_option = st.radio("• 사진 방식 선택  -  얼굴(정면)을 업로드 하지 않도록 주의🚨", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    
    img_file = None
    if "📷" in source_option:
        img_file = st.camera_input("📸 현장 사진 촬영")
    elif "🖼️" in source_option:
        img_file = st.file_uploader("🖼️ 사진 파일 업로드", type=['png', 'jpg', 'jpeg'])

# --- 6. AI 분석 실행 ---
if st.button("🚀 KYWA AI 위험요인 분석 시작", use_container_width=True):
    if not user_description.strip() and not img_file:
        st.warning("⚠️ 분석할 내용(글 또는 사진)을 입력해 주세요.")
    else:
        try:
            with st.spinner(f"✨ KYWA AI가 [{selected_facility}] 위험성을 분석 중입니다..."):
                prompt = f"""
                당신은 한국청소년활동진흥원(KYWA)의 안전관리 전문가입니다.
                다음 상황을 분석하여 위험성평가를 실시하십시오.

                [시설 정보]
                - 시설명: {selected_facility}
                - 담당부서: {selected_dept}
                - 현장 상황: {user_description}

                [필수 지시사항]
                1. category(분류): [보행 안전, 시설 안전, 화재 안전, 작업 안전, 활동 안전, 보건 및 위생관리, 화학물질 관리, 작업 환경, 기계(설비)적 요인, 전기적 요인, 재난 안전] 중 선택.
                2. p(빈도)와 s(강도)는 1~5 정수. 
                3. 매우 낮음(1~3점), 낮음(4~6점), 보통(8~12점), 높음(15점 이상).
                4. 반드시 다음 JSON 형식(리스트 형태)으로 출력:
                   [{{ "category": "...", "scenario": "...", "p": 0, "s": 0, "score": 0, "grade": "...", "law": "...", "solution": "..." }}]
                """
                
                content = [prompt]
                if img_file:
                    content.append(Image.open(img_file))
                
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                
                # 결과 저장 (리스트 형태 보장)
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.success("✅ 위험성 분석 완료!")
                st.rerun()
        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")

# --- 7. 결과 표시 및 데이터 처리 ---
if st.session_state.analysis_results:
    st.markdown("### 📊 분석 결과")
    
    st.session_state.final_data = [] # 데이터 저장용 리스트 초기화

    # 1. 스타일 및 헤더 정의 (예전 코드처럼 table_html 변수 하나로 시작)
    table_html = """
    <style>
        .report-table { width:100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
        .report-table th { background-color: #f0f2f6; color: #31333F; padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: bold; }
        .report-table td { padding: 10px; border: 1px solid #ddd; text-align: center; color: #31333F; vertical-align: middle; }
        .grade-high { background-color: #ff4b4b; color: white !important; font-weight: bold; }
        .grade-medium { background-color: #ffa421; color: white !important; font-weight: bold; }
        .grade-low { background-color: #00cc96; color: white !important; font-weight: bold; }
        .text-left { text-align: left !important; }
    </style>
    <table class="report-table">
        <thead>
            <tr>
                <th width="10%">분류</th>
                <th width="30%">위험상황</th>
                <th width="5%">빈도</th>
                <th width="5%">강도</th>
                <th width="5%">점수</th>
                <th width="10%">등급</th>
                <th width="15%">관련근거</th>
                <th width="20%">감소대책</th>
            </tr>
        </thead>
        <tbody>
    """

    # 2. 데이터 반복문 (table_html에 직접 문자열 이어붙이기)
    for item in st.session_state.analysis_results:
        # 빈도/강도 숫자 변환
        try:
            p = int(item.get('p', 0))
            s = int(item.get('s', 0))
        except:
            p, s = 0, 0
            
        score = p * s
        
        # 등급 계산
        if score <= 3: grade = "매우 낮음"
        elif score <= 6: grade = "낮음"
        elif score <= 12: grade = "보통"
        else: grade = "높음"
        
        # 스타일 클래스 지정
        if grade == "높음": grade_class = "grade-high"
        elif grade == "보통": grade_class = "grade-medium"
        else: grade_class = "grade-low"

        # 텍스트 내 줄바꿈 처리 (예전 코드의 replace 로직 적용)
        # 엑셀 셀 내에서 줄바꿈(Alt+Enter)한 내용을 HTML 줄바꿈(<br>)으로 변경
        scenario_text = str(item.get('scenario', '-')).replace('\n', '<br>')
        solution_text = str(item.get('solution', '-')).replace('\n', '<br>')

        # HTML 행 추가 (들여쓰기 없이 한 줄로 이어붙여 오류 방지)
        table_html += f'<tr>'
        table_html += f'<td>{item.get("category", "-")}</td>'
        table_html += f'<td class="text-left">{scenario_text}</td>'
        table_html += f'<td>{p}</td>'
        table_html += f'<td>{s}</td>'
        table_html += f'<td>{score}</td>'
        table_html += f'<td class="{grade_class}">{grade}</td>'
        table_html += f'<td>{item.get("law", "-")}</td>'
        table_html += f'<td class="text-left">{solution_text}</td>'
        table_html += f'</tr>'
        
        # 최종 데이터 저장용 업데이트
        item['score'] = score
        item['grade'] = grade
        st.session_state.final_data.append(item)

    # 3. 테이블 닫기 및 출력
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

# --- 8. 최종 데이터 전송 및 저장 (밀림 현상 수정본) ---
st.write("")
if st.button("✅ KYWA AI 안전센터로 데이터 최종 전송", use_container_width=True):
    if not st.session_state.final_data:
        st.error("⚠️ 전송할 데이터가 없습니다. 먼저 분석을 진행해 주세요.")
    else:
        with st.spinner("🚀 'KYWA 안전센터'에 데이터를 전송 중입니다..."):
            try:
                # 폼 응답 URL
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLSeBGGpZQKh62zTomgTS14hhvgWzQ0FdGNVf9-r3FTzhd6ufQQ/formResponse"
                
                success_count = 0
                for row in st.session_state.final_data:
                    # 각 열(B~I)에 정확히 대응하도록 ID를 재배정함
                    payload = {
                        "entry.1651948586": selected_facility,      # B열: 시설명
                        "entry.1328786382": selected_dept,          # C열: 담당 부서
                        "entry.1297326802": row.get("category"),     # D열: 유해위험요인 (분류)
                        "entry.1421719401": row.get("scenario"),     # E열: 위험상황
                        "entry.1752607260": row.get("grade"),        # F열: 위험등급
                        "entry.271461796": row.get("solution"),      # G열: 감소대책
                        "entry.956205828": row.get("law"),           # H열: 관련근거
                        "entry.1058871339": "사진 포함" if img_file else "사진 없음"      # I열: 사진 기록 (텍스트)
                    }
                    
                    res = requests.post(form_url, data=payload)
                    if res.status_code == 200:
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ 최종 제출한 데이터 {success_count}건이 'KYWA AI 안전센터'에 정상적으로 전송되었습니다!")
                    st.balloons()
                else:
                    st.error("전송에 실패했습니다. 응답 코드를 확인하세요.")
                    
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
                
    # 저장 버튼
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button("📂 Word 저장", data=create_docx(st.session_state.final_data), file_name=f"KYWA_{selected_facility}.docx", use_container_width=True)
    with dl_col2:
        st.download_button("📊 Excel 저장", data=create_excel(st.session_state.final_data), file_name=f"KYWA_{selected_facility}.xlsx", use_container_width=True)

# --- [수정] 날짜 형식 오류를 해결한 데이터 로드 함수 ---
def load_dashboard_data():
    # 구글 시트 CSV 내보내기 링크
    sheet_url = "https://docs.google.com/spreadsheets/d/1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q/export?format=csv&gid=413707311"
    
    try:
        df = pd.read_csv(sheet_url)
        
        if '타임스탬프' in df.columns:
            # 1. 한국어 '오전/오후'를 Pandas가 인식 가능한 'AM/PM'으로 변경
            df['타임스탬프'] = df['타임스탬프'].str.replace('오전', 'AM').str.replace('오후', 'PM')
            
            # 2. 날짜 형식으로 변환 (format을 지정하지 않아도 치환 후에는 잘 작동합니다)
            df['타임스탬프'] = pd.to_datetime(df['타임스탬프'], errors='coerce')
            
            # 3. 변환 실패한 데이터(NaT) 제거 (선택 사항)
            df = df.dropna(subset=['타임스탬프'])
            
        return df
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return None

# --- 대시보드 섹션 ---
st.write("---")
dashboard_data = load_dashboard_data()

if dashboard_data is not None:
    # 2. 날짜 필터링 (2026년 데이터만)
    if '타임스탬프' in dashboard_data.columns:
        yearly_data = dashboard_data[dashboard_data['타임스탬프'].dt.year == 2026].copy()
    else:
        yearly_data = dashboard_data.copy()

    if yearly_data.empty:
        st.warning("📅 2026년도로 기록된 데이터가 시트에 아직 없습니다. 첫 번째 데이터를 전송해 보세요!")
    else:
        st.subheader("📊 실시간 점검 데이터 현황 (2026년)")
        
        # 3. 상단 지표
        total_count = len(yearly_data)
        m1, m2 = st.columns(2)
        m1.metric("올해 누적 점검 건수", f"{total_count} 건")
        
        author_col = "작성자 성명" 
        if author_col in yearly_data.columns:
            m2.metric("참여 인원(명)", f"{yearly_data[author_col].nunique()} 명")
        else:
            m2.metric("점검 시설 종류", f"{yearly_data['시설명'].nunique()} 곳")

        # --- 색상 맵 설정 ---
        CATEGORY_COLOR_MAP = {
            "시설 안전": "#D32F2F", "화재 안전": "#FF5722", "재난 안전": "#880E4F",
            "작업환경 요인": "#455A64", "작업 환경": "#455A64", "기계(설비)적 요인": "#795548",
            "작업 안전": "#FFA000", "전기적 요인": "#FBC02D", "보건 및 위생관리": "#E91E63",
            "화학물질 관리": "#9C27B0", "보행 안전": "#1976D2", "활동 안전": "#388E3C"
        }

        FACILITY_COLOR_MAP = {
            "중앙": "#B93444", "본원": "#6B5B95", "평창": "#E2725B",
            "바이오": "#D2B48C", "해양": "#5B84B1", "우주": "#2E4A62",
            "미래": "#92B06A", "생태": "#5F7161"
        }

        # --- 4. 그래프 시각화 영역 ---
        g_col1, g_col2 = st.columns(2)

        with g_col1:
            if len(yearly_data.columns) >= 4:
                target_col_cat = yearly_data.columns[3] 
                st.write(f"**{target_col_cat} 현황**")
                if not yearly_data[target_col_cat].dropna().empty:
                    yearly_data[target_col_cat] = yearly_data[target_col_cat].astype(str).str.strip()
                    
                    fig_pie = px.pie(
                        yearly_data, names=target_col_cat, hole=0.3,
                        color=target_col_cat, color_discrete_map=CATEGORY_COLOR_MAP
                    )
                    # 파이 차트도 확대/축소 방지 적용
                    fig_pie.update_layout(
                        margin=dict(t=30, b=0, l=0, r=0), 
                        height=350,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=None),
                        dragmode=False
                    )
                    st.plotly_chart(fig_pie, use_container_width=True, theme="streamlit", config={'displayModeBar': False})

        with g_col2:
            target_col_fac = "시설명" 
            if target_col_fac in yearly_data.columns:
                st.write(f"**{target_col_fac}별 점검 건수**")
                
                # [중요] 데이터 집계 로직 (이 부분이 누락되어 NameError가 발생했었습니다)
                yearly_data[target_col_fac] = yearly_data[target_col_fac].astype(str).str.strip()
                fac_counts = yearly_data[target_col_fac].value_counts().reset_index()
                fac_counts.columns = [target_col_fac, '건수']
                
                fig_bar = px.bar(
                    fac_counts, x=target_col_fac, y='건수', color=target_col_fac,
                    color_discrete_map=FACILITY_COLOR_MAP
                )
                
                # 확대/축소 방지 및 레이아웃 설정
                fig_bar.update_xaxes(fixedrange=True)
                fig_bar.update_yaxes(fixedrange=True)
                
                fig_bar.update_layout(
                    margin=dict(t=30, b=0, l=0, r=0), 
                    height=350, 
                    showlegend=False,
                    xaxis_title=None, 
                    yaxis_title="점검 건수",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=None),
                    dragmode=False 
                )
                
                st.plotly_chart(
                    fig_bar, 
                    use_container_width=True, 
                    theme="streamlit",
                    config={'displayModeBar': False}
                )

# --- 푸터(Footer) 섹션 ---
st.write("") # 간격 확보
st.write("---")
footer_cols = st.columns([3, 1])

with footer_cols[0]:
    st.markdown("### 🔒 Data Governance & Privacy")
    st.caption("""
    **© 2026 한국청소년활동진흥원(KYWA) 안전경영부.** 본 시스템은 **'공공기관 AI 활용 가이드라인'** 및 기관 내부 **'정보보안 업무규정'**을 엄격히 준수합니다.
    
    * **데이터 보안:** 입력된 모든 정보는 API 옵트아웃(Opt-out) 설정이 적용되어 외부 모델 학습에 활용되지 않습니다.
    * **운영 방침:** 'KYWA AI 안전센터'로 전송된 데이터는 **안전경영부 담당자의 데이터 정합성 검토**를 거칩니다. 
      점검 내용이 부적절하거나 중복된 경우, 데이터 신뢰성 유지를 위해 운영 관리자에 의해 임의 수정 또는 삭제될 수 있습니다.
    * **면책 고지:** AI 분석 결과는 안전 점검 보조 도구로써 제공되며, 실제 위험성 평가 시 전문가의 최종 확정을 권고합니다.
    """)

with footer_cols[1]:
    st.markdown("### 📞 Contact")
    # HTML을 사용하여 아이콘 색상을 제어합니다 (Dark Gray/Black 계열)
    st.markdown(f"""
    <div style="line-height: 1.6;">
        <span style="font-weight: bold; font-size: 0.9rem; color: #31333F;">안전경영부(Safety Management)</span><br>
        <span style="color: #444; font-size: 0.85rem;">📧 archi01@kywa.or.kr</span><br>
        <span style="color: #444; font-size: 0.85rem;">
            <span style="display: inline-block; transform: rotate(10deg); color: #000;">📞</span> 02-6959-7138
        </span>
    </div>
    """, unsafe_allow_html=True)

# 최하단 한 줄 강조
st.markdown("<p style='font-size: 0.8rem; color: gray; text-align: center;'>Safe Together, KYWA AI Risk Assessment System</p>", unsafe_allow_html=True)
