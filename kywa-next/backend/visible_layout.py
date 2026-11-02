"""Translate institution-preserved visible columns to the internal 19-cell schema.

All identities, fingerprints and journals use canonical order. Only Google IO
uses physical order, including KHIDI's existing D-column name.
"""
from .sheet_schema import KEYS, Layout, SheetSchemaError
from .domain import HEADERS

VISIBLE_KEYS = KEYS[:18] + ['submitter_name']
CANONICAL_HEADER = HEADERS[:18] + ['제출자 성명']
MANAGEMENT_KEYS = ['id', 'policy', 'status', 'revision', 'data']


class VisibleLayout:
    def __init__(self, header, org):
        layout = Layout(header, org)
        if len(header) != 19 or set(layout.columns) != set(VISIBLE_KEYS):
            raise SheetSchemaError('기관 평가표의 19개 열을 확인하세요.')
        self.header = list(header)
        self.positions = [layout.columns[k] for k in VISIBLE_KEYS]

    def canonical(self, row, empty=''):
        return [row[i] if i < len(row) else empty for i in self.positions]

    def physical(self, row, empty=''):
        result = [empty] * 19
        for i, position in enumerate(self.positions):
            result[position] = row[i] if i < len(row) else empty
        return result


def is_visible(header, org):
    try:
        VisibleLayout(header, org)
        return True
    except SheetSchemaError:
        return False
