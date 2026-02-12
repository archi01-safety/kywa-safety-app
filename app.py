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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import datetime

# --- [수정] 페이지 설정은 "반드시" 코드 최상단에 한 번만! ---
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

# --- [1단계] 구글 드라이브/시트 설정 ---
DRIVE_FOLDER_ID = "1K4hIEsAfX9iGsk9NX_4-4Z9bGXLNVzKC"
SPREADSHEET_ID = "1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q"

drive_service = None
sheets_service = None

if "gcp_service_account" in st.secrets:
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"]
            # 1. 문자열로 들어온 \n 처리
            pk = pk.replace("\\n", "\n")
            # 2. PEM 데이터만 정확히 추출하여 불순물 제거
            if "-----BEGIN PRIVATE KEY-----" in pk:
                parts = pk.split("-----BEGIN PRIVATE KEY-----")
                key_body = parts[1].split("-----END PRIVATE KEY-----")[0]
                # 내부 공백 및 줄바꿈 모두 제거 후 깨끗하게 재조립
                clean_key = "".join(key_body.split())
                pk = f"-----BEGIN PRIVATE KEY-----\n{clean_key}\n-----END PRIVATE KEY-----\n"
            
            creds_dict["private_key"] = pk

        SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
    except Exception as e:
        st.error(f"GCP 인증 실패 세부 에러: {e}")

# --- 스타일 설정 ---
st.markdown("""
    <style>
    html, body, [data-testid="stWidgetLabel"] p { color: var(--text-color); }
    .stDataFrame { width: 100% !important; }
    div.stButton > button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 0.5rem !important;
    }
    .report-table { width:100%; border-collapse: collapse; font-size: 14px; }
    .report-table th { background-color: #f0f2f6; padding: 10px; border: 1px solid #ddd; }
    .report-table td { padding: 10px; border: 1px solid #ddd; text-align: center; }
    .grade-high { background-color: #ff4b4b; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 환경 변수 및 세션 초기화
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "final_data" not in st.session_state:
    st.session_state.final_data = None

# Gemini 모델 설정
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"], transport='rest')
        model = genai.GenerativeModel('gemini-1.5-flash') # 최신 모델 권장
    else:
        st.error("Secrets에 'GEMINI_API_KEY'가 없습니다.")
        st.stop()
except Exception as e:
    st.error(f"API 설정 오류: {e}")
    st.stop()

# --- 주요 함수 ---
def upload_photo_to_drive(file_obj, filename):
    try:
        file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_obj.getvalue()), mimetype='image/jpeg')
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        return uploaded_file.get('webViewLink')
    except Exception as e:
        return f"업로드 실패: {e}"

def append_row_to_sheet(row_data):
    try:
        range_name = "'설문지 응답 시트1'!A1"
        body = {'values': [row_data]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()
        return True
    except Exception as e:
        st.error(f"시트 저장 실패: {e}")
        return False

# --- 화면 구성 (헤더) ---
header_col1, header_col2 = st.columns([1, 4])
with header_col1:
    st.image("https://raw.githubusercontent.com/archi01-safety/kywa-safety-app/main/kywa_logo.png", width=250)
with header_col2:
    st.title("🚨 KYWA AI 위험성평가 시스템")

# --- 입력 섹션 ---
col1, col2 = st.columns(2)
with col1:
    selected_facility = st.radio("🏢 시설명 선택", ["중앙", "평창", "우주", "바이오", "해양", "미래", "생태", "본원"], horizontal=True)
    selected_dept = st.selectbox("📂 담당 부서", ["활동부", "협력부", "청렴감사실", "기획혁신부", "인재경영부", "홍보전략부", "안전경영부", "재무회계부", "디지털정보부", "자회사"])
    user_description = st.text_area("📝 상황 설명 입력", placeholder="예: 본관 2층 난간 흔들림", height=100)
with col2:
    source_option = st.radio("📸 사진 업로드", ("📷 카메라", "🖼️ 갤러리", "🚫 없음"), horizontal=True)
    img_file = st.camera_input("촬영") if "📷" in source_option else st.file_uploader("업로드", type=['jpg','png']) if "🖼️" in source_option else None

# --- 분석 로직 ---
if st.button("🚀 AI 분석 시작", use_container_width=True):
    if not user_description.strip() and not img_file:
        st.warning("내용을 입력해주세요.")
    else:
        with st.spinner("분석 중..."):
            prompt = f"당신은 안전전문가입니다. 시설:{selected_facility}, 부서:{selected_dept}, 상황:{user_description}. 다음 JSON 형식으로만 답하세요: [{{'category':'','scenario':'','p':1,'s':1,'score':1,'grade':'','law':'','solution':''}}]"
            content = [prompt, Image.open(img_file)] if img_file else [prompt]
            response = model.generate_content(content, generation_config={"response_mime_type": "application/json"})
            st.session_state.analysis_results = json.loads(response.text)
            st.rerun()

# --- 결과 출력 및 전송 ---
if st.session_state.analysis_results:
    st.markdown("### 📊 분석 결과")
    st.session_state.final_data = []
    # (여기에 분석 결과 테이블 렌더링 로직 - 생략하지 말고 그대로 사용하세요)
    # ... 테이블 출력 코드 ...

    if st.button("✅ 데이터 최종 전송", use_container_width=True):
        if not drive_service:
            st.error("GCP 인증 오류가 있습니다. Secrets를 확인하세요.")
        else:
            with st.spinner("전송 중..."):
                photo_url = upload_photo_to_drive(img_file, f"{selected_facility}_photo.jpg") if img_file else "없음"
                for row in st.session_state.analysis_results:
                    data = [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), selected_facility, selected_dept, row.get('category'), row.get('scenario'), row.get('grade'), row.get('solution'), row.get('law'), photo_url]
                    append_row_to_sheet(data)
                st.success("데이터 전송 완료!")
                st.balloons()
