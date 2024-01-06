from __future__ import annotations

import contextlib
import importlib.util
import os
from types import SimpleNamespace
from typing import Generator

import numpy
import pytest

from pyhgtmap import hgt
from pyhgtmap.hgt.file import calcHgtArea, clip_polygons, hgtFile, hgtTile, polygon_mask
from tests import TEST_DATA_PATH

HGT_SIZE: int = 1201


def toulon_tiles(
    smooth_ratio: float,
    custom_options: SimpleNamespace | None = None,
) -> list[hgtTile]:
    hgt_file = hgtFile(
        os.path.join(TEST_DATA_PATH, "N43E006.hgt"),
        0,
        0,
        smooth_ratio=smooth_ratio,
    )
    # Fake command line parser output
    options = custom_options or SimpleNamespace(
        area=None,
        maxNodesPerTile=0,
        contourStepSize=20,
    )
    tiles: list[hgtTile] = hgt_file.makeTiles(options)
    return tiles


@pytest.fixture()
def toulon_tiles_raw() -> list[hgtTile]:
    return toulon_tiles(smooth_ratio=1)


@pytest.fixture()
def toulon_tiles_smoothed() -> list[hgtTile]:
    return toulon_tiles(smooth_ratio=3)


# Bounding box of the N43E006 test file
(
    MIN_LON,
    MIN_LAT,
    MAX_LON,
    MAX_LAT,
) = (
    pytest.approx(6),
    pytest.approx(43),
    pytest.approx(7),
    pytest.approx(44),
)


@contextlib.contextmanager
def handle_optional_geotiff_support() -> Generator[None, None, None]:
    """
    Context manager handling the cases where optional GeoTiff support has an impact.
    Cases should run fully if geotiff dependencies are available, else specific exception is
    expected.
    """
    try:
        # Execute test case
        yield
    except ImportError as ex:
        if importlib.util.find_spec("osgeo") is not None:
            # GDAL module is available, do NOT ignore the exception
            raise
        # GDAL not available, ensure the proper errror message is raised
        assert (  # noqa: PT017 # Test is more complex
            ex.msg
            == "GeoTiff optional support not enabled; please install with 'pip install pyhgtmap[geotiff]'"
        )


class TestHgtFile:
    @staticmethod
    def test_make_tiles_chopped() -> None:
        """Tiles chopped due to nodes threshold."""
        custom_options = SimpleNamespace(
            area=None,
            maxNodesPerTile=500000,
            contourStepSize=20,
        )
        tiles: list[hgtTile] = toulon_tiles(1, custom_options)
        assert len(tiles) == 4
        assert [tile.get_stats() for tile in tiles] == [
            "tile with 601 x 1201 points, bbox: (6.00, 43.00, 7.00, 43.50); minimum elevation: -4.00; maximum elevation: 770.00",
            "tile with 301 x 1201 points, bbox: (6.00, 43.50, 7.00, 43.75); minimum elevation: -12.00; maximum elevation: 1703.00",
            "tile with 151 x 1201 points, bbox: (6.00, 43.75, 7.00, 43.88); minimum elevation: 327.00; maximum elevation: 1908.00",
            "tile with 151 x 1201 points, bbox: (6.00, 43.88, 7.00, 44.00); minimum elevation: 317.00; maximum elevation: 1923.00",
        ]
        assert tiles[0].bbox() == (MIN_LON, MIN_LAT, MAX_LON, pytest.approx(43.5))
        assert tiles[0].bbox(doTransform=False) == (
            MIN_LON,
            MIN_LAT,
            MAX_LON,
            pytest.approx(43.5),
        )

    @staticmethod
    def test_make_tiles_chopped_with_area() -> None:
        """Tiles chopped due to nodes threshold and area."""
        custom_options = SimpleNamespace(
            area="6.2:43.1:7.1:43.8",
            maxNodesPerTile=500000,
            contourStepSize=20,
        )
        tiles: list[hgtTile] = toulon_tiles(1, custom_options)
        # Result is cropped to the input area; less tiles are needed
        assert len(tiles) == 2
        assert [tile.get_stats() for tile in tiles] == [
            "tile with 421 x 961 points, bbox: (6.20, 43.10, 7.00, 43.45); minimum elevation: -4.00; maximum elevation: 770.00",
            "tile with 421 x 961 points, bbox: (6.20, 43.45, 7.00, 43.80); minimum elevation: -12.00; maximum elevation: 1703.00",
        ]

    @staticmethod
    def test_make_tiles_fully_masked() -> None:
        """No tile should be generated out of a fully masked input."""
        # Create a fake file, manually filling data
        hgt_file = hgtFile("no-name.not_hgt", 0, 0)
        # Simulate init - fully masked data
        hgt_file.zData = numpy.ma.array([0, 1, 2, 3], mask=[True] * 4).reshape((2, 2))
        hgt_file.minLon, hgt_file.minLat, hgt_file.maxLon, hgt_file.maxLat = (
            0,
            0,
            1,
            1,
        )
        hgt_file.polygons = []
        hgt_file.latIncrement, hgt_file.lonIncrement = 1, 1
        hgt_file.transform = None
        options = SimpleNamespace(area=None, maxNodesPerTile=0, contourStepSize=20)
        tiles: list[hgtTile] = hgt_file.makeTiles(options)
        assert tiles == []

    @staticmethod
    @pytest.mark.parametrize(
        "file_name",
        ["N43E006.hgt", "N43E006.tiff"],
    )
    def test_init(file_name: str) -> None:
        """Validate init from various sources types."""
        with handle_optional_geotiff_support():
            hgt_file = hgtFile(os.path.join(TEST_DATA_PATH, file_name), 0, 0)

            assert hgt_file.numOfCols == 1201
            assert hgt_file.numOfRows == 1201
            assert hgt_file.minLat == MIN_LAT
            assert hgt_file.maxLat == MAX_LAT
            assert hgt_file.minLon == MIN_LON
            assert hgt_file.maxLon == MAX_LON
            assert hgt_file.latIncrement == pytest.approx(0.000833333)
            assert hgt_file.lonIncrement == hgt_file.lonIncrement
            assert hgt_file.transform is None
            assert hgt_file.polygons is None

    @staticmethod
    def test_init_geotiff_transform() -> None:
        """Validate init from geotiff in EPSG 3857 projection."""
        with handle_optional_geotiff_support():
            hgt_file = hgtFile(os.path.join(TEST_DATA_PATH, "N43E006_3857.tiff"), 0, 0)

            assert hgt_file.numOfCols == 1201
            assert hgt_file.numOfRows == 1201
            # Coordinates are kept in original projection
            assert hgt_file.minLat == pytest.approx(5311972)
            assert hgt_file.maxLat == pytest.approx(5465442)
            assert hgt_file.minLon == pytest.approx(667917)
            assert hgt_file.maxLon == pytest.approx(779236)
            assert hgt_file.latIncrement == pytest.approx(127.89195462114967)
            assert hgt_file.lonIncrement == pytest.approx(92.76624238134882)
            # Transform functions must be set
            assert hgt_file.transform is not None
            assert hgt_file.reverseTransform is not None
            assert hgt_file.polygons is None
            # Transformed coordinates must match usual ones
            assert hgt.transformLonLats(
                hgt_file.minLon,
                hgt_file.minLat,
                hgt_file.maxLon,
                hgt_file.maxLat,
                hgt_file.transform,
            ) == (MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)


def test_polygon_mask() -> None:
    x_data = numpy.array([0, 1, 2, 3, 4, 5])
    y_data = numpy.array([0, 1, 2, 3, 4, 5])

    # Mask matching exactly the border of the data
    # Result is a bit strange as the behabior on boundary is unpredictable
    polygon_full: list[tuple[float, float]] = [(0, 0), (0, 5), (5, 5), (5, 0), (0, 0)]
    mask_full = polygon_mask(x_data, y_data, [polygon_full], None)
    numpy.testing.assert_array_equal(
        mask_full,
        numpy.array(
            [
                [True, True, True, True, True, True],
                [True, False, False, False, False, True],
                [True, False, False, False, False, True],
                [True, False, False, False, False, True],
                [True, False, False, False, False, True],
                [True, False, False, False, False, True],
            ],
        ),
    )

    # Polygon bigger than data
    polygon_bigger: list[tuple[float, float]] = [
        (-1, -1),
        (-1, 6),
        (6, 6),
        (6, -1),
        (-1, -1),
    ]
    mask_bigger = polygon_mask(x_data, y_data, [polygon_bigger], None)
    numpy.testing.assert_array_equal(
        mask_bigger,
        numpy.full((x_data.size, y_data.size), False),
    )

    # Polygon splitting data
    polygon_split: list[tuple[float, float]] = [
        (-1, -1),
        (-1, 6),
        (2, 6),
        (5, -1),
        (-1, -1),
    ]
    mask_split = polygon_mask(x_data, y_data, [polygon_split], None)
    numpy.testing.assert_array_equal(
        mask_split,
        numpy.array(
            [
                [False, False, False, False, False, True],
                [False, False, False, False, False, True],
                [False, False, False, False, True, True],
                [False, False, False, False, True, True],
                [False, False, False, True, True, True],
                [False, False, False, True, True, True],
            ],
        ),
    )

    # Polygon resulting in several intersection polygons
    polygon_multi: list[tuple[float, float]] = [
        (-1, -1),
        (-1, 2.5),
        (2.5, 2.5),
        (2.5, -1),
        (4.5, -1),
        (4.5, 6),
        (6, 6),
        (6, -1),
        (-1, -1),
    ]
    mask_multi = polygon_mask(x_data, y_data, [polygon_multi], None)
    numpy.testing.assert_array_equal(
        mask_multi,
        numpy.array(
            [
                [False, False, False, True, True, False],
                [False, False, False, True, True, False],
                [False, False, False, True, True, False],
                [True, True, True, True, True, False],
                [True, True, True, True, True, False],
                [True, True, True, True, True, False],
            ],
        ),
    )

    # Polygon not intersecting data
    polygon_out: list[tuple[float, float]] = [
        (-1, -1),
        (-1, -2),
        (6, -2),
        (6, -1),
        (-1, -1),
    ]
    mask_out = polygon_mask(x_data, y_data, [polygon_out], None)
    numpy.testing.assert_array_equal(mask_out, numpy.full((1), True))


@pytest.mark.parametrize(
    "file_name",
    ["N43E006.hgt", "N43E006.tiff"],
)
def test_calcHgtArea(file_name: str) -> None:
    with handle_optional_geotiff_support():
        bbox: tuple[float, float, float, float] = calcHgtArea(
            [(os.path.join(TEST_DATA_PATH, file_name), False)],
            0,
            0,
        )
        assert bbox == (MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)


def test_clip_polygons() -> None:
    clip_polygon: list[tuple[float, float]] = [
        (-0.1, 48.900000000009435),
        (-0.1, 50.1),
        (1.1, 50.1),
        (1.1, 48.900000000009435),
        (-0.1, 48.900000000009435),
    ]
    # Multi-polygons in input
    polygons: list[list[tuple[float, float]]] = [
        # Real intersection is a polygon + a line; line must be discarded properly
        [
            (2.3, 51.6),
            (2.5, 51.3),
            (2.4, 50.9),
            (1.3, 50.1),
            (0.7, 50.1),
            (0.4, 49.9),
            (-0.5, 50.0),
            (-0.9, 49.8),
            (-2.2, 49.7),
            (-2.9, 49.8),
        ],
        # No intersection
        [
            (-14.6, 57.6),
            (-14.6, 57.9),
            (-13.9, 58.4),
            (-13.2, 58.3),
            (-12.8, 57.9),
            (-12.9, 57.1),
            (-13.4, 56.8),
            (-14.2, 56.9),
            (-14.6, 57.3),
            (-14.6, 57.6),
        ],
        # Single point intersection
        [
            (2, 52),
            (2, 50.1),
            (1.1, 50.1),
            (1.1, 52),
            (2, 52),
        ],
        # Single line intersection
        [
            (2, 48),
            (2, 50),
            (1.1, 50),
            (1.1, 48),
            (2, 48),
        ],
    ]

    clipped_polygons = clip_polygons(polygons, clip_polygon)
    assert clipped_polygons == [
        [
            (0.4, 49.9),
            (-0.1, 49.955555555555556),
            (-0.1, 50.1),
            (0.7, 50.1),
            (0.4, 49.9),
        ],
    ]
