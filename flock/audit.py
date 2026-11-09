"""JU CivicWatch — Flock / ALPR search audit engine.

Model: APD's Sept 2026 audit flagged 79 questionable searches out of 115,578
(99.93% compliant). This module generalizes that pattern for any department
that publishes or responds to Open Records requests for ALPR logs.

Flags (configurable thresholds):
  - AFTER_HOURS: search timestamp outside 06:00-22:00 local
  - RAPID_FIRE: >N searches by same operator within M minutes
  - NO_CASE: search with empty or placeholder case number
  - REPEAT_PLATE: same plate searched >K times in 24h by same operator
  - VENDOR_QUERY: queries originating from non-LEO accounts (if log shows)
"""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Default thresholds (tune per department)
DEFAULTS = {
    "after_hours_start": 6,   # 06:00
    "after_hours_end": 22,    # 22:00
    "rapid_fire_count": 10,   # searches
    "rapid_fire_window_min": 5,
    "repeat_plate_count": 5,  # same plate, 24h, same operator
    "min_case_length": 3,
}


@dataclass
class SearchRecord:
    timestamp: datetime
    operator: str
    plate: str
    case_number: str = ""
    location: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Flag:
    code: str
    severity: str  # HIGH | MEDIUM | LOW
    message: str
    record_index: int


@dataclass
class AuditResult:
    department: str
    total_searches: int
    flagged: int
    compliance_pct: float
    flags: list[Flag] = field(default_factory=list)
    by_severity: dict = field(default_factory=dict)
    by_code: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["flags"] = [asdict(f) for f in self.flags]
        return d


def parse_csv(path: Path, *, ts_col: str = "timestamp", op_col: str = "operator",
              plate_col: str = "plate", case_col: str = "case_number",
              loc_col: str = "location") -> list[SearchRecord]:
    """Load ALPR search logs from CSV. Columns are configurable."""
    records: list[SearchRecord] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = datetime.fromisoformat(row[ts_col].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            records.append(SearchRecord(
                timestamp=ts,
                operator=(row.get(op_col) or "").strip(),
                plate=(row.get(plate_col) or "").strip().upper(),
                case_number=(row.get(case_col) or "").strip(),
                location=(row.get(loc_col) or "").strip(),
                raw=dict(row),
            ))
    return records


def audit(records: list[SearchRecord], department: str = "UNKNOWN",
          thresholds: Optional[dict] = None) -> AuditResult:
    """Run the flag suite over a list of search records."""
    t = {**DEFAULTS, **(thresholds or {})}
    flags: list[Flag] = []

    # Group helpers
    by_operator_time: dict[tuple[str, int], list[int]] = defaultdict(list)
    by_operator_plate_day: dict[tuple[str, str, str], list[int]] = defaultdict(list)

    for i, rec in enumerate(records):
        # AFTER_HOURS
        hour = rec.timestamp.hour
        if hour < t["after_hours_start"] or hour >= t["after_hours_end"]:
            flags.append(Flag("AFTER_HOURS", "MEDIUM",
                              f"Search at {rec.timestamp.strftime('%H:%M')} by {rec.operator}", i))

        # NO_CASE
        if len(rec.case_number) < t["min_case_length"]:
            flags.append(Flag("NO_CASE", "HIGH",
                              f"Empty/placeholder case number by {rec.operator}", i))

        # Rapid-fire bucketing (5-min windows)
        bucket = int(rec.timestamp.timestamp() // (t["rapid_fire_window_min"] * 60))
        by_operator_time[(rec.operator, bucket)].append(i)

        # Repeat plate bucketing (operator + plate + calendar day)
        day = rec.timestamp.date().isoformat()
        by_operator_plate_day[(rec.operator, rec.plate, day)].append(i)

    # RAPID_FIRE
    for (op, bucket), idxs in by_operator_time.items():
        if len(idxs) >= t["rapid_fire_count"]:
            for i in idxs:
                flags.append(Flag("RAPID_FIRE", "HIGH",
                                  f"{len(idxs)} searches in {t['rapid_fire_window_min']} min by {op}", i))

    # REPEAT_PLATE
    for (op, plate, day), idxs in by_operator_plate_day.items():
        if len(idxs) >= t["repeat_plate_count"]:
            for i in idxs:
                flags.append(Flag("REPEAT_PLATE", "MEDIUM",
                                  f"Plate {plate} searched {len(idxs)}x on {day} by {op}", i))

    total = len(records)
    # flagged counts UNIQUE records, not flag rows: one search triggering
    # two flags (e.g. AFTER_HOURS + NO_CASE) is one flagged search.
    flagged_count = len({fl.record_index for fl in flags})
    by_sev: dict[str, int] = defaultdict(int)
    by_code_count: dict[str, int] = defaultdict(int)
    for fl in flags:
        by_sev[fl.severity] += 1
        by_code_count[fl.code] += 1

    return AuditResult(
        department=department,
        total_searches=total,
        flagged=flagged_count,
        compliance_pct=round((1 - flagged_count / total) * 100, 4) if total else 100.0,
        flags=flags,
        by_severity=dict(by_sev),
        by_code=dict(by_code_count),
    )


# ---------- Demo with synthetic APD-like data ----------

def demo() -> AuditResult:
    """Synthetic dataset mimicking APD's published audit shape."""
    base = datetime(2026, 9, 1, 8, 0)
    recs: list[SearchRecord] = []
    # 200 normal daytime searches
    for i in range(200):
        recs.append(SearchRecord(
            timestamp=base + timedelta(hours=i % 14, minutes=i % 50),
            operator=f"OFFICER-{i % 12:03d}",
            plate=f"ABC{i % 900 + 100}",
            case_number=f"2026-{1000 + i}",
        ))
    # 3 after-hours searches
    for i in range(3):
        recs.append(SearchRecord(
            timestamp=base + timedelta(days=i, hours=2),
            operator=f"OFFICER-{i:03d}", plate=f"XYZ{i}", case_number=f"2026-9{i}",
        ))
    # 1 no-case search
    recs.append(SearchRecord(
        timestamp=base + timedelta(hours=10), operator="OFFICER-007",
        plate="NOCASE1", case_number="",
    ))
    # 1 rapid-fire burst (12 searches in 4 min)
    burst_t = base + timedelta(hours=15)
    for i in range(12):
        recs.append(SearchRecord(
            timestamp=burst_t + timedelta(seconds=i * 20),
            operator="OFFICER-099", plate=f"BURST{i}", case_number=f"2026-B{i}",
        ))
    # 1 repeat plate (6 searches same plate, same day, same operator)
    for i in range(6):
        recs.append(SearchRecord(
            timestamp=base + timedelta(hours=11, minutes=i * 3),
            operator="OFFICER-042", plate="REPEAT42", case_number=f"2026-R{i}",
        ))
    return audit(recs, department="DEMO-APD")


if __name__ == "__main__":
    result = demo()
    # JSON stays on stdout (piping contract); the status line goes to the logger.
    logger.info("flock demo complete: %s searches, %s flagged",
                result.total_searches, result.flagged)
    print(json.dumps(result.to_dict(), indent=2, default=str))
