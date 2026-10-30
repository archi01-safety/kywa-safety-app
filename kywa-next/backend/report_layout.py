"""A4 report template: one overview, then at most two editable cards per page."""
import base64
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .report_model import GRADES
from .services import ServiceError

WIDTH, HEIGHT = 595.28, 841.89
INK, MUTED, LINE, ACCENT = '#202C3B', '#526172', '#D8DFE7', '#A9133C'
COLORS = ['#4C7298','#58A188','#DBA94F','#9B83B5','#D77F71','#76A9B7','#A1A65A']


def font(bold=False):
    name='KywaReportBold' if bold else 'KywaReport'
    filename='NanumGothicBold.ttf' if bold else 'NanumGothic.ttf'
    if name not in pdfmetrics.getRegisteredFontNames():
        path = next((p for p in [Path('/usr/share/fonts/truetype/nanum')/filename,
            Path(__file__).parent/'assets'/filename,Path('C:/Windows/Fonts')/('malgunbd.ttf' if bold else 'malgun.ttf')] if p.exists()),None)
        if not path:
            raise ServiceError('보고서 한글 글꼴이 준비되지 않았습니다.')
        pdfmetrics.registerFont(TTFont(name,str(path)))
    return name


def page(number):
    return dict(number=number,width=WIDTH,height=HEIGHT,lines=[],tables=[],pictures=[],rules=[],warnings=[],nativeText=True)


def line(text,x,y,size=10,color=INK,bold=False):
    return dict(x=x,y=y,width=pdfmetrics.stringWidth(text,font(),size),height=size,
        baseline=y+size*.86,ascent=size*.86,metricHeight=size*1.25,
        runs=[dict(text=text,font='맑은 고딕',size=size,bold=bold,italic=False,ratio=100,color=color)])


def wrapped(text,width,size):
    lines=[]
    for paragraph in str(text).split('\n'):
        current=''
        for ch in paragraph:
            if current and pdfmetrics.stringWidth(current+ch,font(),size)>width:
                lines.append(current.rstrip()); current=ch.lstrip()
            else: current+=ch
        lines.append(current)
    return lines


def text(p,value,x,y,width,size=10,leading=14,color=INK,bold=False,max_lines=None):
    lines=wrapped(value,width,size)
    if max_lines and len(lines)>max_lines:
        raise ServiceError('보고서 요약이 정해진 영역보다 깁니다. 다시 생성해 주세요.')
    for value in lines:
        p['lines'].append(line(value,x,y,size,color,bold)); y+=leading
    return y


def rule(p,x,y,width,color=LINE,height=.7):
    p['rules'].append(dict(x=x,y=y,width=width,height=height,color=color))


def table(p,values,x,y,width,row_height=22,size=10):
    rows,cols=len(values),len(values[0]); cell_width=width/cols
    cells=[]
    for r,row in enumerate(values):
        for c,value in enumerate(row):
            cx,cy=x+c*cell_width,y+r*row_height
            lines=wrapped(str(value),cell_width-10,size)
            if len(lines)>1: raise ServiceError('보고서 표 내용이 영역을 초과했습니다.')
            item=line(str(value),cx+5,cy+(row_height-size)/2,size,INK,r==0)
            item['x']=cx+(cell_width-item['width'])/2
            cells.append(dict(row=r,col=c,rowSpan=1,colSpan=1,x=cx,y=cy,width=cell_width,height=row_height,
                lines=[item],fill='#EFF2F6' if r==0 else '#FFFFFF',
                borders={k:dict(color=LINE,width=.5) for k in ['left','right','top','bottom']}))
    p['tables'].append(dict(x=x,y=y,width=width,height=rows*row_height,rows=rows,cols=cols,cells=cells))
    return y+rows*row_height


def picture(p,data,x,y,w,h,name):
    with Image.open(io.BytesIO(data)) as original:
        im=original.convert('RGB'); im.thumbnail((1100,600))
        ratio=min(w/im.width,h/im.height); pw,ph=im.width*ratio,im.height*ratio
        out=io.BytesIO(); im.save(out,'PNG')
    p['pictures'].append(dict(x=x+(w-pw)/2,y=y+(h-ph)/2,width=pw,height=ph,filename=name+'.png',
        data=base64.b64encode(out.getvalue()).decode('ascii')))


def pie(p,categories,x,y):
    im=Image.new('RGB',(500,500),'white'); draw=ImageDraw.Draw(im); angle=-90; total=sum(categories.values())
    for i,count in enumerate(categories.values()):
        end=angle+360*count/total
        draw.pieslice((4,4,496,496),angle,end,fill=COLORS[i%len(COLORS)],outline='white',width=3); angle=end
    out=io.BytesIO(); im.save(out,'PNG'); picture(p,out.getvalue(),x,y,132,132,'categories')
    for i,(category,count) in enumerate(categories.items()):
        rule(p,x+160,y+10+i*22,10,COLORS[i%len(COLORS)],10)
        text(p,f'{category}   {count}건 ({count/total:.0%})',x+180,y+9+i*22,280,10)


def build(model,records,store):
    p=page(1); facts=model['facts']; pages=[p]
    text(p,facts['title'],36,40,523,19,27,bold=True,max_lines=3)
    rule(p,36,110,523,ACCENT,2)
    text(p,'1. 위험성평가 개요',36,129,523,13,bold=True)
    text(p,'평가 기간  '+facts['period'],36,155,523,10)
    facility_label = facts['facilities'][0] if len(facts['facilities'])==1 else str(len(facts['facilities']))+'개 시설 · '+', '.join(sorted({r['facility'] for r in records}))
    text(p,'평가 대상  '+facility_label,36,175,523,10,14,max_lines=2)
    table(p,[['총 평가','개선 완료','미완료'],[f"{facts['total']}건",f"{facts['complete']}건",f"{facts['incomplete']}건"]],36,213,523,27,12)
    text(p,'2. 최초 위험등급별 현황',36,284,523,13,bold=True)
    grades=GRADES+[g for g in facts['grades'] if g not in GRADES]
    table(p,[grades,[str(facts['grades'].get(g,0))+'건' for g in grades]],36,310,523,24,9.5)
    text(p,'3. 유해위험요인 분류',36,378,523,13,bold=True)
    pie(p,facts['categories'],55,406)
    text(p,'4. 총평 및 우선 조치사항',36,560,523,13,bold=True)
    y=text(p,model['overview'],36,586,523,10,15,max_lines=6)
    for value in model['priorities']:
        y=text(p,'• '+value,43,y+5,516,10,14,max_lines=2)
    if y>748:
        raise ServiceError('총평이 첫 페이지 영역보다 깁니다. 다시 생성해 주세요.')
    text(p,'상기 위험요인의 개선조치와 이행 여부를 지속 확인하여야 함.  끝.',36,y+9,523,10)
    text(p,'붙임  위험성평가 세부 결과.  끝.',36,y+37,523,10)
    for index,detail in enumerate(model['details']):
        if index%2==0:
            p=page(len(pages)+1); pages.append(p)
            text(p,'붙임  위험성평가 세부 결과',36,32,523,15,bold=True)
            rule(p,36,56,523,ACCENT,1.3)
        top=72+(index%2)*361; b=detail['before']; a=detail['after']; s=detail['summary']
        y=text(p,f"{index+1:02d}  {b['location']}",42,top,511,12,16,bold=True,max_lines=2)
        y=text(p,f"{detail['facility']} · {detail['department']} · {b['category']} · {detail['status']}",42,y+3,511,9.5,13,color=MUTED,max_lines=2)
        before=f"최초  빈도 {b['p']} × 강도 {b['s']} = {b['score']}점 · {b['grade']}"
        after=f"개선 후  빈도 {a['p']} × 강도 {a['s']} = {a['score']}점 · {a['grade']}" if a else '개선 후  미기록'
        y=table(p,[[before],[after]],42,y+4,511,19,9.5)+6
        for label,key,limit in [('위험상황','scenario',3),('감소대책','solution',3),('실제 조치','action',2),('관련근거','law',3)]:
            text(p,label,42,y,55,9.5,bold=True)
            y=text(p,s[key] or '기록 없음',102,y,451,9.5,12,max_lines=limit)+4
        # Fixed photo frame, with measured text stopping before it.
        photo_y=max(y+8,top+186)
        if y>top+241:
            raise ServiceError('세부 요약이 사진 영역을 초과했습니다. 다시 생성해 주세요.')
        record=records[index]
        for col,(label,fid) in enumerate([('개선 전',record.get('photo_id')),('개선 후',(record.get('after') or {}).get('photo_id'))]):
            x=42+col*260
            text(p,label,x,photo_y,248,9,color=MUTED)
            if fid:
                try: data=store.get(fid)
                except Exception: raise ServiceError('보고서 사진을 불러오지 못했습니다. 다시 시도해 주세요.') from None
                if not data: raise ServiceError('보고서 사진을 불러오지 못했습니다. 다시 시도해 주세요.')
                picture(p,data,x,photo_y+14,248,top+346-photo_y-14,f'{index+1}-{col}')
            else: text(p,'사진 없음',x+95,photo_y+48,150,9,color=MUTED)
        rule(p,36,top+351,523)
    for p in pages:
        text(p,f"- {p['number']} -",275,812,100,9,color=MUTED)
    return pages


def pdf(pages):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader
    out=io.BytesIO(); canvas=Canvas(out,pagesize=(WIDTH,HEIGHT))
    canvas.setTitle('위험성평가 및 개선조치 보고서')
    def draw_line(item):
        r=item['runs'][0]; canvas.setFillColor(HexColor(r['color'])); canvas.setFont(font(r['bold']),r['size'])
        canvas.drawString(item['x'],HEIGHT-item['baseline'],r['text'])
    for p in pages:
        for t in p['tables']:
            for cell in t['cells']:
                canvas.setFillColor(HexColor(cell['fill'])); canvas.setStrokeColor(HexColor(LINE)); canvas.setLineWidth(.5)
                canvas.rect(cell['x'],HEIGHT-cell['y']-cell['height'],cell['width'],cell['height'],stroke=1,fill=1)
                for item in cell['lines']: draw_line(item)
        for r in p['rules']:
            canvas.setFillColor(HexColor(r['color'])); canvas.rect(r['x'],HEIGHT-r['y']-r['height'],r['width'],r['height'],stroke=0,fill=1)
        for item in p['lines']: draw_line(item)
        for i in p['pictures']:
            canvas.drawImage(ImageReader(io.BytesIO(base64.b64decode(i['data']))),i['x'],HEIGHT-i['y']-i['height'],i['width'],i['height'])
        canvas.showPage()
    canvas.save(); return out.getvalue()


def hwpx(pages):
    node=os.environ.get('REPORT_NODE') or shutil.which('node')
    if not node:
        candidates=list((Path(__file__).resolve().parents[2]/'.tools/node-runtime').glob('*/node.exe'))
        node=str(candidates[0]) if candidates else None
    if not node: raise ServiceError('한글 보고서 실행 환경이 준비되지 않았습니다.')
    try:
        result=subprocess.run([node,str(Path(__file__).parent/'assets/hwpx-writer.cjs')],
            input=json.dumps(pages,ensure_ascii=False).encode(),capture_output=True,timeout=90,check=True)
        if not result.stdout.startswith(b'PK'): raise ValueError()
        return result.stdout
    except Exception:
        raise ServiceError('편집 가능한 한글 보고서를 만들지 못했습니다. 다시 시도해 주세요.') from None
