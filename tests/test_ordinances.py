"""Ordinance tracker tests. Offline only: local JSON/CSV, no network."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ordinances.tracker import (
    SEED_PATH,
    OrdinanceStore,
    demo,
    ingest,
    load_csv,
    load_json,
    parse_records,
)


def test_parse_public_seed():
    records = load_json(SEED_PATH)
    assert len(records) == 3
    by_citation = {r.citation: r for r in records}
    statute = by_citation["O.C.G.A. § 35-1-22"]
    assert statute.jurisdiction == "Georgia"
    assert statute.instrument_type == "statute"
    assert statute.status == "enacted"
    assert statute.topic == "alpr"
    assert statute.source_url.startswith("https://")
    assert statute.last_checked == "2026-11-06"

    atlanta = by_citation["26-O-1401"]
    assert atlanta.jurisdiction == "Atlanta, GA"
    assert atlanta.status == "held_in_committee"
    assert atlanta.instrument_type == "ordinance"

    dekalb = by_citation["2024-0244"]
    assert dekalb.status == "adopted"
    assert dekalb.topic == "video_surveillance"
    assert "convenience stores" in dekalb.summary


def test_parse_rejects_missing_source_url():
    try:
        parse_records([{
            "jurisdiction": "Atlanta, GA",
            "title": "Untitled",
            "last_checked": "2026-11-06",
        }])
    except ValueError as exc:
        assert "source_url" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parse_rejects_bad_date_and_url():
    base = {
        "jurisdiction": "Atlanta, GA",
        "title": "Cameras",
        "source_url": "https://example.com/ord",
        "last_checked": "11/06/2026",
    }
    try:
        parse_records([base])
    except ValueError as exc:
        assert "last_checked" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    base["last_checked"] = "2026-11-06"
    base["source_url"] = "ftp://example.com/ord"
    try:
        parse_records([base])
    except ValueError as exc:
        assert "source_url" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parse_csv_and_default_last_checked(tmp_path):
    csv_path = tmp_path / "ordinances.csv"
    csv_path.write_text(
        "jurisdiction,title,source_url,citation,status,topic\n"
        "\"Sample County, GA\",Sample camera rule,https://example.com/sample,SAMPLE-1,adopted,video_surveillance\n",
        encoding="utf-8",
    )
    records = load_csv(csv_path, default_last_checked="2026-11-06")
    assert len(records) == 1
    assert records[0].jurisdiction == "Sample County, GA"
    assert records[0].last_checked == "2026-11-06"
    assert records[0].citation == "SAMPLE-1"


def test_store_and_list_roundtrip(tmp_path):
    store = OrdinanceStore(tmp_path / "catalog.json")
    incoming = load_json(SEED_PATH)
    stored = store.upsert(incoming)
    assert len(stored) == 3
    assert store.path.exists()

    reloaded = OrdinanceStore(store.path).load()
    assert [r.citation for r in reloaded] == [
        "26-O-1401",
        "2024-0244",
        "O.C.G.A. § 35-1-22",
    ]

    atlanta = store.list(jurisdiction="atlanta")
    assert len(atlanta) == 1
    assert atlanta[0].citation == "26-O-1401"

    adopted = store.list(status="adopted")
    assert [r.citation for r in adopted] == ["2024-0244"]

    alpr = store.list(topic="alpr")
    assert len(alpr) == 1
    assert alpr[0].instrument_type == "statute"

    assert store.list(jurisdiction="nowhere") == []


def test_ingest_is_idempotent_and_receipted(tmp_path):
    store = OrdinanceStore(tmp_path / "catalog.json")
    receipts = tmp_path / "receipts"
    first = ingest(SEED_PATH, store, receipt_dir=receipts)
    second = ingest(SEED_PATH, store, receipt_dir=receipts)
    assert first["incoming"] == 3
    assert first["stored_count"] == 3
    assert second["stored_count"] == 3
    assert len(store.load()) == 3

    receipt_files = list(receipts.glob("*.json"))
    assert len(receipt_files) == 2
    loaded = json.loads(receipt_files[0].read_text(encoding="utf-8"))
    assert loaded["operation"] == "ORDINANCE-INGEST"
    assert loaded["status"] == "VERIFIED"
    assert loaded["record_count"] == 3
    assert loaded["cost_usd"] == 0.0
    assert loaded["input_hash"]
    assert loaded["output_hash"]


def test_demo_uses_isolated_store(tmp_path):
    out = demo(store_path=tmp_path / "catalog.json", receipt_dir=tmp_path / "receipts")
    assert out["incoming"] == 3
    assert out["stored_count"] == 3
    assert out["cost_usd"] == 0.0
    assert out["by_status"]["adopted"] == 1
    assert out["by_status"]["held_in_committee"] == 1
    assert out["by_status"]["enacted"] == 1
    assert Path(out["receipt_path"]).exists()
    assert (tmp_path / "catalog.json").exists()
