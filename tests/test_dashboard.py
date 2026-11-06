"""Dashboard build tests. Offline only: local JSON and in-process demos."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.build import build_dashboard
from ordinances.tracker import SEED_PATH


def _build(tmp_path, **kwargs):
    out = kwargs.pop("out", tmp_path / "index.html")
    receipts = kwargs.pop("receipts_dir", tmp_path / "empty-receipts")
    receipts.mkdir(parents=True, exist_ok=True)
    result = build_dashboard(
        out=out,
        receipts_dir=receipts,
        receipt_dir=kwargs.pop("receipt_dir", tmp_path / "written-receipts"),
        **kwargs,
    )
    html = out.read_text(encoding="utf-8")
    return result, html


def test_build_from_seed_includes_public_catalog(tmp_path):
    result, html = _build(
        tmp_path,
        catalog_path=tmp_path / "missing.json",
        seed_path=SEED_PATH,
    )
    assert result["ordinance_count"] == 3
    assert result["ordinance_origin"] == "seed"
    assert result["cost_usd"] == 0.0
    assert "O.C.G.A. § 35-1-22" in html
    assert "26-O-1401" in html
    assert "2024-0244" in html
    assert "Atlanta, GA" in html
    assert "DeKalb County, GA" in html
    assert "held in committee" in html.lower()
    assert "https://law.justia.com/codes/georgia/title-35/chapter-1/section-35-1-22/" in html
    assert "Synthetic" in html
    assert "DEMO-APD" in html
    assert "DEKALB" in html
    assert "lonniebeal@gmail.com" not in html
    assert "<script" not in html.lower()
    assert "cdn." not in html.lower()
    assert "Outreach drafts stay with a person" in html
    receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["operation"] == "DASHBOARD-BUILD"
    assert receipt["status"] == "VERIFIED"
    assert receipt["cost_usd"] == 0.0
    assert receipt["record_count"] == 3


def test_catalog_wins_and_html_is_escaped(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"records": [{
        "jurisdiction": "Test City",
        "title": "Cameras <script>alert(1)</script>",
        "source_url": "https://example.com/ord?q=1&x=2",
        "last_checked": "2026-11-06",
        "citation": "TEST-ONLY",
        "status": "adopted",
        "topic": "alpr",
        "summary": "A <b>bold</b> claim",
        "notes": "note",
    }]}), encoding="utf-8")
    result, html = _build(tmp_path, catalog_path=catalog, seed_path=SEED_PATH)
    assert result["ordinance_origin"] == "catalog"
    assert result["ordinance_count"] == 1
    assert "TEST-ONLY" in html
    assert "26-O-1401" not in html
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html
    assert "https://example.com/ord?q=1&amp;x=2" in html


def test_local_json_overrides_synthetic_demos(tmp_path):
    flock = tmp_path / "flock.json"
    flock.write_text(json.dumps({
        "department": "FILE-DEPT",
        "total_searches": 10,
        "flagged": 1,
        "compliance_pct": 90.0,
        "by_code": {"NO_CASE": 1},
        "by_severity": {"HIGH": 1},
        "flags": [{"code": "NO_CASE", "severity": "HIGH", "message": "from file <x>"}],
    }), encoding="utf-8")
    uof = tmp_path / "uof.json"
    uof.write_text(json.dumps({
        "records": [{
            "date": "2026-01-02",
            "department": "FILE-PD",
            "force_type": "PHYSICAL",
            "force_level": "CONTACT",
            "injury": "None",
            "case_number": "F-1",
        }],
        "summary": {"total_incidents": 1, "by_department": {"FILE-PD": 1}},
    }), encoding="utf-8")
    _, html = _build(
        tmp_path,
        catalog_path=tmp_path / "missing.json",
        flock_path=flock,
        uof_path=uof,
    )
    assert "FILE-DEPT" in html
    assert "from file &lt;x&gt;" in html
    assert "DEMO-APD" not in html
    assert "FILE-PD" in html
    assert "local file" in html.lower()


def test_lists_local_receipts_without_inventing_any(tmp_path):
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    (receipts / "ordinance-ingest-sample.json").write_text(json.dumps({
        "operation": "ORDINANCE-INGEST",
        "status": "VERIFIED",
        "record_count": 3,
        "cost_usd": 0.0,
        "completed_at": "2026-11-06T00:00:00+00:00",
        "output_hash": "abc123def456",
        "notes": "<ignore>",
    }), encoding="utf-8")
    result, html = _build(
        tmp_path,
        catalog_path=tmp_path / "missing.json",
        receipts_dir=receipts,
    )
    assert "ORDINANCE-INGEST" in html
    assert "VERIFIED" in html
    assert "&lt;ignore&gt;" in html
    assert "<ignore>" not in html
    assert result["receipt_count"] == 1


def test_missing_receipts_dir_is_an_empty_state(tmp_path):
    _, html = _build(
        tmp_path,
        catalog_path=tmp_path / "missing.json",
        receipts_dir=tmp_path / "nope",
    )
    assert "No receipt files" in html


def test_cli_smoke_writes_page(tmp_path):
    out = tmp_path / "index.html"
    receipts = tmp_path / "empty"
    receipts.mkdir()
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "dashboard" / "build.py"),
            "--out", str(out),
            "--catalog", str(tmp_path / "missing.json"),
            "--seed", str(SEED_PATH),
            "--receipts-dir", str(receipts),
            "--receipt-dir", str(tmp_path / "receipts-out"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    assert "O.C.G.A. § 35-1-22" in out.read_text(encoding="utf-8")
    assert "ordinance_count" in proc.stdout
    written = list((tmp_path / "receipts-out").glob("*.json"))
    assert len(written) == 1


def test_committed_page_matches_seed_build(tmp_path):
    out = tmp_path / "index.html"
    build_dashboard(
        out=out,
        catalog_path=tmp_path / "missing.json",
        seed_path=SEED_PATH,
        receipts_dir=tmp_path / "empty",
        write_receipt_file=False,
    )
    committed = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == committed
