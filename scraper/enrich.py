"""Fill empty employer columns from LinkedIn company pages via SocialCrawl (5 credits per company).

    python -m scraper.enrich            # uses SOCIALCRAWL_API_KEY, spends at most SOCIALCRAWL_ENRICH_MAX_CREDITS
    python -m scraper.enrich --dry-run  # show which companies would be looked up, spend nothing

Only blank (or invalid) cells are filled: li_url, c_url, size, and adress/postal_code when the LinkedIn
headquarters is in the row's city. Nothing that is already filled is overwritten.
Lookup: by the row's LinkedIn URL if it has one, otherwise by the domain of its website.
Companies already looked up are remembered in data/enrich_cache.json and not paid for again.
"""
import argparse
import json
import os
from datetime import date
from urllib.parse import urlparse

import requests

from . import config, excel
from .build import blank

BASE = "https://www.socialcrawl.dev/v1/linkedin"
COST = 5
CACHE_FILE = config.DATA_DIR / "enrich_cache.json"
MAX_CREDITS = int(os.environ.get("SOCIALCRAWL_ENRICH_MAX_CREDITS", "100"))
CITY_NAMES = {"München": ["münchen", "munich"], "Köln": ["köln", "cologne"],
              "Frankfurt am Main": ["frankfurt"], "Düsseldorf": ["düsseldorf", "dusseldorf"]}


def bad(row, col):
    v = row[col]
    if blank(v):
        return True
    if col == "size":
        return v not in config.SIZES
    if col == "li_url":
        return "linkedin.com/company/" not in str(v)
    return False


def needs(row):
    return [c for c in ("li_url", "c_url", "size", "adress", "postal_code") if bad(row, c)]


def domain(url):
    if blank(url):
        return None
    host = urlparse(url if "://" in str(url) else "https://" + str(url)).netloc.lower()
    return host[4:] if host.startswith("www.") else host or None


def size_bucket(ext):
    n = ext.get("employee_count")
    if not n:
        start = (ext.get("employee_count_range") or {}).get("start")
        n = start if start and start > 1 else None
    if not n:
        return None
    for limit, bucket in ((10, "1-10"), (50, "11-50"), (200, "51-200"), (500, "201-500")):
        if n <= limit:
            return bucket
    return "500+"


def lookup(row):
    """Return (author dict or None, credits used)."""
    headers = {"x-api-key": config.SOCIALCRAWL_API_KEY, "User-Agent": config.USER_AGENT}
    if not bad(row, "li_url"):
        url, params = f"{BASE}/company", {"url": row["li_url"]}
    else:
        url, params = f"{BASE}/company/by-domain", {"domain": domain(row["c_url"])}
    r = requests.get(url, params=params, headers=headers, timeout=90)
    if r.status_code == 402:
        raise RuntimeError("SocialCrawl: out of credits")
    if r.status_code == 404:
        return None, 0
    r.raise_for_status()
    body = r.json()
    return (body.get("data") or {}).get("author"), int(body.get("credits_used") or 0)


def apply(df, idx, author, city):
    row, filled = df.loc[idx], []
    ext = author.get("ext") or {}
    li = author.get("url")
    if li and "linkedin.com/company/" in li and bad(row, "li_url"):
        df.at[idx, "li_url"] = "https://www.linkedin.com/company/" + li.split("/company/")[1].strip("/") + "/"
        filled.append("li_url")
    if ext.get("website") and bad(row, "c_url"):
        df.at[idx, "c_url"] = ext["website"]
        filled.append("c_url")
    if bad(row, "size") and size_bucket(ext):
        df.at[idx, "size"] = size_bucket(ext)
        filled.append("size")
    # street address only for an office in the row's own city (HQ or one of the listed locations)
    names = CITY_NAMES.get(city, [city.lower()])
    offices = [ext.get("headquarters") or {}] + [(l or {}).get("address") or {} for l in ext.get("locations") or []]
    office = next((o for o in offices if o.get("country") in (None, "DE") and o.get("line1")
                   and "redacted" not in o["line1"] and any(n in str(o.get("city", "")).lower() for n in names)), None)
    if office and bad(row, "adress") and bad(row, "postal_code"):
        df.at[idx, "adress"] = office["line1"]
        filled.append("adress")
        if str(office.get("postal_code") or "").replace(" ", "").isdigit():
            df.at[idx, "postal_code"] = str(office["postal_code"]).replace(" ", "")
            filled.append("postal_code")
    return filled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cities", default=os.environ.get("ENRICH_CITIES", ""),
                    help="comma-separated sheet names to limit the run to, e.g. cologne,frankfurt,stuttgart")
    args = ap.parse_args()

    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    frames = excel.read_city_sheets()
    todo = []
    only = {c.strip().lower() for c in args.cities.split(",") if c.strip()}
    for sheet, df in frames.items():
        if only and sheet not in only:
            continue
        for idx, row in df.iterrows():
            if row["agent_check"] == "pending":          # not researched yet: Claude fills these first
                continue
            key = f"{row['c_name']}|{row['city']}"
            missing = needs(row)
            if not missing or key in cache:
                continue
            if bad(row, "li_url") and not domain(row["c_url"]):
                continue                                 # nothing reliable to look up by
            todo.append((sheet, idx, key, missing))

    print(f"{len(todo)} companies with gaps to look up (~{len(todo) * COST} credits, cap {MAX_CREDITS})")
    if args.dry_run or not config.SOCIALCRAWL_API_KEY:
        for sheet, idx, key, missing in todo:
            print(f"  {key}: {', '.join(missing)}")
        if not config.SOCIALCRAWL_API_KEY and not args.dry_run:
            print("SOCIALCRAWL_API_KEY not set - nothing looked up")
        return

    spent, changed = 0, 0
    for sheet, idx, key, missing in todo:
        if spent + COST > MAX_CREDITS:
            print(f"credit cap reached ({spent}); the rest is looked up next run")
            break
        df = frames[sheet]
        try:
            author, used = lookup(df.loc[idx])
        except requests.RequestException as e:
            print(f"  {key}: error {e}")
            continue
        spent += used
        filled = apply(df, idx, author, df.at[idx, "city"]) if author else []
        cache[key] = {"date": date.today().isoformat(), "found": bool(author), "filled": filled}
        changed += bool(filled)
        print(f"  {key}: {'filled ' + ', '.join(filled) if filled else 'no LinkedIn page' if not author else 'nothing new'}")

    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    if changed:
        excel.write_city_sheets(frames)
    print(f"Done: {changed} companies updated, {spent} credits used")


if __name__ == "__main__":
    main()
