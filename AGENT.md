# GeoCareers employer agent

Finds GIS jobs in Germany's 10 largest cities, researches every employer it hasn't seen before,
and keeps `data/gis_employers.xlsx` up to date (one sheet per city, your column layout).

## What happens on each run

1. **Find jobs**
   - Bundesagentur für Arbeit API (free): GIS, Geoinformatik, Geodaten, ArcGIS, QGIS, Kartographie — 25 km around each city.
   - LinkedIn via SocialCrawl (only when you tick the box): 1 page per city = 100 credits.
   - Only titles that look like GIS jobs are kept.
2. **Match employers** to the rows already in the workbook (by name, and after research by website domain).
3. **Research new employers** with Claude + web search. The agent fills
   `c_name, c_url, adress, postal_code, sector, g_role, g_stack, size, kp_url, kununu_url, kununu_rate, li_url, eng, de, sprach`.
   Results are cached, so a company is only researched once.
4. **Geocode** addresses with Nominatim, Photon as fallback (your `geocode_pbsa` logic).
5. **Write outputs**
   - `data/gis_employers.xlsx` — your 17 columns, plus grey helper columns:
     `lat, lon, open_jobs, job_titles, job_links, first_seen, last_seen, source, agent_check, agent_notes`
   - `data/companies.geojson` — for the web map
   - `data/companies.gpkg` — for ArcGIS Pro / QGIS (EPSG:25832)

**Your edits are safe:** the agent only fills empty cells and adds rows; it never deletes a company or overwrites a value you typed.
Rows with `agent_check = done (low)` are worth a quick manual look.

## Setup (once)

1. Repo → Settings → Secrets and variables → Actions → add two secrets:
   - `ANTHROPIC_API_KEY` — from console.anthropic.com (needs a few € of API credit)
   - `SOCIALCRAWL_API_KEY` — your (new) SocialCrawl key
2. Repo → Settings → Actions → General → Workflow permissions → **Read and write permissions**.
3. Actions → **Update GIS employers** → Run workflow → tick **LinkedIn** for the first run.

After that it runs daily on its own (Arbeitsagentur only). Tick LinkedIn manually whenever you have credits.

## Costs

| Item | Cost |
|---|---|
| Arbeitsagentur API, Nominatim, Photon | free |
| SocialCrawl | 10 credits per page; a LinkedIn run = 100 credits |
| Claude research (Sonnet + web search) | roughly €0.15–0.30 per new company; capped by `AGENT_MAX_COMPANIES` (default 40 per run) |

Daily runs only research *new* employers, so after the first runs the cost is small.

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...  SOCIALCRAWL_API_KEY=...
python -m scraper.build --linkedin      # full run
python -m scraper.build --no-agent      # only jobs + geocoding, no research
```

## Settings

`scraper/config.py`: cities, search terms, radius, the allowed values for size / g_role / sector / sprach
(taken from your Reference Lists sheet), agent model and limits.
