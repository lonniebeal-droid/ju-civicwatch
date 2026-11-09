"""JU CivicWatch — acceptance tests.

Run: python -m pytest tests/ -v
No network, no paid services. Pure local.
"""

import json
import sys
from pathlib import Path

# Allow running from repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.receipts import hash_text, make_receipt, write_receipt
from flock.audit import SearchRecord, audit, demo as flock_demo
from openrecords.automator import ORARequest, ORATracker, demo as ora_demo
from uof.normalizer import aggregate, demo as uof_demo, normalize_row


def test_receipt_roundtrip():
    r = make_receipt("TEST", "local", {"a": 1}, {"b": 2}, record_count=1)
    assert r.input_hash == hash_text(json.dumps({"a": 1}, sort_keys=True))
    assert r.output_hash == hash_text(json.dumps({"b": 2}, sort_keys=True))
    assert r.status == "VERIFIED"
    p = write_receipt(r)
    assert p.exists()
    loaded = json.loads(p.read_text())
    assert loaded["operation"] == "TEST"
    assert loaded["input_hash"] == r.input_hash


def test_flock_demo_flags():
    result = flock_demo()
    assert result.total_searches == 222
    assert result.flagged > 0
    codes = {f.code for f in result.flags}
    assert "AFTER_HOURS" in codes
    assert "NO_CASE" in codes
    assert "RAPID_FIRE" in codes
    assert "REPEAT_PLATE" in codes
    assert result.compliance_pct < 100


def test_flock_clean_dataset():
    recs = [SearchRecord(
        timestamp=__import__("datetime").datetime(2026, 9, 1, 10, i),
        operator="OFF-001", plate=f"PLT{i}", case_number=f"CASE{i}",
    ) for i in range(50)]
    result = audit(recs, department="CLEAN")
    assert result.flagged == 0
    assert result.compliance_pct == 100.0


def test_flock_multi_flag_single_record():
    """One record triggering two flags counts as ONE flagged search.

    Regression test for the flock compliance bug: flagged must count unique
    record indexes, not flag rows, or compliance_pct is understated.
    """
    from datetime import datetime

    recs = [SearchRecord(
        timestamp=datetime(2026, 9, 1, 10, i),
        operator="OFF-001", plate=f"PLT{i}", case_number=f"CASE{i}",
    ) for i in range(9)]
    # After hours (02:30) AND no case number: two flags, one record.
    recs.append(SearchRecord(
        timestamp=datetime(2026, 9, 1, 2, 30),
        operator="OFF-001", plate="PLT9", case_number="",
    ))
    result = audit(recs, department="MULTI-FLAG")
    assert result.total_searches == 10
    assert len(result.flags) == 2
    assert {f.code for f in result.flags} == {"AFTER_HOURS", "NO_CASE"}
    assert result.flagged == 1
    assert result.compliance_pct == 90.0


def test_uof_demo():
    out = uof_demo()
    assert out["summary"]["total_incidents"] == 5
    assert out["summary"]["by_department"]["APD"] == 3
    assert out["summary"]["by_department"]["DEKALB"] == 2
    assert "TASER" in out["summary"]["by_force_type"]


def test_uof_normalize_apd_row():
    row = {"incident_date": "2026-10-01", "incident_time": "14:30",
           "type_of_force": "TASER", "force_level": "DISCHARGE",
           "subject_injury": "Minor", "call_type": "Disturbance", "case_num": "X"}
    rec = normalize_row(row, "APD")
    assert rec.department == "APD"
    assert rec.force_type == "TASER"
    assert rec.date == "2026-10-01"


def test_ora_demo():
    out = ora_demo()
    assert "O.C.G.A." in out["draft_letter"]
    assert "lonniebeal@gmail.com" in out["draft_letter"]
    assert out["tracker_summary"]["total"] == 1
    assert out["request"]["status"] == "SUBMITTED"
    assert out["request"]["deadline"] is not None


def test_ora_deadline_business_days():
    req = ORARequest(agency="X", contact_email="x@y.z", subject="S",
                     records_requested=["R"])
    # Wednesday Nov 4 2026 -> 3 business days = Monday Nov 9
    req.mark_submitted(__import__("datetime").date(2026, 11, 4))
    assert req.deadline == "2026-11-09"


def test_ora_overdue():
    tracker = ORATracker()
    req = ORARequest(agency="X", contact_email="x@y.z", subject="S",
                     records_requested=["R"])
    req.mark_submitted(__import__("datetime").date(2026, 10, 1))
    tracker.add(req)
    assert len(tracker.overdue()) == 1


if __name__ == "__main__":
    import subprocess
    r = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], cwd=str(ROOT))
    sys.exit(r.returncode)
