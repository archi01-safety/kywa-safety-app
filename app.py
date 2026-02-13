import subprocess
import sys
import time

# [1] 라이브러리 강제 설치 (가장 먼저 실행)
def install_requirements():
    try:
        import mediapipe
    except ImportError:
        # 설치가 안 되어 있다면 강제로 설치 프로세스 실행
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mediapipe==0.10.11", "opencv-python-headless"])
        time.sleep(2) 

install_requirements()

# [2] 페이지 설정 (모든 st 함수 중 가장 처음에 와야 함)
import streamlit as st
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

# [3] 필수 라이브러리 임포트 (중복 제거)
import os
import ssl
import json
import requests
import io
import datetime
import base64
import codecs
import pandas as pd
import numpy as np
import cv2
import plotly.express as px
from PIL import Image
from docx import Document
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# [4] MediaPipe 임포트 (가장 안전한 방식)
try:
    import mediapipe as mp
    from mediapipe.python.solutions import face_detection as mp_face
except Exception as e:
    st.error(f"MediaPipe 로딩 실패: {e}")



# --- [수정] 페이지 설정은 코드 최상단에 "단 한 번만" 위치해야 합니다 ---
st.set_page_config(page_title="KYWA AI 위험성평가 시스템", layout="wide", page_icon="🚨")

# --- [1단계] 구글 드라이브/시트 설정 (PEM 로드 집중 수정 버전) ---
DRIVE_FOLDER_ID = "1K4hIEsAfX9iGsk9NX_4-4Z9bGXLNVzKC"
SPREADSHEET_ID = "1kL18jQn5t0UX8ECpVEm3RHLQAWu7lum8_Wb-EtxkU5Q"

# --- [추가] 실제 구글 드라이브에 파일을 업로드하는 함수 ---
def upload_to_drive(file_name, file_content, mime_type):
    """
    구글 드라이브의 특정 폴더로 파일을 업로드합니다.
    """
    if drive_service is None:
        st.error("구글 드라이브 서비스가 연결되지 않았습니다.")
        return None
    
    try:
        # 파일 메타데이터 설정 (이름과 저장될 폴더 지정)
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]  # 이전에 설정하신 폴더 ID가 여기 쓰입니다.
        }
        
        # 파일 콘텐츠 준비
        media = MediaIoBaseUpload(
            io.BytesIO(file_content), 
            mimetype=mime_type, 
            resumable=True
        )
        
        # 드라이브에 파일 생성
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # 업로드된 파일의 링크 반환
        return file.get('webViewLink')
        
    except Exception as e:
        st.error(f"구글 드라이브 업로드 중 에러 발생: {e}")
        return None

drive_service = None
sheets_service = None

if "gcp_service_account" in st.secrets:
    try:
        creds_info = st.secrets["gcp_service_account"]
        
        # private_key 내의 실제 줄바꿈 문자 처리 (가장 흔한 오류 원인)
        if isinstance(creds_info, (dict, st.runtime.secrets.AttrDict)):
            creds_dict = dict(creds_info)
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            
            drive_service = build('drive', 'v3', credentials=creds)
            sheets_service = build('sheets', 'v4', credentials=creds)
    except Exception as e:
        st.error(f"⚠️ 인증 설정 오류: {e}")

else:
    st.error("Secrets 설정에서 'gcp_service_account'를 찾을 수 없습니다.")

# (이후 기존의 CSS 설정 및 나머지 코드를 이어 붙이시면 됩니다.)
# 주의: 아래쪽에 있는 st.set_page_config(page_title="KYWA AI 위험성평가 시스템", ...) 코드는 삭제하세요.

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



# --- [2단계] 구글 드라이브/시트 전송 함수 추가 ---

def upload_photo_to_drive(file_obj, filename):
    try:
        # Apps Script 웹 앱 URL (방금 복사한 주소)
        apps_script_url = "https://script.google.com/macros/s/AKfycbwMhipDH9zMVajhbD2LBXGgnJdaqs3oHmatjqtvAXWL0PXhInk6tqsqRcb6MJkZFChm/exec"
        
        file_obj.seek(0)
        img_base64 = base64.b64encode(file_obj.getvalue()).decode('utf-8')
        
        payload = {
            "filename": filename,
            "fileBase64": img_base64
        }
        
        # POST 요청으로 사진 전송
        response = requests.post(apps_script_url, json=payload)
        res_data = response.json()
        
        return res_data.get("url", "업로드 실패")
    except Exception as e:
        return f"업로드 실패: {str(e)}"

def append_row_to_sheet(row_data):
    try:
        # [확인 필요] 실제 시트 탭 이름과 공백이 정확히 일치해야 합니다.
        # 만약 구글폼 연동 시트라면 보통 '설문지 응답 1' 입니다.
        range_name = "'설문지 응답 시트1'!A1" 
        
        body = {'values': [row_data]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, 
            range=range_name,
            valueInputOption='USER_ENTERED', 
            insertDataOption='INSERT_ROWS', # [추가] 새 행을 삽입하며 추가하도록 명시
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"시트 저장 실패: {str(e)}")
        return False

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

def apply_face_blur(img_file):
    import cv2
    import numpy as np
    import sys

    try:
        # 이미지 읽기
        img_file.seek(0)
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None: return img_file.getvalue()
        
        h, w, _ = image.shape

        # [2] 이미지 전처리 (어두운 얼굴 인식률 향상)
        # 대비를 높여 측면이나 그늘진 얼굴 특징을 부각시킵니다.
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        enhanced_img = cv2.merge((cl,a,b))
        enhanced_img = cv2.cvtColor(enhanced_img, cv2.COLOR_LAB2RGB) # 모델 입력용

        all_detections = []

        # [3] 초강력 이중 감지 (근거리 + 원거리 합집합)
        # 감지 민감도를 0.3으로 낮추어 측면 얼굴도 최대한 잡습니다.
        for model_type in [0, 1]: 
            with mp_face.FaceDetection(model_selection=model_type, min_detection_confidence=0.3) as detector:
                results = detector.process(enhanced_img)
                if results.detections:
                    all_detections.extend(results.detections)

        if all_detections:
            for detection in all_detections:
                bbox = detection.location_data.relative_bounding_box
                
                # 좌표 계산 및 안전 범위 지정
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                rw = int(bbox.width * w)
                rh = int(bbox.height * h)
                
                # 얼굴 영역을 실제보다 20% 더 넓게 잡음 (머리카락, 귀 보호)
                padding_w = int(rw * 0.2)
                padding_h = int(rh * 0.2)
                
                x_final = max(0, x - padding_w)
                y_final = max(0, y - padding_h)
                rw_final = min(w - x_final, rw + (padding_w * 2))
                rh_final = min(h - y_final, rh + (padding_h * 2))

                if rw_final > 0 and rh_final > 0:
                    face_roi = image[y_final:y_final+rh_final, x_final:x_final+rw_final]
                    
                    # 더 강력한 블러 효과 (가우시안 + 모자이크 혼합 느낌)
                    level = max(rw_final, rh_final) // 4
                    if level % 2 == 0: level += 1
                    image[y_final:y_final+rh_final, x_final:x_final+rw_final] = cv2.GaussianBlur(face_roi, (level, level), 0)

            st.toast(f"✅ {len(all_detections)}개 포인트 비식별화 완료")

        # 결과 반환
        _, buffer = cv2.imencode('.jpg', image)
        return buffer.tobytes()

    except Exception as e:
        st.error(f"비식별화 프로세스 오류: {e}")
        img_file.seek(0)
        return img_file.getvalue()

# --- [3단계] 전송 버튼 로직 내 수정 ---
processed_img_final = None  # 처리된 이미지를 담을 변수

if img_file:
    with st.spinner("🔒 개인정보 비식별화 처리 중..."):
        # 원본 대신 블러 처리된 이미지 생성
        processed_img_bytes = apply_face_blur(img_file)
        # Bytes 데이터를 파일 객체처럼 변환 (io.BytesIO 사용)
        processed_img_final = io.BytesIO(processed_img_bytes)
        # 파일 이름을 식별하기 위해 name 속성 부여
        processed_img_final.name = img_file.name

# --- 6. AI 분석 실행 ---
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
                2. 점수 조정 예시: 보도블럭 파손(빈도 2, 강도 1 -> 2점), 바닥 물기(빈도 3, 강도 1 -> 3점), 키보드 및 마우스 작업(빈도 3, 강도 1 -> 3점)

                [종합 등급 판정 가이드라인]
                - 매우 낮음(1~3점), 낮음(4~6점), 보통(8점), 높음(9~12점), 매우 높음(16~20점)
                - 8점부터는 '허용 불가능한 수준'의 사안으로 판단하므로 경미한 사항은 최대 6점을 기준으로 함.
                - 모든 문장은 명사형 종결.
                - 반드시 다음 JSON 형식을 엄수하세요: 키는 category, scenario, p, s, score, grade, law, solution 이며 리스트 [] 안에 담아 출력하세요.
                """

                # 분석 데이터 준비
                content = [prompt]
                if img_file:
                    from PIL import Image
                    content.append(Image.open(img_file))
                
                # 모델 호출 및 결과 처리
                if processed_img_final:
                    content.append(Image.open(processed_img_final))
                response = model.generate_content(content, generation_config={"response_mime_type": "application/json", "temperature": 0.0})
                res_data = json.loads(response.text.strip())
                
                # 결과 저장 및 리프레시
                st.session_state.analysis_results = res_data if isinstance(res_data, list) else [res_data]
                st.success(f"✅ [{selected_facility}] 시설 분석 완료!")
                st.rerun()

        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

# --- 7. 결과 표시 및 데이터 처리 ---
if st.session_state.analysis_results:
    st.markdown("### 📊 분석 결과")
    
    st.session_state.final_data = [] # 데이터 저장용 리스트 초기화

# 1. 스타일 정의 (요청하신 5단계 색상 반영)
    table_html = """
    <style>
        .report-table { width:100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
        .report-table th { background-color: #f0f2f6; color: #31333F; padding: 10px; border: 1px solid #ddd; text-align: center; }
        .report-table td { padding: 10px; border: 1px solid #ddd; text-align: center; vertical-align: middle; }
        
        /* 등급별 배경색 설정 */
        .grade-very-low, .grade-low { background-color: #ffffff; color: #31333F; } /* 흰색 */
        .grade-medium { background-color: #ffff00; color: #000000; font-weight: bold; } /* 노란색 */
        .grade-slightly-high { background-color: #ffcc00; color: #000000; font-weight: bold; } /* 주황색(짙은노랑) */
        .grade-high { background-color: #ff9999; color: #000000; font-weight: bold; } /* 옅은 빨간색 */
        .grade-very-high { background-color: #cc0000; color: #ffffff !important; font-weight: bold; } /* 어두운 빨간색 */
        
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

    # 2. 데이터 반복문
    for item in st.session_state.analysis_results:
        try:
            p = int(item.get('p', 0))
            s = int(item.get('s', 0))
        except:
            p, s = 0, 0
            
        score = p * s
        
        # [수정] 등급 판정 및 스타일 클래스 매칭
        if score <= 3: 
            grade, grade_class = "매우 낮음", "grade-very-low"
        elif score <= 6: 
            grade, grade_class = "낮음", "grade-low"
        elif score <= 9: # 8, 9점 포함
            grade, grade_class = "보통", "grade-medium"
        elif score <= 12: 
            grade, grade_class = "약간 높음", "grade-slightly-high"
        elif score <= 16: # 15, 16점 포함
            grade, grade_class = "높음", "grade-high"
        else: # 20점 이상
            grade, grade_class = "매우 높음", "grade-very-high"
        
        # 텍스트 내 줄바꿈 처리
        scenario_text = str(item.get('scenario', '-')).replace('\n', '<br>')
        solution_text = str(item.get('solution', '-')).replace('\n', '<br>')

        # HTML 행 생성
        table_html += f'<tr>'
        table_html += f'<td>{item.get("category", "-")}</td>'
        table_html += f'<td class="text-left">{scenario_text}</td>'
        table_html += f'<td>{p}</td>'
        table_html += f'<td>{s}</td>'
        table_html += f'<td>{score}</td>'
        table_html += f'<td class="{grade_class}">{grade}</td>' # 적용된 클래스
        table_html += f'<td>{item.get("law", "-")}</td>'
        table_html += f'<td class="text-left">{solution_text}</td>'
        table_html += f'</tr>'
        
        # 세션 데이터 업데이트
        item['score'] = score
        item['grade'] = grade
        st.session_state.final_data.append(item)

    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)


# --- [3단계] 전송 버튼 로직 (타임스탬프 수정 버전) ---
st.write("")
if st.button("✅ KYWA AI 안전센터로 데이터 최종 전송", use_container_width=True):
    if sheets_service is None or drive_service is None:
        st.error("⚠️ GCP 인증에 실패하여 데이터를 전송할 수 없습니다. 관리자에게 문의하세요.")
        st.stop()
    
    if not st.session_state.final_data:
        st.error("⚠️ 전송할 데이터가 없습니다. 먼저 분석을 진행해 주세요.")
    else:
        with st.spinner("🚀 KYWA AI 안전센터로 데이터를 전송 중입니다..."):
            try:
                # [수정] 한국 시간(KST)으로 현재 시간 설정
                now_kst = datetime.datetime.now() + datetime.timedelta(hours=9)
                current_time = now_kst.strftime("%Y-%m-%d %H:%M:%S") # 시트 기록용 (2026-02-12 18:00:20)
                timestamp_str = now_kst.strftime("%Y%m%d_%H%M%S")    # 파일 이름용 (20260212_180020)

                # 1. 사진 업로드
                photo_link = "사진 없음"
                if processed_img_final: # img_file 대신 블러 처리된 변수 사용
                    filename = f"{selected_facility}_{timestamp_str}.jpg"
                    # 위에서 정의한 함수 이름으로 호출 (upload_photo_to_drive)
                    photo_link = upload_photo_to_drive(processed_img_final, filename)
                
                # 2. 시트 데이터 준비 및 전송
                success_count = 0
                for row in st.session_state.final_data:
                    # current_time 변수가 이제 한국 시간으로 전달됩니다.
                    sheet_row = [
                        current_time,                   # A열: 타임스탬프 (한국 시간)
                        selected_facility,              # B열: 시설명
                        selected_dept,                  # C열: 담당 부서
                        row.get("category"),            # D열: 유해위험요인
                        row.get("scenario"),            # E열: 위험상황
                        row.get("grade"),               # F열: 위험등급
                        row.get("solution"),            # G열: 감소대책
                        row.get("law"),                  # H열: 관련근거
                        photo_link                      # I열: 사진 기록
                    ]
                    
                    if append_row_to_sheet(sheet_row):
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ 데이터 {success_count}건이 KYWA AI 안전센터로 정상 제출되었습니다!")
                    st.balloons()
                    # (선택) 전송 후 데이터 초기화가 필요하다면 아래 주석 해제
                    # st.session_state.final_data = None
                    # st.session_state.analysis_results = None
                    # st.rerun()
                
            except Exception as e:
                st.error(f"❌ 전송 중 오류 발생: {e}")

                
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
    **© 2026 한국청소년활동진흥원(KYWA) 안전경영부.** 본 시스템은 **공공기관 AI 활용 가이드라인** 및 **정보보안 업무규정** 을 엄격히 준수합니다.
    
    * **데이터 보안:** 입력된 모든 정보는 **API 옵트아웃(Opt-out) 설정**이 적용되어 외부 모델 학습에 활용되지 않습니다.
    * **운영 방침:** **KYWA AI 안전센터**로 전송된 데이터는 **담당자의 데이터 정합성 검토**를 거칩니다. 
      점검 내용이 부적절하거나 중복된 경우, 데이터 신뢰성 유지를 위해 운영 관리자에 의해 임의 수정 또는 삭제될 수 있습니다.
    * **면책 고지:** AI 분석 정보는 위험 요인 발굴을 돕는 가이드라인입니다. 실제 위험성 평가 시에는 현장 상황을 반영한 담당 직원의 면밀한 검토를 권고합니다.
    """)

with footer_cols[1]:
    st.markdown("### 📞 Contact")
    # HTML을 사용하여 아이콘 색상을 제어합니다 (Dark Gray/Black 계열)
    st.markdown(f"""
    <div style="line-height: 1.6;">
        <span style="font-weight: bold; font-size: 0.9rem; color: #31333F;">경영지원본부 안전경영부</span><br>
        <span style="color: #444; font-size: 0.85rem;">📧 archi01@kywa.or.kr</span><br>
        <span style="color: #444; font-size: 0.85rem;">
            <span style="display: inline-block; transform: rotate(10deg); color: #000;">📞</span> 02-6959-7138
        </span>
    </div>
    """, unsafe_allow_html=True)

# 최하단 한 줄 강조
st.markdown("<p style='font-size: 0.8rem; color: gray; text-align: center;'>Safe Together, KYWA AI Risk Assessment System</p>", unsafe_allow_html=True)




