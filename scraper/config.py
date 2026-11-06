"""Settings for the GeoCareers job agent."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WORKBOOK = DATA_DIR / "gis_employers.xlsx"      # input AND output (rows are added/filled, never deleted)
JOBS_FILE = DATA_DIR / "jobs.json"
GEOJSON_FILE = DATA_DIR / "companies.geojson"
GPKG_FILE = DATA_DIR / "companies.gpkg"
AGENT_CACHE = DATA_DIR / "agent_cache.json"

# Top 10 German cities: name used in searches -> (sheet name, centre lat, lon)
CITIES = {
    "Berlin": ("berlin", 52.5200, 13.4050),
    "Hamburg": ("hamburg", 53.5511, 9.9937),
    "München": ("munich", 48.1351, 11.5820),
    "Köln": ("cologne", 50.9375, 6.9603),
    "Frankfurt am Main": ("frankfurt", 50.1109, 8.6821),
    "Stuttgart": ("stuttgart", 48.7758, 9.1829),
    "Düsseldorf": ("dusseldorf", 51.2277, 6.7735),
    "Leipzig": ("leipzig", 51.3397, 12.3731),
    "Dortmund": ("dortmund", 51.5136, 7.4653),
    "Essen": ("essen", 51.4556, 7.0116),
}
CITY_ALIASES = {"munich": "München", "cologne": "Köln", "frankfurt": "Frankfurt am Main",
                "dusseldorf": "Düsseldorf", "duesseldorf": "Düsseldorf"}
CITY_RADIUS_KM = 25

# Columns of the employer table, in order (same as Natasha's workbook)
COLUMNS = ["id", "c_name", "c_url", "adress", "postal_code", "city", "sector", "g_role", "g_stack",
           "size", "kp_url", "kununu_url", "kununu_rate", "li_url", "eng", "de", "sprach"]
# Extra columns the agent maintains to the right
EXTRA_COLUMNS = ["lat", "lon", "open_jobs", "job_titles", "job_links", "first_seen", "last_seen", "source", "agent_check", "agent_notes"]

# Allowed values (from the "Reference Lists" sheet)
SIZES = ["1-10", "11-50", "51-200", "201-500", "500+"]
G_ROLES = ["Core product", "Dedicated team", "Side tool"]
SECTORS = ["Urban Planning", "Logistics", "Mobility", "Real Estate", "Environment", "Defense / Security",
           "Public Sector", "Tech / Consulting", "Architecture", "Surveying", "Agriculture", "Infrastructure",
           "Energy", "Engineering", "Earth Observation", "Insurance", "Tech / GIS", "Other"]
LANGS = ["DE", "ENG", "DE/ENG"]

# --- Bundesagentur für Arbeit (free) ---------------------------------------
BA_SEARCH_TERMS = ["GIS", "Geoinformatik", "Geodaten", "ArcGIS", "QGIS", "Kartographie"]
BA_DAYS_BACK = 30
BA_PAGE_SIZE = 100

# --- SocialCrawl (LinkedIn jobs; 10 credits per page) ----------------------
SOCIALCRAWL_API_KEY = os.environ.get("SOCIALCRAWL_API_KEY", "")
SOCIALCRAWL_QUERY = "GIS"
SOCIALCRAWL_DATE_POSTED = "month"         # month | week | day
SOCIALCRAWL_PAGES_PER_CITY = 1
SOCIALCRAWL_MAX_CREDITS = int(os.environ.get("SOCIALCRAWL_MAX_CREDITS", "100"))

# --- Research agent (Claude API with web search) ---------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5-5")
AGENT_MAX_COMPANIES = int(os.environ.get("AGENT_MAX_COMPANIES", "40"))   # per run, cost guard
AGENT_MAX_SEARCHES = 8                   # web searches per company ($10 per 1,000)
AGENT_MAX_FETCHES = 6                    # page fetches per company (token cost only)

EXPIRY_DAYS = {"ba": 3, "linkedin": 14}

RELEVANCE_KEYWORDS = [
    "gis", "geoinform", "geodat", "geospatial", "geo-", "geodät", "arcgis", "qgis",
    "kartograph", "cartograph", "fernerkundung", "remote sensing", "spatial",
    "vermess", "geomatik", "geomatics", "mapping", "geodata", "geoinformation", "postgis",
]

USER_AGENT = "GeoCareers-job-map/1.0 (+https://natashlazarpro.github.io/gis-jobs-berlin)"
