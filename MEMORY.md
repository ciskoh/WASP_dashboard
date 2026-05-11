# WASP Dashboard — Project Memory

## Current task (2026-04-29)

**Task:** Create `weather_sources` abstraction under `src/api_hooks/`

### Plan summary
Unified API to query daily-sum precipitation from four sources:

| ID | Source | Access |
|----|--------|--------|
| 2 | TexMesonet | MesoWest REST API |
| 5 | NASA GPM IMERG | NASA GES DISC (EarthData) |
| 7 | PRISM | Oregon State HTTP |
| 10 | ERA5 / ERA5-Land | ECMWF CDS API |

Public interface:
```python
from src.api_hooks import get_precipitation, list_sources

ds = get_precipitation(
    data_source_id="10",
    start_time="2024-01-01",
    end_time="2024-01-03",
    location_poly_or_point={"type": "Point", "coordinates": [-103.5, 30.5]},
)  # -> xarray.Dataset with precip_mm (time, lat, lon)
```

### Key decisions
- Source registry is a hardcoded Python dict — the CSV in `refs/` is a reference doc, not read at runtime
- Credentials live in `.env` (gitignored), loaded via `python-dotenv`
- Output: `xarray.Dataset`, variable `precip_mm`, units `mm/day`
- SMAP excluded (soil moisture, not precipitation); NEXRAD discarded
- TDD: tests written and user-approved before each implementation step

### Implementation order
1. ✅ Registry + dispatch (`weather_sources.py`, `__init__.py`) — all 9 Phase A tests pass
2. ➡️ ERA5 (`_era5.py`)
3. GPM IMERG (`_gpm_imerg.py`)
4. PRISM (`_prism.py`)
5. TexMesonet (`_texmesonet.py`)
6. Simplifier pass

---

## Step 2 — ERA5 ✅ done

`src/api_hooks/_era5.py` implemented. Packages installed: cdsapi, python-dotenv, h5netcdf.

---

## Step 3 — GPM IMERG plan (pending approval)

**File:** `src/api_hooks/_era5.py`

**Dependencies:** `cdsapi`, `python-dotenv`, `h5netcdf` (installed)

**Credentials:** `CDSAPI_URL` + `CDSAPI_KEY` from `.env`

**Key details:**
- `reanalysis-era5-land` dataset, variable `total_precipitation` (metres/hour)
- All 24 h requested; `resample("1D").sum() * 1000` gives mm/day
- Dims renamed: `valid_time→time`, `latitude→lat`, `longitude→lon`
- Extra days trimmed to exactly the requested range

---

## Step 3 — GPM IMERG ✅ done + fixed (2026-05-11)

`src/api_hooks/_gpm_imerg.py` implemented. Package installed: earthaccess.
- v07 changed format: flat root group (no `Grid`), `precipitation` already in mm/day (no × 24)
- Switched from `earthaccess.open()` to `earthaccess.download()` → local paths passed to threads (fsspec handles are not thread-safe)
- Dims transposed to (time, lat, lon); clipped to bbox
- Credentials: `EARTHDATA_USERNAME` + `EARTHDATA_PASSWORD`

---

## Step 4 — PRISM ✅ done + fixed (2026-05-11)

`src/api_hooks/_prism.py` implemented. No new packages needed.
- **New URL:** `https://services.nacse.org/prism/data/get/us/4km/ppt/{YYYYMMDD}` (old `/data/public/` path is dead)
- Now delivers GeoTIFF (`.tif`) inside ZIP, not BIL (`.bil`) — rasterio handles both
- Rate limit: 2 downloads per file per day (Pacific time); non-ZIP response guarded with clear RuntimeError
- Point location uses ±0.1° buffer

---

## Step 5 — TexMesonet ✅ done + fixed (2026-05-11)

`src/api_hooks/_texmesonet.py` implemented. Credentials: `TEXMESONET_API_KEY` (Synoptic API token — free account required at synopticdata.com).
- Synoptic free tier allows ~1 year of history; integration test uses a rolling 5–7 days-ago window to stay within it
- Empty-token guard raises `RuntimeError` before hitting the API

---

## Step 6 — Simplifier pass ✅ done

- Extracted `bbox()` to `src/api_hooks/_utils.py`; removed 4 local copies
- `load_dotenv()` now uses explicit `Path(__file__).parent / ".env"` path in all fetchers (bare `load_dotenv()` failed to find `src/api_hooks/.env` when pytest runs from project root)
- PRISM: parallel day downloads via `ThreadPoolExecutor(max_workers=4)`
- IMERG: parallel granule processing via `ThreadPoolExecutor(max_workers=4)` on local files
- `__init__.py`: `get_precipitation` with `-> xr.Dataset` return type

---

## API gotchas (2026-05-11)

| Source | Gotcha |
|--------|--------|
| ERA5 | CDS API v2 wraps the NetCDF4 file in a ZIP (`data_0.nc` inside) |
| IMERG | v07 dropped the `Grid` HDF5 group; `precipitation` is already mm/day |
| PRISM | URL changed to `/data/get/us/4km/`; returns GeoTIFF not BIL; rate-limited to 2/day/file |
| TexMesonet | Synoptic free tier: ~1 year history only; token required (free signup) |

## Completion notes

All 9 Phase A (unit) tests pass. All 4 Phase C (integration) tests pass with valid credentials. Run integration tests with `pytest -m integration`.
