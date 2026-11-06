"""Geocoding based on Natasha's geocode_pbsa(): Nominatim first, Photon as fallback.

Adapted for the employer table: the address comes from the columns adress + postal_code + city
(the employer table has street and house number in one column).
"""
import time

import geopandas as gpd
import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim, Photon

from . import config

# EPSG:25832 (ETRS89 / UTM 32N) covers all 10 cities; 25833 is only right for eastern Germany
TARGET_CRS = "EPSG:25832"


def geocode_companies(df):
    """Fill lat/lon for rows that have an address but no coordinates yet. Returns df."""
    nom = RateLimiter(Nominatim(user_agent=config.USER_AGENT, timeout=10).geocode, min_delay_seconds=1)
    photon = RateLimiter(Photon(user_agent=config.USER_AGENT, timeout=10).geocode, min_delay_seconds=0.5)

    def s(col):
        return df[col].fillna("").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    df["query"] = s("adress") + ", " + s("postal_code") + " " + s("city") + ", Germany"
    df["query_alt"] = df["query"].str.replace("ß", "ss")

    def geocode(address, geocoder, retries=2):
        for _ in range(retries):
            try:
                loc = geocoder(address)
                return (loc.latitude, loc.longitude) if loc else (None, None)
            except Exception:
                time.sleep(1)
        return (None, None)

    todo = df["lat"].isna() & (s("adress") != "")
    for idx in df[todo].index:
        lat, lon = geocode(df.at[idx, "query"], nom)
        if lat is None:  # fallback: Photon with alternative spelling
            lat, lon = geocode(df.at[idx, "query_alt"], photon)
        df.at[idx, "lat"], df.at[idx, "lon"] = lat, lon

    return df.drop(columns=["query", "query_alt"])


def to_geodataframe(df):
    """GeoDataFrame in EPSG:25832 for ArcGIS Pro / QGIS (rows without coordinates are skipped)."""
    pts = df.dropna(subset=["lat", "lon"]).copy()
    return gpd.GeoDataFrame(
        pts, geometry=gpd.points_from_xy(pts["lon"].astype(float), pts["lat"].astype(float)), crs="EPSG:4326"
    ).to_crs(TARGET_CRS)
