"""
NASA GPM IMERG Final Daily precipitation fetcher via NASA EarthData.

Uses the GPM_3IMERGDF product (Final Run, ~3.5-month latency, 0.1° global grid).
Credentials are read from EARTHDATA_USERNAME and EARTHDATA_PASSWORD environment
variables, which should be set in a .env file at the project root.

Output convention: xr.Dataset with variable 'precip_mm' (time, lat, lon),
units mm/day, covering the requested date range and bounding box.
"""

import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import xarray as xr
from dotenv import load_dotenv

from src.api_hooks._utils import bbox

_ENV_FILE = Path(__file__).parent / ".env"


def _process_granule(
    path: str,
    west: float,
    south: float,
    east: float,
    north: float,
) -> xr.DataArray:
    """Open one IMERG v07 granule (local file), clip to bbox."""
    # v07: flat root group, precipitation already in mm/day, dims (time, lon, lat)
    raw = xr.open_dataset(path, engine="h5netcdf")
    precip = raw["precipitation"]
    if "lon" in precip.dims and precip.dims.index("lon") < precip.dims.index("lat"):
        precip = precip.transpose(..., "lat", "lon")
    return precip.sel(lat=slice(south, north), lon=slice(west, east)).load()


def _fetch_imerg(start_time: str, end_time: str, location: dict) -> xr.Dataset:
    """
    Fetch GPM IMERG Final Daily precipitation for a location and date range.

    Parameters
    ----------
    start_time : str  ISO date, e.g. "2024-01-01"
    end_time   : str  ISO date, e.g. "2024-01-03"
    location   : dict GeoJSON Point or Polygon

    Returns
    -------
    xr.Dataset with variable precip_mm (time, lat, lon), units mm/day
    """
    import earthaccess  # deferred: optional dependency

    load_dotenv(_ENV_FILE)
    earthaccess.login(strategy="environment")

    w, s, e, n = bbox(location)

    results = earthaccess.search_data(
        short_name="GPM_3IMERGDF",
        version="07",
        temporal=(start_time, end_time),
        bounding_box=(w, s, e, n),
    )

    if not results:
        raise ValueError(
            f"No IMERG granules found for {start_time} to {end_time} "
            f"in bbox ({w}, {s}, {e}, {n})"
        )

    process = partial(_process_granule, west=w, south=s, east=e, north=n)
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = earthaccess.download(results, local_path=tmpdir)
        with ThreadPoolExecutor(max_workers=4) as pool:
            day_datasets = list(pool.map(process, paths))

    combined = xr.concat(day_datasets, dim="time")
    ds = xr.Dataset({"precip_mm": combined})
    ds["precip_mm"].attrs["units"] = "mm/day"
    return ds
