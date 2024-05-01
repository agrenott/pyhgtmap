from __future__ import annotations

from collections.abc import Iterable
from math import isclose
from typing import Callable

from pyhgtmap import BBox, Coordinates

# Coordinates transformation function prototype
TransformFunType = Callable[
    [Iterable[Coordinates]],
    Iterable[Coordinates],
]


def makeBBoxString(bbox: BBox) -> str:
    return f"{{0:s}}lon{bbox[0]:.2f}_{bbox[2]:.2f}lat{bbox[1]:.2f}_{bbox[3]:.2f}"


def ensure_aligned_coordinates(
    low_left: Coordinates,
    high_left: Coordinates,
    high_right: Coordinates,
    low_right: Coordinates,
) -> None:
    """
    Raises ValueError if the tile doesn't map to an aligned rectangle in WSG84 coordinates.
    """
    if (
        not isclose(low_left.lat, low_right.lat)
        or not isclose(low_left.lon, high_left.lon)
        or not isclose(high_left.lat, high_right.lat)
        or not isclose(high_right.lon, low_right.lon)
    ):
        raise ValueError(
            "Tile doesn't map to an aligned rectangle in WSG84 coordinates"
        )


def transform_lon_lats(
    minLon: float,
    minLat: float,
    maxLon: float,
    maxLat: float,
    transform: TransformFunType | None,
) -> BBox:
    if transform is None:
        return BBox(minLon, minLat, maxLon, maxLat)
    else:
        coordinates = transform(
            [
                Coordinates(minLon, minLat),
                Coordinates(minLon, maxLat),
                Coordinates(maxLon, maxLat),
                Coordinates(maxLon, minLat),
            ],
        )
        low_left, high_left, high_right, low_right = coordinates

        # The resulting projection must be a horizontal rectangle in WSG84 coordinates.
        ensure_aligned_coordinates(low_left, high_left, high_right, low_right)

        # Do not assume low/high/left/right are the same after transformation
        minLon = min([x.lon for x in coordinates])
        maxLon = max([x.lon for x in coordinates])
        minLat = min([x.lat for x in coordinates])
        maxLat = max([x.lat for x in coordinates])
        return BBox(minLon, minLat, maxLon, maxLat)
