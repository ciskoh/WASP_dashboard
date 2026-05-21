"""
Integration tests for all weather api hooks.

Each test verifies that the processed output is coherent with the CONTEXT
defined in settings.toml: correct variable name, units, time range, and
spatial coverage where applicable.

All tests hit external APIs and require credentials — run with:
    pytest tests/test_weather_apis.py -v
"""

import xarray as xr

from src.api_hooks._utils import Context
from src.api_hooks._era5 import fetch_era5, process_era5, ERA5_SETTINGS
from src.api_hooks._gpm_imerg import fetch_imerg, process_imerg, IMERG_SETTINGS
from src.api_hooks._prism import fetch_prism, process_prism, PRISM_SETTINGS
from src.api_hooks._texmesonet import fetch_texmesonet, process_texmesonet, TEXMESONET_SETTINGS

SETTINGS_PATH = "src/api_hooks/settings.toml"

# --
INPUT_era5 = {
    "context": Context(SETTINGS_PATH),
    "save_temp": False,
}


def test_fetch_era5_returns_dataset(input=INPUT_era5):
    ds = fetch_era5(**input)
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims


def test_process_era5_timeframe(input=INPUT_era5):
    ctx = input["context"]
    raw = fetch_era5(**input)
    ds = process_era5(raw, ctx, save_processed=False)
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_process_era5_units(input=INPUT_era5):
    ctx = input["context"]
    raw = fetch_era5(**input)
    ds = process_era5(raw, ctx, save_processed=False)
    out_var = ERA5_SETTINGS["variables"][0]
    assert out_var in ds.data_vars
    assert ds[out_var].attrs.get("units") == ERA5_SETTINGS["out_units"][out_var]["units_to"]


# --
INPUT_imerg = {
    "context": Context(SETTINGS_PATH),
    "save_raw": False,
}


def test_fetch_imerg_returns_dataset(input=INPUT_imerg):
    ds = fetch_imerg(**input)
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims
    assert "lat" in ds.dims
    assert "lon" in ds.dims


def test_fetch_imerg_timeframe(input=INPUT_imerg):
    ctx = input["context"]
    ds = fetch_imerg(**input)
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_fetch_imerg_location(input=INPUT_imerg):
    ctx = input["context"]
    ds = fetch_imerg(**input)
    assert float(ds.lat.min()) <= ctx.location.y <= float(ds.lat.max())
    assert float(ds.lon.min()) <= ctx.location.x <= float(ds.lon.max())


def test_process_imerg_units(input=INPUT_imerg):
    ds = fetch_imerg(**input)
    processed = process_imerg(ds, input["context"], save_processed=False)
    out_var = IMERG_SETTINGS["out_variable"]
    assert out_var in processed.data_vars
    assert processed[out_var].attrs.get("units") == IMERG_SETTINGS["units"]


# --
INPUT_prism = {
    "context": Context(SETTINGS_PATH),
    "save_raw": False,
}


def test_fetch_prism_returns_dataset(input=INPUT_prism):
    ds = fetch_prism(**input)
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims
    assert "lat" in ds.dims
    assert "lon" in ds.dims


def test_fetch_prism_timeframe(input=INPUT_prism):
    ctx = input["context"]
    ds = fetch_prism(**input)
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_fetch_prism_location(input=INPUT_prism):
    ctx = input["context"]
    ds = fetch_prism(**input)
    assert float(ds.lat.min()) <= ctx.location.y <= float(ds.lat.max())
    assert float(ds.lon.min()) <= ctx.location.x <= float(ds.lon.max())


def test_process_prism_units(input=INPUT_prism):
    ds = fetch_prism(**input)
    processed = process_prism(ds, input["context"], save_processed=False)
    out_var = PRISM_SETTINGS["out_variable"]
    assert out_var in processed.data_vars
    assert processed[out_var].attrs.get("units") == PRISM_SETTINGS["units"]


# --
INPUT_texmesonet = {
    "context": Context(SETTINGS_PATH),
    "save_raw": False,
}


def test_fetch_texmesonet_returns_dataset(input=INPUT_texmesonet):
    ds = fetch_texmesonet(**input)
    assert isinstance(ds, xr.Dataset)
    assert "time" in ds.dims


def test_fetch_texmesonet_timeframe(input=INPUT_texmesonet):
    ctx = input["context"]
    ds = fetch_texmesonet(**input)
    assert str(ds.time.values[0])[:10] == ctx.time_frame[0]
    assert str(ds.time.values[-1])[:10] == ctx.time_frame[1]


def test_process_texmesonet_units(input=INPUT_texmesonet):
    ds = fetch_texmesonet(**input)
    processed = process_texmesonet(ds, input["context"], save_processed=False)
    out_var = TEXMESONET_SETTINGS["out_variable"]
    assert out_var in processed.data_vars
    assert processed[out_var].attrs.get("units") == TEXMESONET_SETTINGS["units"]
