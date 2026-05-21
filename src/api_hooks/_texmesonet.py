"""
TexMesonet / SynopticLabs daily precipitation fetcher and processor.

Queries the SynopticLabs REST API (v2) for stations with hourly precipitation
data within the bounding box derived from the runtime Context, then sums to
daily totals.

Fallback rule: if no stations are found inside the bounding box, the station
closest to the centroid of the location is selected via a 500-mile radius query.

Credentials: TEXMESONET_API_KEY environment variable (loaded from .env).

Typical usage
-------------
    context = Context("src/api_hooks/settings.toml")
    raw_path = fetch_texmesonet(context, save_raw=True)
    ds = process_texmesonet(raw_path, context, save_processed=False)
"""

import os
import pathlib as p
from datetime import datetime
from math import sqrt
from pathlib import Path

import numpy as np
import requests
import xarray as xr
from dotenv import load_dotenv

from src.api_hooks._utils import Context, date_range, open_ds

TEXMESONET_SETTINGS = {
    "url": "https://api.synopticdata.com/v2/stations/timeseries",
    "token_env_var": "TEXMESONET_API_KEY",
    "fallback_radius": 500,
    "variable": "precip_raw",
    "out_variable": "total_precipitation",
    "units": "mm",
}

_ENV_FILE = Path(__file__).parent / ".env"


def _query_synoptic(url: str, token: str, extra_params: dict, start: str, end: str) -> list:
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
    resp = requests.get(url, params=params, timeout=90)
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


def fetch_texmesonet(
    context: Context,
    settings: dict = TEXMESONET_SETTINGS,
    save_raw: bool = True,
) -> p.Path | xr.Dataset:
    """Fetch TexMesonet daily precipitation for the location and time range in *context*.

    Queries the SynopticLabs API for stations within the bounding box, selects
    the nearest station, and sums hourly observations to daily totals.

    Parameters
    ----------
    context:
        Runtime context carrying location, time_frame, and folder paths.
    settings:
        Source-specific settings dict; defaults to TEXMESONET_SETTINGS.
    save_raw:
        If True, write the dataset to a NetCDF file in context.temp_folder
        and return its path. If False, return the xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset

    Raises
    ------
    RuntimeError
        If the API token is not set or no stations are found.
    """
    load_dotenv(_ENV_FILE)
    token = os.environ.get(settings["token_env_var"], "")
    if not token:
        raise RuntimeError(
            f"{settings['token_env_var']} is not set. "
            "Add your Synoptic/TexMesonet token to src/api_hooks/.env"
        )

    w, s, e, n = context.location_buffer.bounds
    clon, clat = context.location.x, context.location.y
    api_start = datetime.strptime(context.time_frame[0], "%Y-%m-%d").strftime("%Y%m%d0000")
    api_end = datetime.strptime(context.time_frame[1], "%Y-%m-%d").strftime("%Y%m%d2359")

    stations = _query_synoptic(
        settings["url"], token, {"bbox": f"{w},{s},{e},{n}"}, api_start, api_end
    )

    if not stations:
        stations = _query_synoptic(
            settings["url"],
            token,
            {"radius": f"{clat},{clon},{settings['fallback_radius']}", "limit": "20"},
            api_start,
            api_end,
        )

    if not stations:
        raise RuntimeError(
            f"No TexMesonet stations found near ({clat:.3f}, {clon:.3f})"
        )

    station = _nearest(stations, clon, clat)
    dates = list(date_range(*context.time_frame))
    daily = _daily_precip(station, dates)

    da = xr.DataArray(
        [daily[d] for d in dates],
        dims=["time"],
        coords={
            "time": np.array(dates, dtype="datetime64[D]"),
            "lat": float(station["LATITUDE"]),
            "lon": float(station["LONGITUDE"]),
        },
    )
    ds = xr.Dataset({settings["variable"]: da})

    if save_raw:
        out_path = (
            p.Path(context.temp_folder)
            / f"texmesonet_raw_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        ds.to_netcdf(out_path)
        ds.close()
        return out_path

    return ds


def process_texmesonet(
    raw_texmesonet: str | xr.Dataset,
    context: Context,
    settings: dict = TEXMESONET_SETTINGS,
    save_processed: bool = True,
) -> p.Path | xr.Dataset:
    """Rename the precipitation variable and annotate units.

    Parameters
    ----------
    raw_texmesonet:
        Path to a NetCDF file produced by :func:`fetch_texmesonet`, or an
        xr.Dataset already in memory.
    context:
        Runtime context carrying time_frame and folder paths.
    settings:
        Source-specific settings dict; defaults to TEXMESONET_SETTINGS.
    save_processed:
        If True, write the processed dataset to context.local_folder and
        return its path. If False, return the xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset

    Raises
    ------
    TypeError
        If *raw_texmesonet* is neither a file path nor an xr.Dataset.
    """
    ds = open_ds(raw_texmesonet)
    ds = ds.rename({settings["variable"]: settings["out_variable"]})
    ds[settings["out_variable"]].attrs["units"] = settings["units"]

    if save_processed:
        out_path = (
            p.Path(context.local_folder)
            / f"texmesonet_processed_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        ds.to_netcdf(out_path)
        ds.close()
        return out_path

    return ds
