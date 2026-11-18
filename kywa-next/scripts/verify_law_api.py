"""Opt-in live law API check. No OC/account/credential URLs in output."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.law_links import LawLinks


def verify(env_file,base_url):
    from dotenv import dotenv_values
    oc=dotenv_values(env_file).get('LAW_API_OC','')
    if not oc:raise ValueError('비공개 환경 파일에 LAW_API_OC를 설정하세요.')
    service=LawLinks(oc,referer=base_url)
    try:
        listing=service._xml('lawSearch.do',target='eflaw',query='산업안전보건법',search=1,display=20,nw=3)
    except Exception as exc:
        response=getattr(exc,'response',None)
        return {'passed':False,'stage':'list','error_type':type(exc).__name__,'status':getattr(response,'status_code',None)}
    cases=['산업안전보건법 제38조(안전조치)',
           '산업안전보건기준에 관한 규칙 제3조',
           '산업안전보건기준에 관한 규칙 제4조(작업장의 청결)']
    result={'passed':False,'list_matches':len(listing.findall('.//law')),'cases':[]}
    for text in cases:
        refs=service.resolve(text)
        result['cases'].append({'citation':text,'references':refs})
    result['title_mismatch_rejected']=all(not r['verified'] for r in service.resolve('산업안전보건기준에 관한 규칙 제3조(실제와 다른 조문 제목)'))
    result['missing_article_rejected']=all(not r['verified'] for r in service.resolve('산업안전보건법 제9999조'))
    result['passed']=bool(result['list_matches']) and all(row['references'] and all(r['verified'] for r in row['references']) for row in result['cases']) and result['title_mismatch_rejected'] and result['missing_article_rejected']
    return result


def verify_exports(result,folder):
    import io,zipfile,xml.etree.ElementTree as ET
    from backend.config import Settings
    from backend.report_model import compose
    from backend.report_layout import build,pdf
    from backend.report_semantic import Photos,hwpx
    from backend.excel_kywa import create_excel
    from backend.services import AIService
    from backend.tests.test_institutions import current_record
    from openpyxl import load_workbook
    from pypdf import PdfReader
    cfg=Settings(_env_file=None);records=[]
    for row in result['cases']:
        record=current_record(cfg.organization)
        record['before'].update(law=row['citation'],law_references=row['references'])
        records.append(record)
    photos=Photos(records,None);model=compose(records,AIService(cfg),org=cfg.organization)
    outputs={'pdf':pdf(build(model,records,photos)),'hwpx':hwpx(model,photos),'xlsx':create_excel(records,photos,cfg.organization)}
    book=load_workbook(io.BytesIO(outputs['xlsx']));links=[row[2].hyperlink.target for row in list(book['관련근거'])[1:]]
    assert len(links)==3 and all('/(' in url for url in links)
    document=PdfReader(io.BytesIO(outputs['pdf']))
    links=[a.get_object()['/A']['/URI'] for p in document.pages for a in p.get('/Annots',[]) if a.get_object().get('/A')]
    assert len(links)==3 and all('/(' in url for url in links)
    z=zipfile.ZipFile(io.BytesIO(outputs['hwpx']));root=ET.fromstring(z.read('Contents/section0.xml'))
    assert len(root.findall('.//{http://www.hancom.co.kr/hwpml/2011/paragraph}fieldBegin'))==3
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    for extension,data in outputs.items():(folder/('law-links.'+extension)).write_bytes(data)
    return {'xlsx_real_links':True,'pdf_real_links':True,'hwpx_editable_links':True,'records':3}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--env-file',required=True);p.add_argument('--base-url',default='https://kywa-safety.onrender.com');p.add_argument('--output',default='local-data/law-api-verification.json');p.add_argument('--exports',action='store_true');a=p.parse_args()
    result=verify(a.env_file,a.base_url)
    if result['passed'] and a.exports:result['exports']=verify_exports(result,'local-data/v11-law-exports')
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
