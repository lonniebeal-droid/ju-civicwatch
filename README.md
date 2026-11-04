# JU CivicWatch

**Free civic accountability platform for Georgia.** Statewide police data transparency, Flock/surveillance audit tooling, use-of-force aggregation, and public records automation.

Built for the Bottoms transition team and Dickens' office — but owned by the people.

## What It Does

- **Flock Audit Engine** (`flock/audit.py`) — flags after-hours searches, rapid-fire bursts, empty case numbers, repeat plates. Model: APD's Sept 2026 audit (115,578 searches, 79 flagged, 99.93% compliant).
- **Use-of-Force Aggregator** (`uof/normalizer.py`) — normalizes UOF reports from APD, DeKalb, and any department into one canonical schema. Hashes officer IDs, never stores raw ones.
- **Open Records Automator** (`openrecords/automator.py`) — drafts Georgia ORA requests (O.C.G.A. § 50-18-70), tracks 3-business-day deadlines, flags overdue.
- **Receipt System** (`core/receipts.py`) — every data pull gets a SHA-256 verified receipt. Receipts or it didn't happen.

## Quick Start

```bash
# Flock audit demo (synthetic APD-like data)
python flock/audit.py

# UOF normalizer demo (synthetic multi-department data)
python uof/normalizer.py

# Open Records automator demo
python openrecords/automator.py

# Receipt smoke test
python core/receipts.py
```

## Architecture

```
ju-civicwatch/
├── core/receipts.py        SHA-256 receipt system
├── flock/audit.py          ALPR search flag engine
├── uof/normalizer.py       Use-of-force schema normalizer
├── openrecords/automator.py  ORA request drafting + deadline tracking
├── ordinances/             (planned) Local surveillance ordinance tracker
├── dashboard/              (planned) Public transparency UI
└── tests/                  (planned) Acceptance tests
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
- [ ] Ordinances tracker
- [ ] Dashboard UI
- [ ] Outreach to Bottoms transition team
- [ ] Andre-to-Keisha draft finalized

## License

MIT — build it, use it, improve it. This belongs to Atlanta.
