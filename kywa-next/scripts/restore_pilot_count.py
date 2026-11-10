"""Remove only the synthetic smoke row identified by its locally recorded idempotency receipt."""
import argparse,json,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import Settings
from backend.repository import google_client,quoted
from backend.sheet_sync import KEY

p=argparse.ArgumentParser();p.add_argument('receipt',type=Path);args=p.parse_args()
d=json.loads(args.receipt.read_text(encoding='utf-8'))
assert d['origin'] in {'https://kywa-safety-pilot.vercel.app','https://kywa-safety-pilot-api.onrender.com'}
assert d['id']==str(uuid.uuid5(uuid.UUID(d['request_id']),'0'))
c=Settings(_env_file=None);sid=c.spreadsheet_id
assert sid and sid!=c.organization.storage.spreadsheet_id
drive=google_client(c,'drive','v3')
inf=drive.files().get(fileId=sid,fields='name,appProperties',supportsAllDrives=True).execute()
assert inf.get('name')=='KYWA 합성 평가 150건' and inf.get('appProperties',{}).get('kywa_fixture')=='vercel-pilot-v1'
sheet=google_client(c,'sheets','v4').spreadsheets()
doc=sheet.get(spreadsheetId=sid,ranges=[quoted(c.sheet_name)+'!A:S'],
    fields='sheets(properties(sheetId,title),data(rowMetadata(developerMetadata(metadataKey,metadataValue)),rowData(values(effectiveValue))))').execute()['sheets'][0]
assert doc['properties']['title']==c.sheet_name
g=doc['data'][0]
indices=[i for i,row in enumerate(g['rowMetadata']) if any(m.get('metadataKey')==KEY and m.get('metadataValue')==d['id'] for m in row.get('developerMetadata',[]))]
if not indices:print('Synthetic row already absent')
else:
    assert len(indices)==1 and indices[0]>0
    i=indices[0]
    assert g['rowData'][i]['values'][18]['effectiveValue']['stringValue']=='시㉭'
    sheet.batchUpdate(spreadsheetId=sid,body={'requests':[{'deleteDimension':{'range':{'sheetId':doc['properties']['sheetId'],
                    'dimension':'ROWS','startIndex':i,'endIndex':i+1}}}]}).execute()
    print('Removed only the smoke receipt row. Fixture history and protected photo retained.')
