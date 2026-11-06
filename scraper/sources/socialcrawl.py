"""LinkedIn job search via SocialCrawl (paid credits, 10 credits per page).

Docs: https://www.socialcrawl.dev/platforms/jobs/linkedin-search
The API key is read from the SOCIALCRAWL_API_KEY environment variable — never hard-code it.
"""
import requests

from .. import config

URL = "https://www.socialcrawl.dev/v1/jobs/linkedin/search"


class OutOfCredits(Exception):
    pass


def fetch(city, budget):
    """Return (jobs, credits_used) for one city, never spending more than `budget`."""
    if not config.SOCIALCRAWL_API_KEY:
        return [], 0
    headers = {"x-api-key": config.SOCIALCRAWL_API_KEY, "User-Agent": config.USER_AGENT}
    jobs, spent, cursor = [], 0, None

    for _ in range(config.SOCIALCRAWL_PAGES_PER_CITY):
        if budget - spent < 10:
            break
        params = {
            "query": config.SOCIALCRAWL_QUERY,
            "location": f"{city}, Germany",
            "date_posted": config.SOCIALCRAWL_DATE_POSTED,
            "max_pages": 1,          # one page per request; we paginate ourselves
            "max_credits": 10,       # hard cap per request (sending this alone would default max_pages to 50)
        }
        if cursor:
            params["cursor"] = cursor
        r = requests.get(URL, params=params, headers=headers, timeout=60)
        if r.status_code in (402, 429):
            raise OutOfCredits(r.text[:200])
        r.raise_for_status()
        body = r.json()
        spent += int(body.get("credits_used") or 0)

        for item in (body.get("data") or {}).get("items") or []:
            j = item.get("job") or item
            company = j.get("company") or {}
            loc = (j.get("location") or "").lower()
            # use the city named in the listing; fall back to the searched city
            real_city = next((c for c in config.CITIES if c.lower() in loc
                              or (c == "München" and "munich" in loc)
                              or (c == "Köln" and "cologne" in loc)
                              or (c == "Frankfurt am Main" and "frankfurt" in loc)), city)
            jobs.append({
                "id": f"linkedin:{j.get('id')}",
                "source": "linkedin",
                "title": j.get("title") or "",
                "company": company.get("name") or (j.get("ext") or {}).get("linkedin_company_name") or "",
                "company_url": company.get("url"),
                "city": real_city,
                "location_text": j.get("location") or city,
                "address": "",
                "lat": None,
                "lon": None,
                "posted": j.get("listed_at"),
                "url": j.get("url") or j.get("apply_url"),
                "remote": j.get("remote"),
                "experience_level": j.get("experience_level"),
                "description": (j.get("description") or "")[:3000],
            })

        pag = body.get("pagination") or {}
        cursor = pag.get("next_cursor")
        if not pag.get("has_more") or not cursor:
            break

    return jobs, spent
