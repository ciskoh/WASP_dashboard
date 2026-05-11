"""
Tests for src/api_hooks/weather_sources.py

Phase A  — registry and dispatch (no network, no credentials required)
Phase C  — per-source integration tests (require credentials + network access)

Run all credential-free tests with:
    pytest tests/test_weather_sources.py -m "not integration"
"""

from datetime import date, timedelta

import pytest
import polars as pl
import xarray as xr

from src.api_hooks import get_precipitation, list_sources
from src.api_hooks.weather_sources import REGISTRY, FETCHERS

# ---------------------------------------------------------------------------
# Phase A — registry
# ---------------------------------------------------------------------------

EXPECTED_source_ids = {"2", "5", "7", "10"}
EXPECTED_source_names = {
    "2": "TexMesonet",
    "5": "NASA GPM IMERG",
    "7": "PRISM",
    "10": "ERA5 / ERA5-Land",
}


def test_registry_contains_expected_sources():
    assert set(REGISTRY.keys()) == EXPECTED_source_ids


def test_registry_source_names():
    for sid, name in EXPECTED_source_names.items():
        assert REGISTRY[sid]["name"] == name, f"Wrong name for source {sid}"


def test_list_sources_returns_polars_dataframe():
    df = list_sources()
    assert isinstance(df, pl.DataFrame)


def test_list_sources_has_correct_row_count():
    df = list_sources()
    assert len(df) == 4


def test_list_sources_has_required_columns():
    df = list_sources()
    for col in ("id", "name", "org", "resolution", "latency"):
        assert col in df.columns, f"Missing column: {col}"


def test_list_sources_ids_match_registry():
    df = list_sources()
    assert set(df["id"].to_list()) == EXPECTED_source_ids


# ---------------------------------------------------------------------------
# Phase A — dispatch routing (no real fetcher calls)
# ---------------------------------------------------------------------------

EXPECTED_dispatch_ids = list(EXPECTED_source_ids)


def test_fetchers_registered_for_all_sources():
    assert set(FETCHERS.keys()) == EXPECTED_source_ids


def test_get_precipitation_raises_for_unknown_source():
    with pytest.raises(ValueError, match="Unknown data_source_id"):
        get_precipitation(
            data_source_id="99",
            start_time="2024-01-01",
            end_time="2024-01-03",
            location_poly_or_point={"type": "Point", "coordinates": [-103.5, 30.5]},
        )


def test_get_precipitation_dispatches_to_correct_fetcher(monkeypatch):
    """Check that each source ID routes to its own fetcher (not a real API call)."""
    import src.api_hooks.weather_sources as ws

    sentinel = object()

    for sid in EXPECTED_source_ids:
        called_with = {}

        def fake_fetch(start_time, end_time, location, _sid=sid):
            called_with["sid"] = _sid
            return sentinel

        monkeypatch.setitem(ws.FETCHERS, sid, fake_fetch)
        result = get_precipitation(
            data_source_id=sid,
            start_time="2024-01-01",
            end_time="2024-01-01",
            location_poly_or_point={"type": "Point", "coordinates": [0, 0]},
        )
        assert result is sentinel, f"Source {sid} did not return sentinel"
        assert called_with["sid"] == sid


# ---------------------------------------------------------------------------
# Phase C — ERA5 integration (requires CDS credentials in .env)
# ---------------------------------------------------------------------------

INPUT_get_precipitation_era5 = {
    "data_source_id": "10",
    "start_time": "2024-01-01",
    "end_time": "2024-01-03",
    "location_poly_or_point": {"type": "Point", "coordinates": [-103.5, 30.5]},
}

EXPECTED_get_precipitation_era5_n_days = 3


@pytest.mark.integration
def test_get_precipitation_era5(input=INPUT_get_precipitation_era5):
    ds = get_precipitation(**input)
    assert isinstance(ds, xr.Dataset)
    assert "precip_mm" in ds.data_vars
    assert set(ds.dims) >= {"time", "lat", "lon"}
    assert len(ds.time) == EXPECTED_get_precipitation_era5_n_days
    assert ds["precip_mm"].attrs.get("units") == "mm/day"
    assert float(ds["precip_mm"].min()) >= 0


# ---------------------------------------------------------------------------
# Phase C — GPM IMERG integration (requires NASA EarthData credentials in .env)
# ---------------------------------------------------------------------------

INPUT_get_precipitation_imerg = {
    "data_source_id": "5",
    "start_time": "2024-01-01",
    "end_time": "2024-01-03",
    "location_poly_or_point": {"type": "Point", "coordinates": [-103.5, 30.5]},
}

EXPECTED_get_precipitation_imerg_n_days = 3


@pytest.mark.integration
def test_get_precipitation_imerg(input=INPUT_get_precipitation_imerg):
    ds = get_precipitation(**input)
    assert isinstance(ds, xr.Dataset)
    assert "precip_mm" in ds.data_vars
    assert set(ds.dims) >= {"time", "lat", "lon"}
    assert len(ds.time) == EXPECTED_get_precipitation_imerg_n_days
    assert ds["precip_mm"].attrs.get("units") == "mm/day"
    assert float(ds["precip_mm"].min()) >= 0


# ---------------------------------------------------------------------------
# Phase C — PRISM integration (no credentials needed, public HTTP)
# ---------------------------------------------------------------------------

INPUT_get_precipitation_prism = {
    "data_source_id": "7",
    "start_time": "2024-01-01",
    "end_time": "2024-01-03",
    "location_poly_or_point": {"type": "Point", "coordinates": [-103.5, 30.5]},
}

EXPECTED_get_precipitation_prism_n_days = 3


@pytest.mark.integration
def test_get_precipitation_prism(input=INPUT_get_precipitation_prism):
    ds = get_precipitation(**input)
    assert isinstance(ds, xr.Dataset)
    assert "precip_mm" in ds.data_vars
    assert set(ds.dims) >= {"time", "lat", "lon"}
    assert len(ds.time) == EXPECTED_get_precipitation_prism_n_days
    assert ds["precip_mm"].attrs.get("units") == "mm/day"
    assert float(ds["precip_mm"].min()) >= 0


# ---------------------------------------------------------------------------
# Phase C — TexMesonet integration (requires TEXMESONET_API_KEY in .env)
# ---------------------------------------------------------------------------

# Synoptic free tier allows ~1 year of history; use a rolling window to stay within it
_TMESO_END = (date.today() - timedelta(days=5)).isoformat()
_TMESO_START = (date.today() - timedelta(days=7)).isoformat()

INPUT_get_precipitation_texmesonet = {
    "data_source_id": "2",
    "start_time": _TMESO_START,
    "end_time": _TMESO_END,
    "location_poly_or_point": {"type": "Point", "coordinates": [-103.5, 30.5]},
}

EXPECTED_get_precipitation_texmesonet_n_days = 3


@pytest.mark.integration
def test_get_precipitation_texmesonet(input=INPUT_get_precipitation_texmesonet):
    ds = get_precipitation(**input)
    assert isinstance(ds, xr.Dataset)
    assert "precip_mm" in ds.data_vars
    assert "time" in ds.dims
    assert len(ds.time) == EXPECTED_get_precipitation_texmesonet_n_days
    assert ds["precip_mm"].attrs.get("units") == "mm/day"
    assert float(ds["precip_mm"].min()) >= 0
