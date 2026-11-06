# Receipt — local dashboard (2026-11-06)

Local only. No network fetch, no paid API, no deploy. `cost_usd` 0.

The page is a static HTML file. Opening it does not call out. Source URLs in the ordinance cards are ordinary links.

## Commands

From the repo root, Python 3.12:

```bash
python -m pytest tests/ -q
python dashboard/build.py
# open dashboard/index.html in a browser
```

`python dashboard/build.py` reads `ordinances/data/catalog.json` when that file exists, otherwise `ordinances/data/seed.json`. It writes `dashboard/index.html` and a `DASHBOARD-BUILD` receipt under `receipts/` (gitignored). `--no-receipt` skips the receipt file.

Flock and use-of-force blocks use `flock/data/summary.json` and `uof/data/summary.json` when those files are already on disk. This repo does not ship those exports, so the build falls back to the offline synthetic demos and labels them as demos. Open-records drafts are not rendered.

## Results

`python -m pytest tests/ -q` — **22 passed** in 0.10s (8 acceptance, 7 ordinance, 7 dashboard). Dashboard tests cover the seed page, catalog override, HTML escaping, local Flock/UOF JSON overriding the demos, receipt listing, the empty-receipt state, the CLI smoke script, and a byte match between `dashboard/index.html` and a fresh seed build. No test opens a network socket.

Seed build (`python dashboard/build.py` with no catalog and no receipt files):

- ordinance_count 3, origin `seed`, source `ordinances/data/seed.json`
- flock origin `demo` (DEMO-APD, 222 searches, 31 flag rows, compliance 86.036)
- use-of-force origin `demo` (5 incidents; APD 3, DEKALB 2)
- receipt_count 0
- cost_usd 0.0
- page bytes 13928
- citations on the page: `26-O-1401` (held in committee), `2024-0244` (adopted), `O.C.G.A. § 35-1-22` (enacted)
- receipt example: `receipts/dashboard-build-20261106T144908197577Z.json`
  - operation `DASHBOARD-BUILD`, status `VERIFIED`, record_count 3, cost_usd 0.0
  - input_hash `e113398bf360ffc54a4f4e99a14ecc6c590a208aad6183f7b3da917a1f33b384`
  - output_hash `f9307637594148a28ff48ec5e4c7c9232cf9d439b0699b6cd4eebe12d20b1806`

Checked in a browser (local `http.server`, Chrome). In-page links for Ordinances, Flock / ALPR, Use of force, and Receipts update the location hash. Atlanta notes open. The page has no `<script>` and does not include the open-records requester email. At 1280px and at 390px the document does not scroll sideways; use-of-force rows stack into labeled cards on the narrow viewport.

## Still human

Outreach to the Bottoms transition team, and the Andre-to-Keisha draft, are not generated here. This page does not send email or file a records request.
