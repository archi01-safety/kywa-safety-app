"""Local synthetic workload only. Does not call Gemini, Sheets, or Drive."""
import copy
import io
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.repository import DemoRepository
from backend import reports

process = psutil.Process()
peak = [process.memory_info().rss]
stop = threading.Event()
def sample():
    while not stop.wait(.01): peak[0] = max(peak[0], process.memory_info().rss)
watch = threading.Thread(target=sample, daemon=True)
watch.start()
outdir = Path(__file__).resolve().parent.parent / 'artifacts'
outdir.mkdir(exist_ok=True)
results = {'environment':'Windows local synthetic; not a Render load guarantee', 'records':100, 'photos':200}
class Photos:
    def get(self, file_id):
        data=io.BytesIO()
        Image.new('RGB',(1280,960),(int(file_id)%255,80,130)).save(data,'JPEG')
        return data.getvalue()
try:
    with tempfile.TemporaryDirectory() as folder:
        record=DemoRepository(Path(folder)/'demo.json').records()[0]
        records=[]
        for i in range(100):
            item=copy.deepcopy(record)
            item.update(id=f'load-{i}',photo_id=str(i),status='완료')
            item['after']=dict(p=1,s=2,score=2,grade='매우 낮음',text='합성 데이터: 조치 후 확인',actor='synthetic',created_at=item['created_at'],photo_id=str(i+100))
            records.append(item)
        for fmt, writer in [('xlsx',reports.excel),('pdf',reports.pdf)]:
            start=time.perf_counter()
            output=writer(records,Photos())
            results[fmt]={'seconds':round(time.perf_counter()-start,2),'bytes':len(output)}
            (outdir/f'load-100.{fmt}').write_bytes(output)
finally:
    stop.set();watch.join()
results['peak_process_rss_mib']=round(peak[0]/1024/1024,1)
(outdir/'load-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False))
