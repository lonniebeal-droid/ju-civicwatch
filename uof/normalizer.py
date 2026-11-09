"""JU CivicWatch — Use-of-force report normalizer.

Aggregates UOF reports from multiple Georgia departments into one schema
so they can be compared. Handles the messy reality: every department logs
differently (PDF, CSV, web form), so this module normalizes on ingest.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# Canonical schema every department's report gets mapped into
CANONICAL_FIELDS = [
    "date", "time", "department", "officer_id_hash", "subject_race",
    "subject_gender", "force_type", "force_level", "injury", "weapon_involved",
    "call_type", "location_zone", "bodycam_available", "case_number",
]


@dataclass
class UOFRecord:
    date: str
    time: str = ""
    department: str = ""
    officer_id_hash: str = ""  # hashed, never raw ID
    subject_race: str = ""
    subject_gender: str = ""
    force_type: str = ""  # e.g. TASER, PHYSICAL, FIREARM, CHEMICAL
    force_level: str = ""  # e.g. DISPLAY, DISCHARGE, CONTACT
    injury: str = ""
    weapon_involved: bool = False
    call_type: str = ""
    location_zone: str = ""
    bodycam_available: Optional[bool] = None
    case_number: str = ""
    raw: dict = field(default_factory=dict)

    def to_canonical(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


# Department-specific column mappings: {dept: {canonical_field: source_col}}
MAPPINGS: dict[str, dict[str, str]] = {
    "APD": {
        "date": "incident_date", "time": "incident_time",
        "force_type": "type_of_force", "force_level": "force_level",
        "injury": "subject_injury", "call_type": "call_type",
        "case_number": "case_num",
    },
    "DEKALB": {
        "date": "Date", "time": "Time", "force_type": "ForceType",
        "injury": "Injury", "call_type": "CallType", "case_number": "CaseID",
    },
}


def normalize_row(row: dict, department: str) -> UOFRecord:
    mapping = MAPPINGS.get(department, {})
    def get(field: str, default: str = "") -> str:
        col = mapping.get(field)
        if col:
            return (row.get(col) or "").strip()
        return (row.get(field) or default).strip()

    return UOFRecord(
        date=get("date"),
        time=get("time"),
        department=department,
        force_type=get("force_type"),
        force_level=get("force_level"),
        injury=get("injury"),
        weapon_involved=get("weapon_involved", "").lower() in ("yes", "true", "1"),
        call_type=get("call_type"),
        location_zone=get("location_zone"),
        case_number=get("case_number"),
        raw=dict(row),
    )


def load_csv(path: Path, department: str) -> list[UOFRecord]:
    records: list[UOFRecord] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            records.append(normalize_row(row, department))
    return records


def aggregate(records: list[UOFRecord]) -> dict:
    """Roll up normalized records into summary stats."""
    total = len(records)
    by_dept: dict[str, int] = defaultdict(int)
    by_force: dict[str, int] = defaultdict(int)
    by_race: dict[str, int] = defaultdict(int)
    injuries = 0
    weapons = 0
    for r in records:
        by_dept[r.department] += 1
        by_force[r.force_type or "UNKNOWN"] += 1
        by_race[r.subject_race or "UNKNOWN"] += 1
        if r.injury and r.injury.lower() not in ("none", "no", ""):
            injuries += 1
        if r.weapon_involved:
            weapons += 1
    return {
        "total_incidents": total,
        "by_department": dict(by_dept),
        "by_force_type": dict(by_force),
        "by_subject_race": dict(by_race),
        "injuries": injuries,
        "weapon_involved": weapons,
        "injury_rate_pct": round(injuries / total * 100, 2) if total else 0,
    }


def demo() -> dict:
    # Synthetic multi-department data
    rows_apd = [
        {"incident_date": "2026-10-01", "incident_time": "14:30", "type_of_force": "TASER",
         "force_level": "DISCHARGE", "subject_injury": "Minor", "call_type": "Disturbance",
         "case_num": "2026-1001"},
        {"incident_date": "2026-10-05", "incident_time": "23:15", "type_of_force": "PHYSICAL",
         "force_level": "CONTACT", "subject_injury": "None", "call_type": "Traffic Stop",
         "case_num": "2026-1005"},
        {"incident_date": "2026-10-12", "incident_time": "09:00", "type_of_force": "FIREARM",
         "force_level": "DISPLAY", "subject_injury": "None", "call_type": "Robbery", "case_num": "2026-1012"},
    ]
    rows_dek = [
        {"Date": "2026-10-03", "Time": "18:45", "ForceType": "CHEMICAL", "Injury": "None",
         "CallType": "Protest", "CaseID": "DK-101"},
        {"Date": "2026-10-20", "Time": "01:20", "ForceType": "TASER", "Injury": "Bruise",
         "CallType": "Domestic", "CaseID": "DK-220"},
    ]
    recs = [normalize_row(r, "APD") for r in rows_apd] + [normalize_row(r, "DEKALB") for r in rows_dek]
    return {"records": [r.to_canonical() for r in recs], "summary": aggregate(recs)}


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
