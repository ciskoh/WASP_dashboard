"""ERA5-Land hourly precipitation fetcher and processor via ARCO Google Cloud Storage."""

import pathlib as p

import xarray as xr

from ._utils import Context, open_ds

ERA5_SETTINGS = {
    "data_source": "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3",
    "chunks": 48,
    "variables": ["total_precipitation"],
    "resample": "1D",
    "out_units": {
        "total_precipitation": {
            "units_from": "m",
            "units_to": "mm",
            "conversion": lambda x: x * 1000,
        }
    },
}


def fetch_era5(context: Context, settings: dict = ERA5_SETTINGS, save_temp: bool = True):
    """Fetch ERA5-Land hourly precipitation for the location and time range in *context*.

    Downloads data from the ARCO public Zarr store on GCS (anonymous access).
    ARCO stores longitude in 0–360°, so negative (western) longitudes are
    converted before the spatial selection.

    Parameters
    ----------
    context:
        Runtime context carrying location, time_frame, and folder paths.
    settings:
        Source-specific settings dict; defaults to ERA5_SETTINGS.
    save_temp:
        If True, write the raw subset to a NetCDF file in context.temp_folder
        and return its path. If False, return the xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset
    """
    ds = xr.open_zarr(
        settings["data_source"],
        chunks={"time": settings["chunks"]},
        storage_options={"token": "anon"},
    )

    # ARCO longitude is 0–360, so convert negative (western) longitudes.
    lat = context.location.y
    lon = context.location.x % 360

    sub = (
        ds[settings["variables"]]
        .sel(latitude=lat, longitude=lon, method="nearest")
        .sel(time=slice(*context.time_frame))
    )

    if save_temp:
        out_path = (
            p.Path(context.temp_folder)
            / f"era5_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        sub.to_netcdf(out_path)
        return out_path

    return sub


def process_era5(
    raw_era5: str | xr.Dataset,
    context: Context,
    settings: dict = ERA5_SETTINGS,
    save_processed: bool = True,
):
    """Resample hourly ERA5 precipitation to daily totals and convert units.

    Hourly ``total_precipitation`` in ERA5 is a per-hour accumulation in metres.
    Daily totals are computed by summing the 24 hourly values for each UTC day,
    then converted to the target units defined in ``settings["out_units"]``.

    Parameters
    ----------
    raw_era5:
        Path to a NetCDF file produced by :func:`fetch_era5`, or an
        xr.Dataset already loaded in memory.
    context:
        Runtime context carrying time_frame and folder paths.
    settings:
        Source-specific settings dict; defaults to ERA5_SETTINGS.
    save_processed:
        If True, write the processed dataset to context.local_folder and
        return its path. If False, return the xr.Dataset directly.

    Returns
    -------
    pathlib.Path | xr.Dataset

    Raises
    ------
    AssertionError
        If *raw_era5* is neither a valid file path nor an xr.Dataset.
    NotImplementedError
        If a required unit conversion is not defined in *settings*.
    """
    raw_era5 = open_ds(raw_era5)
    daily = raw_era5[settings["variables"]].resample(time=settings["resample"]).sum()

    for var, unit_spec in settings["out_units"].items():
        if var not in daily.data_vars:
            continue
        current_units = daily[var].attrs.get("units")
        if current_units == unit_spec["units_to"]:
            continue
        if current_units == unit_spec["units_from"]:
            daily[var] = unit_spec["conversion"](daily[var])
            daily[var].attrs["units"] = unit_spec["units_to"]
        else:
            raise NotImplementedError(
                f"No conversion defined from {current_units!r} to {unit_spec['units_to']!r}"
            )

    if save_processed:
        out_path = (
            p.Path(context.local_folder)
            / f"era5_processed_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        daily.to_netcdf(out_path)
        return out_path

    return daily
