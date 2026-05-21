"""Shared utilities for weather source fetchers."""

import pathlib as p
from typing import List

import toml
import shapely as shap
import xarray as xr


def bbox(location: dict, buffer: float = 0.5) -> tuple[float, float, float, float]:
    """Return a (west, south, east, north) bounding box from a GeoJSON location dict.

    Parameters
    ----------
    location:
        GeoJSON geometry dict. Supported types: Point, Polygon, MultiPolygon.
    buffer:
        Degrees to expand the bounding box on each side. Only applied to
        Point geometries; polygon extents are used as-is.

    Returns
    -------
    tuple[float, float, float, float]
        ``(west, south, east, north)`` in decimal degrees.

    Raises
    ------
    ValueError
        If *location* has an unsupported GeoJSON type.
    """
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


class Context:
    """Runtime context shared across all fetcher and processor functions.

    Holds the spatial location, time window, and working-folder paths needed
    to fetch and process weather data. Typically constructed from a TOML
    settings file.

    Attributes
    ----------
    time_frame:
        Two-element list ``[start_date, end_date]`` as ISO-format strings.
    temp_folder:
        Directory for intermediate / raw downloads.
    local_folder:
        Directory for processed output files.
    """

    time_frame: List[str]
    temp_folder: str | p.Path
    local_folder: str | p.Path

    def __init__(self, toml_file_path: str | p.Path = None):
        """Initialise a Context from a TOML settings file.

        Parameters
        ----------
        toml_file_path:
            Path to a TOML file with a ``[context]`` section containing
            ``st_date``, ``en_date``, ``location``, ``temp_folder``, and
            ``local_folder`` keys.

        Raises
        ------
        NotImplementedError
            If called without *toml_file_path* (direct keyword construction
            is not yet implemented).
        """
        if toml_file_path:
            self._load_from_toml(toml_file_path)
        else:
            raise NotImplementedError("A toml_file_path is required to create a Context object.")

    def _load_from_toml(self, toml_file_path: str | p.Path) -> None:
        """Populate attributes from the ``[context]`` section of a TOML file."""
        toml_dict = toml.load(toml_file_path)["context"]
        self.time_frame = [toml_dict["st_date"], toml_dict["en_date"]]
        self._location = toml_dict["location"]
        self.temp_folder = toml_dict["temp_folder"]
        self.local_folder = toml_dict["local_folder"]

    @property
    def location(self) -> shap.Point:
        """Return the configured location as a Shapely Point (lon, lat)."""
        return shap.Point(self._location)

    @property
    def location_buffer(self) -> shap.geometry.base.BaseGeometry:
        """Return the location as a 0.5°-buffered square Shapely geometry.

        The buffer ensures grid-based fetchers always capture at least one grid
        cell around the point. Call .bounds on the result for (west, south,
        east, north). The 0.5° value matches the bbox() utility default.
        """
        return shap.Point(self._location).buffer(0.5, cap_style="square")

    def __repr__(self) -> str:
        return (
            f"time_frame: {self.time_frame}, "
            f"location: {self.location}, "
            f"folders: [temp] {self.temp_folder}, [processed] {self.local_folder}"
        )


def date_range(start_time: str, end_time: str):
    """Yield ISO date strings (YYYY-MM-DD) from start_time to end_time inclusive."""
    from datetime import datetime, timedelta
    current = datetime.strptime(start_time, "%Y-%m-%d")
    end = datetime.strptime(end_time, "%Y-%m-%d")
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def open_ds(raw: str | p.Path | xr.Dataset) -> xr.Dataset:
    """Return an xr.Dataset from either a file path or an existing Dataset.

    Raises TypeError if *raw* is neither.
    """
    if isinstance(raw, xr.Dataset):
        return raw
    try:
        return xr.open_dataset(raw)
    except Exception as exc:
        raise TypeError(
            f"Expected a file path or xr.Dataset, got {type(raw).__name__!r}"
        ) from exc
