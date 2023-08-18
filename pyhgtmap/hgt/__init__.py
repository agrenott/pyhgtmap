from typing import Callable, Iterable, Optional, Tuple

# Coordinates transformation function prototype
TransformFunType = Callable[
    [Iterable[Tuple[float, float]]], Iterable[Tuple[float, float]]
]


def makeBBoxString(bbox: Tuple[float, float, float, float]) -> str:
    return "{{0:s}}lon{0[0]:.2f}_{0[2]:.2f}lat{0[1]:.2f}_{0[3]:.2f}".format(bbox)


def transformLonLats(
    minLon: float,
    minLat: float,
    maxLon: float,
    maxLat: float,
    transform: Optional[TransformFunType],
) -> Tuple[float, float, float, float]:
    if transform is None:
        return minLon, minLat, maxLon, maxLat
    else:
        (lon1, lat1), (lon2, lat2), (lon3, lat3), (lon4, lat4) = transform(
            [(minLon, minLat), (maxLon, maxLat), (minLon, maxLat), (maxLon, maxLat)]
        )
        minLon = min([lon1, lon2, lon3, lon4])
        maxLon = max([lon1, lon2, lon3, lon4])
        minLat = min([lat1, lat2, lat3, lat4])
        maxLat = max([lat1, lat2, lat3, lat4])
        return minLon, minLat, maxLon, maxLat
