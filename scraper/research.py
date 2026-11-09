"""Helpers for the scheduled Claude research task (see RESEARCH.md).

    python -m scraper.research list [N]          # print up to N companies still waiting for research (JSON)
    python -m scraper.research check results.json  # only validate a results file (used by the research task)
    python -m scraper.research add results.json    # validate researched records and store them in data/agent_cache.json
    python -m scraper.research ingest             # add every file in research/inbox/, then delete them (GitHub job)
    python -m scraper.research new                # add new employers from $NEW_EMPLOYERS (JSON list, GitHub job input)
"""
import json
import sys

from . import agent, config, excel
from .build import apply_research, blank, company_key, domain, same_company


def pending(limit=25):
    cache = agent.load_cache()
    rows = []
    for sheet, df in excel.read_city_sheets().items():
        for _, r in df[df["agent_check"] == "pending"].iterrows():
            key = f"{company_key(r['c_name'])}|{r['city']}"
            if key in cache:
                continue
            rows.append({
                "key": key, "c_name": r["c_name"], "city": r["city"],
                "address_from_job_ad": None if blank(r["adress"]) else f"{r['adress']}, {r['postal_code'] or ''}".strip(", "),
                "open_jobs": int(r["open_jobs"] or 0),
                "job_titles": None if blank(r["job_titles"]) else r["job_titles"],
                "job_links": None if blank(r["job_links"]) else r["job_links"],
            })
    rows.sort(key=lambda x: -x["open_jobs"])
    return rows[:limit]


def validate(rec):
    """Return a list of problems with one research record (empty list = OK)."""
    problems = []
    for f in ("key", "c_name", "city", "eng", "de", "confidence"):
        if blank(rec.get(f)):
            problems.append(f"missing {f}")
    allowed = {"size": config.SIZES, "g_role": config.G_ROLES, "sprach": config.LANGS,
               "confidence": ["high", "medium", "low"]}
    for f, values in allowed.items():
        if not blank(rec.get(f)) and rec[f] not in values:
            problems.append(f"{f}={rec[f]!r} not in {values}")
    for f in ("c_url", "kp_url", "kununu_url", "li_url"):
        v = rec.get(f)
        if not blank(v) and not str(v).startswith("http"):
            problems.append(f"{f} must be a full URL")
    if not blank(rec.get("kp_url")) and "linkedin." in str(rec["kp_url"]):
        problems.append("kp_url must be the company's own careers page, not LinkedIn")
    if not blank(rec.get("kununu_rate")):
        try:
            if not 1 <= float(str(rec["kununu_rate"]).replace(",", ".")) <= 5:
                problems.append("kununu_rate must be 1-5")
        except ValueError:
            problems.append("kununu_rate must be a number")
    if not blank(rec.get("postal_code")) and not str(rec["postal_code"]).isdigit():
        problems.append("postal_code must be digits only")
    return problems


INBOX = config.ROOT / "research" / "inbox"


def check(path):
    records = json.loads(open(path, encoding="utf-8").read())
    records = [records] if isinstance(records, dict) else records
    bad = 0
    for rec in records:
        problems = validate(rec)
        if problems:
            bad += 1
            print(f"PROBLEM {rec.get('c_name')}: {'; '.join(problems)}")
    print(f"{len(records) - bad} records OK, {bad} with problems")
    return bad == 0


def ingest():
    """Move research results handed off through the repo into the cache, then delete the files."""
    files = sorted(INBOX.glob("*.json")) if INBOX.exists() else []
    for f in files:
        print(f"[research] ingesting {f.name}")
        add(f)
        f.unlink()
    return len(files)


def add_new_employers(records):
    """Add employers found by research (not from a job ad) as new rows; existing ones only get empty cells filled."""
    from datetime import date
    import pandas as pd
    frames = excel.read_city_sheets()
    sheet_of = {city: sheet for city, (sheet, _, _) in config.CITIES.items()}
    added = filled = skipped = 0
    for rec in records:
        rec.setdefault("key", f"{company_key(rec.get('c_name'))}|{rec.get('city')}")
        to_research = bool(rec.pop("pending", False))      # only name + city known: the research task fills the rest
        problems = [] if to_research and rec.get("c_name") else validate(rec)
        sheet = sheet_of.get(rec.get("city"))
        if problems or sheet is None:
            skipped += 1
            print(f"SKIPPED {rec.get('c_name')}: {'; '.join(problems) or 'unknown city'}")
            continue
        df = frames[sheet]
        key, dom = company_key(rec["c_name"]), domain(rec.get("c_url"))
        match = next((i for i in df.index if same_company(company_key(df.at[i, "c_name"]), key)
                      or (dom and domain(df.at[i, "c_url"]) == dom)), None)
        if match is None:
            max_id = pd.to_numeric(df["id"], errors="coerce").max()
            row = {c: None for c in df.columns}
            row.update(id=(0 if pd.isna(max_id) else int(max_id)) + 1, c_name=rec["c_name"], city=rec["city"],
                       open_jobs=0, first_seen=date.today().isoformat(), source="research")
            df.loc[len(df)] = row
            match = len(df) - 1
            added += 1
        else:
            filled += 1
            if to_research:
                continue                                    # already in the workbook
        if to_research:
            df.at[match, "agent_check"] = "pending"
            df.at[match, "agent_notes"] = rec.get("notes")
            frames[sheet] = df
            continue
        if rec.get("adress") and not blank(df.at[match, "adress"]) and df.at[match, "source"] != "research":
            rec = {k: v for k, v in rec.items() if k not in ("adress", "postal_code")}   # keep known address
        apply_research(df, match, rec)
        frames[sheet] = df
    excel.write_city_sheets(frames)
    print(f"[research] {added} new employers added, {filled} existing ones filled, {skipped} skipped")
    return skipped == 0


def add(path):
    records = json.loads(open(path, encoding="utf-8").read())
    if isinstance(records, dict):
        records = [records]
    cache = agent.load_cache()
    ok, bad = 0, 0
    for rec in records:
        problems = validate(rec)
        if problems:
            bad += 1
            print(f"SKIPPED {rec.get('c_name')}: {'; '.join(problems)}")
            continue
        if not blank(rec.get("kununu_rate")):
            rec["kununu_rate"] = float(str(rec["kununu_rate"]).replace(",", "."))
        cache[rec.pop("key")] = rec
        ok += 1
    agent.save_cache(cache)
    print(f"stored {ok} records, skipped {bad}")
    return bad == 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        print(json.dumps(pending(int(sys.argv[2]) if len(sys.argv) > 2 else 25), ensure_ascii=False, indent=1))
    elif cmd == "check":
        sys.exit(0 if check(sys.argv[2]) else 1)
    elif cmd == "add":
        sys.exit(0 if add(sys.argv[2]) else 1)
    elif cmd == "new":
        import os
        spec = os.environ.get("NEW_EMPLOYERS", "").strip()
        sys.exit(0 if not spec or add_new_employers(json.loads(spec)) else 1)
    elif cmd == "ingest":
        print(f"{ingest()} file(s) ingested")
    else:
        sys.exit(__doc__)
