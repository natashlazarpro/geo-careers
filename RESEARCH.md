# Employer research — instructions for the scheduled Claude task

GitHub Actions finds GIS jobs every morning and adds new employers to `data/gis_employers.xlsx`
with `agent_check = pending`. This task researches those employers and fills their columns.

## Steps

1. `pip install -r requirements.txt`
2. `python -m scraper.research list 25` — the companies still waiting (most open jobs first).
   If the list is empty, stop: nothing to do.
3. Research each company with web search / web fetch (rules below) and write all results to
   `research_batch.json` (a JSON list, one object per company, `key` copied from the list).
4. `python -m scraper.research add research_batch.json` — fix and re-add anything it reports as SKIPPED.
5. `python -m scraper.build --skip-fetch --no-geocode` — writes the results into the workbook.
   (Addresses are geocoded by the next GitHub Actions run.)
6. Delete `research_batch.json`, commit `data/` and push to `main`.
   If the push is rejected, `git fetch origin main && git reset --hard origin/main`, then repeat
   steps 4–6 (the batch is deterministic, so re-applying is safe).

## Fields

| field | what to put |
|---|---|
| key | copy from the list |
| c_name | official company name incl. legal form, e.g. `VISTA GmbH` |
| c_url | company homepage (full URL) |
| adress | street + house number of the office **in that city** (Impressum / contact page) |
| postal_code | 5-digit PLZ of that office |
| city | the city from the list |
| sector | 1–3 sectors joined with ` / `, preferably: Urban Planning, Logistics, Mobility, Real Estate, Environment, Defense / Security, Public Sector, Tech / Consulting, Architecture, Surveying, Agriculture, Infrastructure, Energy, Engineering, Earth Observation, Insurance, Tech / GIS, Other |
| g_role | `Core product` (GIS/geodata is the product) · `Dedicated team` (a GIS team supports the business) · `Side tool` (GIS used occasionally) |
| g_stack | comma-separated GIS/data tools named in their job ads or tech pages, e.g. `ArcGIS Pro, QGIS, PostGIS, Python, FME` |
| size | `1-10`, `11-50`, `51-200`, `201-500`, `500+` (company-wide employees) |
| kp_url | careers page on the company's **own** website or own job portal (e.g. `careers.x.de`, `x.jobs.personio.de`) — never LinkedIn, StepStone or Indeed |
| kununu_url | kununu.com company profile |
| kununu_rate | kununu score 1.0–5.0, only if it appears in search results; otherwise null. Don't scrape kununu. |
| li_url | `https://www.linkedin.com/company/...` |
| eng | 2–3 factual sentences in English: what they do, for whom, how GIS/geodata fits in |
| de | the same in German |
| sprach | working language required in their GIS job ads: `DE`, `ENG` or `DE/ENG` |
| confidence | `high` / `medium` / `low` — how sure you are it's the right company and office |
| notes | anything uncertain, e.g. "several offices, chose the Berlin one" |

Use `null` for anything you can't verify. Never guess URLs.
If a "company" is really a recruiting agency or the posting isn't a GIS job, still add a record with
`confidence: "low"` and say so in `notes`, so it isn't researched again.
