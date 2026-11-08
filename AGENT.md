# GeoCareers employer agent

Finds GIS jobs in Germany's 10 largest cities, researches every employer it hasn't seen before,
and keeps the workbook `gis_employers.xlsx` up to date (one sheet per city, your column layout).

**Where the data lives:** in Cloudflare Workers KV (namespace `geocareers-data`), not in this repo.
The `data-schield` Worker (`worker/`) serves only the map data, and only to geocareers.app.

## How it runs

**Every morning ~06:17 — GitHub Actions (free)**
1. Finds GIS jobs:
   - Bundesagentur für Arbeit API: GIS, Geoinformatik, Geodaten, ArcGIS, QGIS, Kartographie — 25 km around each city.
   - LinkedIn via SocialCrawl, only when you start the workflow by hand and tick the box (1 page per city = 100 credits).
   - Only titles that look like GIS jobs are kept.
2. Matches employers to the rows already in the workbook. New employers are added with `agent_check = pending`.
3. Geocodes addresses with Nominatim, Photon as fallback (your `geocode_pbsa` logic).
4. Writes the outputs (below) and commits them.

**Every morning ~08:31 — scheduled Claude task (your Claude subscription)**
Researches the employers in `research/pending.json` with web search and fills
`c_name, c_url, adress, postal_code, sector, g_role, g_stack, size, kp_url, kununu_url, kununu_rate, li_url, eng, de, sprach`,
following `RESEARCH.md`. It pushes the results to `research/inbox/`; the GitHub job adds them to the workbook
in Cloudflare and deletes the file. A company is only researched once.

## Outputs (stored in Cloudflare)

- `gis_employers.xlsx` — your 17 columns, plus grey helper columns:
  `lat, lon, open_jobs, job_titles, job_links, first_seen, last_seen, source, agent_check, agent_notes`
- `companies.json` — what the website loads through data-schield
- `companies.geojson` — GeoJSON
- `companies.gpkg` — for ArcGIS Pro / QGIS (EPSG:25832)

**Your edits are safe:** only empty cells are filled and rows are added; nothing you typed is overwritten or deleted.
Rows with `agent_check = done (low)` are worth a quick manual look.

## Setup

- Secret `CLOUDFLARE_API_TOKEN` (Cloudflare token from the "Edit Cloudflare Workers" template) — reads/writes the data
  and deploys data-schield. Without it the job falls back to keeping the data in `data/` in the repo.

- For LinkedIn runs: Settings → Secrets and variables → Actions → secret `SOCIALCRAWL_API_KEY`.
- Start a run by hand: Actions → **Update GIS employers** → Run workflow (tick LinkedIn if you want it).

## Costs

| Item | Cost |
|---|---|
| Arbeitsagentur API, Nominatim, Photon, GitHub Actions | free |
| SocialCrawl | 10 credits per page; a LinkedIn run = 100 credits |
| Employer research | counts toward your Claude subscription's usage |

## Run locally

```bash
pip install -r requirements.txt
export CLOUDFLARE_API_TOKEN=... CF_ACCOUNT_ID=c0692e0b23a25270623944360c717438
python -m scraper.store pull                       # download the data from Cloudflare into data/
python -m scraper.build --no-agent                 # jobs + workbook + geocoding
python -m scraper.build --no-agent --linkedin      # also LinkedIn (needs SOCIALCRAWL_API_KEY)
python -m scraper.research list                    # employers waiting for research
```

## Settings

`scraper/config.py`: cities, search terms, radius, and the allowed values for size / g_role / sector / sprach
(from your Reference Lists sheet).
