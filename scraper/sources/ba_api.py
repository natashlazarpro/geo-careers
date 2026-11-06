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
    """Handle the v6 format (ergebnisliste/firma/stellenlokationen) and the older v4 format."""
    if "referenznummer" in item or "firma" in item:                       # v6
        loc = (item.get("stellenlokationen") or [{}])[0]
        adr = loc.get("adresse") or {}
        street = " ".join(p for p in [adr.get("strasse"), adr.get("hausnummer")] if p) or None
        refnr, title, company = item.get("referenznummer"), item.get("stellenangebotsTitel"), item.get("firma")
        lat, lon, plz, ort = loc.get("breite"), loc.get("laenge"), adr.get("plz"), adr.get("ort")
        posted = item.get("datumErsteVeroeffentlichung")
    else:                                                                  # v4
        ort_ = item.get("arbeitsort") or {}
        coords = ort_.get("koordinaten") or {}
        street, plz, ort = ort_.get("strasse"), ort_.get("plz"), ort_.get("ort")
        refnr, title, company = item.get("refnr"), item.get("titel") or item.get("beruf"), item.get("arbeitgeber")
        lat, lon = coords.get("lat"), coords.get("lon")
        posted = item.get("aktuelleVeroeffentlichungsdatum") or item.get("eintrittsdatum")
    address = ", ".join(p for p in [street, f"{plz or ''} {ort or ''}".strip()] if p)
    return {
        "id": f"ba:{refnr}",
        "source": "ba",
        "title": title or "",
        "company": company or "",
        "city": city,
        "location_text": ort or city,
        "address": address,
        "street": street,
        "plz": plz,
        "lat": lat,
        "lon": lon,
        "posted": posted,
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
            items = data.get("ergebnisliste") or data.get("stellenangebote") or []
            for it in items:
                job = _normalise(it, city)
                jobs[job["id"]] = job
            if len(items) < config.BA_PAGE_SIZE or page >= 5:
                break
            page += 1
            time.sleep(0.5)
        time.sleep(0.5)
    return list(jobs.values())
