from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy
import pytest

from pyhgtmap import Coordinates, Polygon, PolygonsList, hgt
from pyhgtmap.configuration import Configuration
from pyhgtmap.hgt.file import (
    HgtFile,
    HgtTile,
    calc_hgt_area,
    clip_polygons,
    parse_geotiff_bbox,
    polygon_mask,
)
from tests import TEST_DATA_PATH
from tests.hgt import handle_optional_geotiff_support

if TYPE_CHECKING:
    from pyhgtmap import BBox

HGT_SIZE: int = 1201


def toulon_tiles(
    smooth_ratio: float,
    custom_options: Configuration | None = None,
) -> list[HgtTile]:
    hgt_file = HgtFile(
        os.path.join(TEST_DATA_PATH, "N43E006.hgt"),
        0,
        0,
        smooth_ratio=smooth_ratio,
    )
    # Fake command line parser output
    options = custom_options or Configuration(
        area=None,
        maxNodesPerTile=0,
        contourStepSize=20,
    )
    tiles: list[HgtTile] = hgt_file.make_tiles(options)
    return tiles


@pytest.fixture()
def toulon_tiles_raw() -> list[HgtTile]:
    return toulon_tiles(smooth_ratio=1)


@pytest.fixture()
def toulon_tiles_smoothed() -> list[HgtTile]:
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


class TestHgtFile:
    @staticmethod
    def test_make_tiles_chopped() -> None:
        """Tiles chopped due to nodes threshold."""
        custom_options = Configuration(
            area=None,
            maxNodesPerTile=500000,
            contourStepSize=20,
        )
        tiles: list[HgtTile] = toulon_tiles(1, custom_options)
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
        custom_options = Configuration(
            area="6.2:43.1:7.1:43.8",
            maxNodesPerTile=500000,
            contourStepSize=20,
        )
        tiles: list[HgtTile] = toulon_tiles(1, custom_options)
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
        hgt_file = HgtFile("no-name.not_hgt", 0, 0)
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
        options = Configuration(area=None, maxNodesPerTile=0, contourStepSize=20)
        tiles: list[HgtTile] = hgt_file.make_tiles(options)
        assert tiles == []

    @staticmethod
    @pytest.mark.parametrize(
        "file_name",
        ["N43E006.hgt", "N43E006.tiff"],
    )
    def test_init(file_name: str) -> None:
        """Validate init from various sources types."""
        with handle_optional_geotiff_support():
            hgt_file = HgtFile(os.path.join(TEST_DATA_PATH, file_name), 0, 0)

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
            hgt_file = HgtFile(os.path.join(TEST_DATA_PATH, "N43E006_3857.tiff"), 0, 0)

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
            assert hgt.transform_lon_lats(
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
    polygon_full: Polygon = [
        Coordinates(0, 0),
        Coordinates(0, 5),
        Coordinates(5, 5),
        Coordinates(5, 0),
        Coordinates(0, 0),
    ]
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
    polygon_bigger: Polygon = [
        Coordinates(-1, -1),
        Coordinates(-1, 6),
        Coordinates(6, 6),
        Coordinates(6, -1),
        Coordinates(-1, -1),
    ]
    mask_bigger = polygon_mask(x_data, y_data, [polygon_bigger], None)
    numpy.testing.assert_array_equal(
        mask_bigger,
        numpy.full((x_data.size, y_data.size), False),
    )

    # Polygon splitting data
    polygon_split: Polygon = [
        Coordinates(-1, -1),
        Coordinates(-1, 6),
        Coordinates(2, 6),
        Coordinates(5, -1),
        Coordinates(-1, -1),
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
    polygon_multi: Polygon = [
        Coordinates(-1, -1),
        Coordinates(-1, 2.5),
        Coordinates(2.5, 2.5),
        Coordinates(2.5, -1),
        Coordinates(4.5, -1),
        Coordinates(4.5, 6),
        Coordinates(6, 6),
        Coordinates(6, -1),
        Coordinates(-1, -1),
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
    polygon_out: Polygon = [
        Coordinates(-1, -1),
        Coordinates(-1, -2),
        Coordinates(6, -2),
        Coordinates(6, -1),
        Coordinates(-1, -1),
    ]
    mask_out = polygon_mask(x_data, y_data, [polygon_out], None)
    numpy.testing.assert_array_equal(mask_out, numpy.full((1), True))


@pytest.mark.parametrize(
    "file_name",
    ["N43E006.hgt", "N43E006.tiff"],
)
def test_calcHgtArea(file_name: str) -> None:
    with handle_optional_geotiff_support():
        bbox: BBox = calc_hgt_area(
            [(os.path.join(TEST_DATA_PATH, file_name), False)],
            0,
            0,
        )
        assert bbox == (MIN_LON, MIN_LAT, MAX_LON, MAX_LAT)


def test_clip_polygons() -> None:
    clip_polygon: Polygon = [
        Coordinates(-0.1, 48.900000000009435),
        Coordinates(-0.1, 50.1),
        Coordinates(1.1, 50.1),
        Coordinates(1.1, 48.900000000009435),
        Coordinates(-0.1, 48.900000000009435),
    ]
    # Multi-polygons in input
    polygons: PolygonsList = [
        # Real intersection is a polygon + a line; line must be discarded properly
        [
            Coordinates(2.3, 51.6),
            Coordinates(2.5, 51.3),
            Coordinates(2.4, 50.9),
            Coordinates(1.3, 50.1),
            Coordinates(0.7, 50.1),
            Coordinates(0.4, 49.9),
            Coordinates(-0.5, 50.0),
            Coordinates(-0.9, 49.8),
            Coordinates(-2.2, 49.7),
            Coordinates(-2.9, 49.8),
        ],
        # No intersection
        [
            Coordinates(-14.6, 57.6),
            Coordinates(-14.6, 57.9),
            Coordinates(-13.9, 58.4),
            Coordinates(-13.2, 58.3),
            Coordinates(-12.8, 57.9),
            Coordinates(-12.9, 57.1),
            Coordinates(-13.4, 56.8),
            Coordinates(-14.2, 56.9),
            Coordinates(-14.6, 57.3),
            Coordinates(-14.6, 57.6),
        ],
        # Single point intersection
        [
            Coordinates(2, 52),
            Coordinates(2, 50.1),
            Coordinates(1.1, 50.1),
            Coordinates(1.1, 52),
            Coordinates(2, 52),
        ],
        # Single line intersection
        [
            Coordinates(2, 48),
            Coordinates(2, 50),
            Coordinates(1.1, 50),
            Coordinates(1.1, 48),
            Coordinates(2, 48),
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


def test_parse_geotiff_bbox() -> None:
    # Skip any test using this fixture if GDAL is not installed
    pytest.importorskip("osgeo")
    bbox = parse_geotiff_bbox(os.path.join(TEST_DATA_PATH, "N43E006.tiff"), 0, 0, True)
    assert bbox == pytest.approx((6, 43, 7, 44))


def test_parse_geotiff_bbox_transform() -> None:
    # Skip any test using this fixture if GDAL is not installed
    pytest.importorskip("osgeo")
    bbox = parse_geotiff_bbox(
        os.path.join(TEST_DATA_PATH, "N43E006_3857.tiff"), 0, 0, True
    )
    assert bbox == pytest.approx((6, 43, 7, 44))


def test_parse_geotiff_bbox_no_transform() -> None:
    # Skip any test using this fixture if GDAL is not installed
    pytest.importorskip("osgeo")
    bbox = parse_geotiff_bbox(
        os.path.join(TEST_DATA_PATH, "N43E006_3857.tiff"), 0, 0, False
    )
    assert bbox == pytest.approx((667916.9, 5311972.4, 779236.4, 5465442.7))


def test_parse_geotiff_bbox_non_square() -> None:
    # Skip any test using this fixture if GDAL is not installed
    pytest.importorskip("osgeo")
    with pytest.raises(
        ValueError,
        match="Tile doesn't map to an aligned rectangle in WSG84 coordinates",
    ):
        parse_geotiff_bbox(os.path.join(TEST_DATA_PATH, "lambert.tif"), 0, 0, True)
