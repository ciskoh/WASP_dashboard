"""
TexMesonet / SynopticLabs daily precipitation fetcher.

Queries the SynopticLabs REST API (v2) for stations with hourly precipitation
data within the requested bounding box, then sums to daily totals.

Fallback rule: if no stations are found inside the bounding box, the station
closest to the centroid of the location is selected via a 100-mile radius query.

Credentials: TEXMESONET_API_KEY environment variable (loaded from .env).

Output convention: xr.Dataset with variable 'precip_mm' (time,),
scalar coordinates lat/lon for the selected station, units mm/day.
"""

import os
from datetime import datetime, timedelta
from math import sqrt
from pathlib import Path

import numpy as np
import requests
import xarray as xr
from dotenv import load_dotenv

from src.api_hooks._utils import bbox

_ENV_FILE = Path(__file__).parent / ".env"

_SYNOPTIC_URL = "https://api.synopticdata.com/v2/stations/timeseries"


def _centroid(location: dict) -> tuple[float, float]:
    """Return (lon, lat) centroid of a GeoJSON location."""
    if location["type"] == "Point":
        lon, lat = location["coordinates"]
        return (lon, lat)
    w, s, e, n = bbox(location, buffer=0)
    return ((w + e) / 2, (s + n) / 2)


def _date_range(start_time: str, end_time: str):
    """Yield ISO date strings from start_time to end_time inclusive."""
    current = datetime.strptime(start_time, "%Y-%m-%d")
    end = datetime.strptime(end_time, "%Y-%m-%d")
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def _query_synoptic(token: str, extra_params: dict, start: str, end: str) -> list:
    """Call SynopticLabs timeseries endpoint; return STATION list (may be empty)."""
    params = {
        "token": token,
        "vars": "precip_accum_one_hour",
        "units": "metric",
        "output": "json",
        "start": start,
        "end": end,
        **extra_params,
    }
    resp = requests.get(_SYNOPTIC_URL, params=params, timeout=90)
    resp.raise_for_status()
    return resp.json().get("STATION") or []


def _nearest(stations: list, clon: float, clat: float) -> dict:
    """Return the station with the smallest Euclidean distance to (clon, clat)."""
    return min(
        stations,
        key=lambda s: sqrt(
            (float(s["LONGITUDE"]) - clon) ** 2 + (float(s["LATITUDE"]) - clat) ** 2
        ),
    )


def _daily_precip(station: dict, dates: list[str]) -> dict[str, float]:
    """Sum hourly precip observations into daily totals (mm)."""
    obs = station.get("OBSERVATIONS", {})
    precip_key = next(
        (k for k in obs if k.startswith("precip_accum_one_hour")), None
    )
    daily = {d: 0.0 for d in dates}
    if precip_key is None:
        return daily
    for timestamp, value in zip(obs["date_time"], obs[precip_key]):
        date = timestamp[:10]
        if date in daily and value is not None:
            daily[date] += float(value)
    return daily


def _fetch_texmesonet(start_time: str, end_time: str, location: dict) -> xr.Dataset:
    """
    Fetch TexMesonet daily precipitation for a location and date range.

    Parameters
    ----------
    start_time : str  ISO date, e.g. "2024-01-01"
    end_time   : str  ISO date, e.g. "2024-01-03"
    location   : dict GeoJSON Point or Polygon

    Returns
    -------
    xr.Dataset with variable precip_mm (time,), scalar lat/lon coords, units mm/day
    """
    load_dotenv(_ENV_FILE)
    token = os.environ.get("TEXMESONET_API_KEY", "")
    if not token:
        raise RuntimeError(
            "TEXMESONET_API_KEY is not set. Add your Synoptic/TexMesonet token "
            "to src/api_hooks/.env"
        )
    api_start = start_time.replace("-", "") + "0000"
    api_end = end_time.replace("-", "") + "2359"

    w, s, e, n = bbox(location)
    clon, clat = _centroid(location)

    stations = _query_synoptic(
        token, {"bbox": f"{w},{s},{e},{n}"}, api_start, api_end
    )

    # Fallback: nearest station within 500 miles of the centroid
    if not stations:
        stations = _query_synoptic(
            token, {"radius": f"{clat},{clon},500", "limit": "20"}, api_start, api_end
        )

    if not stations:
        raise ValueError(
            f"No TexMesonet stations found near ({clat:.3f}, {clon:.3f})"
        )

    station = _nearest(stations, clon, clat)
    dates = list(_date_range(start_time, end_time))
    daily = _daily_precip(station, dates)

    da = xr.DataArray(
        [daily[d] for d in dates],
        dims=["time"],
        coords={
            "time": [np.datetime64(d) for d in dates],
            "lat": float(station["LATITUDE"]),
            "lon": float(station["LONGITUDE"]),
        },
    )
    ds = xr.Dataset({"precip_mm": da})
    ds["precip_mm"].attrs["units"] = "mm/day"
    return ds
