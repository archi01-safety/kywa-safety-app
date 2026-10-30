"""Header-preserving adapters for append-only Streamlit and the new writer."""
import copy
import json
import re
import uuid

from .domain import HEADERS, digest, sheet_row

KEYS = ['created_at','facility','department','location','category','scenario','p','s','score','grade',
        'solution','law','photo','after_p','after_s','after_score','after_grade','after_photo',
        'id','policy','status','revision','data','submitter_name']
LABELS = dict(zip(KEYS, HEADERS+['제출자 성명']))
ALIASES = {
    'created_at':['제출일시','제출일','등록일시'], 'facility':['시설','기관명'],
    'department':['담당부서','부서','부서명','사업장','담당 팀명','팀명'], 'category':['유해위험요인(분류)','분류'],
    'scenario':['위험 상황'], 'law':['관련 근거'], 'photo':['사진기록','사진 링크'],
    'submitter_name':['작성자 성명','작성자 이름','성명','이름'],
}
MANAGED = KEYS[13:23]


class SheetSchemaError(ValueError):
    pass


def normalized(value):
    return re.sub(r'\s+', '', str(value))


def base_keys(org):
    keys = KEYS[:13].copy()
    if org.storage.legacy_name_column:
        keys.insert(3, 'submitter_name')
    return keys


class Layout:
    def __init__(self, header, org):
        self.header, self.org = list(header), org
        self.columns = {}
        for index,label in enumerate(header):
            found = [key for key in KEYS if normalized(label) in
                     {normalized(x) for x in [LABELS[key]]+ALIASES.get(key,[])}]
            if found:
                key = found[0]
                if key in self.columns:
                    raise SheetSchemaError('같은 의미의 헤더가 중복되었습니다. 열 매핑을 확인하세요.')
                self.columns[key] = index
        self.base = base_keys(org)
        if any(self.columns.get(key) != i for i,key in enumerate(self.base)):
            raise SheetSchemaError('기관별 기존 열 순서와 헤더가 다릅니다. 원본 열을 이동하지 말고 매핑을 확인하세요.')

    def value(self, row, key):
        col = self.columns.get(key)
        return row[col] if col is not None and col < len(row) else ''

    def require_writable(self):
        required = KEYS if self.org.submitter_name.mode != 'disabled' else KEYS[:-1]
        if any(key not in self.columns for key in required):
            raise SheetSchemaError('관리 열 준비가 필요합니다. migrate 미리보기 후 적용하세요. KYWA 성명은 X1을 확인하세요.')

    def fingerprint(self, row):
        padded = list(row)+['']*max(0,len(self.header)-len(row))
        return digest(padded)

    def decode(self, row, row_index, identity):
        value = self.value(row,'data')
        if value:
            try:
                record = json.loads(value)
                if not isinstance(record,dict) or self.value(row,'id') != record['id']:
                    raise ValueError()
            except (ValueError, TypeError, KeyError):
                raise SheetSchemaError('평가 ID와 시스템데이터를 확인하세요.') from None
            if record.get('organization_id',self.org.id) != self.org.id:
                raise SheetSchemaError('다른 기관의 기록이 포함된 시트입니다.')
            if 'submitter_name' not in record:
                record['submitter_name'] = self.value(row,'submitter_name')
        else:
            if any(self.value(row,k) != '' for k in ('id','policy','status','revision')):
                raise SheetSchemaError('일부 관리 정보만 있는 행입니다. 백업과 원본을 확인하세요.')
            record = self.legacy(row, row_index, identity)
        record.update(_sheet_row=row_index, _sheet_hash=self.fingerprint(row), _sheet_revision=record.get('revision',1))
        return record

    def legacy(self,row,row_index,identity):
        from .migrate import timestamp, integer, drive_id
        get = lambda key: self.value(row,key)
        try:
            before = {key:str(get(key)) for key in ('location','category','scenario','solution','law','grade')}
            before.update(p=integer(get('p'),1,10),s=integer(get('s'),1,10),score=integer(get('score'),0,10000))
            if not before['grade'] or not get('facility'):
                raise ValueError()
            created_at=timestamp(get('created_at'))
            after=None
            if any(get(k) != '' for k in KEYS[13:17]):
                after=dict(p=integer(get('after_p'),1,10),s=integer(get('after_s'),1,10),
                           score=integer(get('after_score'),0,10000),grade=str(get('after_grade')),
                           photo_id=drive_id(get('after_photo')),text='기존 기록에 조치내용 없음',actor='',created_at='',policy='LEGACY-UNKNOWN')
                if not after['grade']: raise ValueError()
        except (ValueError,TypeError,IndexError):
            raise SheetSchemaError(f'{row_index+1}행의 기존 날짜·평가 값 형식을 확인하세요.') from None
        canonical = [get(k) for k in KEYS[:18]]
        stable = digest([get(k) for k in self.base])
        return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{identity}:{row_index}:{stable}')),
                    organization_id=self.org.id,created_at=created_at,facility=str(get('facility')),
                    department=str(get('department')),before=before,after=after,photo_id=drive_id(get('photo')),
                    submitter_name=str(get('submitter_name')),policy='LEGACY-UNKNOWN',
                    legacy_values=canonical,legacy_source='streamlit',
                    reassessment_policy_snapshot=self.org.policy.model_dump(),
                    revision=1,status='완료' if after else '접수')

    def encoded(self,record):
        clean=copy.deepcopy(record)
        from .submitter_name import display_name
        clean['submitter_name'] = display_name(clean.get('submitter_name'))
        for key in list(clean):
            if key.startswith('_sheet_'): clean.pop(key)
        values=sheet_row(clean,True)
        return dict(zip(KEYS,values))

    def new_row(self,record):
        self.require_writable()
        values=self.encoded(record)
        row=['']*len(self.header)
        for key,index in self.columns.items(): row[index]=values[key]
        return row


def expanded_header(rows,org):
    if not rows:
        header=[LABELS[k] for k in base_keys(org)]
    else:
        header=list(rows[0])
        while header and header[-1]=='': header.pop()
        if any(any(str(v).strip() for v in row[len(header):]) for row in rows[1:]):
            raise SheetSchemaError('헤더 없는 열에 기존 데이터가 있습니다. X열을 포함한 확장을 중단합니다.')
    layout=Layout(header,org)
    needed=KEYS if org.submitter_name.mode!='disabled' else KEYS[:-1]
    return header+[LABELS[key] for key in needed if key not in layout.columns]
