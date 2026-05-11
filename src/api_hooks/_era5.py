"""
ERA5-Land daily precipitation fetcher via the ECMWF CDS API.

Credentials are read from environment variables CDSAPI_URL and CDSAPI_KEY,
which should be set in a .env file at the project root.

Output convention: xr.Dataset with variable 'precip_mm' (time, lat, lon),
units mm/day, covering the requested date range and bounding box.
"""

import os
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import xarray as xr
from dotenv import load_dotenv

from src.api_hooks._utils import bbox

_ENV_FILE = Path(__file__).parent / ".env"


def _date_range(start_time: str, end_time: str):
    """Yield datetime objects from start_time to end_time inclusive."""
    current = datetime.strptime(start_time, "%Y-%m-%d")
    end = datetime.strptime(end_time, "%Y-%m-%d")
    while current <= end:
        yield current
        current += timedelta(days=1)


def _fetch_era5(start_time: str, end_time: str, location: dict) -> xr.Dataset:
    """
    Fetch ERA5-Land daily precipitation sum for a location and date range.

    Parameters
    ----------
    start_time : str  ISO date, e.g. "2024-01-01"
    end_time   : str  ISO date, e.g. "2024-01-03"
    location   : dict GeoJSON Point or Polygon

    Returns
    -------
    xr.Dataset with variable precip_mm (time, lat, lon), units mm/day
    """
    import cdsapi  # deferred: optional dependency

    load_dotenv(_ENV_FILE)

    dates = list(_date_range(start_time, end_time))
    years  = sorted({d.strftime("%Y") for d in dates})
    months = sorted({d.strftime("%m") for d in dates})
    days   = sorted({d.strftime("%d") for d in dates})

    client = cdsapi.Client(
        url=os.environ["ERA5_CDSAPI_URL"],
        key=os.environ["ERA5_CDSAPI_KEY"],
        quiet=True,
    )

    w, s, e, n = bbox(location)

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "era5.zip")
        client.retrieve(
            "reanalysis-era5-land",
            {
                "variable": "total_precipitation",
                "year": years,
                "month": months,
                "day": days,
                "time": [f"{h:02d}:00" for h in range(24)],
                "area": [n, w, s, e],  # CDS format: [N, W, S, E]
                "data_format": "netcdf",
            },
            zip_path,
        )
        with zipfile.ZipFile(zip_path) as zf:
            nc_name = next(n for n in zf.namelist() if n.endswith(".nc"))
            zf.extract(nc_name, tmpdir)
        tmp_path = os.path.join(tmpdir, nc_name)
        with xr.open_dataset(tmp_path, engine="h5netcdf") as raw:
            tp = raw["tp"]
            time_dim = "valid_time" if "valid_time" in tp.dims else "time"
            # tp is metres/hour; daily sum × 1000 → mm/day
            daily_mm = (tp.resample({time_dim: "1D"}).sum() * 1000.0).load()

    daily_mm = daily_mm.rename({time_dim: "time", "latitude": "lat", "longitude": "lon"})

    # CDS may return extra days at month boundaries — keep only what was requested
    requested = pd.DatetimeIndex([d.strftime("%Y-%m-%d") for d in dates])
    time_index = pd.DatetimeIndex(daily_mm.time.values).normalize()
    daily_mm = daily_mm.isel(time=time_index.isin(requested))

    ds = xr.Dataset({"precip_mm": daily_mm})
    ds["precip_mm"].attrs["units"] = "mm/day"
    return ds
