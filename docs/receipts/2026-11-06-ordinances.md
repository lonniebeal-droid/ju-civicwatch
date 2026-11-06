# Receipt — surveillance ordinance tracker (2026-11-06)

Local only. No network fetch, no paid API, no deploy. `cost_usd` 0.

## Commands

From the repo root, Python 3.12:

```bash
python -m pytest tests/ -v
python ordinances/tracker.py
python ordinances/tracker.py list --status adopted
python ordinances/tracker.py list --jurisdiction Atlanta
python ordinances/tracker.py ingest ordinances/data/seed.json
```

`python ordinances/tracker.py` ingests `ordinances/data/seed.json` into gitignored `ordinances/data/catalog.json` and writes a SHA-256 receipt under `receipts/`.

## Results

`python -m pytest tests/ -v` — **15 passed** in 0.03s (8 existing acceptance tests, 7 ordinance tests). Ordinance tests cover parse of the public seed, rejection of a missing `source_url` / bad date / non-http URL, CSV parse, store round-trip, filtered list, idempotent ingest, and an isolated demo. No test opens a network socket.

Demo (`python ordinances/tracker.py`):

- incoming 3, stored 3, `cost_usd` 0.0
- by status: `held_in_committee` 1, `adopted` 1, `enacted` 1
- by jurisdiction: Atlanta, GA 1; DeKalb County, GA 1; Georgia 1
- citations: `26-O-1401`, `2024-0244`, `O.C.G.A. § 35-1-22`
- receipt example: `receipts/ordinance-ingest-20261106T143839734346Z.json`
  - operation `ORDINANCE-INGEST`, status `VERIFIED`, record_count 3, cost_usd 0.0
  - input_hash `33c88b93350add31022655e80a758c90f7c03081a73d576bd79421a9db470f9a`
  - output_hash `6e0673795841cbef0f484c9b461d5b6ae86b9e796e9dcc15075b8f66bcb6ad77`

`python ordinances/tracker.py list --jurisdiction Atlanta` returned count 1: `26-O-1401`, status `held_in_committee`.

`python ordinances/tracker.py list --status adopted` returned count 1, citation `2024-0244`, topic `video_surveillance`, source URL `https://library.municode.com/ga/dekalb_county/ordinances/code_of_ordinances?nodeId=2024`, `last_checked` `2026-11-06`. The stored summary states it was adopted February 14, 2024 and amends Chapter 15 for convenience-store cameras.

A second `ingest` of the same seed kept `stored_count` at 3 (upsert, no duplicate rows) and wrote another `VERIFIED` receipt.

## Seed sources (checked 2026-11-06, not fetched at runtime)

| Citation | Jurisdiction | Status | Public page |
| --- | --- | --- | --- |
| O.C.G.A. § 35-1-22 | Georgia | enacted | https://law.justia.com/codes/georgia/title-35/chapter-1/section-35-1-22/ |
| 26-O-1401 | Atlanta, GA | held_in_committee | https://civicduty.app/local-body/atlanta-city-council/meetings/8a7980ff-20e4-45bf-9ce9-a47ab0909ea4/verdicts/8bf97f9a-de6d-40aa-a707-5b62ad1cc96e |
| 2024-0244 | DeKalb County, GA | adopted | https://library.municode.com/ga/dekalb_county/ordinances/code_of_ordinances?nodeId=2024 |

Atlanta 26-O-1401 is proposed oversight legislation. Sources checked on this date do not show adoption. DeKalb 2024-0244 regulates convenience-store cameras, not law-enforcement license plate readers. APD LPR policy (APD.SOP.5193) is a department procedure and is not in this catalog.
