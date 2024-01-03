from typing import Callable, Iterable, Optional, Tuple

# Coordinates transformation function prototype
TransformFunType = Callable[
    [Iterable[Tuple[float, float]]], Iterable[Tuple[float, float]]
]


def makeBBoxString(bbox: Tuple[float, float, float, float]) -> str:
    return f"{{0:s}}lon{bbox[0]:.2f}_{bbox[2]:.2f}lat{bbox[1]:.2f}_{bbox[3]:.2f}"


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
