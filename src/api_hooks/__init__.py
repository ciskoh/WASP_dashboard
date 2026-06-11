"""
Public API for weather data sources.

    list_sources() -> pl.DataFrame
    get_precipitation(data_source_id, start_time, end_time, location_poly_or_point) -> xr.Dataset
"""

import polars as pl
import xarray as xr

from src.api_hooks.weather_sources import FETCHERS, REGISTRY


def list_sources() -> pl.DataFrame:
    rows = [
        {
            "id": sid,
            "name": meta["name"],
            "org": meta["org"],
            "resolution": meta["resolution"],
            "latency": meta["latency"],
        }
        for sid, meta in REGISTRY.items()
    ]
    return pl.DataFrame(rows)


def get_precipitation(
    data_source_id: str,
    start_time: str,
    end_time: str,
    location_poly_or_point: dict,
) -> xr.Dataset:
    """Fetch precipitation data from a registered source over a time range and area.

    Parameters
    ----------
    data_source_id : str
        ID of the data source to query. Use ``list_sources()`` to see all options.
        Current valid values:
          "2"  — TexMesonet (TWDB, real-time TX station data)
          "5"  — NASA GPM IMERG (0.1° global grid, ~4–14 h latency)
          "7"  — PRISM (4 km CONUS grid, 1–3 day latency)
          "10" — ERA5-Land (ECMWF reanalysis, ~11 km, ~5 day latency)

    start_time : str
        Inclusive start of the requested period, ISO-8601 format.
        Examples: ``"2024-01-01"``, ``"2024-06-15T06:00:00"``

    end_time : str
        Inclusive end of the requested period, ISO-8601 format.
        Examples: ``"2024-01-31"``, ``"2024-06-15T18:00:00"``

    location_poly_or_point : dict
        GeoJSON geometry dict describing the area or point of interest.
        Supported ``"type"`` values:

        * ``"Point"`` — single lon/lat coordinate::

              {"type": "Point", "coordinates": [-97.74, 30.27]}

        * ``"Polygon"`` — closed ring of lon/lat pairs (first == last)::

              {
                  "type": "Polygon",
                  "coordinates": [[
                      [-100.0, 29.0], [-99.0, 29.0],
                      [-99.0, 30.0], [-100.0, 30.0],
                      [-100.0, 29.0],
                  ]]
              }

        * ``"MultiPolygon"`` — list of Polygon coordinate arrays.

        Grid-based sources (IMERG, PRISM, ERA5) clip to the bounding box of the
        geometry. TexMesonet uses the centroid to select the nearest station.

    Returns
    -------
    xr.Dataset
        Dataset with at least a ``precipitation`` variable (units: mm).
        Dimensions vary by source (e.g. ``time`` for all; ``lat``/``lon`` for
        gridded sources; ``station`` for TexMesonet).

    Raises
    ------
    ValueError
        If ``data_source_id`` is not in the registry.

    Examples
    --------
    >>> from src.api_hooks import get_precipitation
    >>> ds = get_precipitation(
    ...     data_source_id="7",
    ...     start_time="2024-03-01",
    ...     end_time="2024-03-31",
    ...     location_poly_or_point={"type": "Point", "coordinates": [-97.74, 30.27]},
    ... )
    >>> ds["precipitation"]
    """
    if data_source_id not in FETCHERS:
        raise ValueError(f"Unknown data_source_id: {data_source_id!r}")
    return FETCHERS[data_source_id](start_time, end_time, location_poly_or_point)
