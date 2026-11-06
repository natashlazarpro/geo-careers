"""Bundesagentur für Arbeit Jobsuche API (free, public).

Docs: https://github.com/bundesAPI/jobsuche-api
"""
import time
import requests

from .. import config

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
PATHS = ["/pc/v6/jobs", "/pc/v5/jobs", "/pc/v4/jobs", "/pc/v4/app/jobs"]   # newest first; older ones as fallback
_working_path = None
HEADERS = {"X-API-Key": "jobboerse-jobsuche", "User-Agent": config.USER_AGENT}


def _get(params):
    global _working_path
    last_err = None
    for path in ([_working_path] if _working_path else PATHS):
        try:
            r = requests.get(BASE + path, params=params, headers=HEADERS, timeout=30)
            if r.status_code in (403, 404):
                last_err = f"{path}: HTTP {r.status_code}"
                continue
            r.raise_for_status()
            if _working_path is None:
                print(f"[BA] using {path}")
            _working_path = path
            return r.json()
        except requests.RequestException as e:
            last_err = e
    raise RuntimeError(f"BA API failed: {last_err}")


def _normalise(item, city):
    ort = item.get("arbeitsort") or {}
    coords = ort.get("koordinaten") or {}
    refnr = item.get("refnr")
    address = ", ".join(p for p in [ort.get("strasse"), f"{ort.get('plz', '')} {ort.get('ort', '')}".strip()] if p)
    return {
        "id": f"ba:{refnr}",
        "source": "ba",
        "title": item.get("titel") or item.get("beruf") or "",
        "company": item.get("arbeitgeber") if isinstance(item.get("arbeitgeber"), str)
                   else (item.get("arbeitgeber") or {}).get("name", ""),
        "city": city,
        "location_text": ort.get("ort") or city,
        "address": address,
        "street": ort.get("strasse"),
        "plz": ort.get("plz"),
        "lat": coords.get("lat"),
        "lon": coords.get("lon"),
        "posted": item.get("aktuelleVeroeffentlichungsdatum") or item.get("eintrittsdatum"),
        "url": item.get("externeUrl") or f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}",
    }


def fetch(city):
    """Return normalised GIS jobs for one city."""
    jobs = {}
    for term in config.BA_SEARCH_TERMS:
        page = 1
        while True:
            data = _get({
                "was": term,
                "wo": city,
                "umkreis": config.CITY_RADIUS_KM,
                "angebotsart": 1,                       # 1 = employment (no training/self-employed)
                "veroeffentlichtseit": config.BA_DAYS_BACK,
                "size": config.BA_PAGE_SIZE,
                "page": page,
            })
            items = data.get("stellenangebote") or data.get("jobs") or data.get("ergebnisse") or []
            if not items and data and "maxErgebnisse" not in data:
                print(f"[BA] unexpected response fields: {list(data)[:10]}")
            for it in items:
                job = _normalise(it, city)
                jobs[job["id"]] = job
            total = int(data.get("maxErgebnisse") or 0)
            if not items or page * config.BA_PAGE_SIZE >= total or page >= 5:
                break
            page += 1
            time.sleep(0.5)
        time.sleep(0.5)
    return list(jobs.values())
