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

# Local dashboard (writes dashboard/index.html; no server required)
python dashboard/build.py
```

Acceptance tests (offline):

```bash
python -m pytest tests/ -v
```

**Live dashboard (GitHub Pages):** https://lonniebeal-droid.github.io/ju-civicwatch/ → redirects to `dashboard/index.html`

## Architecture

```
ju-civicwatch/
├── core/receipts.py        SHA-256 receipt system
├── flock/audit.py          ALPR search flag engine
├── uof/normalizer.py       Use-of-force schema normalizer
├── openrecords/automator.py  ORA request drafting + deadline tracking
├── ordinances/tracker.py   Local surveillance ordinance tracker
├── ordinances/data/seed.json Public metadata seed (no live fetch)
├── dashboard/build.py      Local HTML generator (no network)
├── dashboard/index.html    Static page built from the seed snapshot
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
- [x] Dashboard UI (local static page)
- [x] Flock compliance counts unique flagged records (Card A, PR #3)
- [x] ORA requester identity from env vars / CLI flags (Card C, PR #4)
- [x] GitHub Pages deploy docs (Card D, PR #5)
- [x] Hygiene: requirements-dev.txt, top-level imports, module logging (Card E, PR #6)
- [x] CI workflow (Card B)
- [x] **GitHub Pages LIVE** — https://lonniebeal-droid.github.io/ju-civicwatch/ and `/dashboard/index.html` HTTP 200 (verified 2026-11-22 Grok probe)
- [ ] Outreach to Bottoms transition team (owner)
- [ ] Andre-to-Keisha draft finalized (owner)

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

## Local dashboard

`dashboard/build.py` writes a self-contained `dashboard/index.html` from files already on disk. It does not fetch source pages, call a paid API, or deploy.

## Deploy (GitHub Pages, $0)

**LIVE:** https://lonniebeal-droid.github.io/ju-civicwatch/

Root serves a redirect to `dashboard/index.html`. Rebuild snapshot after ingest if you want the published page to follow local catalog/receipts.

```bash
python -m dashboard.build --out dashboard/index.html --no-receipt
git add dashboard/index.html
git commit -m "docs: rebuild dashboard snapshot"
```

## License

MIT — build it, use it, improve it. This belongs to Atlanta.
