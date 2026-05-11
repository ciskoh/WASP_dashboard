"""Shared utilities for weather source fetchers."""


def bbox(location: dict, buffer: float = 0.5) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) bounding box from a GeoJSON location."""
    if location["type"] == "Point":
        lon, lat = location["coordinates"]
        return (lon - buffer, lat - buffer, lon + buffer, lat + buffer)

    if location["type"] == "Polygon":
        rings = location["coordinates"]
    elif location["type"] == "MultiPolygon":
        rings = [ring for poly in location["coordinates"] for ring in poly]
    else:
        raise ValueError(f"Unsupported GeoJSON type: {location['type']!r}")

    lons = [c[0] for ring in rings for c in ring]
    lats = [c[1] for ring in rings for c in ring]
    return (min(lons), min(lats), max(lons), max(lats))
