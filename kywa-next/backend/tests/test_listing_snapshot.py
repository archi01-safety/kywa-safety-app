import json
from types import SimpleNamespace

import pytest

from backend.compact_storage import HEAD, TAB, VISIBLE, visible
from backend.config import Settings
from backend.repository import SheetsRepository, cells
from backend.sheet_sync import CONFIG, KEY, fingerprint
from backend.tests.test_institutions import current_record
from backend.visible_layout import VisibleLayout


def grid_row(values):
    return {"values": [{"effectiveValue": c["userEnteredValue"]} for c in cells(values)["values"]]}


@pytest.mark.parametrize("institution", ["kywa", "ayf", "khidi"])
def test_listing_reads_one_grid_with_physical_columns_and_chunked_metadata(monkeypatch, institution):
    cfg = Settings(_env_file=None, organization_id=institution)
    org = cfg.organization
    record = current_record(org)
    row = visible(record)
    header = VISIBLE.copy()
    if institution == "ayf":
        header = [name for index, name in enumerate(header) if index not in (2, 18)]
    if institution == "khidi":
        header.insert(3, header.pop())
    layout = VisibleLayout(header, org)
    value = {"record": record, "source_values": row, "hash": fingerprint(row)}
    raw = json.dumps(value)
    metadata = {"metadataId": 1, "metadataKey": KEY, "metadataValue": record["id"], "visibility": "DOCUMENT",
                "location": {"dimensionRange": {"dimension": "ROWS", "startIndex": 1, "endIndex": 2}}}
    doc = {"sheets": [
        {"properties": {"title": cfg.sheet_name, "sheetId": 0}, "data": [{
            "rowData": [grid_row(header), grid_row(layout.physical(row))],
            "rowMetadata": [{}, {"developerMetadata": [metadata]}]}]},
        {"properties": {"title": TAB, "sheetId": 1}, "data": [{"rowData": [
            grid_row(HEAD), grid_row([*CONFIG, '{"version":2}']),
            grid_row(["record", record["id"], raw[:150], raw[150:]])]}]},
        {"properties": {"title": cfg.history_sheet_name, "sheetId": 2}},
    ]}
    calls = []

    def get(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(execute=lambda: doc)

    service = SimpleNamespace(spreadsheets=lambda: SimpleNamespace(get=get))
    monkeypatch.setattr("backend.repository.google_client", lambda *args: service)
    records, issues = SheetsRepository(cfg).listing_snapshot()
    assert not issues and len(records) == 1 and records[0]["id"] == record["id"]
    assert records[0]["before"]["score"] == record["before"]["score"]
    assert len(calls) == 1 and "userEnteredFormat" not in calls[0]["fields"]
