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

## Local dashboard

`dashboard/build.py` writes a self-contained `dashboard/index.html` from files already on disk. It does not fetch source pages, call a paid API, or deploy.

- Ordinances come from `ordinances/data/catalog.json` when that file exists, otherwise from `ordinances/data/seed.json`.
- Flock and use-of-force sections use `flock/data/summary.json` or `uof/data/summary.json` when those files exist. Otherwise they show the offline synthetic demos and label them as demos.
- Receipt JSON already in `receipts/` is listed. That directory is gitignored, so a fresh clone shows an empty receipts section until you run a module and rebuild.
- Open-records drafts are not rendered. Outreach drafts stay with a person.

The checked-in `dashboard/index.html` is the seed snapshot (no catalog, no receipt files). Rebuild after ingest if you want the page to follow `catalog.json`.

```bash
python dashboard/build.py
# then open dashboard/index.html in a browser
```

`python dashboard/build.py` also writes a `DASHBOARD-BUILD` receipt with `cost_usd` 0. Pass `--no-receipt` to skip that file.

## Deploy (GitHub Pages, $0)

The dashboard is a static page — no server, no build step, no paid service. The $0 deploy path is GitHub Pages. This lane documents the taps only; it does not enable Pages (that is an account-level setting).

**Owner taps (github.com, signed in as the repo owner):**

1. Open the repo → **Settings** → **Pages** (left sidebar, under Code and automation).
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Set **Branch** to `main` and **Folder** to `/` (root). The checked-in `dashboard/index.html` is served at the site root. (Choosing `/dashboard` also works, but then the site root shows a directory listing instead of the dashboard.)
4. Save. GitHub shows the published site URL on the same Pages settings page once the first deploy finishes (a few minutes).

**Before publishing, rebuild the page from the latest main:**

```bash
python -m dashboard.build --out dashboard/index.html --no-receipt
git add dashboard/index.html
git commit -m "docs: rebuild dashboard snapshot"
```

The page lists whatever is in `receipts/` at build time (empty on a fresh clone = the seed snapshot). Rebuild after ingest if you want the page to follow `catalog.json` or show local receipts.

**What is NOT verified yet:** no live Pages URL has been checked by any lane — the first publish needs the owner taps above, then a live fetch of the published URL. Netlify is the upgrade path only if forms or auth are added later; do not build a Netlify deploy first.

## License

MIT — build it, use it, improve it. This belongs to Atlanta.
