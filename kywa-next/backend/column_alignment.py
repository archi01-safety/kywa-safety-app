"""Semantic alignment shared by visible-sheet writes and print workbooks."""
import copy
from .visible_layout import VISIBLE_KEYS

SHORT_FIELDS=frozenset({'created_at','facility','department','category','p','s','score','grade',
    'after_p','after_s','after_score','after_grade','submitter_name'})
SHORT_CANONICAL=frozenset(i for i,key in enumerate(VISIBLE_KEYS) if key in SHORT_FIELDS)


def row_alignment(index):
    return 'CENTER' if index in SHORT_CANONICAL else 'LEFT'


def centered_template(formats):
    result=copy.deepcopy(formats)
    for index in SHORT_CANONICAL:
        if index<len(result):result[index]['horizontalAlignment']='CENTER'
    return result


def center_requests(layout,sheet_id):
    # Physical order differs in KHIDI and AYF. No headers/values/links are touched.
    columns=sorted(layout.positions[i] for i in SHORT_CANONICAL
        if i<len(layout.positions) and layout.positions[i] is not None)
    return [{'repeatCell':{'range':{'sheetId':sheet_id,'startRowIndex':1,
        'startColumnIndex':column,'endColumnIndex':column+1},
        'cell':{'userEnteredFormat':{'horizontalAlignment':'CENTER'}},
        'fields':'userEnteredFormat.horizontalAlignment'}} for column in columns]
