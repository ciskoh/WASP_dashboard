"""
PRISM daily precipitation fetcher (4 km gridded, public HTTP).

No credentials required. Historical data available from 1895; provisional
data available 1-3 days after the observation date.

Downloads one ZIP per requested day from the PRISM Climate Group service,
reads the BIL raster with rasterio, clips to the requested bounding box,
and returns daily precipitation in mm. Days are fetched in parallel.

Output convention: xr.Dataset with variable 'precip_mm' (time, lat, lon),
units mm/day.
"""

import io
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import requests
import xarray as xr

from src.api_hooks._utils import bbox

_PRISM_URL = "https://services.nacse.org/prism/data/get/us/4km/ppt/{date}"


def _date_range(start_time: str, end_time: str):
    """Yield (YYYYMMDD, YYYY-MM-DD) pairs from start_time to end_time inclusive."""
    current = datetime.strptime(start_time, "%Y-%m-%d")
    end = datetime.strptime(end_time, "%Y-%m-%d")
    while current <= end:
        yield current.strftime("%Y%m%d"), current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def _fetch_day(
    date_yyyymmdd: str,
    west: float,
    south: float,
    east: float,
    north: float,
) -> xr.DataArray:
    """Download and parse one day's PRISM precipitation GeoTIFF raster."""
    import rasterio
    from rasterio.windows import from_bounds

    url = _PRISM_URL.format(date=date_yyyymmdd)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()

    if not resp.content[:4] == b"PK\x03\x04":
        raise RuntimeError(
            f"PRISM returned a non-ZIP response for {date_yyyymmdd} "
            f"(likely rate-limited): {resp.text[:300]}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(tmpdir)

        tif_files = list(Path(tmpdir).glob("*.tif"))
        if not tif_files:
            raise FileNotFoundError(f"No .tif file in PRISM ZIP for {date_yyyymmdd}")

        with rasterio.open(tif_files[0]) as src:
            window = from_bounds(west, south, east, north, src.transform)
            data = src.read(1, window=window, masked=True).filled(np.nan).astype(float)
            win_transform = src.window_transform(window)

    height, width = data.shape
    lons = win_transform.c + (np.arange(width) + 0.5) * win_transform.a
    lats = win_transform.f + (np.arange(height) + 0.5) * win_transform.e

    return xr.DataArray(data, dims=["lat", "lon"], coords={"lat": lats, "lon": lons})


def _fetch_prism(start_time: str, end_time: str, location: dict) -> xr.Dataset:
    """
    Fetch PRISM daily precipitation for a location and date range.

    Parameters
    ----------
    start_time : str  ISO date, e.g. "2024-01-01"
    end_time   : str  ISO date, e.g. "2024-01-03"
    location   : dict GeoJSON Point or Polygon

    Returns
    -------
    xr.Dataset with variable precip_mm (time, lat, lon), units mm/day
    """
    w, s, e, n = bbox(location, buffer=0.1)
    date_pairs = list(_date_range(start_time, end_time))

    def fetch_day(pair):
        date_compact, date_iso = pair
        da = _fetch_day(date_compact, w, s, e, n)
        return da.expand_dims({"time": [np.datetime64(date_iso)]})

    with ThreadPoolExecutor(max_workers=4) as pool:
        arrays = list(pool.map(fetch_day, date_pairs))

    combined = xr.concat(arrays, dim="time")
    ds = xr.Dataset({"precip_mm": combined})
    ds["precip_mm"].attrs["units"] = "mm/day"
    return ds
