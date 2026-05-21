import earthaccess  # deferred: optional dependency
from src.api_hooks._utils import bbox, Context
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import xarray as xr
import pathlib as p
#------
IMERG_SETTINGS = dict(
    strategy="environment",
    short_name="GPM_3IMERGDF",
    version="07",
    variables="total_precipitation",
)


def _process_granule(
    path: str,
    west: float,
    south: float,
    east: float,
    north: float,
) -> xr.DataArray:
    """Open one IMERG v07 granule (local file), clip to bbox."""
    raw = xr.open_dataset(path, engine="h5netcdf")
    precip = raw["precipitation"]

    # Build slices that respect coordinate direction (IMERG lat/lon
    # can be ascending or descending; a wrong-direction slice silently
    # returns an empty array rather than erroring).
    lat = precip["lat"]
    lon = precip["lon"]
    lat_slice = slice(south, north) if float(lat[0]) <= float(lat[-1]) else slice(north, south)
    lon_slice = slice(west, east) if float(lon[0]) <= float(lon[-1]) else slice(east, west)

    # Select first (lazy, layout-independent), THEN materialize,
    # THEN transpose in memory — avoids the lazy transpose+index fusion.
    sub = precip.sel(lat=lat_slice, lon=lon_slice).load()
    return sub.transpose(..., "lat", "lon")


def identify_imerg(context: Context, settings: dict = IMERG_SETTINGS, save_raw: bool = True):
    earthaccess.login(strategy=settings["strategy"])
    # location_buffer returns a 0.5°-buffered square; .bounds gives (W, S, E, N)
    w, s, e, n = context.location_buffer.bounds

    results = earthaccess.search_data(
        short_name=settings["short_name"],
        version=settings["version"],
        temporal=(context.time_frame[0], context.time_frame[1]),
        bounding_box=(w, s, e, n),
    )
    return results

def download_imerg(imerg_granules: List[Any], context: Context, settings: dict = IMERG_SETTINGS, save_raw: bool = True):
    w, s, e, n = context.location_buffer.bounds
    process = partial(_process_granule, west=w, south=s, east=e, north=n)

    paths = earthaccess.download(imerg_granules, local_path=context.temp_folder)
    with ThreadPoolExecutor(max_workers=4) as pool:
        day_datasets = list(pool.map(process, paths))

    combined = xr.concat(day_datasets, dim="time")
    if save_raw:
        out_path = (
            p.Path(context.temp_folder)
            / f"imerg_raw_{context.time_frame[0]}-{context.time_frame[1]}.nc"
        )
        combined.to_netcdf(out_path)
        return out_path
    else:
        return combined.to_dataset()

def process_imerg(raw_imerg: str | xr.Dataset, CONTEXT: Context, settings:dict=IMERG_SETTINGS, save_raw=True):
    try:
        ds = xr.open_dataset(raw_imerg)
    except TypeError:
        assert isinstance(raw_imerg, xr.Dataset), (
            "raw_imerg must be a path to a NetCDF file or an xr.Dataset"
        )
        ds=raw_imerg

    ds=ds.rename({"precipitation": settings["variables"]})

    ds[settings["variables"]].attrs["units"] = "mm"
    return ds