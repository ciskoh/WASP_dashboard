"""
NASA GPM IMERG v07 daily precipitation fetcher and processor.

Uses earthaccess to authenticate against NASA Earthdata and download
granules from the GPM_3IMERGDF short-name collection. Granules are
downloaded in parallel and clipped to the bounding box derived from
the runtime Context. The raw combined dataset can optionally be saved
to context.temp_folder before renaming and unit-annotating in the
process step.

Typical usage
-------------
    context = Context("src/api_hooks/settings.toml")
    raw_path = fetch_imerg(context, save_raw=True)
    ds = process_imerg(raw_path, context, save_processed=False)
"""

import pathlib as p
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import xarray as xr
from dotenv import load_dotenv

from src.api_hooks._utils import Context, open_ds

_ENV_FILE = Path(__file__).parent.parent.parent / ".env"

IMERG_SETTINGS = {
    "strategy": "environment",
    "short_name": "GPM_3IMERGDF",
    "version": "07",
    "variable": "precipitation",
    "out_variable": "total_precipitation",
    "units": "mm",
    "max_workers": 4,
}


def _process_granule(
    path: str,
    west: float,
    south: float,
    east: float,
    north: float,
) -> xr.DataArray:
    """Open one IMERG v07 granule (local file) and clip it to the given bbox.

    IMERG lat/lon axes can be ascending or descending; the slice direction is
    chosen accordingly so an inverted range does not silently return an empty
    array.
    """
    with xr.open_dataset(path, engine="h5netcdf") as raw:
        precip = raw["precipitation"]

        lat = precip["lat"]
        lon = precip["lon"]
        lat_slice = slice(south, north) if float(lat[0]) <= float(lat[-1]) else slice(north, south)
        lon_slice = slice(west, east) if float(lon[0]) <= float(lon[-1]) else slice(east, west)

        sub = precip.sel(lat=lat_slice, lon=lon_slice).load()
    return sub.transpose(..., "lat", "lon")


def fetch_imerg(
    context: Context,
    settings: dict = IMERG_SETTINGS,
    save_raw: bool = True,
) -> p.Path | xr.Dataset:
    """Search and download IMERG v07 granules for the location and time range in *context*.

    Authenticates with NASA Earthdata via earthaccess (credentials read from
    environment variables), searches for matching daily granules, downloads
    them to context.temp_folder, clips each to the bounding box, and
    concatenates the results along the time dimension.

    Parameters
    ----------
    context:
        Runtime context carrying location, time_frame, and folder paths.
    settings:
        Source-specific settings dict; defaults to IMERG_SETTINGS.
    save_raw:
        If True, write the combined dataset to a NetCDF file in
        context.temp_folder and return its path. If False, return the
        xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset
    """
    import earthaccess  # optional dependency, deferred to avoid hard import at module load
    load_dotenv(_ENV_FILE)
    earthaccess.login(strategy=settings["strategy"])
    w, s, e, n = context.location_buffer.bounds

    granules = earthaccess.search_data(
        short_name=settings["short_name"],
        version=settings["version"],
        temporal=(context.time_frame[0], context.time_frame[1]),
        bounding_box=(w, s, e, n),
    )

    paths = earthaccess.download(granules, local_path=context.temp_folder)
    process = partial(_process_granule, west=w, south=s, east=e, north=n)

    with ThreadPoolExecutor(max_workers=settings["max_workers"]) as pool:
        day_datasets = list(pool.map(process, paths))

    combined = xr.concat(day_datasets, dim="time")

    if save_raw:
        out_path = (
            p.Path(context.temp_folder)
            / f"imerg_raw_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        combined.to_netcdf(out_path)
        combined.close()
        return out_path

    return combined.to_dataset()


def process_imerg(
    raw_imerg: str | xr.Dataset,
    context: Context,
    settings: dict = IMERG_SETTINGS,
    save_processed: bool = True,
) -> p.Path | xr.Dataset:
    """Rename the precipitation variable and annotate units.

    Renames the raw ``precipitation`` variable to the name defined in
    ``settings["out_variable"]`` and sets the ``units`` attribute to ``"mm"``.

    Parameters
    ----------
    raw_imerg:
        Path to a NetCDF file produced by :func:`fetch_imerg`, or an
        xr.Dataset already in memory.
    context:
        Runtime context carrying time_frame and folder paths.
    settings:
        Source-specific settings dict; defaults to IMERG_SETTINGS.
    save_processed:
        If True, write the processed dataset to context.local_folder and
        return its path. If False, return the xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset

    Raises
    ------
    TypeError
        If *raw_imerg* is neither a file path nor an xr.Dataset.
    """
    ds = open_ds(raw_imerg)
    ds = ds.rename({settings["variable"]: settings["out_variable"]})
    ds[settings["out_variable"]].attrs["units"] = settings["units"]

    if save_processed:
        out_path = (
            p.Path(context.local_folder)
            / f"imerg_processed_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        ds.to_netcdf(out_path)
        return out_path

    return ds
