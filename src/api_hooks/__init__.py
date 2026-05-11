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
    if data_source_id not in FETCHERS:
        raise ValueError(f"Unknown data_source_id: {data_source_id!r}")
    return FETCHERS[data_source_id](start_time, end_time, location_poly_or_point)
