"""Company research agent: Claude with web search + web fetch fills the employer fields.

For every new company the agent searches the web, opens the company website, careers page,
LinkedIn and kununu result pages, and returns one structured record via the save_company tool.
"""
import json

from . import config

SAVE_TOOL = {
    "name": "save_company",
    "description": "Save the researched company profile. Call exactly once, when research is done. "
                   "Use null for anything you could not verify.",
    "input_schema": {
        "type": "object",
        "properties": {
            "c_name": {"type": "string", "description": "Official company name incl. legal form, e.g. 'VISTA GmbH'"},
            "c_url": {"type": ["string", "null"], "description": "Company homepage"},
            "adress": {"type": ["string", "null"], "description": "Street + house number of the office in the given city, e.g. 'Invalidenstraße 116-119'"},
            "postal_code": {"type": ["string", "null"], "description": "5-digit PLZ of that office"},
            "city": {"type": "string"},
            "sector": {"type": ["string", "null"], "description": "1-3 sectors joined with ' / ', preferably from: " + ", ".join(config.SECTORS)},
            "g_role": {"type": ["string", "null"], "enum": config.G_ROLES + [None],
                       "description": "Core product = GIS/geodata IS the product; Dedicated team = a GIS team/department supports the business; Side tool = GIS is used occasionally"},
            "g_stack": {"type": ["string", "null"], "description": "Comma-separated GIS/data tools named in job ads or tech pages, e.g. 'ArcGIS Pro, QGIS, PostGIS, Python, FME'"},
            "size": {"type": ["string", "null"], "enum": config.SIZES + [None], "description": "Employees (company-wide)"},
            "kp_url": {"type": ["string", "null"], "description": "Careers page on the company's OWN website (or its own job portal, e.g. careers.x.de / x.jobs.personio.de). Never LinkedIn/StepStone/Indeed."},
            "kununu_url": {"type": ["string", "null"], "description": "kununu.com company profile URL"},
            "kununu_rate": {"type": ["number", "null"], "description": "kununu score 1.0-5.0 as shown in search results; null if not seen"},
            "li_url": {"type": ["string", "null"], "description": "LinkedIn company page, https://www.linkedin.com/company/..."},
            "eng": {"type": "string", "description": "2-3 sentence factual company description in English: what they do, for whom, how geodata/GIS fits in"},
            "de": {"type": "string", "description": "The same description in German"},
            "sprach": {"type": ["string", "null"], "enum": config.LANGS + [None],
                       "description": "Working language required in their GIS job ads: DE, ENG, or DE/ENG"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"], "description": "How sure you are this is the right company and office"},
            "notes": {"type": ["string", "null"], "description": "Anything uncertain, e.g. 'several offices, chose the Berlin one'"},
        },
        "required": ["c_name", "city", "eng", "de", "confidence"],
    },
}

SYSTEM = """You research employers of GIS / geodata professionals in Germany for a public job map.
Be factual and verify from sources; never guess URLs. Work efficiently:
1. Search the company name + city to find the homepage, the office address in that city (Impressum or contact page) and size.
2. Find the careers page on their own site.
3. Search "<company> kununu" and "<company> linkedin" to get those profile URLs (take the kununu score from the search result if shown).
4. Use the job ads provided (and the careers page) to judge the GIS role, the tool stack and the working language.
Then call save_company once."""


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _prompt(company, city, jobs):
    lines = [f"Company: {company}", f"City: {city}", "", "GIS job ads found for this company:"]
    for j in jobs[:5]:
        lines.append(f"- {j['title']} ({j['source']}) {j.get('url') or ''}")
        if j.get("description"):
            lines.append("  " + j["description"][:1200].replace("\n", " "))
    return "\n".join(lines)


def research(company, city, jobs, client=None):
    """Return a dict with the employer fields, or None if the agent failed."""
    client = client or _client()
    messages = [{"role": "user", "content": _prompt(company, city, jobs)}]
    tools = [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": config.AGENT_MAX_SEARCHES,
         "user_location": {"type": "approximate", "country": "DE", "timezone": "Europe/Berlin"}},
        {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": config.AGENT_MAX_FETCHES,
         "max_content_tokens": 8000},
        SAVE_TOOL,
    ]
    force = None
    for _ in range(6):  # pause_turn continuations
        kwargs = {"tool_choice": {"type": "tool", "name": "save_company"}} if force else {}
        resp = client.messages.create(model=config.AGENT_MODEL, max_tokens=4000, system=SYSTEM,
                                      messages=messages, tools=tools, **kwargs)
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "save_company":
                return dict(block.input)
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        # finished without saving: ask once more explicitly
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": "Please call save_company now with what you found."})
        force = True
    return None


def load_cache():
    if config.AGENT_CACHE.exists():
        return json.loads(config.AGENT_CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache):
    config.AGENT_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
