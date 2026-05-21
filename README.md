# WASP dashboard for dustups
This github holds code and experiments on the WASP dashboard for dustups

**Objective:**
Simple dashboard containing satellite derived information for a specific area, maybe with zonal statistics and historical dynamic. The objective is to support operations (current situation snapshot) and demonstrate improvements or changes (long term)

## Data layers 

based on discussion with Shaun and others (see [this note](/home/matt/Desktop/zetllr/TerraDataLabs/Sustainability vertical/20260428_WASP_regen_dashboard_for_DUSTUPS.md))

### 1. Water 
Key point: provide overview of current water availability (10 days ?), in a way that is understandable and compatible with local measurement. Also give broader overview of improvements if any.

key variables: precipitation (10 d) / aridity index (monthly/yearly)/ evapotranspiration(?)

data sources: era5 recent / modis (?) /other

validation: meteo station

outputs: 
- average soil moisture maps 10 years
- precipitation in the last 10 days compared to 10 years average
- aridity index evolution ←


### 2. Soil

Focus 1: provide key info about soil texture and [exposure (bare soil)?]
Focus: show soil temp 

key variables: 
- soil texture from soilgrids /sentinel 2

### 3. Landscape
Focus 2: showcase erosion and changes in canyon shape over the years

key variables:
- changes using sentinel 1 (to be investigated)←embeddings

validation: none /user

output:
- highlight pixel changed by year /rain event

### 4. Plant

Focus 1: show grass layer dynamics throughout the years
Focus 2: show tree veg changes by the river

variables: aridity adapted NDVI per year (max and min)

output:
- map of veg changes by the year (plot by pixel)

stephan Pascal Waelti
# Next steps:
  - investigate general landscape change
  - investigate aridity index
  - identify data sources for precipitation
  - collect reference data
 - define general design principles

---------------------------------------------------------------
# data sources for precipitation

Quick claude search delivered the following selection of [data sources](/home/matt/Documents/terraDataLab/sust_vertical/DUSTUPS_Regen_dashboard/precipitation_sources_30N_105W.csv)

---------------------------------------------------------------
# Developer notes

## Environment setup

Install dependencies and activate the conda environment:
```bash
conda activate wasp
pip install -r requirements.txt
```

## Credentials

Copy and fill in `src/api_hooks/.env` (never commit this file):
```
ERA5_CDSAPI_URL=https://cds.climate.copernicus.eu/api
ERA5_CDSAPI_KEY=<your-CDS-key>          # copernicus.eu account
EARTHDATA_USERNAME=<username>            # urs.earthdata.nasa.gov account
EARTHDATA_PASSWORD=<password>
TEXMESONET_API_KEY=<token>              # free at synopticdata.com
```

## Running tests

```bash
# Fast unit tests only (no credentials, no network):
pytest tests/ -m "not integration"

# Full integration suite (requires credentials + network):
pytest tests/ -m integration -v
```

## api_hooks — precipitation data sources

### Configuration

All fetchers read location, time range, and output folders from `src/api_hooks/settings.toml`:

```toml
[context]
st_date      = "2025-02-01"
en_date      = "2025-02-28"
location     = [-105.0885872, 30.8128463]   # [lon, lat]
temp_folder  = "data/raw/weather/temp"       # raw downloads
local_folder = "data/raw/weather/processed" # processed output
```

### Public API

```python
from src.api_hooks import get_precipitation, list_sources

list_sources()   # returns a polars DataFrame of available sources

ds = get_precipitation(
    data_source_id="7",           # 2=TexMesonet, 5=IMERG, 7=PRISM, 10=ERA5
    start_time="2024-06-01",
    end_time="2024-06-07",
    location_poly_or_point={"type": "Point", "coordinates": [-103.5, 30.5]},
)
# ds["total_precipitation"], units mm
```

### Per-source fetch/process API

Each source exposes `fetch_*` and `process_*` functions that accept a `Context` object and a settings dict. All processed outputs use variable `total_precipitation`, units `mm`.

```python
from src.api_hooks._utils import Context
from src.api_hooks._era5 import fetch_era5, process_era5
from src.api_hooks._gpm_imerg import fetch_imerg, process_imerg
from src.api_hooks._prism import fetch_prism, process_prism
from src.api_hooks._texmesonet import fetch_texmesonet, process_texmesonet

ctx = Context("src/api_hooks/settings.toml")

raw = fetch_prism(ctx, save_raw=True)       # saves to ctx.temp_folder
ds  = process_prism(raw, ctx, save_processed=False)
```

### Known source limitations

| Source | Notes |
|--------|-------|
| ERA5 | Anonymous access via ARCO GCS Zarr store; hourly data resampled to daily |
| IMERG | v07 flat HDF5; requires NASA Earthdata credentials in `.env`; `earthaccess` optional dep |
| PRISM | Rate-limited (~2 req/file/day Pacific time); no credentials needed |
| TexMesonet | Synoptic free tier: ~1 year history; `TEXMESONET_API_KEY` required in `.env` |