"""JU CivicWatch — Georgia Open Records Act request automator.

O.C.G.A. § 50-18-70: any citizen can request public records from any
Georgia agency. Standard response window is 3 business days; agencies can
extend but must cite a specific reason. This module drafts requests,
tracks deadlines, and logs every submission with a receipt.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


ORA_STATUTE = "O.C.G.A. § 50-18-70"
RESPONSE_DAYS = 3  # business days


@dataclass
class ORARequest:
    agency: str
    contact_email: str
    subject: str
    records_requested: list[str]
    requester_name: str = "Lonnie Beal"
    requester_email: str = "lonniebeal@gmail.com"
    date_submitted: Optional[str] = None
    deadline: Optional[str] = None
    status: str = "DRAFT"  # DRAFT | SUBMITTED | EXTENDED | COMPLETE | DENIED
    extension_reason: str = ""
    response_summary: str = ""
    notes: str = ""

    def draft_letter(self) -> str:
        lines = [
            f"To: {self.agency}",
            f"Email: {self.contact_email}",
            f"From: {self.requester_name} <{self.requester_email}>\n",
            f"Re: Open Records Request — {self.subject}\n",
            f"Submitted under {ORA_STATUTE}. Please provide the following records:",
        ]
        for i, r in enumerate(self.records_requested, 1):
            lines.append(f"  {i}. {r}")
        lines.append(
            f"\nPlease respond within {RESPONSE_DAYS} business days as required by statute."
        )
        lines.append("If any portion is withheld, please cite the specific exemption.")
        return "\n".join(lines)

    def mark_submitted(self, on: Optional[date] = None) -> None:
        d = on or date.today()
        self.date_submitted = d.isoformat()
        # 3 business days
        deadline = d
        added = 0
        while added < RESPONSE_DAYS:
            deadline += timedelta(days=1)
            if deadline.weekday() < 5:
                added += 1
        self.deadline = deadline.isoformat()
        self.status = "SUBMITTED"


@dataclass
class ORATracker:
    requests: list[ORARequest] = field(default_factory=list)

    def add(self, req: ORARequest) -> None:
        self.requests.append(req)

    def overdue(self) -> list[ORARequest]:
        today = date.today().isoformat()
        return [r for r in self.requests
                if r.status == "SUBMITTED" and r.deadline and r.deadline < today]

    def summary(self) -> dict:
        by_status: dict[str, int] = __import__("collections").defaultdict(int)
        for r in self.requests:
            by_status[r.status] += 1
        return {
            "total": len(self.requests),
            "by_status": dict(by_status),
            "overdue": len(self.overdue()),
        }


# ---------- Demo ----------

def demo() -> dict:
    tracker = ORATracker()
    req = ORARequest(
        agency="Atlanta Police Department — Open Records Unit",
        contact_email="apdopencrecords@atlantaga.gov",
        subject="Flock ALPR search logs — September 2026",
        records_requested=[
            "All Flock Safety ALPR search logs for September 1-30, 2026, including operator ID, timestamp, plate queried, case number, and location.",
            "Any internal audit or review of Flock searches conducted in September 2026.",
            "List of all Flock camera locations active in Atlanta as of September 30, 2026.",
        ],
    )
    req.mark_submitted(date(2026, 11, 4))
    tracker.add(req)
    return {
        "draft_letter": req.draft_letter(),
        "tracker_summary": tracker.summary(),
        "request": asdict(req),
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
