from importlib.metadata import version

__author__ = "Aurélien Grenotton (agrenott@gmail.com)"
__version__ = version("pyhgtmap")
__license__ = "GPLv2+"

# Some type aliases
Polygon = list[tuple[float, float]]
PolygonsList = list[Polygon]
