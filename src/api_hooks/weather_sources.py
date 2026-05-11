"""
Registry and fetcher stubs for precipitation data sources.

REGISTRY maps source ID strings to metadata dicts with keys:
    name, org, resolution, latency

FETCHERS maps the same IDs to callables with signature:
    fetch(start_time: str, end_time: str, location: dict) -> xr.Dataset
"""

REGISTRY = {
    "2": {
        "name": "TexMesonet",
        "org": "Texas Water Development Board (TWDB)",
        "resolution": "Point stations (statewide TX)",
        "latency": "Real-time",
    },
    "5": {
        "name": "NASA GPM IMERG",
        "org": "NASA / JAXA",
        "resolution": "0.1 deg x 0.1 deg (~11 km)",
        "latency": "4h (Early) / 14h (Late) / ~3.5 months (Final)",
    },
    "7": {
        "name": "PRISM",
        "org": "PRISM Climate Group / Oregon State University",
        "resolution": "4 km (free) / 800 m (paid)",
        "latency": "1-3 days (preliminary)",
    },
    "10": {
        "name": "ERA5 / ERA5-Land",
        "org": "ECMWF / Copernicus Climate Change Service",
        "resolution": "31 km (ERA5) / ~11 km (ERA5-Land)",
        "latency": "~5 days",
    },
}


def _fetch_texmesonet(start_time, end_time, location):
    from src.api_hooks._texmesonet import _fetch_texmesonet as _impl
    return _impl(start_time, end_time, location)


def _fetch_imerg(start_time, end_time, location):
    from src.api_hooks._gpm_imerg import _fetch_imerg as _impl
    return _impl(start_time, end_time, location)


def _fetch_prism(start_time, end_time, location):
    from src.api_hooks._prism import _fetch_prism as _impl
    return _impl(start_time, end_time, location)


def _fetch_era5(start_time, end_time, location):
    from src.api_hooks._era5 import _fetch_era5 as _impl
    return _impl(start_time, end_time, location)


FETCHERS = {
    "2": _fetch_texmesonet,
    "5": _fetch_imerg,
    "7": _fetch_prism,
    "10": _fetch_era5,
}
