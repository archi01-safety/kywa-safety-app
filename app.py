import os
import ssl
import json
import requests
import io
import time
import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL

# 1. 환경 설정 및 보안 우회
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 2. 페이지 설정
st.set_page_config(page_title="KYWA AI 위험성평가 시스템 (V2.5)", layout="wide", page_icon="🚨")

# 세션 상태 초기화
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "final_processed_data" not in st.session_state:
    st.session_state.final_processed_data = None

# --- [Data] 구글 시트 대시보드 데이터 로드 ---
SHEET_ID = "1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=413707311"

def load_dashboard_data():
    try:
        updated_url = f"{SHEET_URL}&t={int(time.time())}"
        df = pd.read_csv(updated_url)
        df.columns = [c.strip() for c in df.columns]
        
        if '타임스탬프' in df.columns:
            df['타임스탬프'] = df['타임스탬프'].str.replace('오전', 'AM').str.replace('오후', 'PM')
            df['타임스탬프'] = pd.to_datetime(df['타임스탬프'], errors='coerce')
            df = df.dropna(subset=['타임스탬프'])
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# --- [Export] 파일 생성 함수 ---
def create_excel(data):
    if not data: return None
    df = pd.DataFrame(data)
    column_mapping = {'category': '분류', 'scenario': '위험상황', 'p': '빈도', 's': '강도', 'score': '점수', 'grade': '등급', 'law': '관련근거', 'solution': '감소대책'}
    df = df.rename(columns=column_mapping)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='위험성평가_결과')
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
    for item in data:
        row_cells = table.add_row().cells
        vals = [item.get('category'), item.get('scenario'), item.get('p'), item.get('s'), item.get('score'), item.get('grade'), item.get('law'), item.get('solution')]
        for idx, v in enumerate(vals):
            row_cells[idx].text = str(v)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- [UI] 헤더 및 CSS ---
raw_logo_url = "https://raw.githubusercontent.com/archi01-safety/kywa-safety-app/main/kywa_logo.png"
st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
        <a href="https://kywa-safety-check.streamlit.app/" target="_self">
            <img src="{raw_logo_url}" width="200">
        </a>
        <div>
            <h1 style="margin:0;">🚨 KYWA AI 위험성평가 시스템</h1>
            <p style="color: grey; margin:0;">Korea Youth Work Agency - 스마트 안전관리 플랫폼</p>
        </div>
    </div>
    <style>
    .stButton>button {{ width: 100%; border-radius: 8px; font-weight: bold; background-color: #E60012; color: white; height: 3.5em; }}
    .report-table {{ width: 100%; border-collapse: collapse; }}
    .report-table th, .report-table td {{ padding: 10px; border: 1px solid #dee2e6; text-align: left; font-size: 0.9em; }}
    .report-table th {{ background-color: #f8f9fa; }}
    .grade-high {{ background-color: #ffe3e3; color: #b91c1c; font-weight: bold; }}
    .grade-medium {{ background-color: #fff5dc; color: #92400e; }}
    .grade-low {{ background-color: #ebfbee; color: #166534; }}
    </style>
""", unsafe_allow_html=True)

# API 설정
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"], transport='rest')
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("API Key 미설정")
    st.stop()

# --- [Input] 입력 섹션 ---
col1, col2 = st.columns(2)
with col1:
    user_name = st.text_input("👤 작성자 성명", placeholder="성명을 입력하세요")
    selected_facility = st.radio("점검 대상 시설", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    user_description = st.text_area("현장 상황 설명", placeholder="위험 상황을 구체적으로 적어주세요.", height=150)

with col2:
    source_option = st.radio("사진 방식", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    img_file = st.camera_input("촬영") if "📷" in source_option else st.file_uploader("업로드") if "🖼️" in source_option else None

# --- [AI Analysis] 분석 로직 ---
if st.button("🚀 AI 위험요인 분석 시작"):
    if not user_name.strip() or (not user_description.strip() and not img_file):
        st.warning("⚠️ 작성자 성명과 분석 내용(글/사진)을 확인해주세요.")
    else:
        with st.spinner("KYWA AI가 분석 중..."):
            prompt = f"""
            시설명: [{selected_facility}], 상황: {user_description}.
            반드시 다음 JSON 형식을 엄수하세요. (리스트 형태 [])
            [필수 분류: 보행 안전, 시설 안전, 화재 안전, 작업 안전, 활동 안전, 보건 및 위생관리, 화학물질 관리, 재난 안전 중 선택]
            [규칙: 경미한 전도는 강도 1, 빈도 산정은 엄격하게]
            키: category, scenario, p, s, law, solution
            """
            content = [prompt]
            if img_file: content.append(Image.open(img_file))
            
            try:
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.1})
                res_data = json.loads(response.text.strip())
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.rerun()
            except Exception as e:
                st.error(f"AI 분석 오류: {e}")

# --- [Result] 결과 표시 및 전송 ---
if st.session_state.analysis_results:
    st.subheader(f"📊 {user_name} 님의 분석 결과")
    processed_data = []
    
    table_html = '<table class="report-table"><tr><th>분류</th><th>위험상황</th><th>P</th><th>S</th><th>점수</th><th>등급</th><th>관련근거</th><th>감소대책</th></tr>'
    for item in st.session_state.analysis_results:
        p, s = int(item.get('p', 1)), int(item.get('s', 1))
        score = p * s
        grade = "높음" if score >= 13 else "보통" if score >= 8 else "낮음" if score >= 4 else "매우 낮음"
        item.update({"score": score, "grade": grade})
        processed_data.append(item)
        
        g_cls = "grade-high" if score >= 13 else "grade-medium" if score >= 8 else "grade-low"
        table_html += f'<tr><td>{item["category"]}</td><td>{item["scenario"]}</td><td>{p}</td><td>{s}</td><td>{score}</td><td class="{g_cls}">{grade}</td><td>{item["law"]}</td><td>{item["solution"]}</td></tr>'
    
    table_html += '</table>'
    st.markdown(table_html, unsafe_allow_html=True)
    st.session_state.final_processed_data = processed_data

    if st.button("✅ KYWA 안전센터로 데이터 최종 전송"):
        with st.spinner("전송 중..."):
            form_url = "https://docs.google.com/forms/d/e/1FAIpQLSeBGGpZQKh62zTomgTS14hhvgWzQ0FdGNVf9-r3FTzhd6ufQQ/formResponse"
            for row in st.session_state.final_processed_data:
                # [저장된 정보]에 따른 매칭: 시설명(1902283977), 분류(1485620273), 상황(2072170485), 등급(1212734944), 대책(2124342735), 근거(543223131)
                payload = {
                    "entry.1651948586": user_name,
                    "entry.1902283977": selected_facility,
                    "entry.1485620273": row['category'],
                    "entry.2072170485": row['scenario'],
                    "entry.1212734944": row['grade'],
                    "entry.2124342735": row['solution'],
                    "entry.543223131": row['law'],
                    "entry.1058871339": "사진 포함" if img_file else "사진 없음"
                }
                requests.post(form_url, data=payload)
            st.success("데이터 전송 완료!")
            st.balloons()

# --- [Dashboard] 실시간 현황 ---
st.write("---")
dash_df = load_dashboard_data()
if dash_df is not None and not dash_df.empty:
    st.subheader("📊 2026 실시간 안전 점검 대시보드")
    df_2026 = dash_df[dash_df['타임스탬프'].dt.year == 2026]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("올해 누적 건수", f"{len(df_2026)} 건")
    m2.metric("참여 인원", f"{df_2026['작성자 성명'].nunique() if '작성자 성명' in df_2026 else 0} 명")
    m3.metric("최근 점검일", df_2026['타임스탬프'].max().strftime('%Y-%m-%d') if not df_2026.empty else "-")

    c1, c2 = st.columns(2)
    with c1:
        if "유해위험요인" in df_2026.columns:
            fig = px.pie(df_2026, names="유해위험요인", title="위험요인별 분포", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if "시설명" in df_2026.columns:
            fig = px.bar(df_2026['시설명'].value_counts().reset_index(), x='index', y='시설명', title="시설별 점검 빈도", color='index')
            st.plotly_chart(fig, use_container_width=True)

# 하단 저장 버튼
if st.session_state.final_processed_data:
    st.write("---")
    sc1, sc2 = st.columns(2)
    sc1.download_button("📂 Word 보고서 다운로드", create_docx(st.session_state.final_processed_data), f"KYWA_{user_name}.docx")
    sc2.download_button("📂 Excel 데이터 다운로드", create_excel(st.session_state.final_processed_data), f"KYWA_{user_name}.xlsx")
