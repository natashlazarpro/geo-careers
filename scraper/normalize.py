"""Keep the employer table consistent: one spelling per tool in g_stack, and fixed formats for
sprach, size, kununu_rate and the URL columns. Applied every time the workbook is written.
"""
import re
from datetime import datetime

import pandas as pd

from . import config

# Canonical tool names, in the order they are listed in g_stack (GIS first, then CAD, surveying,
# databases, languages, web, cloud/data). Unknown tools are kept and placed at the end.
ORDER = [
    # GIS
    "ArcGIS", "ArcGIS Pro", "ArcGIS Enterprise", "ArcGIS Online", "ArcGIS Utility Network", "ArcMap", "ArcPy",
    "QGIS", "QField", "PostGIS", "FME", "FME Flow", "FME Form", "GDAL", "GeoServer", "MapServer", "Mapbender",
    "MapStore", "OpenLayers", "Leaflet", "Mapbox", "OpenStreetMap", "VertiGIS Studio", "Smallworld GIS", "Magik",
    "XPlanung", "GeoDIN", "G!nius", "ProVI", "NIS", "CableScout", "ConnectMaster", "Megaplan", "LaRA", "TKI", "PNI",
    "Geosi Plan", "WebGIS", "GIS",
    # CAD / BIM
    "AutoCAD", "Civil 3D", "BricsCAD", "MicroStation", "Revit", "Vectorworks", "InfoCAD", "SOFiSTiK", "CARD/1",
    "GEOgraf", "CAD",
    # surveying / remote sensing
    "Trimble Business Center", "Trimble Access", "Trimble TerraFlex", "Trimble Connect", "Trimble RealWorks",
    "Trimble", "Leica Cyclone", "Leica", "NavVis", "Agisoft Metashape", "GNSS", "Total station", "Laser scanning",
    "LiDAR", "Mobile mapping", "Photogrammetry", "Drones/UAV", "Remote sensing", "SAR", "AIS",
    "DFK", "DOP", "DGM", "LoD2",
    # databases
    "PostgreSQL", "Oracle", "Microsoft SQL Server", "SAP HANA", "MySQL", "MariaDB", "MongoDB", "DuckDB", "SQL",
    # languages
    "Python", "R", "Java", "Kotlin", "C#", "C++", "Rust", "Fortran", "MATLAB", "JavaScript", "TypeScript", "PHP",
    "Bash", "PowerShell",
    # web
    "Node.js", "React", "Angular", "NgRx", "RxJS", "PrimeNG", "SvelteKit", "Symfony", "Spring", "FastAPI",
    "GraphQL", "REST API", "SOAP", "HTML", "CSS", "XML", "JSON",
    # cloud / devops / data
    "AWS", "Azure", "Azure DevOps", "Google Cloud", "Docker", "Kubernetes", "Terraform", "Jenkins", "Git", "GitHub",
    "GitLab", "CI/CD", "Linux", "WSL", "Airflow", "Dagster", "Prefect", "Databricks", "ETL", "MLflow", "Ray",
    "PyTorch", "PyTorch Lightning", "AI/ML", "Grafana", "Datadog", "Sentry", "Metabase", "Tableau", "Power BI",
    "Amazon QuickSight",
    # office / other
    "Excel", "MS Office", "Adobe Creative Suite", "SAP",
]
_CANON = {n.lower(): n for n in ORDER}

ALIASES = {
    "arcgis (hydro portal, enc systems)": "ArcGIS", "esri arcgis": "ArcGIS", "esri": "ArcGIS",
    "esri arcgis utility network": "ArcGIS Utility Network",
    "smallworld": "Smallworld GIS", "ge smallworld": "Smallworld GIS",
    "osm": "OpenStreetMap", "geoserver": "GeoServer",
    "gis applications": "GIS", "gis systems (cad/gis)": "GIS",
    "autocad": "AutoCAD", "autodesk civil 3d": "Civil 3D", "vectorworks": "Vectorworks", "sofistik": "SOFiSTiK",
    "tbc plugins": "Trimble Business Center", "trimble surveying solutions (gnss, total stations, software)": ["Trimble", "GNSS", "Total station"],
    "leica geosystems": "Leica", "leica total station": "Total station", "total stations": "Total station",
    "sokkia gnss/total station": "Total station", "surveying (tachymetric, gnss)": ["Total station", "GNSS"],
    "gnss rover": "GNSS", "gps": "GNSS",
    "3d laser scanning": "Laser scanning", "3d scanning": "Laser scanning", "lidar mobile mapping": "LiDAR",
    "mobile mapping": "Mobile mapping", "aerial photogrammetry": "Photogrammetry", "photogrammetry": "Photogrammetry",
    "agisoft photoscan": "Agisoft Metashape", "drones": "Drones/UAV", "drone/uav": "Drones/UAV",
    "satellite data": "Remote sensing", "satellite remote sensing": "Remote sensing",
    "ais technology": "AIS", "ldbv data (dfk, dop, dgm, lod2)": ["DFK", "DOP", "DGM", "LoD2"], "lod2": "LoD2",
    "postgre sql": "PostgreSQL", "postgres": "PostgreSQL", "ms sql server": "Microsoft SQL Server",
    "mssql": "Microsoft SQL Server", "matlab": "MATLAB",
    "nodejs": "Node.js", "react.js": "React", "html5": "HTML", "api": "REST API", "apis": "REST API", "rest": "REST API",
    "aws cloud": "AWS", "azure blob storage": "Azure", "gcp": "Google Cloud", "gitlab": "GitLab",
    "elt": "ETL", "quicksight": "Amazon QuickSight", "exel": "Excel", "sap r/3": "SAP",
    "vision language models": "AI/ML", "blockchain (solana)": "Solana",
    "leica and trimble surveying equipment": ["Leica", "Trimble"],
}
# not tools: website trackers, companies, methods, or descriptions of the business
DROP = {"jquery migrate", "google fonts api", "parse.ly", "onetrust", "allterra", "systra", "scrum", "signals",
        "assembly", "metal forming", "additive manufacturing simulation",
        "fea/cae simulation software", "urban data platforms", "digital city planning", "smart city technology",
        "infrastructure mapping", "real-time mapping apis", "power corridor optimization",
        "gis-based power network analysis", "proprietary iot sensor networks", "supply chain mapping",
        "site-selection analytics", "geodatabases"}
DROP_WORDS = re.compile(r"confirmed|planning|optimi[sz]ation|scheduling|route |analytics", re.I)


def g_stack(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    tools = []
    for part in re.split(r"[,;\n](?![^(]*\))", str(value)):     # commas inside (...) don't split
        t = re.sub(r"\s+", " ", part).strip()
        if not t:
            continue
        key = t.lower()
        if key in DROP or DROP_WORDS.search(t) or key.startswith("route"):
            continue
        names = ALIASES.get(key) or _CANON.get(key) or t
        for n in names if isinstance(names, list) else [names]:
            if n not in tools:
                tools.append(n)
    pos = {n: i for i, n in enumerate(ORDER)}
    tools.sort(key=lambda n: pos.get(n, len(ORDER)))
    return ", ".join(tools) or None


def sprach(value):
    v = str(value or "").strip().upper().replace(" ", "")
    if not v or v == "NAN":
        return None
    has_de, has_en = "DE" in v, "EN" in v
    return "DE/ENG" if has_de and has_en else "DE" if has_de else "ENG" if has_en else None


def size(value):
    if isinstance(value, (datetime, pd.Timestamp)):          # Excel turned "1-10" into a date
        return "1-10" if {value.day, value.month} == {1, 10} else None
    v = str(value or "").strip().replace("–", "-")
    if v in config.SIZES:
        return v
    if v.isdigit():
        n = int(v)
        return "1-10" if n <= 10 else "11-50" if n <= 50 else "51-200" if n <= 200 else "201-500" if n < 500 else "500+"
    if v.endswith("+") and v[:-1].isdigit() and int(v[:-1]) >= 500:
        return "500+"
    return None


def kununu_rate(value):
    try:
        x = round(float(str(value).replace(",", ".")), 1)
    except (TypeError, ValueError):
        return None
    return x if 1 <= x <= 5 else None


def url(value, col):
    v = str(value or "").strip()
    if not v or v.lower() == "nan" or " " in v or "." not in v:
        return None
    if not v.startswith("http"):
        v = "https://" + v
    if col == "li_url":
        if "linkedin.com/company/" not in v:
            return None
        v = "https://www.linkedin.com/company/" + v.split("linkedin.com/company/")[1].strip("/") + "/"
    return v


def clean_frame(df):
    df = df.copy()
    df["g_stack"] = df["g_stack"].map(g_stack)
    df["sprach"] = df["sprach"].map(sprach)
    df["size"] = df["size"].map(size)
    df["kununu_rate"] = df["kununu_rate"].map(kununu_rate)
    for col in ("c_url", "kp_url", "kununu_url", "li_url"):
        df[col] = df[col].map(lambda v, c=col: url(v, c))
    for col in ("sector", "adress", "c_name"):
        df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
    df["postal_code"] = df["postal_code"].map(
        lambda v: None if v is None or (isinstance(v, float) and pd.isna(v))
        else str(int(v)).zfill(5) if isinstance(v, (int, float)) else str(v).strip())
    return df.astype(object).where(df.notna(), None)
