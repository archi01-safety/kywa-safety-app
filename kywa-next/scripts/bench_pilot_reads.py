"""Measure just the Sheets read path on the isolated workbook, not browser latency."""
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings
from backend.overview import summarize
from backend.pilot_read import read_records
from backend.repository import SheetsRepository
from googleapiclient.http import HttpRequest


def main():
    settings=Settings(_env_file=None)
    expected=summarize(read_records(settings),2026,settings.organization)
    assert expected['total']==150 and expected['completed']==50
    repo=SheetsRepository(settings)
    samples={'baseline':[], 'pilot':[]}
    counts={'baseline':[], 'pilot':[]}
    execute=HttpRequest.execute
    calls=0
    def counted(request,*args,**kwargs):
        nonlocal calls
        calls+=1
        return execute(request,*args,**kwargs)
    with patch.object(HttpRequest,'execute',counted):
        for i in range(21):
            order=('baseline','pilot') if i%2==0 else ('pilot','baseline')
            for label in order:
                calls=0
                start=time.perf_counter()
                records=repo.records() if label=='baseline' else read_records(settings)
                result=summarize(records,2026,settings.organization)
                assert result==expected
                if i:
                    samples[label].append(round((time.perf_counter()-start)*1000))
                    counts[label].append(calls if label=='baseline' else 1)
            # Leave headroom for other Google API users sharing this account.
            time.sleep(6)
    print(json.dumps({k:{'n':len(s), 'median_ms':statistics.median(s), 'p95_ms':sorted(s)[18],
                         'sheets_calls':counts[k], 'samples_ms':s} for k,s in samples.items()}))

if __name__=='__main__':
    main()
