from importlib.metadata import version
from typing import List, Tuple

__author__ = "Aurélien Grenotton (agrenott@gmail.com)"
__version__ = version("pyhgtmap")
__license__ = "GPLv2+"

# Can't use __future__ annotations for type aliases: https://github.com/python/cpython/issues/95805
# Some type aliases
Polygon = List[Tuple[float, float]]
PolygonsList = List[Polygon]
BoudingBox = Tuple[float, float, float, float]
