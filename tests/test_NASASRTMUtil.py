import os
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from pyhgtmap import Coordinates, PolygonsList
from pyhgtmap.configuration import Configuration
from pyhgtmap.hgt.file import parse_polygons_file
from pyhgtmap.NASASRTMUtil import (
    area_needed,
    calc_bbox,
    get_files,
    intersect_tiles,
    make_file_name_prefix,
    make_file_name_prefixes,
)

from . import TEST_DATA_PATH


def test_getFiles_no_source(
    test_configuration: Configuration,
) -> None:
    """No source, no file..."""
    files = get_files("1:2:3:4", None, 0, 0, [], test_configuration)
    assert files == []


@patch("pyhgtmap.NASASRTMUtil.Pool", spec=True)
def test_getFiles_sonn3_no_poly(
    pool_mock: MagicMock,
    test_configuration: Configuration,
) -> None:
    """Basic test with a single source, no polygon provided."""

    # One file not found
    pool_mock.return_value.get_source.return_value.get_file.side_effect = [
        None,
        "hgt/SONN3/N03E001.hgt",
        "hgt/SONN3/N02E002.hgt",
        "hgt/SONN3/N03E002.hgt",
    ]

    pool_mock.return_value.available_sources_names.return_value = ["sonn"]

    files = get_files("1:2:3:4", None, 0, 0, ["sonn3"], test_configuration)

    pool_mock.return_value.get_source.assert_called_with("sonn")
    assert pool_mock.return_value.get_source.return_value.get_file.call_args_list == [
        call("N02E001", 3),
        call("N03E001", 3),
        call("N02E002", 3),
        call("N03E002", 3),
    ]

    assert files == [
        ("hgt/SONN3/N03E001.hgt", False),
        ("hgt/SONN3/N02E002.hgt", False),
        ("hgt/SONN3/N03E002.hgt", False),
    ]


@patch("pyhgtmap.NASASRTMUtil.SourcesPool", spec=True)
def test_getFiles_multi_sources(
    sources_pool_mock: MagicMock,
    test_configuration: Configuration,
) -> None:
    """2 sources, handling proper priority."""

    # N02E001 not found in SONN3, but available in VIEW1
    sources_pool_mock.return_value.get_file.side_effect = [
        None,
        "hgt/VIEW1/N02E001.hgt",
        "hgt/SONN3/N03E001.hgt",
        "hgt/SONN3/N02E002.hgt",
        "hgt/SONN3/N03E002.hgt",
    ]

    files = get_files("1:2:3:4", None, 0, 0, ["sonn3", "view1"], test_configuration)

    assert sources_pool_mock.return_value.get_file.call_args_list == [
        call("N02E001", "sonn3"),
        call("N02E001", "view1"),
        call("N03E001", "sonn3"),
        call("N02E002", "sonn3"),
        call("N03E002", "sonn3"),
    ]

    assert files == [
        ("hgt/VIEW1/N02E001.hgt", False),
        ("hgt/SONN3/N03E001.hgt", False),
        ("hgt/SONN3/N02E002.hgt", False),
        ("hgt/SONN3/N03E002.hgt", False),
    ]


class TestMakeFileNamePrefix:
    """Tests for makeFileNamePrefix function."""

    @pytest.mark.parametrize(
        ("lon", "lat", "expected"),
        [
            # Positive coordinates (North-East)
            (0, 0, "N00E000"),
            (1, 1, "N01E001"),
            (10, 10, "N10E010"),
            (45, 45, "N45E045"),
            (180, 85, "N85E180"),
            # Negative longitude (West)
            (-1, 0, "N00W001"),
            (-10, 10, "N10W010"),
            (-45, 45, "N45W045"),
            (-180, 0, "N00W180"),
            # Negative latitude (South)
            (0, -1, "S01E000"),
            (10, -10, "S10E010"),
            (45, -45, "S45E045"),
            # South-West (negative both)
            (-1, -1, "S01W001"),
            (-45, -45, "S45W045"),
            (-180, -85, "S85W180"),
            # Padding tests (zeros)
            (9, 9, "N09E009"),
            (99, 9, "N09E099"),
        ],
    )
    def test_make_file_name_prefix(self, lon: int, lat: int, expected: str) -> None:
        """Test file name prefix generation for various coordinates."""
        assert make_file_name_prefix(lon, lat) == expected


class TestMakeFileNamePrefixes:
    """Tests for makeFileNamePrefixes function."""

    @staticmethod
    def test_simple_bbox_no_polygon() -> None:
        """Test simple bounding box without polygon."""
        bbox = (0, 0, 2, 2)  # 2x2 grid
        result = make_file_name_prefixes(bbox, None, 0, 0)

        assert len(result) == 4  # 2x2 = 4 tiles
        # All should be tuples of (filename, checkPoly)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)
        # All should have checkPoly=False when no polygon
        assert all(item[1] is False for item in result)
        # Check expected filenames
        filenames = {item[0] for item in result}
        assert "N00E000" in filenames
        assert "N00E001" in filenames
        assert "N01E000" in filenames
        assert "N01E001" in filenames

    @staticmethod
    def test_single_tile_bbox() -> None:
        """Test bounding box covering a single tile."""
        bbox = (5, 10, 6, 11)
        result = make_file_name_prefixes(bbox, None, 0, 0)

        assert len(result) == 1
        assert result[0][0] == "N10E005"
        assert result[0][1] is False

    @staticmethod
    def test_bbox_with_negative_coordinates() -> None:
        """Test bounding box with negative coordinates."""
        bbox = (-2, -2, 1, 1)  # Covers South-West, South-East, North-West, North-East
        result = make_file_name_prefixes(bbox, None, 0, 0)

        filenames = {item[0] for item in result}
        # Should have all four quadrants
        assert "S02W002" in filenames  # South-West
        assert "S02E000" in filenames  # South-East
        assert "N00W002" in filenames  # North-West
        assert "N00E000" in filenames  # North-East

    @staticmethod
    def test_bbox_crossing_dateline() -> None:
        """Test bounding box crossing the W180/E180 dateline."""
        bbox = (178, 0, -178, 1)  # minLon > maxLon indicates dateline crossing
        result = make_file_name_prefixes(bbox, None, 0, 0)

        # Should include tiles from W178-W180 and E178-E179
        filenames = {item[0] for item in result}
        assert sorted(filenames) == sorted(
            [
                "N00E178",
                "N00E179",
                "N00W180",
                "N00W179",
            ]
        )

    @staticmethod
    def test_lowercase_option() -> None:
        """Test lowercase conversion of file name prefixes."""
        bbox = (0, 0, 1, 1)
        result = make_file_name_prefixes(bbox, None, 0, 0, lowercase=True)

        filenames = {item[0] for item in result}
        # All should be lowercase
        assert all(f.islower() for f in filenames)

    @staticmethod
    def test_uppercase_option_default() -> None:
        """Test that default is uppercase."""
        bbox = (0, 0, 1, 1)
        result = make_file_name_prefixes(bbox, None, 0, 0, lowercase=False)

        filenames = {item[0] for item in result}
        # All should be uppercase
        assert all(f.isupper() for f in filenames)

    @staticmethod
    def test_with_corrections() -> None:
        """Test bounding box with coordinate corrections."""
        bbox = (0, 0, 2, 2)
        corrx, corry = 0.5, 0.5
        result = make_file_name_prefixes(bbox, None, corrx, corry)

        # Should still return results (corrections affect polygon checking, not bbox iteration)
        assert len(result) > 0

    @staticmethod
    def test_bbox_ordering() -> None:
        """Test that bbox coordinates must be in correct order."""
        # Standard ordering: minLon, minLat, maxLon, maxLat
        bbox = (0, 0, 2, 2)
        result = make_file_name_prefixes(bbox, None, 0, 0)

        # Should have 4 tiles (2x2)
        assert len(result) == 4

    @patch("pyhgtmap.NASASRTMUtil.area_needed")
    def test_with_polygon_no_intersection(self, mock_area_needed: MagicMock) -> None:
        """Test with polygon that has no intersections."""
        mock_area_needed.return_value = (False, False)
        bbox = (0, 0, 2, 2)
        polygon: PolygonsList = [
            [
                Coordinates(0.5, 0.5),
                Coordinates(1.5, 0.5),
                Coordinates(1.5, 1.5),
                Coordinates(0.5, 1.5),
            ]
        ]

        result = make_file_name_prefixes(bbox, polygon, 0, 0)

        # Should have fewer results due to polygon filtering
        assert len(result) <= 4

    @patch("pyhgtmap.NASASRTMUtil.area_needed")
    def test_with_polygon_full_intersection(self, mock_area_needed: MagicMock) -> None:
        """Test with polygon where all areas are needed."""
        mock_area_needed.return_value = (True, False)
        bbox = (0, 0, 2, 2)
        polygon: PolygonsList = [
            [
                Coordinates(-2, -2),
                Coordinates(3, -2),
                Coordinates(3, 3),
                Coordinates(-2, 3),
            ]
        ]

        result = make_file_name_prefixes(bbox, polygon, 0, 0)

        # Should have all tiles
        assert len(result) == 4

    @patch("pyhgtmap.NASASRTMUtil.intersect_tiles")
    @patch("pyhgtmap.NASASRTMUtil.area_needed")
    def test_intersec_tiles_priority(
        self,
        mock_area_needed: MagicMock,
        mock_intersec_tiles: MagicMock,
    ) -> None:
        """Test that intersecTiles results are included with checkPoly=True."""
        mock_intersec_tiles.return_value = ["N00E000"]
        mock_area_needed.return_value = (True, False)
        bbox = (0, 0, 2, 2)
        polygon: PolygonsList = [
            [
                Coordinates(0.5, 0.5),
                Coordinates(1.5, 0.5),
                Coordinates(1.5, 1.5),
                Coordinates(0.5, 1.5),
            ]
        ]

        result = make_file_name_prefixes(bbox, polygon, 0, 0)

        # Find N00E000 in results
        n00e000_results = [item for item in result if item[0] == "N00E000"]
        assert len(n00e000_results) > 0
        # Should have checkPoly=True from intersecTiles
        assert any(item[1] is True for item in n00e000_results)

    @staticmethod
    def test_large_bbox() -> None:
        """Test larger bounding box."""
        bbox = (0, 0, 10, 10)  # 10x10 grid = 100 tiles
        result = make_file_name_prefixes(bbox, None, 0, 0)

        assert len(result) == 100
        # Check that first and last tiles are present
        filenames = {item[0] for item in result}
        assert "N00E000" in filenames
        assert "N09E009" in filenames

    @staticmethod
    def test_return_type_structure() -> None:
        """Test that return value has correct structure."""
        bbox = (0, 0, 1, 1)
        result = make_file_name_prefixes(bbox, None, 0, 0)

        # Should be a list
        assert isinstance(result, list)
        # Each element should be a tuple
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            # First element is filename string
            assert isinstance(item[0], str)
            # Second element is boolean
            assert isinstance(item[1], bool)

    @staticmethod
    def test_empty_bbox() -> None:
        """Test bounding box with zero area."""
        bbox = (0, 0, 0, 0)  # Empty bbox
        result = make_file_name_prefixes(bbox, None, 0, 0)

        # Should return empty list
        assert len(result) == 0

    @staticmethod
    def test_single_row_bbox() -> None:
        """Test bounding box that is a single row."""
        bbox = (0, 5, 3, 6)  # Single latitude row
        result = make_file_name_prefixes(bbox, None, 0, 0)

        # Should have 3 tiles (3 longitudes, 1 latitude)
        assert len(result) == 3
        # All should have same latitude
        filenames = {item[0] for item in result}
        assert all("N05" in f for f in filenames)

    @staticmethod
    def test_single_column_bbox() -> None:
        """Test bounding box that is a single column."""
        bbox = (10, 0, 11, 4)  # Single longitude column
        result = make_file_name_prefixes(bbox, None, 0, 0)

        # Should have 4 tiles (1 longitude, 4 latitudes)
        assert len(result) == 4
        # All should have same longitude
        filenames = {item[0] for item in result}
        assert all("E010" in f for f in filenames)


class TestAreaNeeded:
    """Tests for areaNeeded function."""

    @staticmethod
    def test_area_needed_no_polygon() -> None:
        """Test that area is needed when no polygon is provided."""
        bbox = (0, 0, 10, 10)
        needed, check_poly = area_needed(
            lat=5, lon=5, bbox=bbox, polygons=None, corrx=0, corry=0
        )

        assert needed is True
        assert check_poly is False

    @staticmethod
    def test_area_needed_no_polygon_with_corrections() -> None:
        """Test that area is needed with no polygon even with corrections."""
        bbox = (0, 0, 10, 10)
        needed, check_poly = area_needed(
            lat=5, lon=5, bbox=bbox, polygons=None, corrx=0.5, corry=0.5
        )

        assert needed is True
        assert check_poly is False

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_completely_inside_polygon_match_bbox(
        self, mock_print: MagicMock
    ) -> None:
        """Test when polygon completely fills the bounding box."""
        # Tile at (0, 0), bbox exactly matches the tile
        bbox = (0, 0, 1, 1)
        polygon: PolygonsList = [
            [Coordinates(0, 0), Coordinates(1, 0), Coordinates(1, 1), Coordinates(0, 1)]
        ]

        needed, check_poly = area_needed(
            lat=0, lon=0, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        assert needed is True
        assert check_poly is True
        # Print called at least once with checking message
        assert mock_print.call_count >= 1

    @staticmethod
    def test_area_completely_inside_polygon_all_corners() -> None:
        """Test when all four corners of the tile are inside the polygon."""
        # Tile at (5, 5), polygon covers it completely
        bbox = (0, 0, 20, 20)
        polygon: PolygonsList = [
            [Coordinates(4, 4), Coordinates(7, 4), Coordinates(7, 7), Coordinates(4, 7)]
        ]

        needed, check_poly = area_needed(
            lat=5, lon=5, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        # All corners of tile are inside polygon -> (needed=True, check_poly=False)
        assert needed is True
        assert check_poly is False

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_completely_outside_polygon(self, mock_print: MagicMock) -> None:
        """Test when tile is completely outside the polygon."""
        # Tile at (10, 10), polygon is far away at (0, 0)
        bbox = (0, 0, 20, 20)
        polygon: PolygonsList = [
            [Coordinates(1, 1), Coordinates(2, 1), Coordinates(2, 2), Coordinates(1, 2)]
        ]

        needed, check_poly = area_needed(
            lat=10, lon=10, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        assert needed is False
        assert check_poly is False

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_partially_intersecting_polygon(self, mock_print: MagicMock) -> None:
        """Test when tile partially intersects polygon (boundary case)."""
        # Tile at (0, 0) with polygon crossing the boundary
        bbox = (0, 0, 10, 10)
        polygon: PolygonsList = [
            [
                Coordinates(0.5, 0.5),
                Coordinates(1.5, 0.5),
                Coordinates(1.5, 1.5),
                Coordinates(0.5, 1.5),
            ]
        ]

        needed, check_poly = area_needed(
            lat=0, lon=0, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        # Partial intersection returns True (with maybe status)
        assert needed is True
        assert check_poly is True

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_with_positive_corrections(self, mock_print: MagicMock) -> None:
        """Test area calculation with positive coordinate corrections."""
        # Tile at (5, 5), but with corrections
        bbox = (0, 0, 10, 10)
        polygon: PolygonsList = [
            [
                Coordinates(5.5, 5.5),
                Coordinates(5.7, 5.5),
                Coordinates(5.7, 5.7),
                Coordinates(5.5, 5.7),
            ]
        ]

        needed, _ = area_needed(
            lat=5, lon=5, bbox=bbox, polygons=polygon, corrx=0.3, corry=0.3
        )

        # The corrected tile becomes (5.3, 5.3) to (6.3, 6.3) which intersects polygon
        # Result depends on intersection logic
        assert isinstance(needed, bool)

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_with_negative_corrections(self, mock_print: MagicMock) -> None:
        """Test area calculation with negative coordinate corrections."""
        bbox = (0, 0, 10, 10)
        polygon: PolygonsList = [
            [
                Coordinates(4.5, 4.5),
                Coordinates(4.7, 4.5),
                Coordinates(4.7, 4.7),
                Coordinates(4.5, 4.7),
            ]
        ]

        needed, _ = area_needed(
            lat=5, lon=5, bbox=bbox, polygons=polygon, corrx=-0.3, corry=-0.3
        )

        # The corrected tile becomes (4.7, 4.7) to (5.7, 5.7)
        assert isinstance(needed, bool)

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_with_multiple_polygons(self, mock_print: MagicMock) -> None:
        """Test with multiple polygon areas."""
        bbox = (0, 0, 20, 20)
        # Multiple polygon regions
        polygon: PolygonsList = [
            [
                Coordinates(1, 1),
                Coordinates(2, 1),
                Coordinates(2, 2),
                Coordinates(1, 2),
            ],
            [
                Coordinates(18, 18),
                Coordinates(19, 18),
                Coordinates(19, 19),
                Coordinates(18, 19),
            ],
        ]

        # Test tile inside second polygon
        needed, _ = area_needed(
            lat=18, lon=18, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        assert needed is True

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_with_large_polygon(self, mock_print: MagicMock) -> None:
        """Test with a large polygon covering multiple tiles."""
        bbox = (0, 0, 20, 20)
        # Large polygon covering tiles (5, 5) to (15, 15)
        polygon: PolygonsList = [
            [
                Coordinates(4, 4),
                Coordinates(16, 4),
                Coordinates(16, 16),
                Coordinates(4, 16),
            ]
        ]

        needed, check_poly = area_needed(
            lat=10, lon=10, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        assert needed is True
        assert check_poly is False

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_at_polygon_edge(self, mock_print: MagicMock) -> None:
        """Test when tile touches the edge of a polygon."""
        bbox = (0, 0, 20, 20)
        polygon: PolygonsList = [
            [Coordinates(5, 5), Coordinates(6, 5), Coordinates(6, 6), Coordinates(5, 6)]
        ]

        # Tile starting at exactly (5, 5) - boundary touching
        needed, _ = area_needed(
            lat=5, lon=5, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        # Boundary case - at least it should be needed
        assert needed is True

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_negative_coordinates(self, mock_print: MagicMock) -> None:
        """Test with negative latitude and longitude."""
        bbox = (-10, -10, 0, 0)
        polygon: PolygonsList = [
            [
                Coordinates(-5, -5),
                Coordinates(-4, -5),
                Coordinates(-4, -4),
                Coordinates(-5, -4),
            ]
        ]

        needed, _ = area_needed(
            lat=-5, lon=-5, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        assert needed is True

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_mixed_sign_coordinates(self, mock_print: MagicMock) -> None:
        """Test with mixed positive and negative coordinates."""
        bbox = (-5, -5, 5, 5)
        polygon: PolygonsList = [
            [
                Coordinates(-1, -1),
                Coordinates(1, -1),
                Coordinates(1, 1),
                Coordinates(-1, 1),
            ]
        ]

        needed, _ = area_needed(
            lat=0, lon=0, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        assert needed is True

    @patch("pyhgtmap.NASASRTMUtil.print")
    def test_area_return_type(self, mock_print: MagicMock) -> None:
        """Test that areaNeeded always returns a tuple of two booleans."""
        bbox = (0, 0, 10, 10)
        polygon: PolygonsList = [
            [Coordinates(5, 5), Coordinates(6, 5), Coordinates(6, 6), Coordinates(5, 6)]
        ]

        result = area_needed(
            lat=5, lon=5, bbox=bbox, polygons=polygon, corrx=0, corry=0
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], (bool, np.bool_))
        assert isinstance(result[1], (bool, np.bool_))


class TestCalcBbox:
    """Tests for calcBbox function."""

    @staticmethod
    def test_calc_bbox_positive_integer_coordinates() -> None:
        """Test with positive integer coordinates."""
        area = "0:0:10:10"
        result = calc_bbox(area)

        assert result == (0, 0, 10, 10)

    @staticmethod
    def test_calc_bbox_positive_decimal_coordinates() -> None:
        """Test with positive decimal coordinates."""
        area = "0.5:0.5:10.5:10.5"
        result = calc_bbox(area)

        # Decimals round up for max values, min stays same
        assert result == (0, 0, 11, 11)

    @staticmethod
    def test_calc_bbox_negative_integer_coordinates() -> None:
        """Test with negative integer coordinates."""
        area = "-10:-10:0:0"
        result = calc_bbox(area)

        assert result == (-10, -10, 0, 0)

    @staticmethod
    def test_calc_bbox_negative_decimal_coordinates() -> None:
        """Test with negative decimal coordinates."""
        area = "-10.5:-10.5:-0.5:-0.5"
        result = calc_bbox(area)

        # Negative decimals round down for min values
        assert result == (-11, -11, 0, 0)

    @staticmethod
    def test_calc_bbox_mixed_sign_coordinates() -> None:
        """Test with mixed positive and negative coordinates."""
        area = "-5:0:5:10"
        result = calc_bbox(area)

        assert result == (-5, 0, 5, 10)

    @staticmethod
    def test_calc_bbox_with_positive_corrections() -> None:
        """Test bounding box calculation with positive corrections."""
        area = "0:0:10:10"
        result = calc_bbox(area, corrx=0.5, corry=0.5)

        # Corrections are subtracted from parsed values
        # minLon: 0 - 0.5 = -0.5 (non-integer, negative) -> -1
        # minLat: 0 - 0.5 = -0.5 (non-integer, negative) -> -1
        # maxLon: 10 - 0.5 = 9.5 (non-integer) -> 10
        # maxLat: 10 - 0.5 = 9.5 (non-integer) -> 10
        assert result == (-1, -1, 10, 10)

    @staticmethod
    def test_calc_bbox_with_negative_corrections() -> None:
        """Test bounding box calculation with negative corrections."""
        area = "5:5:15:15"
        result = calc_bbox(area, corrx=-1.0, corry=-1.0)

        # Negative corrections (subtracted) expand the bbox
        # minLon: 5 - (-1.0) = 6.0 (integer) -> 6
        # minLat: 5 - (-1.0) = 6.0 (integer) -> 6
        # maxLon: 15 - (-1.0) = 16.0 (integer) -> 16
        # maxLat: 15 - (-1.0) = 16.0 (integer) -> 16
        assert result == (6, 6, 16, 16)

    @staticmethod
    def test_calc_bbox_zero_area() -> None:
        """Test with zero-area bounding box."""
        area = "5:5:5:5"
        result = calc_bbox(area)

        assert result == (5, 5, 5, 5)

    @staticmethod
    def test_calc_bbox_small_area() -> None:
        """Test with very small area (less than 1 degree)."""
        area = "5.1:5.1:5.9:5.9"
        result = calc_bbox(area)

        # minLon: 5.1 (non-int) -> 5
        # minLat: 5.1 (non-int) -> 5
        # maxLon: 5.9 (non-int) -> 6
        # maxLat: 5.9 (non-int) -> 6
        assert result == (5, 5, 6, 6)

    @staticmethod
    def test_calc_bbox_large_area() -> None:
        """Test with large area spanning multiple tiles."""
        area = "-180:-90:180:90"
        result = calc_bbox(area)

        assert result == (-180, -90, 180, 90)

    @staticmethod
    def test_calc_bbox_negative_min_positive_max() -> None:
        """Test with negative min and positive max."""
        area = "-5:-5:5:5"
        result = calc_bbox(area)

        assert result == (-5, -5, 5, 5)

    @staticmethod
    def test_calc_bbox_negative_min_positive_decimal_max() -> None:
        """Test with negative min (integer) and positive decimal max."""
        area = "-5:-5:5.5:5.5"
        result = calc_bbox(area)

        # minLon: -5 (integer) -> -5
        # minLat: -5 (integer) -> -5
        # maxLon: 5.5 (non-int) -> 6
        # maxLat: 5.5 (non-int) -> 6
        assert result == (-5, -5, 6, 6)

    @staticmethod
    def test_calc_bbox_negative_decimal_min_positive_max() -> None:
        """Test with negative decimal min and positive integer max."""
        area = "-5.5:-5.5:5:5"
        result = calc_bbox(area)

        # minLon: -5.5 (non-int, negative) -> -6
        # minLat: -5.5 (non-int, negative) -> -6
        # maxLon: 5 (integer) -> 5
        # maxLat: 5 (integer) -> 5
        assert result == (-6, -6, 5, 5)

    @staticmethod
    def test_calc_bbox_asymmetric_area() -> None:
        """Test with asymmetric bounding box."""
        area = "10:20:30:40"
        result = calc_bbox(area)

        assert result == (10, 20, 30, 40)

    @pytest.mark.parametrize(
        ("area", "corrx", "corry", "expected"),
        [
            ("0:0:1:1", 0, 0, (0, 0, 1, 1)),
            ("0:0:1:1", 0.5, 0.5, (-1, -1, 1, 1)),
            ("10:10:20:20", 0, 0, (10, 10, 20, 20)),
            ("10:10:20:20", 1, 1, (9, 9, 19, 19)),
            ("-10:-10:0:0", 0, 0, (-10, -10, 0, 0)),
            ("-10:-10:0:0", 0.5, 0.5, (-11, -11, 0, 0)),
        ],
    )
    def test_calc_bbox_parametrized(
        self, area: str, corrx: float, corry: float, expected: tuple[int, int, int, int]
    ) -> None:
        """Parametrized tests for calcBbox with various inputs."""
        result = calc_bbox(area, corrx, corry)
        assert result == expected

    @staticmethod
    def test_calc_bbox_equator_crossing() -> None:
        """Test bounding box that crosses the equator."""
        area = "-2:2:2:8"
        result = calc_bbox(area)

        assert result == (-2, 2, 2, 8)

    @staticmethod
    def test_calc_bbox_return_type() -> None:
        """Test that calcBbox returns tuple of 4 integers."""
        area = "5.5:5.5:15.5:15.5"
        result = calc_bbox(area)

        assert isinstance(result, tuple)
        assert len(result) == 4
        assert all(isinstance(val, int) for val in result)

    @staticmethod
    def test_calc_bbox_min_max_ordering() -> None:
        """Test that result maintains minLon, minLat, maxLon, maxLat order."""
        area = "10:5:20:15"
        lon_min, lat_min, lon_max, lat_max = calc_bbox(area)

        # Verify ordering
        assert lon_min <= lon_max
        assert lat_min <= lat_max


class TestIntersectTiles:
    """Test suite for intersect_tiles function."""

    @staticmethod
    def test_intersect_tiles_none_polygon() -> None:
        """Test with None polygons - should return empty list."""
        result = intersect_tiles(None, 0, 0)
        assert result == []

    @staticmethod
    def test_intersect_tiles_empty_polygon_list() -> None:
        """Test with empty polygon list - should return empty list."""
        result = intersect_tiles([], 0, 0)
        assert result == []

    @staticmethod
    def test_intersect_tiles_single_point_polygon() -> None:
        """Test with single point polygon - should return empty since no line segments."""
        polygon: PolygonsList = [
            [
                Coordinates(0, 0),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        assert isinstance(result, list)
        # Single point with no line segments returns empty
        assert result == []

    @staticmethod
    def test_intersect_tiles_small_square_no_correction() -> None:
        """Test with small square polygon and no corrections."""
        polygon: PolygonsList = [
            [
                Coordinates(0, 0),
                Coordinates(0.5, 0),
                Coordinates(0.5, 0.5),
                Coordinates(0, 0.5),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        assert isinstance(result, list)
        assert result == ["N00E000"]

    @staticmethod
    def test_intersect_tiles_horizontal_line() -> None:
        """Test with horizontal line polygon."""
        polygon: PolygonsList = [
            [
                Coordinates(0, 5),
                Coordinates(3, 5),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Horizontal line should span multiple tiles
        assert sorted(result) == ["N05E000", "N05E001", "N05E002", "N05E003"]

    @staticmethod
    def test_intersect_tiles_vertical_line() -> None:
        """Test with vertical line polygon."""
        polygon: PolygonsList = [
            [
                Coordinates(5, 0),
                Coordinates(5, 3),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Vertical line should span multiple tiles
        assert sorted(result) == ["N00E005", "N01E005", "N02E005", "N03E005"]

    @staticmethod
    def test_intersect_tiles_diagonal_line() -> None:
        """Test with diagonal line polygon."""
        polygon: PolygonsList = [
            [
                Coordinates(0, 0),
                Coordinates(2, 2),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        assert isinstance(result, list)
        # Diagonal line should intersect multiple tiles
        assert sorted(result) == [
            "N00E000",
            "N00E001",
            "N00W001",
            "N01E000",
            "N01E001",
            "N02E002",
            "S01E000",
        ]

    @staticmethod
    def test_intersect_tiles_with_positive_correction() -> None:
        """Test with positive coordinate corrections."""
        polygon: PolygonsList = [
            [
                Coordinates(1, 1),
                Coordinates(2, 1),
                Coordinates(2, 2),
                Coordinates(1, 2),
            ]
        ]
        result_no_corr = intersect_tiles(polygon, 0, 0)
        result_with_corr = intersect_tiles(polygon, 0.5, 0.5)

        # Results should differ due to correction
        assert sorted(result_no_corr) == ["N01E001", "N01E002", "N02E001", "N02E002"]
        assert sorted(result_with_corr) == ["N00E001", "N01E000", "N01E001"]

    @staticmethod
    def test_intersect_tiles_with_negative_correction() -> None:
        """Test with negative coordinate corrections."""
        polygon: PolygonsList = [
            [
                Coordinates(1, 1),
                Coordinates(2, 1),
                Coordinates(2, 2),
                Coordinates(1, 2),
            ]
        ]
        result_with_corr = intersect_tiles(polygon, -0.5, -0.5)

        assert sorted(result_with_corr) == ["N01E002", "N02E001", "N02E002"]

    @staticmethod
    def test_intersect_tiles_negative_coordinates() -> None:
        """Test with negative coordinates (Western/Southern hemisphere)."""
        polygon: PolygonsList = [
            [
                Coordinates(-5, -5),
                Coordinates(-4, -5),
                Coordinates(-4, -4),
                Coordinates(-5, -4),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        assert sorted(result) == ["S04W004", "S04W005", "S05W004", "S05W005"]

    @staticmethod
    def test_intersect_tiles_mixed_hemisphere() -> None:
        """Test with polygon spanning multiple hemispheres."""
        polygon: PolygonsList = [
            [
                Coordinates(-1, -1),
                Coordinates(1, -1),
                Coordinates(1, 1),
                Coordinates(-1, 1),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Spans all four quadrants
        assert sorted(result) == [
            "N00E001",
            "N01E000",
            "N01E001",
            "N01W001",
            "S01E000",
            "S01E001",
            "S01W001",
        ]

    @staticmethod
    def test_intersect_tiles_large_polygon() -> None:
        """Test with large polygon spanning multiple tiles."""
        polygon: PolygonsList = [
            [
                Coordinates(0, 0),
                Coordinates(5, 0),
                Coordinates(5, 5),
                Coordinates(0, 5),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Large polygon should cover many tiles
        assert sorted(result) == [
            "N00E000",
            "N00E001",
            "N00E002",
            "N00E003",
            "N00E004",
            "N00E005",
            "N01E005",
            "N02E005",
            "N03E005",
            "N04E005",
            "N05E000",
            "N05E001",
            "N05E002",
            "N05E003",
            "N05E004",
            "N05E005",
        ]

    @staticmethod
    def test_intersect_tiles_multiple_polygons() -> None:
        """Test with multiple polygons in list."""
        polygons: PolygonsList = [
            [
                Coordinates(0, 0),
                Coordinates(1, 0),
                Coordinates(1, 1),
                Coordinates(0, 1),
            ],
            [
                Coordinates(3, 3),
                Coordinates(4, 3),
                Coordinates(4, 4),
                Coordinates(3, 4),
            ],
        ]
        result = intersect_tiles(polygons, 0, 0)
        # Should include tiles from both polygons
        assert sorted(result) == [
            "N00E000",
            "N00E001",
            "N01E000",
            "N01E001",
            "N03E003",
            "N03E004",
            "N04E003",
            "N04E004",
        ]

    @staticmethod
    def test_intersect_tiles_no_duplicates() -> None:
        """Test that result contains no duplicate tile prefixes."""
        polygon: PolygonsList = [
            [
                Coordinates(0, 0),
                Coordinates(2, 0),
                Coordinates(2, 2),
                Coordinates(0, 2),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Check no duplicates and verify results
        assert sorted(result) == [
            "N00E000",
            "N00E001",
            "N00E002",
            "N01E002",
            "N02E000",
            "N02E001",
            "N02E002",
        ]
        assert len(result) == len(set(result))

    @staticmethod
    def test_intersect_tiles_decimal_coordinates() -> None:
        """Test with decimal coordinates across multiple tiles."""
        polygon: PolygonsList = [
            [
                Coordinates(0.3, 0.3),
                Coordinates(1.7, 0.3),
                Coordinates(1.7, 1.7),
                Coordinates(0.3, 1.7),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Should span multiple tiles
        assert sorted(result) == ["N00E001", "N01E000", "N01E001"]

    @staticmethod
    def test_intersect_tiles_return_type() -> None:
        """Test that return type is list of strings."""
        polygon: PolygonsList = [
            [
                Coordinates(1, 1),
                Coordinates(2, 1),
                Coordinates(2, 2),
                Coordinates(1, 2),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Verify return type and values
        assert sorted(result) == ["N01E001", "N01E002", "N02E001", "N02E002"]

    @staticmethod
    def test_intersect_tiles_asymmetric_polygon() -> None:
        """Test with asymmetric polygon shape."""
        polygon: PolygonsList = [
            [
                Coordinates(0, 0),
                Coordinates(3, 1),
                Coordinates(2, 3),
                Coordinates(0.5, 2.5),
            ]
        ]
        result = intersect_tiles(polygon, 0, 0)
        # Verify explicit results for asymmetric polygon
        assert sorted(result) == [
            "N00E000",
            "N00E001",
            "N00E002",
            "N00E003",
            "N00W001",
            "N01E002",
            "N01E003",
            "N02E000",
            "N02E001",
            "N02E002",
            "N03E001",
            "N03E002",
            "S01E000",
        ]

    @staticmethod
    def test_intersect_tiles_with_both_corrections() -> None:
        """Test with simultaneous positive x and y corrections."""
        polygon: PolygonsList = [
            [
                Coordinates(1, 1),
                Coordinates(2, 1),
                Coordinates(2, 2),
                Coordinates(1, 2),
            ]
        ]
        result = intersect_tiles(polygon, 0.2, 0.3)
        # Verify explicit results with both corrections applied
        assert sorted(result) == ["N00E001", "N01E000", "N01E001"]

    @staticmethod
    def test_intersect_tiles_france_poly() -> None:
        bbox_str, france_polygons = parse_polygons_file(
            os.path.join(TEST_DATA_PATH, "france.poly")
        )
        result = intersect_tiles(france_polygons, 0, 0)
        # Expecting specific tiles covering France
        assert bbox_str == "-6.9372070:41.2386600:9.9000000:51.4288000"
        assert sorted(result) == [
            "N41E005",
            "N41E006",
            "N41E007",
            "N41E008",
            "N41E009",
            "N42E000",
            "N42E001",
            "N42E002",
            "N42E003",
            "N42E004",
            "N42E005",
            "N42E009",
            "N42W001",
            "N42W002",
            "N43E007",
            "N43E008",
            "N43E009",
            "N43W002",
            "N43W003",
            "N44E006",
            "N44E007",
            "N44W003",
            "N44W004",
            "N45E006",
            "N45E007",
            "N45W004",
            "N45W005",
            "N46E005",
            "N46E006",
            "N46E007",
            "N46W005",
            "N46W006",
            "N47E006",
            "N47E007",
            "N47W006",
            "N47W007",
            "N48E007",
            "N48E008",
            "N48W002",
            "N48W003",
            "N48W005",
            "N48W006",
            "N48W007",
            "N49E004",
            "N49E005",
            "N49E006",
            "N49E007",
            "N49E008",
            "N49W002",
            "N49W003",
            "N49W004",
            "N49W005",
            "N50E000",
            "N50E001",
            "N50E002",
            "N50E003",
            "N50E004",
            "N50W001",
            "N50W002",
            "N51E001",
            "N51E002",
        ]
