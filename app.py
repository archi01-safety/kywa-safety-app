import os
import ssl
import json
import requests
import io
import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px  # 시각화를 위해 추가
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL

# 1. 환경 설정 및 보안 우회
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정 및 세션 초기화
st.set_page_config(page_title="KYWA AI 위험성평가 시스템 (V2)", layout="wide", page_icon="🚨")

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# --- [추가] 구글 시트 데이터 로드 및 대시보드 함수 ---
# 실제 구글 시트의 ID를 입력하세요 (URL의 /d/ 와 /edit 사이의 문자열)
SHEET_ID = "1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q" # 실제 시트 ID로 반영
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=413707311"

def load_dashboard_data():
    try:
        import time
        # 캐시 방지를 위해 타임스탬프 쿼리 추가
        updated_url = f"{SHEET_URL}&t={int(time.time())}"
        df = pd.read_csv(updated_url)
        
        # 컬럼명 앞뒤 공백 제거
        df.columns = [c.strip() for c in df.columns]
        
        if '타임스탬프' in df.columns:
            # 한국어 '오전/오후'를 판다스가 인식 가능한 'AM/PM'으로 교체
            df['타임스탬프'] = df['타임스탬프'].str.replace('오전', 'AM').str.replace('오후', 'PM')
            
            # 날짜 형식 변환 (알려주신 2026. 2. 2 포맷 대응)
            df['타임스탬프'] = pd.to_datetime(df['타임스탬프'], errors='coerce')
            
            # 변환 실패 데이터 제거
            df = df.dropna(subset=['타임스탬프'])
            
        return df
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류 발생: {e}")
        return None

# 2.5 로고 이미지 로드
logo_path = "kywa_logo.png"
logo_img = None
if os.path.exists(logo_path):
    logo_img = Image.open(logo_path)

# 3. 헤더 디자인 (수정본)
header_col1, header_col2 = st.columns([1, 4])
with header_col1:
    if logo_img:
        # 로고 이미지 표시 (너비는 적절히 조절하세요)
        st.image(logo_img, width=300) 
    else:
        # 이미지가 없을 경우 기존 텍스트 표시
        st.markdown("<h2 style='color: #E60012; margin-top: 0;'>KYWA</h2>", unsafe_allow_html=True)

with header_col2:
    st.title("🚨 KYWA AI 위험성평가 시스템")
    st.caption("Korea Youth Work Agency - 스마트 안전관리 플랫폼")

# 4. 커스텀 CSS (기존 유지)
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
    
    .report-table th:nth-child(1) { width: 8%; }  
    .report-table th:nth-child(2) { width: 18%; } 
    .report-table th:nth-child(3) { width: 6%; }  
    .report-table th:nth-child(4) { width: 6%; }  
    .report-table th:nth-child(5) { width: 6%; }  
    .report-table th:nth-child(6) { width: 8%; }  
    .report-table th:nth-child(7) { width: 20%; } 
    .report-table th:nth-child(8) { width: 28%; } 
    
    .grade-high { background-color: #ffe3e3 !important; color: #b91c1c !important; font-weight: bold; text-align: center; }
    .grade-medium { background-color: #fff5dc !important; color: #92400e !important; font-weight: bold; text-align: center; }
    .grade-low { background-color: #ebfbee !important; color: #166534 !important; font-weight: bold; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 엑셀 및 워드 생성 함수 (생략 - 기존과 동일) ---
def create_excel(data):
    if not data: return None
    df = pd.DataFrame(data)
    column_mapping = {'category': '분류', 'scenario': '위험상황', 'p': '빈도', 's': '강도', 'score': '점수', 'grade': '등급', 'law': '관련근거', 'solution': '감소대책'}
    df = df.rename(columns=column_mapping)
    final_cols = ['분류', '위험상황', '빈도', '강도', '점수', '등급', '관련근거', '감소대책']
    df = df[[c for c in final_cols if c in df.columns]]
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='위험성평가_결과')
        workbook = writer.book
        worksheet = writer.sheets['위험성평가_결과']
        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
        center_top_format = workbook.add_format({'align': 'center', 'valign': 'top'})
        worksheet.set_column(0, 0, 12, center_top_format)
        worksheet.set_column(1, 1, 25, wrap_format)
        worksheet.set_column(2, 4, 6, center_top_format)
        worksheet.set_column(5, 5, 10, center_top_format)
        worksheet.set_column(6, 6, 30, wrap_format)
        worksheet.set_column(7, 7, 40, wrap_format)
    return bio.getvalue()

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
        for idx, key in enumerate(keys):
            cell = row_cells[idx]
            cell.text = str(item.get(key, ''))
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP 
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if idx in [0, 2, 3, 4, 5] else WD_ALIGN_PARAGRAPH.LEFT
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# 5. 모델 설정 (Secrets에서 키를 안전하게 가져옴)
try:
    # Streamlit Secrets에 저장된 키를 자동으로 호출합니다.
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key, transport='rest')
        model = genai.GenerativeModel('gemini-1.5-flash') # 또는 사용 중인 모델명
    else:
        st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.")
        st.stop()
except Exception as e:
    st.error(f"API 설정 오류가 발생했습니다: {e}")
    st.stop()

# 6. 입력 섹션
col1, col2 = st.columns(2)
with col1:
    user_name = st.text_input("👤 작성자 성명", placeholder="성명을 입력해 주세요 (필수)")
    selected_facility = st.radio("점검 대상 시설", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    placeholder_text = "<예시>\n1. 본관 2층 테라스 난간 흔들림\n2. 정문 보도블록 파손으로 넘어질 위험 등"
    user_description = st.text_area("현장 상황 설명", placeholder=placeholder_text, height=200)

with col2:
    source_option = st.radio("사진 방식", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    img_file = st.camera_input("촬영") if "📷" in source_option else st.file_uploader("업로드") if "🖼️" in source_option else None

# 7. AI 분석 버튼
if st.button("🚀 KYWA AI 위험요인 분석 시작", use_container_width=True):
    if not api_key: 
        st.error("API Key를 입력하세요.")
    elif not user_name.strip():
        st.warning("⚠️ 성명을 입력해 주세요. 작성자 확인이 필요합니다.")
    elif not user_description.strip() and not img_file:
        st.warning("⚠️ 분석할 내용(글 또는 사진)을 입력해 주세요.")
    else:
        with st.spinner(f"KYWA AI가 {user_name} 님의 데이터를 분석 중입니다..."):
            prompt = f"""
            시설명: [{selected_facility}], 상황: {user_description}. 
            반드시 다음 JSON 형식을 엄수하세요. (데이터 리스트 형태 [])
            [등급 판정 가이드라인]
            - 매우 낮음(1~3점), 낮음(4~6점), 보통(8~12점), 높음(15점 이상)
            1. p(빈도), s(강도)는 1~5 정수.
            2. score는 p*s 결과 숫자.
            3. grade는 "매우 낮음", "낮음", "보통", "높음" 중 하나.
            4. 모든 문장은 명사형 종결.
            키: category, scenario, p, s, score, grade, law, solution
            """
            content = [prompt]
            if img_file: content.append(Image.open(img_file))
            try:
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.rerun()
            except Exception as e: st.error(f"오류: {e}")

# 8. 결과 표시
if st.session_state.analysis_results:
    st.markdown(f"### 📊 {user_name} 님의 분석 결과")
    table_html = '<table class="report-table"><thead><tr><th>분류</th><th>위험상황</th><th>빈도</th><th>강도</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr></thead><tbody>'
    st.session_state.final_processed_data = []
    
    for item in st.session_state.analysis_results:
        p_val = int(item.get('p', 3))
        s_val = int(item.get('s', 3))
        score = p_val * s_val
        if score <= 3: refined_grade = "매우 낮음"
        elif score <= 6: refined_grade = "낮음"
        elif score <= 12: refined_grade = "보통"
        else: refined_grade = "높음"
        
        item['grade'] = refined_grade
        item['score'] = score
        grade_class = "grade-high" if "높음" in refined_grade else "grade-medium" if refined_grade == '보통' else "grade-low"
        
        table_html += f'<tr><td style="text-align:center">{item.get("category")}</td><td>{item.get("scenario")}</td>'
        table_html += f'<td style="text-align:center">{p_val}</td><td style="text-align:center">{s_val}</td>'
        table_html += f'<td style="text-align:center">{score}</td><td class="{grade_class}">{refined_grade}</td>'
        table_html += f'<td>{item.get("law")}</td><td>{str(item.get("solution")).replace(chr(10), "<br>")}</td></tr>'
        st.session_state.final_processed_data.append(item)
    
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

# 9. 최종 데이터 전송
if st.button("✅ KYWA 안전센터로 데이터 최종 전송", use_container_width=True):
    if not st.session_state.get("final_processed_data"):
        st.error("전송할 분석 결과가 없습니다.")
    elif not user_name.strip():
        st.warning("작성자 성명을 입력해 주세요.")
    else:
        with st.spinner("데이터를 전송 중입니다..."):
            try:
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLSeBGGpZQKh62zTomgTS14hhvgWzQ0FdGNVf9-r3FTzhd6ufQQ/formResponse"
                success_count = 0
                for row in st.session_state.final_processed_data:
                    payload = {
                        "entry.1651948586": user_name,
                        "entry.906406644": selected_facility,
                        "entry.1297326802": row.get("category", ""),
                        "entry.1421719401": row.get("scenario", ""),
                        "entry.1752607260": row.get("grade", ""),
                        "entry.271461796": row.get("solution", ""),
                        "entry.956205828": row.get("law", ""),
                        "entry.1058871339": "사진 포함" if img_file else "사진 없음"
                    }
                    response = requests.post(form_url, data=payload, timeout=10)
                    if response.status_code == 200:
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"{success_count}건 전송 완료! 대시보드는 새로고침 후 업데이트됩니다.")
                    st.balloons()
                    # 전송 후 대시보드 갱신을 위해 데이터 재로드 가능
            except Exception as e:
                st.error(f"전송 오류: {e}")

# --- [수정] 대시보드 섹션 ---
st.write("---")
dashboard_data = load_dashboard_data()

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
        # '작성자 성명' 컬럼명이 시트와 정확히 일치해야 합니다.
        author_col = "작성자 성명"
        if author_col in yearly_data.columns:
            m2.metric("참여 인원(명)", f"{yearly_data[author_col].nunique()} 명")

        # 4. 그래프 시각화
        g_col1, g_col2 = st.columns(2)
        
        with g_col1:
            # 시트의 실제 컬럼명에 맞춰 수정 (예: '유해위험요인)')
            target_col_cat = "유해위험요인" 
            if target_col_cat in yearly_data.columns:
                st.write(f"**{target_col_cat} 현황**")
                fig_pie = px.pie(yearly_data, names=target_col_cat, hole=0.3)
                fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info(f"'{target_col_cat}' 컬럼을 찾을 수 없습니다.")

        with g_col2:
            target_col_fac = "시설명" 
            if target_col_fac in yearly_data.columns:
                st.write(f"**{target_col_fac}별 점검 건수**")
                fac_counts = yearly_data[target_col_fac].value_counts().reset_index()
                fac_counts.columns = [target_col_fac, '건수']
                fig_bar = px.bar(fac_counts, x=target_col_fac, y='건수', color=target_col_fac)
                fig_bar.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=350, showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)


# 10. 하단 저장 섹션
st.write("---")
if "final_processed_data" in st.session_state and st.session_state.final_processed_data:
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button("Word 저장", data=create_docx(st.session_state.final_processed_data), file_name=f"KYWA_Report_{user_name}_{selected_facility}.docx", use_container_width=True)
    with dl_col2:

        st.download_button("Excel 저장", data=create_excel(st.session_state.final_processed_data), file_name=f"KYWA_Data_{user_name}_{selected_facility}.xlsx", use_container_width=True)
