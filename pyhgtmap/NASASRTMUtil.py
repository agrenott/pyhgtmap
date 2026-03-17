from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, TypeAlias

import numpy
from matplotlib.path import Path as PolygonPath

from pyhgtmap.configuration import CONFIG_DIR, Configuration
from pyhgtmap.sources.pool import Pool

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pyhgtmap import BBox, PolygonsList


IntBBox: TypeAlias = tuple[int, int, int, int]


def calc_bbox(area: BBox, corrx: float = 0.0, corry: float = 0.0) -> IntBBox:
    """Convert a BBox to integer bounding box coordinates for the needed files."""
    min_lon = area.min_lon - corrx
    min_lat = area.min_lat - corry
    max_lon = area.max_lon - corrx
    max_lat = area.max_lat - corry

    if min_lon < 0:
        bbox_min_lon = int(min_lon) if min_lon % 1 == 0 else int(min_lon) - 1
    else:
        bbox_min_lon = int(min_lon)
    if min_lat < 0:
        bbox_min_lat = int(min_lat) if min_lat % 1 == 0 else int(min_lat) - 1
    else:
        bbox_min_lat = int(min_lat)
    if max_lon < 0:
        bbox_max_lon = int(max_lon)
    else:
        bbox_max_lon = int(max_lon) if max_lon % 1 == 0 else int(max_lon) + 1
    if max_lat < 0:
        bbox_max_lat = int(max_lat)
    else:
        bbox_max_lat = int(max_lat) if max_lat % 1 == 0 else int(max_lat) + 1
    return bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat


def get_low_int(n) -> int:
    if n % 1 == 0:
        return int(n)
    if n < 0:
        return int(n) - 1
    else:
        return int(n)


def get_high_int(n) -> int:
    if n < 0 or n % 1 == 0:
        return int(n)
    else:
        return int(n) + 1


def get_range(a, b) -> range:
    a, b = sorted([a, b])
    low, high = get_high_int(a), get_high_int(b)
    return range(low, high)


def intersect_tiles(
    polygons: PolygonsList | None, corrx: float, corry: float
) -> list[str]:
    if not polygons:
        return []
    secs: list[tuple[int, int]] = []
    for polygon in polygons:
        x_last, y_last = polygon[0]
        x_last -= corrx
        y_last -= corry
        for x, y in polygon[1:]:
            x -= corrx
            y -= corry
            secs.append((get_low_int(x), get_low_int(y)))
            if x - x_last == 0:
                # vertical vertex, don't calculate s
                secs.extend(
                    [(get_low_int(x), get_low_int(Y)) for Y in get_range(y, y_last)]
                )
            elif y - y_last == 0:
                # horizontal vertex
                secs.extend(
                    [(get_low_int(X), get_low_int(y)) for X in get_range(x, x_last)]
                )
            else:
                s = (y - y_last) / (x - x_last)
                o = y_last - x_last * s
                for X in get_range(x, x_last):
                    # determine intersections with latitude degrees
                    Y = get_low_int(s * X + o)
                    secs.append((X - 1, Y))  # left
                    secs.append((X, Y))  # right
                for Y in get_range(y, y_last):
                    # determine intersections with longitude degrees
                    X = get_low_int((Y - o) / s)
                    secs.append((X, Y - 1))  # below
                    secs.append((X, Y))  # above
            x_last, y_last = x, y
    return [make_file_name_prefix(x, y) for x, y in set(secs)]


def area_needed(
    lat: int,
    lon: int,
    bbox: IntBBox,
    polygons: PolygonsList | None,
    corrx: float,
    corry: float,
) -> tuple[bool, bool]:
    """checks if a source file is needed depending on the bounding box and
    the passed polygon.
    """
    if polygons is None:
        return True, False
    min_lat = lat + corry
    max_lat = min_lat + 1
    min_lon = lon + corrx
    max_lon = min_lon + 1
    bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat = (float(x) for x in bbox)
    bbox_min_lon += corrx
    bbox_max_lon += corrx
    bbox_min_lat += corry
    bbox_max_lat += corry
    print(
        f"checking if area {make_file_name_prefix(lon, lat):s} intersects with polygon ...",
        end=" ",
    )
    if (
        min_lon == bbox_min_lon
        and min_lat == bbox_min_lat
        and max_lon == bbox_max_lon
        and max_lat == bbox_max_lat
    ):
        # the polygon is completely inside the bounding box
        print("yes")
        # writeTex(lon, lat, lon+1, lat+1, "green")
        return True, True
    # the area is not or completely inside one of the polygons passed to
    # <polygon>.  We just look if the corners are inside the polygons.
    points = [(lo, la) for lo in (min_lon, max_lon) for la in (min_lat, max_lat)]
    inside = numpy.zeros((1, 4))
    for p in polygons:
        inside += PolygonPath(p).contains_points(points)
    if numpy.all(inside):
        # area ist completely inside
        print("yes")
        # writeTex(lon, lat, lon+1, lat+1, "green")
        return True, False
    elif not numpy.any(inside):
        # area is completely outside
        print("no")
        # writeTex(lon, lat, lon+1, lat+1, "red")
        return False, False
    else:
        # This only happens it a polygon vertex is on the tile border.
        # Because in this case points_inside_poly() returns unpredictable
        # results, we better return True here.
        print("maybe")
        # writeTex(lon, lat, lon+1, lat+1, "pink")
        return True, True


def make_file_name_prefix(lon, lat) -> str:
    lonSwitch = "W" if lon < 0 else "E"
    latSwitch = "S" if lat < 0 else "N"

    return f"{latSwitch:s}{abs(lat):0>2d}{lonSwitch:s}{abs(lon):0>3d}"


def make_file_name_prefixes(
    bbox: IntBBox,
    polygons: PolygonsList | None,
    corrx: float,
    corry: float,
    lowercase=False,
) -> list[tuple[str, bool]]:
    """generates a list of filename prefixes of the files containing data within the
    bounding box.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    lon = min_lon
    intersect_areas = intersect_tiles(polygons, corrx, corry)
    prefixes: list[tuple[str, bool]] = []
    lon_range: Iterable[int]
    if min_lon > max_lon:
        # bbox covers the W180/E180 longitude
        lon_range = itertools.chain(range(min_lon, 180), range(-180, max_lon))
    else:
        lon_range = range(min_lon, max_lon)

    for lon in lon_range:
        for lat in range(min_lat, max_lat):
            file_name_prefix = make_file_name_prefix(lon, lat)
            if file_name_prefix in intersect_areas:
                prefixes.append((file_name_prefix, True))
                # writeTex(lon, lat, lon+1, lat+1, "blue")
            else:
                needed, check_poly = area_needed(lat, lon, bbox, polygons, corrx, corry)
                if needed:
                    prefixes.append((file_name_prefix, check_poly))
    if lowercase:
        return [(p.lower(), check_poly) for p, check_poly in prefixes]
    else:
        return prefixes


class SourcesPool:
    """Stateful pool of various HGT data sources."""

    # TODO get rid of this layer once existing sources are migrated to the new framework

    def __init__(self, configuration: Configuration) -> None:
        self._real_pool = Pool(configuration.hgtdir, CONFIG_DIR, configuration)

    def get_file(self, area: str, source: str):
        fileResolution = int(source[4])

        if source[0:4] not in self._real_pool.available_sources_names():
            raise ValueError(f"Unknown source type: {source[0:4]}")

        # New plugin based sources
        file_name = self._real_pool.get_source(source[0:4]).get_file(
            area, fileResolution
        )
        return file_name


def get_files(
    area: BBox,
    polygons: PolygonsList | None,
    corrx: float,
    corry: float,
    sources: list[str],
    configuration: Configuration,
) -> list[tuple[str, bool]]:
    bbox = calc_bbox(area, corrx, corry)
    area_prefixes = make_file_name_prefixes(bbox, polygons, corrx, corry)
    files: list[tuple[str, bool]] = []
    sources_pool = SourcesPool(configuration)

    for area_prefix, check_poly in area_prefixes:
        for source in sources:
            print(f"{area_prefix:s}: trying {source:s} ...")
            save_filename = sources_pool.get_file(area_prefix, source)
            if save_filename:
                files.append((save_filename, check_poly))
                break
        else:
            print(f"{area_prefix:s}: no file found on server.")
            continue
    return files
