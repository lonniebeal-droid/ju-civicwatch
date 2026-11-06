# JU CivicWatch

**Free civic accountability platform for Georgia.** Statewide police data transparency, Flock/surveillance audit tooling, use-of-force aggregation, and public records automation.

Built for the Bottoms transition team and Dickens' office — but owned by the people.

## What It Does

- **Flock Audit Engine** (`flock/audit.py`) — flags after-hours searches, rapid-fire bursts, empty case numbers, repeat plates. Model: APD's Sept 2026 audit (115,578 searches, 79 flagged, 99.93% compliant).
- **Use-of-Force Aggregator** (`uof/normalizer.py`) — normalizes UOF reports from APD, DeKalb, and any department into one canonical schema. Hashes officer IDs, never stores raw ones.
- **Open Records Automator** (`openrecords/automator.py`) — drafts Georgia ORA requests (O.C.G.A. § 50-18-70), tracks 3-business-day deadlines, flags overdue.
- **Surveillance Ordinance Tracker** (`ordinances/tracker.py`) — local catalog of public ordinance and statute metadata (jurisdiction, title, source URL, last checked). Reads a checked-in seed or a local JSON/CSV file. No network fetch.
- **Receipt System** (`core/receipts.py`) — every data pull gets a SHA-256 verified receipt. Receipts or it didn't happen.

## Quick Start

```bash
# Flock audit demo (synthetic APD-like data)
python flock/audit.py

# UOF normalizer demo (synthetic multi-department data)
python uof/normalizer.py

# Open Records automator demo
python openrecords/automator.py

# Surveillance ordinance tracker (local seed; writes ordinances/data/catalog.json)
python ordinances/tracker.py
python ordinances/tracker.py list --status adopted

# Receipt smoke test
python core/receipts.py
```

Acceptance tests (offline):

```bash
python -m pytest tests/ -v
```

## Architecture

```
ju-civicwatch/
├── core/receipts.py        SHA-256 receipt system
├── flock/audit.py          ALPR search flag engine
├── uof/normalizer.py       Use-of-force schema normalizer
├── openrecords/automator.py  ORA request drafting + deadline tracking
├── ordinances/tracker.py   Local surveillance ordinance tracker
├── ordinances/data/seed.json Public metadata seed (no live fetch)
├── dashboard/              (planned) Public transparency UI
└── tests/                  Acceptance tests
```

## Design Principles

1. **Receipts or it didn't happen** — every operation produces a hashed receipt.
2. **$0 to run** — local only, no paid APIs, no cloud spend without approval.
3. **Legal sources only** — Open Records Act, public reports. No credential scraping.
4. **Officials benefit too** — the tool does their audit work for free. That's the leverage.

## Status

- [x] Repo created 2026-11-04
- [x] Power map + execution plan in JU MASTER 3
- [x] Core receipt system
- [x] Flock audit engine + demo
- [x] UOF normalizer + demo
- [x] Open Records automator + demo
- [x] Ordinances tracker (local public-metadata seed)
- [ ] Dashboard UI
- [ ] Outreach to Bottoms transition team
- [ ] Andre-to-Keisha draft finalized

## Surveillance ordinance tracker

`ordinances/tracker.py` keeps a local JSON catalog of public surveillance rules. The checked-in seed covers three public records as of 2026-11-06:

- **Georgia, O.C.G.A. § 35-1-22** — statewide license-plate-data statute (enacted).
- **Atlanta 26-O-1401** — proposed surveillance-technology oversight ordinance (held in committee; not adopted in the sources checked).
- **DeKalb County 2024-0244** — adopted convenience-store video-surveillance ordinance (not an ALPR rule).

Ingest does not download those pages. Drop a local `.json` or `.csv` export on disk and pass it to `ingest`. Each ingest writes a SHA-256 receipt with `cost_usd` 0. `ordinances/data/catalog.json` is generated and gitignored.

```bash
python ordinances/tracker.py ingest ordinances/data/seed.json
python ordinances/tracker.py list --jurisdiction Atlanta
python ordinances/tracker.py list --topic alpr
```

Department policies (for example APD LPR standard operating procedures) are not ordinances and are not in this catalog. Refreshing a row means editing the local file after a manual check of the public source, then ingesting again.

## License

MIT — build it, use it, improve it. This belongs to Atlanta.
