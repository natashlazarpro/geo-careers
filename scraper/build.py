"""GeoCareers agent: find GIS jobs, research the employers, update the Excel workbook and map data.

Usage:
    python -m scraper.build                 # Arbeitsagentur jobs (free) + research of new companies
    python -m scraper.build --linkedin      # also LinkedIn jobs via SocialCrawl (uses credits)
    python -m scraper.build --no-agent      # skip the Claude research step
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta

import pandas as pd

from . import agent, config, excel, geocode
from .sources import ba_api, socialcrawl

LEGAL_FORMS = re.compile(
    r"\b(gmbh\s*&\s*co\.?\s*kg|gmbh|mbh|ag|se|kg|ohg|ug|e\.?\s*v\.?|ltd\.?|inc\.?|llc|"
    r"partg(mbb)?|kgaa|co\.?|deutschland|germany)\b", re.I)


def company_key(name):
    s = LEGAL_FORMS.sub(" ", str(name).lower())
    s = re.sub(r"[^\wäöüß]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def same_company(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 5 and (long_.startswith(short + " ") or long_.endswith(" " + short))


def is_gis_job(title):
    t = title.lower()
    return any(k in t for k in config.RELEVANCE_KEYWORDS)


# --- 1. jobs ------------------------------------------------------------------

def collect(use_linkedin):
    found = []
    for city in config.CITIES:
        try:
            jobs = ba_api.fetch(city)
            print(f"[BA] {city}: {len(jobs)} postings")
            found += jobs
        except Exception as e:
            print(f"[BA] {city}: ERROR {e}", file=sys.stderr)

    if use_linkedin:
        if not config.SOCIALCRAWL_API_KEY:
            print("[LinkedIn] SOCIALCRAWL_API_KEY not set - skipping", file=sys.stderr)
        else:
            budget = config.SOCIALCRAWL_MAX_CREDITS
            for city in config.CITIES:
                if budget < 10:
                    print("[LinkedIn] credit budget used up - stopping")
                    break
                try:
                    jobs, spent = socialcrawl.fetch(city, budget)
                    budget -= spent
                    print(f"[LinkedIn] {city}: {len(jobs)} postings, {spent} credits")
                    found += jobs
                except socialcrawl.OutOfCredits as e:
                    print(f"[LinkedIn] out of credits: {e}", file=sys.stderr)
                    break
                except Exception as e:
                    print(f"[LinkedIn] {city}: ERROR {e}", file=sys.stderr)
    return found


def merge_jobs(store, found, today):
    seen_now = set()
    for job in found:
        if not job.get("company") or not is_gis_job(job["title"]) or job["id"] in seen_now:
            continue
        seen_now.add(job["id"])
        old = store.get(job["id"])
        job["first_seen"] = old["first_seen"] if old else today
        job["last_seen"] = today
        store[job["id"]] = job
    for jid in list(store):
        ttl = config.EXPIRY_DAYS.get(store[jid]["source"], 7)
        if date.fromisoformat(store[jid]["last_seen"]) < date.fromisoformat(today) - timedelta(days=ttl):
            del store[jid]
    return store


# --- 2. companies ---------------------------------------------------------------

def blank(v):
    return v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip())


def update_companies(frames, store, use_agent):
    """Attach jobs to employer rows, add new employers, run the research agent on new ones."""
    by_sheet = {}
    for j in store.values():
        sheet = config.CITIES[j["city"]][0]
        by_sheet.setdefault(sheet, {}).setdefault(company_key(j["company"]), []).append(j)

    cache = agent.load_cache()
    client = None
    if use_agent and config.ANTHROPIC_API_KEY:
        client = agent._client()
    elif use_agent:
        print("[Agent] ANTHROPIC_API_KEY not set - new companies are added without research", file=sys.stderr)
    researched = 0
    pending = []  # (sheet, row index, jobs) of rows the agent should research

    for city, (sheet, _, _) in config.CITIES.items():
        df = frames[sheet]
        keys = [company_key(n) for n in df["c_name"]]
        df["open_jobs"] = 0
        for ckey, jobs in by_sheet.get(sheet, {}).items():
            match = next((i for i, k in enumerate(keys) if same_company(k, ckey)), None)
            researched_as = (cache.get(f"{ckey}|{city}") or {}).get("c_name")
            if match is None and researched_as:   # job-board name -> official name found by research
                match = next((i for i, k in enumerate(keys) if same_company(k, company_key(researched_as))), None)
            if match is None:
                ba = next((j for j in jobs if j["source"] == "ba" and j.get("street")), {})
                row = {c: None for c in df.columns}
                max_id = pd.to_numeric(df["id"], errors="coerce").max()
                row.update(id=(0 if pd.isna(max_id) else int(max_id)) + 1,
                           c_name=jobs[0]["company"], city=city,
                           adress=ba.get("street"),
                           postal_code=ba.get("plz"), lat=ba.get("lat"), lon=ba.get("lon"),
                           first_seen=min(j["first_seen"] for j in jobs), agent_check="pending")
                df.loc[len(df)] = row
                keys.append(ckey)
                match = len(df) - 1
            jobs.sort(key=lambda j: j["first_seen"], reverse=True)
            df.at[match, "open_jobs"] = len(jobs)
            df.at[match, "job_titles"] = " | ".join(j["title"] for j in jobs[:10])
            df.at[match, "job_links"] = " | ".join(j["url"] for j in jobs[:10] if j.get("url"))
            df.at[match, "last_seen"] = max(j["last_seen"] for j in jobs)
            df.at[match, "source"] = ", ".join(sorted({j["source"] for j in jobs}))
            if blank(df.at[match, "first_seen"]):
                df.at[match, "first_seen"] = min(j["first_seen"] for j in jobs)
            if df.at[match, "agent_check"] == "pending":
                pending.append((sheet, match, jobs))
        frames[sheet] = df

    # research the companies with the most open jobs first
    pending.sort(key=lambda p: -len(p[2]))
    for sheet, idx, jobs in pending:
        df = frames[sheet]
        name, city = df.at[idx, "c_name"], df.at[idx, "city"]
        ckey = f"{company_key(name)}|{city}"
        result = cache.get(ckey)
        if result is None and client is not None and researched < config.AGENT_MAX_COMPANIES:
            try:
                print(f"[Agent] researching {name} ({city})")
                result = agent.research(name, city, jobs, client)
                researched += 1
                if result:
                    cache[ckey] = result
                    agent.save_cache(cache)
            except Exception as e:
                print(f"[Agent] {name}: ERROR {e}", file=sys.stderr)
        if result:
            apply_research(df, idx, result)
    # research saved by the scheduled Claude task (data/agent_cache.json) for any other pending row
    for sheet, df in frames.items():
        for idx in df.index[df["agent_check"] == "pending"]:
            result = cache.get(f"{company_key(df.at[idx, 'c_name'])}|{df.at[idx, 'city']}")
            if result:
                apply_research(df, idx, result)
    agent.save_cache(cache)
    print(f"[Agent] researched {researched} new companies this run")
    for sheet in frames:
        frames[sheet] = merge_duplicates(frames[sheet])
    return frames


def domain(url):
    if blank(url):
        return None
    d = re.sub(r"^(https?://)?(www\.)?", "", str(url).strip().lower()).split("/")[0]
    return d or None


def merge_duplicates(df):
    """A newly added row with the same website or the same official name as another row is merged into it
    (your original rows win; between two new rows the older one is kept)."""
    doms = df["c_url"].map(domain)
    names = df["c_name"].map(company_key)
    is_new = df["agent_check"].astype(str).str.startswith(("done", "pending"))
    drop = []
    for i in df.index:
        if not is_new[i]:
            continue
        same = [k for k in df.index if k != i and k not in drop
                and ((doms[i] and doms[k] == doms[i]) or (names[i] and names[k] == names[i]))
                and (not is_new[k] or k < i)]
        twin = min(same, key=lambda k: (is_new[k], k)) if same else None
        if twin is None:
            continue
        df.at[twin, "open_jobs"] = int(df.at[twin, "open_jobs"] or 0) + int(df.at[i, "open_jobs"] or 0)
        for col in ("job_titles", "job_links", "source"):
            parts = [str(df.at[k, col]) for k in (twin, i) if not blank(df.at[k, col])]
            df.at[twin, col] = " | ".join(parts) if parts else None
        df.at[twin, "last_seen"] = df.at[i, "last_seen"]
        if blank(df.at[twin, "first_seen"]):
            df.at[twin, "first_seen"] = df.at[i, "first_seen"]
        drop.append(i)
    return df.drop(index=drop).reset_index(drop=True)


def apply_research(df, idx, r):
    """Copy agent results into empty cells only (never overwrite manual edits)."""
    for col in config.COLUMNS:
        if col in ("id", "city"):
            continue
        val = r.get(col)
        if col == "c_name" and val:
            df.at[idx, col] = val          # agent's official name replaces the job-board spelling
            continue
        if not blank(val) and blank(df.at[idx, col]):
            df.at[idx, col] = val
    if r.get("adress"):                    # agent address beats job-ad address; re-geocode
        df.at[idx, "adress"], df.at[idx, "lat"], df.at[idx, "lon"] = r["adress"], None, None
        if r.get("postal_code"):
            df.at[idx, "postal_code"] = r["postal_code"]
    df.at[idx, "agent_check"] = f"done ({r.get('confidence', '?')})"
    df.at[idx, "agent_notes"] = r.get("notes")


# --- 3. outputs -----------------------------------------------------------------

def write_map_files(frames):
    allrows = pd.concat([df.assign(sheet=s) for s, df in frames.items()], ignore_index=True)
    gdf = geocode.to_geodataframe(allrows)
    features = []
    for _, r in gdf.iterrows():
        props = {c: excel._clean(r[c]) for c in config.COLUMNS + ["open_jobs", "job_titles", "job_links", "last_seen"]}
        props = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in props.items()}
        features.append({"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": [round(float(r["lon"]), 6), round(float(r["lat"]), 6)]},
                         "properties": props})
    config.GEOJSON_FILE.write_text(json.dumps({"type": "FeatureCollection", "updated": date.today().isoformat(),
                                               "features": features}, ensure_ascii=False, default=str), encoding="utf-8")
    # flat list for the website: your 17 columns + coordinates
    site = [{**{c: f["properties"][c] for c in config.COLUMNS},
             "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]} for f in features]
    config.MAP_JSON_FILE.write_text(json.dumps(site, ensure_ascii=False, default=str), encoding="utf-8")
    try:
        out = gdf.copy()
        for c in out.columns:
            if c != "geometry":
                out[c] = out[c].map(lambda v: None if excel._clean(v) is None else str(v))
        out.to_file(config.GPKG_FILE, layer="gis_employers", driver="GPKG")
    except Exception as e:
        print(f"GeoPackage not written: {e}", file=sys.stderr)
    return len(features)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--linkedin", action="store_true", help="also query LinkedIn via SocialCrawl")
    ap.add_argument("--no-agent", action="store_true", help="skip the Claude API research step")
    ap.add_argument("--skip-fetch", action="store_true", help="reuse data/jobs.json instead of fetching jobs")
    ap.add_argument("--no-geocode", action="store_true", help="leave new addresses for the next run to geocode")
    args = ap.parse_args()

    config.DATA_DIR.mkdir(exist_ok=True)
    today = date.today().isoformat()

    store = {}
    if config.JOBS_FILE.exists():
        store = {j["id"]: j for j in json.loads(config.JOBS_FILE.read_text(encoding="utf-8"))}
    if not args.skip_fetch:
        store = merge_jobs(store, collect(args.linkedin), today)
        config.JOBS_FILE.write_text(json.dumps(list(store.values()), ensure_ascii=False, indent=1), encoding="utf-8")

    frames = excel.read_city_sheets()
    frames = update_companies(frames, store, use_agent=not args.no_agent)
    if not args.no_geocode:
        for sheet in frames:
            frames[sheet] = geocode.geocode_companies(frames[sheet])
    excel.write_city_sheets(frames)
    n_points = write_map_files(frames)

    total = sum(len(df) for df in frames.values())
    print(f"Done: {len(store)} open GIS jobs, {total} employers in the workbook, {n_points} on the map")


if __name__ == "__main__":
    main()
