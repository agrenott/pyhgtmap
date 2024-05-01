from importlib.metadata import version
from typing import NamedTuple

__author__ = "Aurélien Grenotton (agrenott@gmail.com)"
__version__ = version("pyhgtmap")
__license__ = "GPLv2+"


class BBox(NamedTuple):
    """Simple bounding box."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class Coordinates(NamedTuple):
    """Simple coordinates."""

    lon: float
    lat: float


# Some type aliases
Polygon = list[Coordinates]
PolygonsList = list[Polygon]
