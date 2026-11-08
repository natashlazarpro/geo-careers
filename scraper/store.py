"""Keep the data files in Cloudflare Workers KV instead of the GitHub repo.

    python -m scraper.store pull     # download the data files from KV into data/
    python -m scraper.store push     # upload data/ to KV (the map data is what the data-schield Worker serves)
    python -m scraper.store ns-id    # print the KV namespace id (created on first use)

Needs the environment variables CLOUDFLARE_API_TOKEN and CF_ACCOUNT_ID.
Without them every command does nothing, so the pipeline keeps using the files in data/.
"""
import os
import sys

import requests

from . import config

NAMESPACE_TITLE = "geocareers-data"
API = "https://api.cloudflare.com/client/v4/accounts/{account}/storage/kv/namespaces"

# KV key -> local file. "companies.json" is the only key the data-schield Worker serves publicly.
FILES = {
    "gis_employers.xlsx": config.WORKBOOK,
    "agent_cache.json": config.AGENT_CACHE,
    "enrich_cache.json": config.DATA_DIR / "enrich_cache.json",
    "jobs.json": config.JOBS_FILE,
    "companies.geojson": config.GEOJSON_FILE,
    "companies.gpkg": config.GPKG_FILE,
    "companies.json": config.MAP_JSON_FILE,
}

_ns_id = None


def enabled():
    return bool(os.environ.get("CLOUDFLARE_API_TOKEN") and os.environ.get("CF_ACCOUNT_ID"))


def _session():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"
    return s


def _base():
    return API.format(account=os.environ["CF_ACCOUNT_ID"])


def namespace_id():
    """Find the KV namespace by its title, create it if it doesn't exist yet."""
    global _ns_id
    if _ns_id:
        return _ns_id
    s = _session()
    page = 1
    while True:
        r = s.get(_base(), params={"per_page": 100, "page": page}, timeout=30)
        r.raise_for_status()
        result = r.json()["result"]
        for ns in result:
            if ns["title"] == NAMESPACE_TITLE:
                _ns_id = ns["id"]
                return _ns_id
        if len(result) < 100:
            break
        page += 1
    r = s.post(_base(), json={"title": NAMESPACE_TITLE}, timeout=30)
    r.raise_for_status()
    _ns_id = r.json()["result"]["id"]
    print(f"[store] created KV namespace {NAMESPACE_TITLE}")
    return _ns_id


def _url(key):
    return f"{_base()}/{namespace_id()}/values/{key}"


def pull():
    if not enabled():
        print("[store] Cloudflare not configured - using the files in data/")
        return
    config.DATA_DIR.mkdir(exist_ok=True)
    s = _session()
    for key, path in FILES.items():
        r = s.get(_url(key), timeout=60)
        if r.status_code == 404:
            print(f"[store] {key}: not in Cloudflare yet" + (" - keeping local file" if path.exists() else ""))
            continue
        r.raise_for_status()
        path.write_bytes(r.content)
        print(f"[store] {key}: {len(r.content) // 1024} KB downloaded")


def push():
    if not enabled():
        print("[store] Cloudflare not configured - nothing uploaded")
        return
    s = _session()
    for key, path in FILES.items():
        if not path.exists():
            continue
        r = s.put(_url(key), data=path.read_bytes(), timeout=120)
        r.raise_for_status()
        print(f"[store] {key}: {path.stat().st_size // 1024} KB uploaded")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pull":
        pull()
    elif cmd == "push":
        push()
    elif cmd == "ns-id":
        print(namespace_id())
    else:
        sys.exit(__doc__)
