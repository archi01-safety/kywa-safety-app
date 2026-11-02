"""KYWA row identities and recoverable writes (enabled by an explicit migration).

Visible cells are authoritative. Hidden records retain identity, audit and receipts.
One app writer is required. Streamlit append and human row deletion are supported;
Google Sheets does not offer compare-and-swap for simultaneous edits to one cell.
"""
import copy
import json
import uuid

from .compact_storage import TAB, VISIBLE, clean, metadata, packed, padded, visible
from .domain import HISTORY_HEADERS, digest, now
from .migrate import timestamp, integer, drive_id
from .organization import Policy
from .repository import RepositoryError, cells, google_client, quoted
from .sheet_format import canonical, DATE_FORMAT, format_requests
from .sheet_schema import Layout
from .submitter_name import display_name

KEY = 'kywa.assessment.id'
CONFIG = ('config', 'row_identity')
NOTE = 'KYWA_APPEND:'


class SyncError(RepositoryError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def enabled(entries):
    return entries.get(CONFIG, (None, {}))[1].get('version') == 2


def comparable(row):
    """Also works for invalid rows; an invalid value is not a global read error."""
    values = padded(row)
    for i in (0, 6, 7, 8, 13, 14, 15):
        try:
            values[i] = canonical(values)[i]
        except (ValueError, TypeError, OverflowError):
            pass
    return values


def fingerprint(row):
    return digest(comparable(row))


def blank(row):
    return not any(str(v).strip() for v in padded(row))


class GoogleRows:
    def __init__(self, repo):
        self.repo, self.sid = repo, repo.settings.spreadsheet_id
        self.api = google_client(repo.settings, 'sheets', 'v4').spreadsheets()
        info = self.api.get(spreadsheetId=self.sid, fields='sheets.properties').execute()
        self.ids = {s['properties']['title']: s['properties']['sheetId'] for s in info['sheets']}
        self.sheet_id = self.ids[repo.settings.sheet_name]

    def entries(self):
        return metadata(self.repo)

    def snapshot(self):
        data = self.api.get(spreadsheetId=self.sid, ranges=[quoted(self.repo.settings.sheet_name)+'!A:S'],
            includeGridData=True, fields='sheets(data(startRow,rowMetadata(developerMetadata),rowData(values(effectiveValue,note,userEnteredFormat))))').execute()
        rows, notes, formats = [], {}, {}
        found=[]
        for block in data['sheets'][0].get('data', []):
            for dimension in block.get('rowMetadata',[]): found.extend(dimension.get('developerMetadata',[]))
            for index, item in enumerate(block.get('rowData', []), block.get('startRow', 0)):
                while len(rows) <= index: rows.append([])
                cs = item.get('values', [])[:19]
                rows[index] = [next(iter(c.get('effectiveValue', {}).values()), '') for c in cs]
                if cs and cs[0].get('note', '').startswith(NOTE): notes[index] = cs[0]['note']
                formats[index] = [c.get('userEnteredFormat', {}) for c in cs]
        if not rows or padded(rows[0]) != VISIBLE:
            raise SyncError('sheet_schema', 'KYWA 평가표의 19개 열을 확인하세요.')
        while len(rows)>1 and blank(rows[-1]) and len(rows)-1 not in notes: rows.pop()
        # Read cell values and row identities in the SAME Google response, so a
        # deletion between separate API reads cannot pair two different rows.
        identities = {}
        for md in found:
            if md.get('metadataKey')!=KEY or md.get('visibility')!='DOCUMENT':continue
            loc = md.get('location', {}).get('dimensionRange', {})
            if loc.get('sheetId') != self.sheet_id: continue
            key = md['metadataValue']
            if key in identities or loc.get('dimension')!='ROWS' or loc.get('endIndex',0)-loc.get('startIndex',0)!=1:
                raise SyncError('identity_conflict', '평가 행의 식별정보가 중복되었습니다. 관리 정보 확인이 필요합니다.')
            identities[key] = {'row':loc['startIndex'], 'metadata_id':md['metadataId']}
        return rows, identities, notes, formats

    def batch(self, requests):
        if requests: return self.api.batchUpdate(spreadsheetId=self.sid, body={'requests':requests}).execute()
        return {}

    def save(self, changes, events=(), extra=()):
        entries = self.entries(); requests = list(extra); appended=[]
        for kind, key, value in changes:
            row = cells(packed(kind, key, value, (kind,key) in entries))
            if (kind,key) in entries:
                requests.append({'updateCells':{'start':{'sheetId':self.ids[TAB], 'rowIndex':entries[(kind,key)][0], 'columnIndex':0},
                    'rows':[row], 'fields':'userEnteredValue'}})
            else: appended.append(row)
        if appended: requests.append({'appendCells':{'sheetId':self.ids[TAB], 'rows':appended, 'fields':'userEnteredValue'}})
        if events:
            if self.repo._values(self.repo.settings.history_sheet_name)[0] != HISTORY_HEADERS:
                raise SyncError('history_schema', '조치이력 탭을 확인하세요.')
            requests.append({'appendCells':{'sheetId':self.ids[self.repo.settings.history_sheet_name], 'fields':'userEnteredValue',
                'rows':[cells([e['id'], e['record_id'], e['at'], e.get('actor',''), e['kind'], e.get('text',''),
                    json.dumps(e, ensure_ascii=False)]) for e in events]}})
        return self.batch(requests)

    def bind(self, key, index):
        return {'createDeveloperMetadata':{'developerMetadata':{'metadataKey':KEY, 'metadataValue':key, 'visibility':'DOCUMENT',
            'location':{'dimensionRange':{'sheetId':self.sheet_id, 'dimension':'ROWS', 'startIndex':index, 'endIndex':index+1}}}}}

    def patch(self, metadata_id, edits):
        values = [None] * (max(edits)+1)
        for col, value in edits.items(): values[col] = value
        response = self.api.values().batchUpdateByDataFilter(spreadsheetId=self.sid, body={'valueInputOption':'RAW', 'data':[
            {'dataFilter':{'developerMetadataLookup':{'metadataId':metadata_id}}, 'majorDimension':'ROWS', 'values':[values]}]}).execute()
        if response.get('totalUpdatedRows') != 1:
            raise SyncError('row_deleted', '평가가 삭제되었습니다. 작성 중인 내용은 유지됩니다.')

    def finish_append(self, rows, indexes):
        if not indexes: return
        # Formatting is already in appendCells, including the all-rows-deleted case.
        # Only expand native table/filter ranges; never copy a possibly deleted row's format.
        requests = format_requests(self.api, self.sid, self.repo.settings.sheet_name, len(rows), len(rows))
        for index in indexes:
            requests.append({'updateCells':{'start':{'sheetId':self.sheet_id, 'rowIndex':index, 'columnIndex':0},
                'rows':[{'values':[{}]}], 'fields':'note'}})
        self.batch(requests)


class Store:
    def __init__(self, repo, gateway=None):
        self.repo, self.org = repo, repo.settings.organization
        self.g = gateway or GoogleRows(repo)

    def _record(self, entries, key):
        return copy.deepcopy(entries.get(('record', key), (None, {}))[1])

    def _deleted(self, key, value, loc=None):
        return self._delete_many([(key,value,loc)])[key]

    def _delete_many(self, items):
        changes=[];events=[];extra=[];result={}
        for key,value,loc in items:
            if value.get('deleted'): result[key]=value;continue
            value={**value,'deleted':True,'deleted_at':now()};result[key]=value
            changes.append(('record',key,value))
            events.append(dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,key+':sheet-deleted')),record_id=key,at=value['deleted_at'],
                actor='',kind='시트 삭제 확인',text='평가표에서 행 삭제 또는 전체 내용 지우기를 확인했습니다.'))
            if loc:extra.append({'deleteDeveloperMetadata':{'dataFilter':{'developerMetadataLookup':{'metadataId':loc['metadata_id']}}}})
        if changes:self.g.save(changes,events,extra)
        return result

    def recover_append(self, operation):
        entries = self.g.entries(); item = entries.get(('request',operation))
        older=[v for (kind,_),(_,v) in entries.items() if kind=='record' and v['record'].get('operation_id')==operation]
        if not item and not older: return []
        if not item or item[1].get('version') != 2:
            rows,identities,_,_=self.g.snapshot();result=[]
            for value in older:
                key=value['record']['id'];loc=identities.get(key)
                if not loc or loc['row']>=len(rows) or blank(rows[loc['row']]):value=self._deleted(key,value,loc)
                result.append({**clean(value['record']),'_sheet_deleted':bool(value.get('deleted'))})
            return result
        journal = copy.deepcopy(item[1])
        rows, identities, notes, _ = self.g.snapshot()
        if journal['state']=='appending':
            additions=[]
            for record in journal['records']:
                key=record['id']; token=NOTE+operation+':'+key
                matches=[i for i,n in notes.items() if n==token]
                if key in identities and notes.get(identities[key]['row'])!=token and len(matches)==1:
                    additions.append({'deleteDeveloperMetadata':{'dataFilter':{'developerMetadataLookup':{'metadataId':identities[key]['metadata_id']}}}})
                    identities.pop(key)
                if key not in identities and len(matches)==1 and not blank(rows[matches[0]]):
                    additions.append(self.g.bind(key,matches[0]))
                elif len(matches)>1:
                    raise SyncError('append_ambiguous','제출 위치가 중복되었습니다. 새 요청으로 전송하지 말고 관리자에게 확인해 주세요.')
            self.g.batch(additions)
            rows,identities,notes,_=self.g.snapshot()
            changes=[]; indexes=[]
            for record in journal['records']:
                key=record['id']; token=NOTE+operation+':'+key; loc=identities.get(key)
                value=self._record(entries,key)
                if not loc or loc['row']>=len(rows) or blank(rows[loc['row']]):
                    value=value or {'record':record,'source_values':visible(record)}
                    value.update(deleted=True,deleted_at=now())
                else:
                    index=loc['row']
                    if notes.get(index)!=token:
                        raise SyncError('append_ambiguous','제출 위치 확인 중 행이 변경되었습니다. 같은 요청으로 다시 시도하세요.')
                    # An editor may have changed cells since append. Baseline stays original.
                    value={'record':record, 'source_values':visible(record), 'hash':fingerprint(visible(record)), **loc}
                    indexes.append(index)
                changes.append(('record',key,value))
            journal['state']='committed'
            self.g.save(changes+[('request',operation,journal)])
            self.g.finish_append(rows,indexes)
            entries=self.g.entries()
        result=[]
        rows,identities,notes,_=self.g.snapshot()
        remaining=[v['row'] for key,v in identities.items() if notes.get(v['row'])==NOTE+operation+':'+key]
        if remaining: self.g.finish_append(rows,remaining)
        for record in journal['records']:
            key=record['id']; value=self._record(entries,key);loc=identities.get(key)
            if not value: raise SyncError('receipt_missing','제출 관리 정보를 확인하지 못했습니다. 같은 요청으로 다시 시도하세요.')
            if not loc or loc['row']>=len(rows) or blank(rows[loc['row']]): value=self._deleted(key,value,loc)
            result.append({**clean(value['record']), '_sheet_deleted':bool(value.get('deleted'))})
        return result

    def append(self, records):
        operation=records[0]['operation_id']
        if any(r['operation_id']!=operation for r in records): raise SyncError('request_conflict','다른 제출 요청이 섞였습니다.')
        entries=self.g.entries(); prior=self.recover_append(operation)
        if prior:
            if [(r['id'],r.get('submit_hash'),r.get('submit_owner')) for r in prior] != [(r['id'],r.get('submit_hash'),r.get('submit_owner')) for r in records]:
                raise SyncError('request_conflict','같은 제출번호로 다른 내용을 저장할 수 없습니다.')
            if any(r.get('_sheet_deleted') for r in prior): raise SyncError('row_deleted','제출 후 관리자가 삭제한 평가입니다.')
            return
        template=entries[CONFIG][1]['formats']
        rows,identities,_,_=self.g.snapshot()
        # Clear tombstones before append can reuse a now-empty final data row.
        deleted=[]
        for (kind,key),(_,value) in entries.items():
            if kind!='record' or value.get('deleted'): continue
            loc=identities.get(key)
            if not loc or loc['row']>=len(rows) or blank(rows[loc['row']]): deleted.append((key,value,loc))
        self._delete_many(deleted)
        appended=[]
        for record in records:
            row=cells(visible(record))
            for index,cell in enumerate(row['values']): cell['userEnteredFormat']=copy.deepcopy(template[index])
            row['values'][0]['note']=NOTE+operation+':'+record['id']
            appended.append(row)
        journal={'version':2,'state':'appending','records':[clean(r) for r in records], 'at':now()}
        # One atomic Google batch: append visible rows AND durable receipt.
        self.g.save([('request',operation,journal)],extra=[{'appendCells':{'sheetId':self.g.sheet_id,
            'rows':appended,'fields':'userEnteredValue,userEnteredFormat,note'}}])
        result=self.recover_append(operation)
        if any(r.get('_sheet_deleted') for r in result): raise SyncError('row_deleted','제출 후 관리자가 삭제한 평가입니다.')

    def _policy(self, target):
        if target.get('policy_snapshot'):
            try: p=Policy.model_validate(target['policy_snapshot'])
            except ValueError: return None
            return p if p.version==target.get('policy') else None
        return self.org.policy if target.get('policy')==self.org.policy.version else None

    def parse(self, row, previous, baseline, force=False):
        """Overlay visible cells; retain actions and historical, unedited grade values."""
        row=padded(row); base=comparable(baseline); current=comparable(row)
        record=clean(previous); record.pop('legacy_values',None)
        edits={}; issues=[]
        try: record['created_at']=timestamp(row[0])
        except (ValueError,TypeError,OverflowError):
            record['created_at']='';issues.append('A열 타임스탬프를 날짜로 입력하세요.')
        for col,key in ((1,'facility'),(2,'department')):
            record[key]=str(row[col]).strip()
            if not record[key]: issues.append(f'{VISIBLE[col]}을 입력하세요.')
        record['submitter_name']=display_name(row[18]); record['photo_id']=drive_id(row[12])
        before=copy.deepcopy(record.get('before') or {})
        for col,key in ((3,'location'),(4,'category'),(5,'scenario'),(10,'solution'),(11,'law')):
            before[key]=str(row[col]).strip()
            if col in (3,4,5,10) and not before[key]: issues.append(f'{VISIBLE[col]}을 입력하세요.')
        changed_before=current[6:10]!=base[6:10]
        changed_after=current[13:17]!=base[13:17]
        needs_policy=False
        def score(target, offset, changed, policy_target):
            nonlocal needs_policy
            try:
                p,s=integer(row[offset],1,10),integer(row[offset+1],1,10)
                policy=self._policy(policy_target)
                if changed and not policy and force: policy=self.org.policy
                if changed and not policy:
                    needs_policy=True
                    issues.append(('최초' if offset==6 else '개선 후')+' 평가 기준을 확인하고 현재 KYWA 기준을 적용하세요.')
                if changed and policy:
                    target.update(policy.risk(p,s))
                    edits.update({offset+2:target['score'],offset+3:target['grade']})
                    policy_target.update(policy=policy.version,policy_snapshot=policy.model_dump())
                else:
                    target.update(p=p,s=s,score=integer(row[offset+2],0,10000),grade=str(row[offset+3]).strip())
                    if not target['grade']: raise ValueError()
                    # Check level bounds only for known policies; retain historic scores.
                    if policy: policy.risk(p,s)
            except (ValueError,TypeError,OverflowError):
                issues.append(('최초' if offset==6 else '개선 후')+' 빈도·강도·점수·등급을 확인하세요.')
        score(before,6,changed_before,record)
        record['before']=before
        if any(row[c]!='' for c in range(13,17)):
            after=copy.deepcopy(record.get('after') or {'text':'','actor':'','created_at':'',
                'policy':record.get('policy','LEGACY-UNKNOWN'), 'policy_snapshot':record.get('policy_snapshot')})
            score(after,13,changed_after,after)
            after['photo_id']=drive_id(row[17]); record['after']=after
            if changed_after: record['status']='조치 중'
        else:
            # Clearing numerical cells is not completion and must not discard action history.
            if record.get('after') and changed_after:
                issues.append('개선 후 수치가 지워졌습니다. 빈도·강도를 다시 입력하세요.')
            elif not record.get('after'): record['after']=None
        return record,edits,issues,needs_policy

    def _event(self, key, old, new, kind='시트 수정 확인'):
        return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,key+':'+digest([old,new]))),record_id=key,at=now(),actor='',kind=kind,
            text='시스템이 Google 시트의 변경을 확인했습니다. 편집자는 확인되지 않았습니다.',
            sheet_before=old,sheet_after=new)

    def recover_edits(self, entries=None):
        for (kind,key),(_,journal) in list((entries or self.g.entries()).items()):
            if kind!='edit' or journal['state']!='pending': continue
            rows,identities,_,_=self.g.snapshot(); loc=identities.get(journal['id'])
            if not loc or loc['row']>=len(rows) or blank(rows[loc['row']]):
                self.g.save([('edit',key,{**journal,'state':'deleted'})]);continue
            actual=rows[loc['row']]
            if fingerprint(actual)==fingerprint(journal['before']):
                if journal['edits']:
                    try: self.g.patch(loc['metadata_id'],{int(k):v for k,v in journal['edits'].items()})
                    except SyncError as exc:
                        if exc.code!='row_deleted': raise
                        self.g.save([('edit',key,{**journal,'state':'deleted'})]);continue
                rows,identities,_,_=self.g.snapshot();loc=identities.get(journal['id'])
                if not loc or loc['row']>=len(rows): continue
                actual=rows[loc['row']]
            if fingerprint(actual)!=fingerprint(journal['after']):
                self.g.save([('edit',key,{**journal,'state':'conflict'})]);continue
            value={**journal['value'],**loc,'source_values':padded(journal['after']),'hash':fingerprint(journal['after'])}
            self.g.save([('record',journal['id'],value),('edit',key,{**journal,'state':'committed'})],journal['events'])

    def write(self, key, value, before, edits, events, operation):
        entries=self.g.entries(); old=entries.get(('edit',operation))
        if old and old[1]['state']=='committed': return
        if old and old[1]['state']=='conflict': raise SyncError('row_conflict','시트 내용이 변경되었습니다. 초안은 유지됩니다. 새로고침 후 다시 확인하세요.')
        target=padded(before)
        for col,v in edits.items(): target[col]=v
        journal={'state':'pending','id':key,'before':padded(before),'after':target,'edits':edits,'value':value,'events':events}
        self.g.save([('edit',operation,journal)])
        self.recover_edits()
        state=self.g.entries()[('edit',operation)][1]['state']
        if state!='committed':
            raise SyncError('row_deleted' if state=='deleted' else 'row_conflict',
                '평가가 삭제되었거나 시트 내용이 변경되었습니다. 작성 중인 내용은 유지됩니다. 목록을 새로고침하세요.')

    def sync(self):
        entries=self.g.entries()
        recovered=False
        for (kind,key),(_,value) in list(entries.items()):
            if kind=='request' and value.get('version')==2 and value.get('state')=='appending':
                self.recover_append(key);recovered=True
        if any(k=='edit' and v['state']=='pending' for (k,_),(_,v) in entries.items()):
            self.recover_edits(entries);recovered=True
        if recovered: entries=self.g.entries()
        rows,identities,notes,_=self.g.snapshot();adopted=False
        deleted=[]
        for (kind,key),(_,value) in entries.items():
            if kind!='record' or value.get('deleted'):continue
            loc=identities.get(key)
            if not loc or loc['row']>=len(rows) or blank(rows[loc['row']]):deleted.append((key,value,loc))
        for key,value in self._delete_many(deleted).items():
            entries[('record',key)]=(entries[('record',key)][0],value)
            identities.pop(key,None)
        occupied={v['row']:k for k,v in identities.items() if not entries.get(('record',k),(None,{}))[1].get('deleted')}
        # Append-only Streamlit rows acquire their own ID, even when content is identical.
        for index,row in enumerate(rows[1:],1):
            if blank(row) or (index in occupied and ('record',occupied[index]) in entries) or index in notes: continue
            key=occupied.get(index) or str(uuid.uuid4())
            if index not in occupied: self.g.batch([self.g.bind(key,index)])
            check,ids,_,_=self.g.snapshot();loc=ids.get(key)
            if not loc or fingerprint(check[loc['row']])!=fingerprint(row):
                raise SyncError('row_conflict','행 연결 중 시트가 변경되었습니다. 다시 새로고침하세요.')
            previous={'id':key,'organization_id':'kywa','revision':1,'status':'접수','policy':'LEGACY-UNKNOWN',
                'before':{},'after':None,'legacy_source':'streamlit','reassessment_policy_snapshot':self.org.policy.model_dump()}
            record,_,errors,_=self.parse(row,previous,row)
            value={**loc,'record':record,'source_values':padded(row),'hash':fingerprint(row)}
            if errors: value['issue']={'messages':errors,'can_confirm_policy':False}
            self.g.save([('record',key,value)])
            adopted=True
        if adopted: entries=self.g.entries();rows,identities,_,_=self.g.snapshot()
        records=[];issues=[]
        for (kind,key),(_,stored) in list(entries.items()):
            if kind!='record': continue
            value=copy.deepcopy(stored);loc=identities.get(key)
            if value.get('deleted'): continue
            if not loc or loc['row']>=len(rows) or blank(rows[loc['row']]):
                self._deleted(key,value,loc);continue
            row=rows[loc['row']];baseline=value.get('source_values')
            if baseline is None: baseline=visible(value['record'])
            changed=fingerprint(row)!=fingerprint(baseline)
            observed=fingerprint(row)!=value.get('observed_hash',value.get('hash'))
            record,edits,errors,needs_policy=self.parse(row,value['record'],baseline)
            if observed or (not errors and value.get('issue')):
                record['revision']=value['record']['revision']+1
                event=self._event(key,value.get('observed_values',baseline),padded(row))
                if errors:
                    # Keep the last valid baseline, so unknown-policy edits stay detectable.
                    value.update(observed_hash=fingerprint(row),observed_values=padded(row),issue={'messages':errors,'can_confirm_policy':needs_policy})
                    value['record']['revision']=record['revision']
                    self.g.save([('record',key,value)],[event])
                else:
                    value={**loc,'record':record}
                    self.write(key,value,row,edits,[event],event['id'])
                    value=self._record(self.g.entries(),key)
            if errors:
                issues.append({'id':key,'row':loc['row']+1,'revision':value['record']['revision'],'code':'policy_unknown' if needs_policy else 'row_invalid',
                    'messages':errors,'can_confirm_policy':needs_policy,'facility':record.get('facility',''),
                    'department':record.get('department',''),'status':record.get('status',''),'created_at':record.get('created_at','')})
                continue
            record=value['record'] if changed else record
            records.append({**clean(record),'_sheet_row':loc['row'],'_sheet_hash':value.get('hash',fingerprint(row)),
                '_sheet_revision':record['revision'],'_sheet_metadata_id':loc['metadata_id']})
        return records,issues

    def update(self, records, events):
        current,issues=self.sync();by_id={r['id']:r for r in current}
        for record in records:
            old=by_id.get(record['id'])
            if not old:
                raise SyncError('row_invalid' if any(x['id']==record['id'] for x in issues) else 'row_deleted',
                    '평가가 삭제되었거나 확인이 필요합니다. 작성 중인 내용은 유지됩니다.')
            if old['revision']!=record['_sheet_revision'] or old['_sheet_hash']!=record['_sheet_hash']:
                raise SyncError('row_conflict','시트 또는 앱에서 평가가 변경되었습니다. 초안은 유지됩니다. 목록을 새로고침하세요.')
            entries=self.g.entries();value=self._record(entries,record['id']);row=value['source_values']
            encoded=visible(record);edits={i:encoded[i] for i in range(13,18) if encoded[i]!=row[i]}
            selected=[e for e in events if e['record_id']==record['id']]
            operation=selected[0]['id'] if selected else str(uuid.uuid4())
            self.write(record['id'],{**value,'record':clean(record)},row,edits,selected,operation)

    def confirm(self, key, revision, operation, actor):
        self.sync(); entries=self.g.entries();value=self._record(entries,key)
        if not value or value.get('deleted'): raise SyncError('row_deleted','평가가 삭제되었습니다.')
        done=entries.get(('edit',operation))
        if done and done[1]['state']=='committed':
            if done[1]['id']!=key or done[1]['value']['record']['revision']!=revision+1:
                raise SyncError('request_conflict','같은 요청번호의 평가 또는 수정 버전이 다릅니다.')
            return
        if value['record']['revision']!=revision: raise SyncError('row_conflict','평가가 변경되었습니다. 새로고침하세요.')
        rows,identities,_,_=self.g.snapshot();loc=identities.get(key)
        if not loc or blank(rows[loc['row']]): raise SyncError('row_deleted','평가가 삭제되었습니다.')
        row=rows[loc['row']]; record,edits,errors,_=self.parse(row,value['record'],value['source_values'],True)
        if errors: raise SyncError('row_invalid',' '.join(errors))
        record['revision']+=1
        event=self._event(key,value['source_values'],row,'현재 KYWA 기준 적용')
        event.update(id=operation,actor=actor)
        self.write(key,{**loc,'record':record},row,edits,[event],operation)


def prepare(repo, gateway=None, apply=False):
    """Dry-run first. Never infer identity where two historical rows match."""
    g=gateway or GoogleRows(repo);entries=g.entries();rows,identities,_,formats=g.snapshot()
    if enabled(entries): return {'already_prepared':True}
    changes=[];extra=[];used=set();deleted=0;matched=0
    for (kind,key),(_,value) in entries.items():
        if kind!='record': continue
        expected=visible(value['record'])
        expected_hash=value.get('hash') or fingerprint(expected)
        candidates=[i for i,row in enumerate(rows[1:],1) if not blank(row) and fingerprint(row)==expected_hash]
        if len(candidates)>1 or any(i in used for i in candidates):
            raise SyncError('migration_ambiguous','동일 내용의 관리 기록 연결이 모호합니다. 원본 백업과 대조해야 합니다.')
        if not candidates:
            changes.append(('record',key,{**value,'deleted':True,'deleted_at':now(),'source_values':expected}));deleted+=1
        else:
            index=candidates[0];used.add(index);matched+=1
            changes.append(('record',key,{**value,'row':index,'hash':fingerprint(rows[index]),'source_values':padded(rows[index])}))
            if key not in identities: extra.append(g.bind(key,index))
    template=[copy.deepcopy(f) for f in (formats.get(1,[])+[{}]*19)[:19]]
    for f in template:
        f.setdefault('textFormat',{}).update(fontFamily='Roboto',fontSize=10)
        f.pop('backgroundColor',None);f.pop('backgroundColorStyle',None)
    template[0]['numberFormat']={'type':'DATE_TIME','pattern':DATE_FORMAT}
    changes.append((*CONFIG,{'version':2,'formats':template,'prepared_at':now()}))
    if apply: g.save(changes,extra=extra)
    return {'matched':matched,'deleted':deleted,'unmanaged':sum(not blank(r) for r in rows[1:])-matched,'columns':len(rows[0]),'applied':apply}
