"""KYWA cell values and table formatting, independent of displayed date strings."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .domain import digest

DATE_FORMAT = 'yyyy. m. d am/pm h:mm:ss'
EPOCH = datetime(1899, 12, 30)


def date_serial(value):
    if isinstance(value, (int, float)):
        return round(float(value), 9)
    from .migrate import timestamp
    d = datetime.fromisoformat(timestamp(value)).astimezone(ZoneInfo('Asia/Seoul')).replace(tzinfo=None)
    return round((d-EPOCH).total_seconds()/86400, 9)


def canonical(row, width=19):
    values = list(row[:width])+['']*max(0,width-len(row))
    if values[0] != '': values[0] = date_serial(values[0])
    for i in (6,7,8,13,14,15):
        if values[i] != '':
            number = float(values[i])
            if not number.is_integer(): raise ValueError('평가 점수는 정수여야 합니다.')
            values[i] = int(number)
    return values


def fingerprint(row):
    return digest(canonical(row))


def format_requests(svc, sid, name, start, end, width=19, sheet_info=None):
    if sheet_info is None:
        meta = svc.get(spreadsheetId=sid, fields='sheets(properties,tables,basicFilter,bandedRanges)').execute()
        sheet_info = next(s for s in meta['sheets'] if s['properties']['title']==name)
    sheet = sheet_info
    sheet_id=sheet['properties']['sheetId']
    requests=[]
    if end > start:
        requests += [
            {'copyPaste':{'source':{'sheetId':sheet_id,'startRowIndex':1,'endRowIndex':2,'startColumnIndex':0,'endColumnIndex':width},
                'destination':{'sheetId':sheet_id,'startRowIndex':start,'endRowIndex':end,'startColumnIndex':0,'endColumnIndex':width},'pasteType':'PASTE_FORMAT'}},
            {'repeatCell':{'range':{'sheetId':sheet_id,'startRowIndex':start,'endRowIndex':end,'startColumnIndex':0,'endColumnIndex':width},
                'cell':{'userEnteredFormat':{'textFormat':{'fontFamily':'Roboto','fontSize':10}}},'fields':'userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize'}},
            {'repeatCell':{'range':{'sheetId':sheet_id,'startRowIndex':start,'endRowIndex':end,'startColumnIndex':0,'endColumnIndex':1},
                'cell':{'userEnteredFormat':{'numberFormat':{'type':'DATE_TIME','pattern':DATE_FORMAT}}},'fields':'userEnteredFormat.numberFormat'}}]
        # The native table owns alternating row colors. Remove copied direct fills.
        if sheet.get('tables'):
            requests.append({'repeatCell':{'range':{'sheetId':sheet_id,'startRowIndex':start,'endRowIndex':end,'startColumnIndex':0,'endColumnIndex':width},
                'cell':{},'fields':'userEnteredFormat.backgroundColor,userEnteredFormat.backgroundColorStyle'}})
    for table in sheet.get('tables',[]):
        r=table['range']
        if r.get('startRowIndex',0)==0 and r.get('startColumnIndex',0)==0:
            requests.append({'updateTable':{'table':{'tableId':table['tableId'],'range':{**r,'endRowIndex':max(end,r.get('endRowIndex',end)),'endColumnIndex':width}},'fields':'range'}})
    if not sheet.get('tables'):
        if sheet.get('basicFilter'):
            f=sheet['basicFilter'];r=f['range']
            requests.append({'setBasicFilter':{'filter':{**f,'range':{**r,'endRowIndex':max(end,r.get('endRowIndex',end)),'endColumnIndex':width}}}})
        for band in sheet.get('bandedRanges',[]):
            r=band['range']
            requests.append({'updateBanding':{'bandedRange':{'bandedRangeId':band['bandedRangeId'],'range':{**r,'endRowIndex':max(end,r.get('endRowIndex',end)),'endColumnIndex':width}},'fields':'range'}})
    return requests
