"""JU CivicWatch — local surveillance ordinance tracker.

Stores public ordinance and statute metadata on disk: jurisdiction, title,
source URL, and last_checked. Ingest reads a local JSON or CSV file. It does
not fetch source pages and does not call paid APIs.

Seed data lives in ordinances/data/seed.json. The working catalog is
ordinances/data/catalog.json (created by ingest; not a substitute for the seed).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.receipts import make_receipt, write_receipt  # noqa: E402


SEED_PATH = Path(__file__).resolve().parent / "data" / "seed.json"
DEFAULT_STORE = Path(__file__).resolve().parent / "data" / "catalog.json"

REQUIRED_FIELDS = ("jurisdiction", "title", "source_url", "last_checked")


@dataclass
class Ordinance:
    jurisdiction: str
    title: str
    source_url: str
    last_checked: str
    citation: str = ""
    instrument_type: str = "ordinance"
    status: str = "unknown"
    topic: str = "surveillance"
    summary: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def record_key(record: Ordinance) -> str:
    """Stable identity for upserts. Citation wins when a jurisdiction has one."""
    citation = record.citation.strip().lower()
    jurisdiction = record.jurisdiction.strip().lower()
    if citation:
        return f"{jurisdiction}|{citation}"
    return f"{jurisdiction}|{record.title.strip().lower()}"


def _coerce_rows(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("ordinances", "records"):
            if key in payload:
                rows = payload[key]
                if not isinstance(rows, list):
                    raise ValueError(f"{key} must be a list")
                return rows
    raise ValueError("ordinance file must be a list or an object with ordinances/records")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_records(
    payload: Any,
    *,
    default_last_checked: Optional[str] = None,
) -> list[Ordinance]:
    """Validate public metadata rows into Ordinance records.

    `payload` is a parsed JSON value (list or wrapper object). Missing
    last_checked is filled from default_last_checked when that is provided.
    """
    rows = _coerce_rows(payload)
    records: list[Ordinance] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"record {i} is not an object")
        data = {str(k): _clean(v) for k, v in row.items()}
        if not data.get("last_checked") and default_last_checked:
            data["last_checked"] = default_last_checked.strip()
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                raise ValueError(f"record {i} missing {field}")
        url = data["source_url"]
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError(f"record {i} source_url must be an http(s) URL")
        try:
            datetime.strptime(data["last_checked"], "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"record {i} last_checked must be YYYY-MM-DD") from exc
        records.append(Ordinance(
            jurisdiction=data["jurisdiction"],
            title=data["title"],
            source_url=url,
            last_checked=data["last_checked"],
            citation=data.get("citation", ""),
            instrument_type=(data.get("instrument_type") or "ordinance").lower(),
            status=(data.get("status") or "unknown").lower(),
            topic=(data.get("topic") or "surveillance").lower(),
            summary=data.get("summary", ""),
            notes=data.get("notes", ""),
        ))
    return records


def load_json(path: Path, *, default_last_checked: Optional[str] = None) -> list[Ordinance]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_records(payload, default_last_checked=default_last_checked)


def load_csv(path: Path, *, default_last_checked: Optional[str] = None) -> list[Ordinance]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return parse_records(rows, default_last_checked=default_last_checked)


def load_path(path: Path, *, default_last_checked: Optional[str] = None) -> list[Ordinance]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json(path, default_last_checked=default_last_checked)
    if suffix == ".csv":
        return load_csv(path, default_last_checked=default_last_checked)
    raise ValueError(f"unsupported ordinance file type: {path.suffix or '(none)'}")


class OrdinanceStore:
    """JSON catalog. One file, rewritten on each upsert."""

    def __init__(self, path: Path = DEFAULT_STORE):
        self.path = path

    def load(self) -> list[Ordinance]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return parse_records(payload)

    def save(self, records: list[Ordinance]) -> None:
        ordered = sorted(records, key=lambda r: (
            r.jurisdiction.lower(),
            r.citation.lower(),
            r.title.lower(),
        ))
        body = {
            "records": [r.to_dict() for r in ordered],
            "record_count": len(ordered),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    def upsert(self, records: list[Ordinance]) -> list[Ordinance]:
        merged = {record_key(r): r for r in self.load()}
        for record in records:
            merged[record_key(record)] = record
        stored = list(merged.values())
        self.save(stored)
        return stored

    def list(
        self,
        *,
        jurisdiction: Optional[str] = None,
        status: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> list[Ordinance]:
        records = self.load()
        if jurisdiction:
            needle = jurisdiction.strip().lower()
            records = [r for r in records if needle in r.jurisdiction.lower()]
        if status:
            want = status.strip().lower()
            records = [r for r in records if r.status == want]
        if topic:
            want = topic.strip().lower()
            records = [r for r in records if r.topic == want]
        return records


def ingest(
    path: Path,
    store: Optional[OrdinanceStore] = None,
    *,
    default_last_checked: Optional[str] = None,
    receipt_dir: Optional[Path] = None,
) -> dict:
    """Parse a local metadata file, upsert it, and write a receipt."""
    store = store or OrdinanceStore()
    incoming = load_path(path, default_last_checked=default_last_checked)
    stored = store.upsert(incoming)
    output = {
        "stored_count": len(stored),
        "citations": [r.citation for r in stored],
    }
    receipt = make_receipt(
        operation="ORDINANCE-INGEST",
        source=str(path),
        input_data={"path": str(path), "incoming": len(incoming)},
        output_data=output,
        record_count=len(incoming),
        notes="Public ordinance metadata ingested from a local file. No network fetch. cost_usd 0.",
    )
    receipt_path = write_receipt(receipt, directory=receipt_dir)
    return {
        "incoming": len(incoming),
        "stored_count": len(stored),
        "store": str(store.path),
        "receipt_path": str(receipt_path),
        "receipt": json.loads(receipt.to_json()),
    }


def demo(
    store_path: Optional[Path] = None,
    receipt_dir: Optional[Path] = None,
) -> dict:
    """Ingest the checked-in public seed and list the catalog."""
    store = OrdinanceStore(store_path or DEFAULT_STORE)
    ingested = ingest(SEED_PATH, store, receipt_dir=receipt_dir)
    listed = store.list()
    by_status: dict[str, int] = {}
    by_jurisdiction: dict[str, int] = {}
    for record in listed:
        by_status[record.status] = by_status.get(record.status, 0) + 1
        by_jurisdiction[record.jurisdiction] = by_jurisdiction.get(record.jurisdiction, 0) + 1
    return {
        "store": str(store.path),
        "incoming": ingested["incoming"],
        "stored_count": ingested["stored_count"],
        "by_status": by_status,
        "by_jurisdiction": by_jurisdiction,
        "records": [r.to_dict() for r in listed],
        "receipt_path": ingested["receipt_path"],
        "cost_usd": ingested["receipt"]["cost_usd"],
    }


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Local surveillance ordinance tracker")
    sub = parser.add_subparsers(dest="command")

    ingest_cmd = sub.add_parser("ingest", help="Ingest a local JSON or CSV metadata file")
    ingest_cmd.add_argument("path", type=Path)
    ingest_cmd.add_argument("--store", type=Path, default=DEFAULT_STORE)
    ingest_cmd.add_argument("--checked", default=None, help="YYYY-MM-DD used when last_checked is blank")
    ingest_cmd.add_argument("--receipt-dir", type=Path, default=None)

    list_cmd = sub.add_parser("list", help="List records in the local catalog")
    list_cmd.add_argument("--store", type=Path, default=DEFAULT_STORE)
    list_cmd.add_argument("--jurisdiction", default=None)
    list_cmd.add_argument("--status", default=None)
    list_cmd.add_argument("--topic", default=None)

    args = parser.parse_args(argv)
    if args.command is None:
        logger.info("ordinance tracker demo complete")
        _print(demo())
        return 0
    if args.command == "ingest":
        if not args.path.exists():
            print(f"File not found: {args.path}", file=sys.stderr)
            return 1
        _print(ingest(
            args.path,
            OrdinanceStore(args.store),
            default_last_checked=args.checked,
            receipt_dir=args.receipt_dir,
        ))
        return 0
    store = OrdinanceStore(args.store)
    if not store.path.exists():
        print(f"No catalog at {store.path}. Run ingest first.", file=sys.stderr)
        return 1
    records = store.list(
        jurisdiction=args.jurisdiction,
        status=args.status,
        topic=args.topic,
    )
    _print({"count": len(records), "records": [r.to_dict() for r in records]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
