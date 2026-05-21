"""
Integration tests for all weather api hooks.

Each test verifies that the processed output is coherent with the CONTEXT
defined in settings.toml: correct variable name, units, time range, and
spatial coverage where applicable.

All tests hit external APIs and require credentials — run with:
    pytest tests/test_weather_apis.py -v
"""

import pathlib as p
from datetime import date, timedelta

import xarray as xr

from src.api_hooks._utils import Context
from src.api_hooks._era5 import fetch_era5, process_era5, ERA5_SETTINGS
from src.api_hooks._gpm_imerg import fetch_imerg, process_imerg, IMERG_SETTINGS
from src.api_hooks._prism import fetch_prism, process_prism, PRISM_SETTINGS
from src.api_hooks._texmesonet import fetch_texmesonet, process_texmesonet, TEXMESONET_SETTINGS

SETTINGS_PATH = p.Path(__file__).parent.parent / "src" / "api_hooks" / "settings.toml"

# --
INPUT_era5 = {
    "context": Context(SETTINGS_PATH),
    "save_temp": False,
}

INPUT_imerg = {
    "context": Context(SETTINGS_PATH),
    "save_raw": False,
}

INPUT_prism = {
    "context": Context(SETTINGS_PATH),
    "save_raw": False,
    "use_cache": True,
}

# Synoptic free tier only keeps ~1 year of history; use rolling dates
_texmesonet_ctx = Context(SETTINGS_PATH)
_texmesonet_ctx.time_frame = [
    (date.today() - timedelta(days=7)).isoformat(),
    (date.today() - timedelta(days=5)).isoformat(),
]

INPUT_texmesonet = {
    "context": _texmesonet_ctx,
    "save_raw": False,
}

# Each source is fetched at most once per test session to avoid redundant
# network calls and PRISM's 2-downloads-per-day-per-file rate limit.
_cache = {}


def _raw_era5():
    if "era5" not in _cache:
        _cache["era5"] = fetch_era5(**INPUT_era5)
    return _cache["era5"]


def _raw_imerg():
    if "imerg" not in _cache:
        _cache["imerg"] = fetch_imerg(**INPUT_imerg)
    return _cache["imerg"]


def _raw_prism():
    if "prism" not in _cache:
        _cache["prism"] = fetch_prism(**INPUT_prism)
    return _cache["prism"]


def _raw_texmesonet():
    if "texmesonet" not in _cache:
        _cache["texmesonet"] = fetch_texmesonet(**INPUT_texmesonet)
    return _cache["texmesonet"]


# --
def test_fetch_era5_returns_dataset():
    ds = _raw_era5()
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims


def test_process_era5_timeframe():
    ctx = INPUT_era5["context"]
    ds = process_era5(_raw_era5(), ctx, save_processed=False)
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_process_era5_units():
    ctx = INPUT_era5["context"]
    ds = process_era5(_raw_era5(), ctx, save_processed=False)
    out_var = ERA5_SETTINGS["variables"][0]
    assert out_var in ds.data_vars
    assert ds[out_var].attrs.get("units") == ERA5_SETTINGS["out_units"][out_var]["units_to"]


# --
def test_fetch_imerg_returns_dataset():
    ds = _raw_imerg()
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims
    assert "lat" in ds.dims
    assert "lon" in ds.dims


def test_fetch_imerg_timeframe():
    ctx = INPUT_imerg["context"]
    ds = _raw_imerg()
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_fetch_imerg_location():
    ctx = INPUT_imerg["context"]
    ds = _raw_imerg()
    assert float(ds.lat.min()) <= ctx.location.y <= float(ds.lat.max())
    assert float(ds.lon.min()) <= ctx.location.x <= float(ds.lon.max())


def test_process_imerg_units():
    ctx = INPUT_imerg["context"]
    processed = process_imerg(_raw_imerg(), ctx, save_processed=False)
    out_var = IMERG_SETTINGS["out_variable"]
    assert out_var in processed.data_vars
    assert processed[out_var].attrs.get("units") == IMERG_SETTINGS["units"]


# --
def test_fetch_prism_returns_dataset():
    ds = _raw_prism()
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims
    assert "lat" in ds.dims
    assert "lon" in ds.dims


def test_fetch_prism_timeframe():
    ctx = INPUT_prism["context"]
    ds = _raw_prism()
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_fetch_prism_location():
    ctx = INPUT_prism["context"]
    ds = _raw_prism()
    assert float(ds.lat.min()) <= ctx.location.y <= float(ds.lat.max())
    assert float(ds.lon.min()) <= ctx.location.x <= float(ds.lon.max())


def test_process_prism_units():
    ctx = INPUT_prism["context"]
    processed = process_prism(_raw_prism(), ctx, save_processed=False)
    out_var = PRISM_SETTINGS["out_variable"]
    assert out_var in processed.data_vars
    assert processed[out_var].attrs.get("units") == PRISM_SETTINGS["units"]


# --
def test_fetch_texmesonet_returns_dataset():
    ds = _raw_texmesonet()
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims


def test_fetch_texmesonet_timeframe():
    ctx = INPUT_texmesonet["context"]
    ds = _raw_texmesonet()
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_process_texmesonet_units():
    ctx = INPUT_texmesonet["context"]
    processed = process_texmesonet(_raw_texmesonet(), ctx, save_processed=False)
    out_var = TEXMESONET_SETTINGS["out_variable"]
    assert out_var in processed.data_vars
    assert processed[out_var].attrs.get("units") == TEXMESONET_SETTINGS["units"]
