"""
PRISM daily precipitation fetcher and processor (4 km gridded, public HTTP).

No credentials required. Historical data available from 1895; provisional
data available 1-3 days after the observation date.

Downloads one ZIP per requested day from the PRISM Climate Group service,
reads the GeoTIFF raster with rasterio, clips to the bounding box from the
runtime Context, and returns daily precipitation. Days are fetched in parallel.

Typical usage
-------------
    context = Context("src/api_hooks/settings.toml")
    raw_path = fetch_prism(context, save_raw=True)
    ds = process_prism(raw_path, context, save_processed=False)
"""

import io
import pathlib as p
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests
import xarray as xr

from src.api_hooks._utils import Context, date_range, open_ds

PRISM_SETTINGS = {
    "url": "https://services.nacse.org/prism/data/get/us/4km/ppt/{date}",
    "variable": "precip_raw",
    "out_variable": "total_precipitation",
    "units": "mm",
    "max_workers": 4,
}



def _fetch_day(
    date_yyyymmdd: str,
    west: float,
    south: float,
    east: float,
    north: float,
    url_template: str,
) -> xr.DataArray:
    """Download and clip one day's PRISM precipitation GeoTIFF from a ZIP archive."""
    import rasterio
    from rasterio.windows import from_bounds

    url = url_template.format(date=date_yyyymmdd)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    raw = resp.content

    if raw[:4] != b"PK\x03\x04":
        raise RuntimeError(
            f"PRISM returned a non-ZIP response for {date_yyyymmdd} "
            f"(likely rate-limited): {resp.text[:300]}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            zf.extractall(tmpdir)

        tif_files = list(p.Path(tmpdir).glob("*.tif"))
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


def fetch_prism(
    context: Context,
    settings: dict = PRISM_SETTINGS,
    save_raw: bool = True,
) -> p.Path | xr.Dataset:
    """Fetch PRISM daily precipitation for the location and time range in *context*.

    Downloads one ZIP per day in parallel, clips each raster to the bounding
    box, and concatenates the results along the time dimension.

    Parameters
    ----------
    context:
        Runtime context carrying location, time_frame, and folder paths.
    settings:
        Source-specific settings dict; defaults to PRISM_SETTINGS.
    save_raw:
        If True, write the combined dataset to a NetCDF file in
        context.temp_folder and return its path. If False, return the
        xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset
    """
    w, s, e, n = context.location_buffer.bounds
    dates = list(date_range(*context.time_frame))

    def fetch_day(date_iso):
        da = _fetch_day(date_iso.replace("-", ""), w, s, e, n, settings["url"])
        return da.expand_dims({"time": [np.datetime64(date_iso)]})

    with ThreadPoolExecutor(max_workers=settings["max_workers"]) as pool:
        arrays = list(pool.map(fetch_day, dates))

    combined = xr.concat(arrays, dim="time")
    ds = xr.Dataset({settings["variable"]: combined})

    if save_raw:
        out_path = (
            p.Path(context.temp_folder)
            / f"prism_raw_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        ds.to_netcdf(out_path)
        ds.close()
        return out_path

    return ds


def process_prism(
    raw_prism: str | xr.Dataset,
    context: Context,
    settings: dict = PRISM_SETTINGS,
    save_processed: bool = True,
) -> p.Path | xr.Dataset:
    """Rename the precipitation variable and annotate units.

    Parameters
    ----------
    raw_prism:
        Path to a NetCDF file produced by :func:`fetch_prism`, or an
        xr.Dataset already in memory.
    context:
        Runtime context carrying time_frame and folder paths.
    settings:
        Source-specific settings dict; defaults to PRISM_SETTINGS.
    save_processed:
        If True, write the processed dataset to context.local_folder and
        return its path. If False, return the xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset

    Raises
    ------
    TypeError
        If *raw_prism* is neither a file path nor an xr.Dataset.
    """
    ds = open_ds(raw_prism)
    ds = ds.rename({settings["variable"]: settings["out_variable"]})
    ds[settings["out_variable"]].attrs["units"] = settings["units"]

    if save_processed:
        out_path = (
            p.Path(context.local_folder)
            / f"prism_processed_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        ds.to_netcdf(out_path)
        ds.close()
        return out_path

    return ds
