# Employer research — instructions for the scheduled Claude task

The data (workbook, caches, map data) lives in Cloudflare, not in this repo. Every morning the GitHub
job finds GIS jobs, adds new employers to the workbook and writes the ones still waiting for research
to `research/pending.json`. This task researches them and hands the results back through
`research/inbox/`; the GitHub job then adds them to the workbook in Cloudflare and deletes the file.

## Steps

1. `pip install -r requirements.txt`
2. Read `research/pending.json`. Each entry has a `task`:
   - `"research"`: an employer nobody has researched yet. Fill **all** fields below.
   - `"fill"`: an already researched employer with empty columns, listed in `missing`. Research only
     those columns (e.g. `g_stack`, `li_url`, `kp_url`, `adress`) and return just them plus `task`, `key`,
     `c_name`, `city`, `notes`. Leave a column out if you can't verify it.
   Work through the whole list (up to 50 entries).
3. Then read `research/targets.json`: cities that still have fewer than 30 employers, with how many are
   missing. Use the remaining time to **find new GIS employers** in those cities (biggest gaps first):
   search GIS job ads, Esri/QGIS partner lists, ÖbVI (Vermessung) lists, state and city geodata offices,
   universities, research institutes, utilities, planning and engineering offices. Only real employers
   with an office in or right next to that city that do GIS/geodata work. Research each fully and add it
   with `"task": "new"` (all fields, `key` = `"<name>|<city>"`). Aim for 10–20 new employers per run.
   Before adding one, make sure it isn't already in the city: check `research/employers.json`.
4. Write everything to `research/inbox/YYYY-MM-DD.json` (add `-2`, `-3` … if that file exists),
   then `python -m scraper.research check research/inbox/<file>.json` and fix anything reported.
5. Commit only that file and push to `main`. If the push is rejected: `git pull --rebase origin main`, push again.
   The push starts the GitHub job, which writes the results into the workbook within a few minutes.

**g_stack** matters: look at the employer's GIS job ads (Arbeitsagentur, StepStone, their careers page)
and tech pages and list the tools they name (ArcGIS Pro, QGIS, PostGIS, FME, Python, ALKIS, …).
**li_url**: search "<company> LinkedIn" and use the `linkedin.com/company/...` URL from the results.

## Fields

| field | what to put |
|---|---|
| key | copy from the list |
| c_name | official company name incl. legal form, e.g. `VISTA GmbH` |
| c_url | company homepage (full URL) |
| adress | street + house number of the office **in that city** (Impressum / contact page) |
| postal_code | 5-digit PLZ of that office |
| city | the city from the list |
| sector | 1–2 branches joined with ` / `, main one first, only from: Renewable Energy, Development & Social, Climate, Surveying & Geodesy, Environment & Conservation, GIS, Geoinformatics, Remote Sensing, Hydrology, Geology, Transport Planning, Urban & Spatial Planning, Other |
| g_role | `Core product` (GIS/geodata is the product) · `Dedicated team` (a GIS team supports the business) · `Side tool` (GIS used occasionally) |
| g_stack | comma-separated GIS/data tools named in their job ads or tech pages, e.g. `ArcGIS Pro, QGIS, PostGIS, Python, FME` — use the spellings in `scraper/normalize.py` (ORDER); the build unifies them anyway |
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
