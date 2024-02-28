from importlib.metadata import version
from typing import NamedTuple

__author__ = "Aurélien Grenotton (agrenott@gmail.com)"
__version__ = version("pyhgtmap")
__license__ = "GPLv2+"

# Can't use __future__ annotations for type aliases: https://github.com/python/cpython/issues/95805
# Some type aliases
Polygon = list[tuple[float, float]]
PolygonsList = list[Polygon]


class BBox(NamedTuple):
    """Simple bounding box."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
