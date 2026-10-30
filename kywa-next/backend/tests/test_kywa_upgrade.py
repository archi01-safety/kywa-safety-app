import copy
import io
import json
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from pypdf import PdfReader
from backend.config import Settings
from backend.compact_storage import VISIBLE,TAB,HEAD,padded
from backend.domain import HEADERS,digest
from backend.migrate_compact import migrate
from backend.photo_privacy import normalize_photo,deidentify_photo,FaceDetection
from backend.report_model import compose,source_data
from backend.report_layout import build,pdf,hwpx
from backend.repository import SheetsRepository
from backend.services import ServiceError,AIService,Drafts
from backend.sheet_schema import Layout,SheetSchemaError
from backend.tests.test_institutions import MemorySheets,settings,old_row,current_record


class CompactSheets(MemorySheets):
    def __init__(self,*args):
        super().__init__(*args);self.before_append=None;self.lose_append=False;self.reject_append=False;self.append_calls=0

    def append(self,**kwargs):
        def execute():
            self.append_calls+=1
            if self.reject_append: raise TimeoutError()
            if self.before_append: self.before_append();self.before_append=None
            name=kwargs['range'].split('!')[0][1:-1]
            rows=self.data[name];start=len(rows)+1;rows.extend(copy.deepcopy(kwargs['body']['values']))
            if self.lose_append: self.lose_append=False;raise TimeoutError()
            return {'updates':{'updatedRange':f"'{name}'!A{start}:T{len(rows)}"}}
        return SimpleNamespace(execute=execute)

    def batchUpdate(self,**kwargs):
        def execute():
            for req in kwargs['body']['requests']:
                if 'duplicateSheet' in req:
                    x=req['duplicateSheet'];name=next(n for n,s in self.ids.items() if s==x['sourceSheetId'])
                    self.data[x['newSheetName']]=copy.deepcopy(self.data[name]);self.ids[x['newSheetName']]=x['newSheetId']
                elif 'deleteDimension' in req:
                    x=req['deleteDimension']['range'];name=next(n for n,s in self.ids.items() if s==x['sheetId'])
                    for row in self.data[name]: del row[x['startIndex']:x['endIndex']]
                elif any(k in req for k in ('copyPaste','repeatCell','updateSheetProperties')):
                    pass
                else:
                    super(CompactSheets,self).batchUpdate(body={'requests':[req]}).execute()
                if req not in self.requests:self.requests.append(copy.deepcopy(req))
            return {}
        return SimpleNamespace(execute=execute)


def setup_sheet(monkeypatch,tmp_path):
    cfg=settings('kywa');org=cfg.organization
    existing=current_record(org)
    rows=[HEADERS+['제출자 성명'],old_row(org),Layout(HEADERS+['제출자 성명'],org).new_row(existing)]
    mem=CompactSheets(cfg,rows)
    monkeypatch.setattr('backend.repository.google_client',lambda *_:mem)
    monkeypatch.setattr('backend.migrate_compact.google_client',lambda *_:mem)
    monkeypatch.setattr('backend.migrate_compact.ROOT',tmp_path)
    return cfg,mem,SheetsRepository(cfg)


def new_record(org):
    return {**current_record(org),'operation_id':str(uuid.uuid4()),'submit_hash':'hash','submit_owner':'owner'}


def test_migration_preserves_values_links_ids_and_is_repeatable(monkeypatch,tmp_path):
    cfg,mem,repo=setup_sheet(monkeypatch,tmp_path)
    before=repo.records(); prefix=[r[:18] for r in mem.data[cfg.sheet_name][1:]]
    result=migrate(cfg,True)
    assert result['applied'] and Path(result['backup']).exists()
    assert mem.data[cfg.sheet_name][0]==VISIBLE
    assert [r['id'] for r in repo.records()]==[r['id'] for r in before]
    assert [r[:len(original)] for r,original in zip(mem.data[cfg.sheet_name][1:],prefix)]==prefix
    assert migrate(cfg,True)['already_applied']
    assert any('copyPaste' in r for r in mem.requests)
    assert any(r.get('repeatCell',{}).get('cell',{}).get('userEnteredFormat',{}).get('textFormat',{}).get('fontFamily')=='Roboto' for r in mem.requests)


def test_old_app_append_interleaves_with_new_append_and_action(monkeypatch,tmp_path):
    cfg,mem,repo=setup_sheet(monkeypatch,tmp_path);migrate(cfg,True)
    old=old_row(cfg.organization)
    mem.before_append=lambda:mem.data[cfg.sheet_name].append(old.copy())
    rec=new_record(cfg.organization);repo.apply([rec],[])
    saved=repo.records();assert len(saved)==4 and saved[-1]['id']==rec['id']
    legacy=saved[-2];original=mem.data[cfg.sheet_name][-2][:13]
    legacy.update(status='완료',revision=2,after={'text':'보수 완료','p':1,'s':1,'score':1,'grade':'매우 낮음','photo_id':'','policy':cfg.organization.policy.version})
    event={'id':str(uuid.uuid4()),'record_id':legacy['id'],'at':'2026-10-30','actor':'qa','kind':'action','text':'보수 완료'}
    repo.apply([legacy],[event])
    assert repo.records()[-2]['status']=='완료'
    assert mem.data[cfg.sheet_name][-2][:13]==original
    assert repo.events(legacy['id'])==[event]
    assert repo.records()[-2]['before']['grade']=='보통'  # Historical 15-point grade is not recalculated.


def test_lost_append_reply_recovers_after_restart_without_new_row(monkeypatch,tmp_path):
    cfg,mem,repo=setup_sheet(monkeypatch,tmp_path);migrate(cfg,True)
    rec=new_record(cfg.organization);mem.lose_append=True
    with pytest.raises(TimeoutError):repo.apply([rec],[])
    restarted=SheetsRepository(cfg)
    assert restarted.records()[-1]['id']==rec['id']
    assert len(restarted.records())==3 and mem.append_calls==1
    request=[json.loads(r[2]) for r in mem.data[TAB][1:] if r[0]=='request'][0]
    assert request['state']=='committed'


@pytest.mark.parametrize('ambiguous',[False,True])
def test_unknown_append_location_never_reappends_or_guesses(monkeypatch,tmp_path,ambiguous):
    cfg,mem,repo=setup_sheet(monkeypatch,tmp_path);migrate(cfg,True)
    rec=new_record(cfg.organization);mem.lose_append=ambiguous;mem.reject_append=not ambiguous
    with pytest.raises(TimeoutError):repo.apply([rec],[])
    if ambiguous:mem.data[cfg.sheet_name].append(copy.deepcopy(mem.data[cfg.sheet_name][-1]))
    repo.records()
    with pytest.raises(Exception,match='저장 위치'):repo.apply([rec],[])
    assert mem.append_calls==1


def test_changed_managed_row_is_rejected(monkeypatch,tmp_path):
    cfg,mem,repo=setup_sheet(monkeypatch,tmp_path);migrate(cfg,True)
    rec=repo.records()[0];mem.data[cfg.sheet_name][1][3]='다른 위치'
    with pytest.raises(SheetSchemaError):repo.apply([rec],[])


@pytest.mark.parametrize('format',['JPEG','PNG','WEBP'])
def test_content_detection_orientation_metadata_and_size(format):
    out=io.BytesIO();im=Image.new('RGB',(2100,900),'navy');exif=Image.Exif();exif[274]=6;exif[270]='private metadata'
    im.save(out,format,exif=exif)
    result=Image.open(io.BytesIO(normalize_photo(out.getvalue())))
    assert result.format=='JPEG' and max(result.size)<=1600 and result.height>result.width
    assert not result.getexif()


def test_heic_primary_image_normalization():
    raw=(Path(__file__).parent/'fixtures/sample.heic').read_bytes()
    im=Image.open(io.BytesIO(normalize_photo(raw)))
    assert im.format=='JPEG' and im.size==(400,200)


def test_photo_failures_and_coordinates_fail_closed():
    with pytest.raises(ServiceError):normalize_photo(b'corrupt')
    with pytest.raises(ServiceError):normalize_photo(b'x'*(20*1024*1024+1))
    cfg=Settings(_env_file=None,app_env='development')
    out=io.BytesIO();Image.new('RGB',(100,100),'white').save(out,'JPEG')
    for response in [{'faces':[{'x_min':800,'y_min':0,'x_max':200,'y_max':300}]},{'faces':[{'x_min':-1,'y_min':0,'x_max':200,'y_max':300}]}]:
        class AI:
            settings=cfg
            def _generate(self,*_):return FaceDetection.model_validate(response)
        with pytest.raises(ServiceError):deidentify_photo(AI(),out.getvalue())


def test_reset_revokes_inflight_draft():
    drafts=Drafts();key=drafts.put('old',{'photo':b'bytes'});drafts.clear_owner('old')
    with pytest.raises(ServiceError):drafts.get('old',key)
    with pytest.raises(ServiceError):drafts.put('old',{'photo':b'late'})
    assert not drafts.items


def test_report_pagination_private_payload_and_editable_hwpx(tmp_path):
    cfg=settings('kywa');records=[current_record(cfg.organization) for _ in range(16)]
    for r in records:r['facility']='평창';r['submitter_name']='홍㉠㉢'
    assert 'submitter_name' not in json.dumps(source_data(records))
    model=compose(records,AIService(cfg));pages=build(model,records,SimpleNamespace(get=lambda _:None))
    assert len(pages)==9
    output=pdf(pages);reader=PdfReader(io.BytesIO(output));assert len(reader.pages)==9
    content=''.join(p.extract_text() for p in reader.pages)
    assert '국립평창청소년수련원' in content
    for forbidden in ['홍㉠㉢','제출자 성명','평가 ID','생성시각']:assert forbidden not in content
    import zipfile
    z=zipfile.ZipFile(io.BytesIO(hwpx(pages)))
    sections=[n for n in z.namelist() if n.startswith('Contents/section')]
    assert len(sections)==9
    xml=z.read(sections[0]).decode();assert '<hp:tbl' in xml and '<hp:t>' in xml and 'editable="1"' in xml


def test_kywa_prompt_restores_original_rules_only_for_kywa():
    from backend.prompts import kywa_prompt
    cfg=settings('kywa');prompt=kywa_prompt(cfg.organization,'중앙','활동부','본관 2층 테라스')
    for required in ['강도(s)를 2 이하','6점 이하','안전수칙 및 작업표준은 있음을 전제','보도블럭 파손','제302조','한국청소년활동진흥원']:
        assert required in prompt
    assert cfg.organization.policy.risk(5,3)['grade']=='높음'
def test_large_journal_is_split_below_google_cell_limit(monkeypatch,tmp_path):
    cfg,mem,repo=setup_sheet(monkeypatch,tmp_path);migrate(cfg,True)
    rec=new_record(cfg.organization)
    rec['description']='상황 설명 ' * 12000
    repo.apply([rec],[])
    rows=[r for r in mem.data[TAB][1:] if r[0]=='request']
    assert len(rows[0])>3 and all(len(str(v))<=40000 for v in rows[0][2:])
    assert repo.records()[-1]['description']==rec['description']
