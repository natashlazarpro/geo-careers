# GeoCareers employer agent

Finds GIS jobs in Germany's 10 largest cities, researches every employer it hasn't seen before,
and keeps `data/gis_employers.xlsx` up to date (one sheet per city, your column layout).

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
Researches up to 25 pending employers with web search and fills
`c_name, c_url, adress, postal_code, sector, g_role, g_stack, size, kp_url, kununu_url, kununu_rate, li_url, eng, de, sprach`,
following `RESEARCH.md`. Results are stored in `data/agent_cache.json`, so a company is only researched once.

## Outputs

- `data/gis_employers.xlsx` — your 17 columns, plus grey helper columns:
  `lat, lon, open_jobs, job_titles, job_links, first_seen, last_seen, source, agent_check, agent_notes`
- `data/companies.geojson` — for the web map
- `data/companies.gpkg` — for ArcGIS Pro / QGIS (EPSG:25832)

**Your edits are safe:** only empty cells are filled and rows are added; nothing you typed is overwritten or deleted.
Rows with `agent_check = done (low)` are worth a quick manual look.

## Setup

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
python -m scraper.build --no-agent                 # jobs + workbook + geocoding
python -m scraper.build --no-agent --linkedin      # also LinkedIn (needs SOCIALCRAWL_API_KEY)
python -m scraper.research list                    # employers waiting for research
```

## Settings

`scraper/config.py`: cities, search terms, radius, and the allowed values for size / g_role / sector / sprach
(from your Reference Lists sheet).
