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
        expected = set(VISIBLE_KEYS)
        if not org.department_enabled and org.submitter_name.mode == "disabled" and len(header) in (17, 18):
            expected -= {"department", "submitter_name"}
        self.multiple_photos = 'before_photo2' in layout.columns
        if self.multiple_photos:
            expected.add('before_photo2')
        if len(header) != len(expected) or set(layout.columns) != expected:
            raise SheetSchemaError('기관 평가표의 열 구성과 기관 설정을 확인하세요.')
        self.header = list(header)
        keys = VISIBLE_KEYS + (['before_photo2'] if self.multiple_photos else [])
        self.positions = [layout.columns.get(k) for k in keys]

    def canonical(self, row, empty=''):
        return [row[i] if i is not None and i < len(row) else empty for i in self.positions]

    def physical(self, row, empty=''):
        result = [empty] * len(self.header)
        for i, position in enumerate(self.positions):
            if position is not None:
                result[position] = row[i] if i < len(row) else empty
        return result


def is_visible(header, org):
    try:
        VisibleLayout(header, org)
        return True
    except SheetSchemaError:
        return False
