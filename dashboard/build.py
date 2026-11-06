"""Build dashboard/index.html from local CivicWatch JSON.

Reads ordinances/data/catalog.json when it exists, otherwise the checked-in
seed. Flock and use-of-force sections use a JSON file when one is already on
disk, otherwise the offline synthetic demos in this repo. Receipt JSON under
receipts/ is listed when present. No network, no paid API, no deploy.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.receipts import make_receipt, write_receipt  # noqa: E402
from ordinances.tracker import SEED_PATH, Ordinance, load_json  # noqa: E402


DEFAULT_OUT = Path(__file__).resolve().parent / "index.html"
DEFAULT_CATALOG = ROOT / "ordinances" / "data" / "catalog.json"
DEFAULT_RECEIPTS = ROOT / "receipts"
STYLES_PATH = Path(__file__).resolve().parent / "styles.css"
FLOCK_JSON = ROOT / "flock" / "data" / "summary.json"
UOF_JSON = ROOT / "uof" / "data" / "summary.json"

UOF_COLUMNS = (
    "date",
    "time",
    "department",
    "force_type",
    "force_level",
    "injury",
    "call_type",
    "case_number",
)


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def status_label(status: str) -> str:
    return (status or "unknown").replace("_", " ")


def status_class(status: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (status or "unknown").lower()).strip("-")
    return "status-" + (slug or "unknown")


def human_topic(topic: str) -> str:
    if (topic or "").lower() == "alpr":
        return "ALPR"
    return (topic or "surveillance").replace("_", " ")


def human_key(key: str) -> str:
    return key.replace("_", " ")


def _repo_label(path: Path, fallback: str) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return fallback


def load_ordinances(
    catalog_path: Path,
    seed_path: Path,
) -> tuple[list[Ordinance], str, str]:
    if catalog_path.exists():
        records = load_json(catalog_path)
        return records, "catalog", "ordinances/data/catalog.json"
    if not seed_path.exists():
        raise FileNotFoundError(
            f"No catalog at {catalog_path} and no seed at {seed_path}"
        )
    return load_json(seed_path), "seed", "ordinances/data/seed.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_flock(path: Optional[Path]) -> dict:
    candidate = path if path is not None else (FLOCK_JSON if FLOCK_JSON.exists() else None)
    if candidate is not None and candidate.exists():
        payload = _read_json(candidate)
        if not isinstance(payload, dict):
            raise ValueError(f"Flock JSON must be an object: {candidate}")
        return {
            "origin": "file",
            "source": _repo_label(candidate, "local file"),
            "data": payload,
        }
    from flock.audit import demo

    return {
        "origin": "demo",
        "source": "flock/audit.py demo()",
        "data": demo().to_dict(),
    }


def load_uof(path: Optional[Path]) -> dict:
    candidate = path if path is not None else (UOF_JSON if UOF_JSON.exists() else None)
    if candidate is not None and candidate.exists():
        payload = _read_json(candidate)
        if not isinstance(payload, dict):
            raise ValueError(f"UOF JSON must be an object: {candidate}")
        records = payload.get("records") or []
        summary = payload.get("summary") or {}
        return {
            "origin": "file",
            "source": _repo_label(candidate, "local file"),
            "records": records if isinstance(records, list) else [],
            "summary": summary if isinstance(summary, dict) else {},
        }
    from uof.normalizer import demo

    payload = demo()
    return {
        "origin": "demo",
        "source": "uof/normalizer.py demo()",
        "records": payload.get("records") or [],
        "summary": payload.get("summary") or {},
    }


def load_receipts(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    rows: list[dict] = []
    for path in sorted(directory.glob("*.json"), key=lambda p: p.name):
        try:
            payload = _read_json(path)
        except json.JSONDecodeError:
            rows.append({"file": path.name, "error": "Could not parse JSON"})
            continue
        if not isinstance(payload, dict):
            continue
        digest = str(payload.get("output_hash") or "")
        rows.append({
            "file": path.name,
            "operation": payload.get("operation", ""),
            "status": payload.get("status", ""),
            "record_count": payload.get("record_count", ""),
            "cost_usd": payload.get("cost_usd", ""),
            "completed_at": payload.get("completed_at", ""),
            "output_hash": digest[:12],
            "notes": payload.get("notes", ""),
        })
    return rows


def _origin_note(kind: str, source: str) -> str:
    if kind == "file":
        if source == "local file":
            return "Source: local file."
        return f"Source: local file ({esc(source)})."
    return f"Synthetic demo from {esc(source)}. Not a department export."


def _sample_flags(flags: list, limit: int = 6) -> list:
    """Prefer one row per flag code, then fill in audit order."""
    picked: list = []
    seen: set[str] = set()
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        code = str(flag.get("code") or "")
        if code not in seen:
            picked.append(flag)
            seen.add(code)
    if len(picked) >= limit:
        return picked[:limit]
    for flag in flags:
        if len(picked) >= limit:
            break
        if isinstance(flag, dict) and flag not in picked:
            picked.append(flag)
    return picked


def _render_kv(value: Any) -> str:
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"<div><dt>{esc(human_key(str(key)))}</dt><dd>{_render_kv(item)}</dd></div>")
        return '<dl class="grid">' + "".join(parts) + "</dl>"
    if isinstance(value, list):
        return esc(", ".join(str(item) for item in value))
    return esc(value)


def _render_ordinances(records: list[Ordinance], origin: str, source: str, seed_count: Optional[int]) -> str:
    if origin == "catalog":
        where = (
            f"These rows are the local catalog at {esc(source)}. "
            "Source URLs are links only; this build does not fetch them."
        )
    else:
        where = (
            f"These rows are the checked-in seed at {esc(source)} "
            "because ordinances/data/catalog.json is not on disk. "
            "Run <code>python ordinances/tracker.py</code>, then rebuild, to use the catalog. "
            "Source URLs are links only; this build does not fetch them."
        )
    seed_note = ""
    if seed_count is not None and origin == "catalog":
        seed_note = (
            f"<p class=\"note\">Checked-in seed ordinances/data/seed.json: {seed_count} records. "
            "This page lists the catalog, not a merge with the seed.</p>"
        )
    cards = []
    for record in sorted(records, key=lambda r: (
        r.jurisdiction.lower(),
        r.citation.lower(),
        r.title.lower(),
    )):
        citation = f"<p class=\"cite\">{esc(record.citation)}</p>" if record.citation else ""
        summary = f"<p>{esc(record.summary)}</p>" if record.summary else ""
        notes = ""
        if record.notes:
            notes = (
                "<details><summary>Notes</summary>"
                f"<p>{esc(record.notes)}</p></details>"
            )
        cards.append(
            "<article class=\"card\">"
            f"<p class=\"kicker\">{esc(record.jurisdiction)} · {esc(record.instrument_type)}</p>"
            f"<h3>{esc(record.title)}</h3>"
            f"{citation}"
            "<p class=\"badges\">"
            f"<span class=\"badge {status_class(record.status)}\">{esc(status_label(record.status))}</span>"
            f"<span class=\"badge\">{esc(human_topic(record.topic))}</span>"
            f"<span class=\"badge\">checked {esc(record.last_checked)}</span>"
            "</p>"
            f"{summary}"
            f"<p class=\"source\"><a href=\"{esc(record.source_url)}\">{esc(record.source_url)}</a></p>"
            f"{notes}"
            "</article>"
        )
    body = "".join(cards) if cards else "<p class=\"note\">No ordinance records in the local catalog.</p>"
    return (
        "<section id=\"ordinances\">"
        "<h2>Surveillance ordinances</h2>"
        f"<p class=\"note\">{where}</p>"
        f"{seed_note}"
        f"{body}"
        "</section>"
    )


def _render_flock(flock: dict) -> str:
    data = flock["data"]
    flags = data.get("flags") or []
    if not isinstance(flags, list):
        flags = []
    shown = _sample_flags(flags)
    extra = len(flags) - len(shown)
    items = []
    for flag in shown:
        if not isinstance(flag, dict):
            continue
        items.append(
            "<li>"
            f"<strong>{esc(flag.get('code', ''))}</strong> "
            f"({esc(flag.get('severity', ''))}) "
            f"{esc(flag.get('message', ''))}"
            "</li>"
        )
    more = (
        f"<p class=\"note\">Showing {len(shown)} of {len(flags)} flag rows.</p>"
        if extra > 0 else ""
    )
    by_code = data.get("by_code") if isinstance(data.get("by_code"), dict) else {}
    by_sev = data.get("by_severity") if isinstance(data.get("by_severity"), dict) else {}
    return (
        "<section id=\"flock\">"
        "<h2>Flock / ALPR audit</h2>"
        f"<p class=\"note\">{_origin_note(flock['origin'], flock['source'])}</p>"
        "<dl class=\"grid\">"
        f"<div><dt>Department</dt><dd>{esc(data.get('department', ''))}</dd></div>"
        f"<div><dt>Searches</dt><dd>{esc(data.get('total_searches', ''))}</dd></div>"
        f"<div><dt>Flagged rows</dt><dd>{esc(data.get('flagged', ''))}</dd></div>"
        f"<div><dt>Compliance pct</dt><dd>{esc(data.get('compliance_pct', ''))}</dd></div>"
        "</dl>"
        "<div class=\"panel\"><h3>By code</h3>"
        f"{_render_kv(by_code)}</div>"
        "<div class=\"panel\"><h3>By severity</h3>"
        f"{_render_kv(by_sev)}</div>"
        "<div class=\"panel\"><h3>Sample flags</h3>"
        f"<ul>{''.join(items) if items else '<li>None</li>'}</ul>{more}</div>"
        "</section>"
    )


def _render_uof(uof: dict) -> str:
    records = [row for row in uof["records"] if isinstance(row, dict)]
    columns = [
        col for col in UOF_COLUMNS
        if any(str(row.get(col) or "").strip() for row in records)
    ]
    if not columns and records:
        columns = ["department"]
    head = "".join(f"<th>{esc(human_key(col))}</th>" for col in columns)
    body_rows = []
    for row in records:
        cells = "".join(
            f"<td data-label=\"{esc(human_key(col))}\">{esc(row.get(col, ''))}</td>"
            for col in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")
    table = (
        "<div class=\"scroll\"><table>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    ) if columns else "<p class=\"note\">No use-of-force rows.</p>"
    return (
        "<section id=\"uof\">"
        "<h2>Use of force</h2>"
        f"<p class=\"note\">{_origin_note(uof['origin'], uof['source'])} "
        "Officer identifiers are not shown.</p>"
        "<div class=\"panel\"><h3>Summary</h3>"
        f"{_render_kv(uof['summary'])}</div>"
        f"{table}"
        "</section>"
    )


def _render_receipts(rows: list[dict], directory: Path) -> str:
    del directory
    if not rows:
        body = (
            "<p class=\"note\">No receipt files in this build. "
            "Receipt JSON is gitignored. Rebuild after a local run to list receipts/*.json.</p>"
        )
    else:
        cards = []
        for row in rows:
            if row.get("error"):
                cards.append(
                    "<article class=\"card\">"
                    f"<h3>{esc(row.get('file', ''))}</h3>"
                    f"<p>{esc(row['error'])}</p></article>"
                )
                continue
            cards.append(
                "<article class=\"card\">"
                f"<h3>{esc(row.get('operation') or row.get('file'))}</h3>"
                "<dl class=\"grid\">"
                f"<div><dt>File</dt><dd>{esc(row.get('file', ''))}</dd></div>"
                f"<div><dt>Status</dt><dd>{esc(row.get('status', ''))}</dd></div>"
                f"<div><dt>Records</dt><dd>{esc(row.get('record_count', ''))}</dd></div>"
                f"<div><dt>Cost USD</dt><dd>{esc(row.get('cost_usd', ''))}</dd></div>"
                f"<div><dt>Completed</dt><dd>{esc(row.get('completed_at', ''))}</dd></div>"
                f"<div><dt>Output hash</dt><dd>{esc(row.get('output_hash', ''))}</dd></div>"
                "</dl>"
                f"<p class=\"note\">{esc(row.get('notes', ''))}</p>"
                "</article>"
            )
        body = "".join(cards)
    return (
        "<section id=\"receipts\">"
        "<h2>Receipts</h2>"
        "<p class=\"note\">SHA-256 receipts already on disk. This page does not create a data pull.</p>"
        f"{body}"
        "</section>"
    )


def _stat(value: Any, label: str) -> str:
    return f"<div class=\"stat\"><b>{esc(value)}</b><span>{esc(label)}</span></div>"


def render_page(
    *,
    records: list[Ordinance],
    origin: str,
    source: str,
    seed_count: Optional[int],
    flock: dict,
    uof: dict,
    receipts: list[dict],
    receipts_dir: Path,
) -> str:
    styles = STYLES_PATH.read_text(encoding="utf-8")
    by_status: dict[str, int] = {}
    for record in records:
        by_status[record.status] = by_status.get(record.status, 0) + 1
    status_bits = ", ".join(
        f"{count} {status_label(status)}" for status, count in sorted(by_status.items())
    ) or "none"
    flock_data = flock["data"]
    uof_total = uof["summary"].get("total_incidents", len(uof["records"]))
    stats = "".join([
        _stat(len(records), "Ordinances"),
        _stat(flock_data.get("compliance_pct", "—"), "Flock compliance %"),
        _stat(uof_total, "Use-of-force rows"),
        _stat(len(receipts), "Receipt files"),
    ])
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>JU CivicWatch — local dashboard</title>\n"
        "<style>\n"
        f"{styles}"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        '<a class="skip" href="#ordinances">Skip to ordinances</a>\n'
        '<div class="wrap">\n'
        '<header class="site">\n'
        '<p class="kicker">JU CivicWatch · Georgia · on this machine</p>\n'
        "<h1>Public accountability dashboard</h1>\n"
        "<p class=\"lede\">Built from files on this machine. Opening this page makes no network "
        "request and calls no paid API. Cost $0.</p>\n"
        "<ul class=\"toc\">\n"
        '<li><a href="#ordinances">Ordinances</a></li>\n'
        '<li><a href="#flock">Flock / ALPR</a></li>\n'
        '<li><a href="#uof">Use of force</a></li>\n'
        '<li><a href="#receipts">Receipts</a></li>\n'
        "</ul>\n"
        "</header>\n"
        f'<section class="stats" aria-label="Counts">{stats}</section>\n'
        f"<p class=\"note\">Ordinance status counts: {esc(status_bits)}.</p>\n"
        f"{_render_ordinances(records, origin, source, seed_count)}\n"
        f"{_render_flock(flock)}\n"
        f"{_render_uof(uof)}\n"
        f"{_render_receipts(receipts, receipts_dir)}\n"
        '<footer class="colophon">\n'
        "<p>Outreach drafts stay with a person. This page does not send email or file a records request.</p>\n"
        "<p>JU CivicWatch · local dashboard · $0</p>\n"
        "</footer>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )


def build_dashboard(
    *,
    root: Optional[Path] = None,
    out: Optional[Path] = None,
    catalog_path: Optional[Path] = None,
    seed_path: Optional[Path] = None,
    receipts_dir: Optional[Path] = None,
    receipt_dir: Optional[Path] = None,
    flock_path: Optional[Path] = None,
    uof_path: Optional[Path] = None,
    write_receipt_file: bool = True,
) -> dict:
    """Write a self-contained index.html and, by default, a zero-cost receipt."""
    del root  # repo root is fixed; argument kept so callers can pass it explicitly
    catalog_path = catalog_path or DEFAULT_CATALOG
    seed_path = seed_path or SEED_PATH
    receipts_dir = receipts_dir or DEFAULT_RECEIPTS
    out = out or DEFAULT_OUT

    records, origin, source = load_ordinances(catalog_path, seed_path)
    seed_count = len(load_json(seed_path)) if seed_path.exists() else None
    flock = load_flock(flock_path)
    uof = load_uof(uof_path)
    receipt_rows = load_receipts(receipts_dir)
    page = render_page(
        records=records,
        origin=origin,
        source=source,
        seed_count=seed_count,
        flock=flock,
        uof=uof,
        receipts=receipt_rows,
        receipts_dir=receipts_dir,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")

    result = {
        "out": str(out),
        "ordinance_count": len(records),
        "ordinance_origin": origin,
        "ordinance_source": source,
        "flock_origin": flock["origin"],
        "uof_origin": uof["origin"],
        "receipt_count": len(receipt_rows),
        "cost_usd": 0.0,
    }
    if write_receipt_file:
        receipt = make_receipt(
            operation="DASHBOARD-BUILD",
            source="local",
            input_data={
                "ordinance_origin": origin,
                "ordinance_source": source,
                "ordinance_count": len(records),
                "flock_origin": flock["origin"],
                "uof_origin": uof["origin"],
                "receipt_count": len(receipt_rows),
            },
            output_data={"out_name": out.name, "bytes": len(page.encode("utf-8"))},
            record_count=len(records),
            notes="Static dashboard HTML built from local files. No network fetch. cost_usd 0.",
        )
        written = write_receipt(receipt, directory=receipt_dir)
        result["receipt_path"] = str(written)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the local CivicWatch dashboard")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--seed", type=Path, default=None)
    parser.add_argument("--receipts-dir", type=Path, default=None)
    parser.add_argument("--receipt-dir", type=Path, default=None)
    parser.add_argument("--flock", type=Path, default=None)
    parser.add_argument("--uof", type=Path, default=None)
    parser.add_argument("--no-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = build_dashboard(
        out=args.out,
        catalog_path=args.catalog,
        seed_path=args.seed,
        receipts_dir=args.receipts_dir,
        receipt_dir=args.receipt_dir,
        flock_path=args.flock,
        uof_path=args.uof,
        write_receipt_file=not args.no_receipt,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
