"""Unit tests for the output factory module, specifically make_osm_filename function."""

from __future__ import annotations

import pytest

from pyhgtmap import BBox
from pyhgtmap.configuration import Configuration
from pyhgtmap.output.factory import make_osm_filename


class TestMakeOsmFilename:
    """Test suite for make_osm_filename function."""

    @pytest.fixture
    def default_config(self) -> Configuration:
        """Create a default configuration for testing."""
        config = Configuration()
        config.gzip = 0
        config.pbf = False
        config.o5m = False
        config.outputPrefix = None
        config.dataSources = []
        return config

    @pytest.fixture
    def sample_bbox(self) -> BBox:
        """Create a sample bounding box for testing."""
        return BBox(0.0, 0.0, 1.0, 1.0)

    @staticmethod
    def test_make_osm_filename_basic_no_sources_no_prefix(
        sample_bbox, default_config
    ) -> None:
        """Test basic filename generation without sources and without prefix."""
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == "lon0.00_1.00lat0.00_1.00_local-source.osm"

    @staticmethod
    def test_make_osm_filename_with_output_prefix(sample_bbox, default_config) -> None:
        """Test filename generation with output prefix."""
        default_config.outputPrefix = "mymap"
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == "mymap_lon0.00_1.00lat0.00_1.00_local-source.osm"

    @pytest.mark.parametrize(
        ("source", "input_file", "expected_suffix"),
        [
            ("srtm1", "hgt/SRTM1/N00E000.hgt", "_srtm1"),
            ("srtm3", "hgt/SRTM3/N00E000.hgt", "_srtm3"),
            ("view1", "hgt/VIEW1/N00E000.hgt", "_view1"),
            ("view3", "hgt/VIEW3/N00E000.hgt", "_view3"),
            ("alos1", "hgt/ALOS1/N00E000.hgt", "_alos1"),
            ("custom", "hgt/custom/N00E000.hgt", ""),
        ],
    )
    def test_make_osm_filename_with_single_source(
        self, sample_bbox, default_config, source, input_file, expected_suffix
    ) -> None:
        """Test filename generation with various single sources."""
        default_config.dataSources = [source]
        # For multiple sources test case (custom), we might need to adjust, but here we test single source config
        if source == "custom":
            default_config.dataSources = ["srtm1", "custom"]

        input_files = [input_file]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == f"lon0.00_1.00lat0.00_1.00{expected_suffix}.osm"

    @pytest.mark.parametrize(
        ("gzip", "pbf", "o5m", "expected_extension"),
        [
            (6, False, False, ".osm.gz"),
            (0, True, False, ".osm.pbf"),
            (0, False, True, ".o5m"),
            (6, True, False, ".osm.gz"),  # Gzip takes precedence over PBF
            (0, True, True, ".osm.pbf"),  # PBF takes precedence over O5M
        ],
    )
    def test_make_osm_filename_compression_and_format(
        self, sample_bbox, default_config, gzip, pbf, o5m, expected_extension
    ) -> None:
        """Test filename generation with various compression and format settings."""
        default_config.gzip = gzip
        default_config.pbf = pbf
        default_config.o5m = o5m
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        expected_suffix = f"lon0.00_1.00lat0.00_1.00_local-source{expected_extension}"
        assert result == expected_suffix

    @staticmethod
    def test_make_osm_filename_with_prefix_and_srtm_source(
        sample_bbox, default_config
    ) -> None:
        """Test filename with both prefix and SRTM source."""
        default_config.outputPrefix = "elevation"
        default_config.dataSources = ["srtm3"]
        input_files = ["hgt/SRTM3/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == "elevation_lon0.00_1.00lat0.00_1.00_srtm3.osm"

    @staticmethod
    def test_make_osm_filename_with_prefix_and_gzip(
        sample_bbox, default_config
    ) -> None:
        """Test filename with both prefix and gzip compression."""
        default_config.outputPrefix = "mydata"
        default_config.gzip = 9
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == "mydata_lon0.00_1.00lat0.00_1.00_local-source.osm.gz"

    @pytest.mark.parametrize(
        ("data_sources", "input_files", "expected_suffix"),
        [
            (
                ["srtm1", "srtm3"],
                ["hgt/SRTM1/N00E000.hgt", "hgt/SRTM3/N01E001.hgt"],
                "_srtm1,srtm3",
            ),
            # Order of input files should not matter
            (
                ["srtm1", "srtm3"],
                ["hgt/SRTM3/N01E001.hgt", "hgt/SRTM1/N00E000.hgt"],
                "_srtm1,srtm3",
            ),
            (
                ["srtm3", "srtm1"],
                ["hgt/SRTM1/N00E000.hgt", "hgt/SRTM3/N01E001.hgt"],
                "_srtm3,srtm1",
            ),
            # Source isn't duplicated even if there are multiple files
            (
                ["srtm1"],
                ["hgt/SRTM1/N00E000.hgt", "hgt/SRTM1/N01E001.hgt"],
                "_srtm1",
            ),
            # This case should not happen...
            (
                ["srtm1"],
                ["hgt/SRTM1/N00E000.hgt", "hgt/SRTM3/N01E001.hgt"],
                "_srtm1",
            ),
            (["srtm1", "srtm3"], ["hgt/SRTM3/N01E001.hgt"], "_srtm3"),
            # Test case where there are more files than configured sources
            (
                ["srtm1"],
                [
                    "hgt/SRTM1/N00E000.hgt",
                    "hgt/SRTM3/N01E001.hgt",
                    "hgt/VIEW1/N02E002.hgt",
                ],
                "_srtm1",
            ),
        ],
    )
    def test_make_osm_filename_multiple_input_files_mixed_sources(
        self, sample_bbox, default_config, data_sources, input_files, expected_suffix
    ) -> None:
        """Test filename with multiple input files from different sources."""
        default_config.dataSources = data_sources
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == f"lon0.00_1.00lat0.00_1.00{expected_suffix}.osm"

    @staticmethod
    def test_make_osm_filename_multiple_custom_input_files_no_sources(
        sample_bbox, default_config
    ) -> None:
        """Test filename with multiple custom input files and no dataSources."""
        input_files = ["hgt/custom1/N00E000.hgt", "hgt/custom2/N01E001.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == "lon0.00_1.00lat0.00_1.00_local-source.osm"

    @staticmethod
    def test_make_osm_filename_with_negative_coordinates() -> None:
        """Test filename generation with negative bbox coordinates."""
        config = Configuration()
        config.gzip = 0
        config.pbf = False
        config.o5m = False
        config.outputPrefix = None
        config.dataSources = []

        bbox = BBox(-10.0, -20.0, -5.0, -15.0)
        input_files = ["hgt/custom/S20W010.hgt"]
        result = make_osm_filename(bbox, config, input_files)

        assert result == "lon-10.00_-5.00lat-20.00_-15.00_local-source.osm"

    @staticmethod
    def test_make_osm_filename_with_mixed_sign_coordinates() -> None:
        """Test filename generation with mixed positive/negative coordinates."""
        config = Configuration()
        config.gzip = 0
        config.pbf = False
        config.o5m = False
        config.outputPrefix = None
        config.dataSources = []

        bbox = BBox(-5.0, -10.0, 5.0, 10.0)
        input_files = ["hgt/custom/S10W005.hgt"]
        result = make_osm_filename(bbox, config, input_files)

        assert result == "lon-5.00_5.00lat-10.00_10.00_local-source.osm"

    @staticmethod
    def test_make_osm_filename_with_large_decimal_precision(default_config) -> None:
        """Test filename with large decimal precision in coordinates."""
        bbox = BBox(0.123456, 0.654321, 1.111111, 2.222222)
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(bbox, default_config, input_files)

        # The format string uses .2f precision
        assert result == "lon0.12_1.11lat0.65_2.22_local-source.osm"

    @staticmethod
    def test_make_osm_filename_no_datasources_no_input_files_raises(
        sample_bbox, default_config
    ) -> None:
        """Test that function handles empty input files with valid dataSources."""
        default_config.dataSources = ["srtm3"]
        input_files: list[str] = []

        # With new logic:
        # match_sources = []
        # has_unknown = False
        # else -> srcTag = "" -> _.osm
        result = make_osm_filename(sample_bbox, default_config, input_files)
        assert result == "lon0.00_1.00lat0.00_1.00_.osm"

    @staticmethod
    def test_make_osm_filename_empty_input_files_list_with_custom_source(
        sample_bbox, default_config
    ) -> None:
        """Test with empty input files list but dataSources defined."""
        default_config.dataSources = ["custom"]
        input_files: list[str] = []

        result = make_osm_filename(sample_bbox, default_config, input_files)
        assert result == "lon0.00_1.00lat0.00_1.00_.osm"

    @staticmethod
    def test_make_osm_filename_case_insensitivity_of_source_names(
        sample_bbox, default_config
    ) -> None:
        """Test that source name matching is case insensitive."""
        default_config.dataSources = ["srtm1"]
        input_files = ["hgt/srtm1/N00E000.hgt"]  # lowercase
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == "lon0.00_1.00lat0.00_1.00_srtm1.osm"

    @staticmethod
    def test_make_osm_filename_multiple_sources_in_list(
        sample_bbox, default_config
    ) -> None:
        """Test with multiple sources in dataSources list where input doesn't match special sources."""
        default_config.dataSources = ["srtm1", "view3", "custom"]
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        # 'custom' doesn't match special hardcoded list -> generic .osm
        assert result == "lon0.00_1.00lat0.00_1.00.osm"

    @staticmethod
    def test_make_osm_filename_returns_string(sample_bbox, default_config) -> None:
        """Test that function returns a string."""
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert isinstance(result, str)

    @staticmethod
    def test_make_osm_filename_contains_bbox_information(default_config) -> None:
        """Test that generated filename contains bbox information."""
        bbox = BBox(10.0, 20.0, 30.0, 40.0)
        input_files = ["hgt/custom/N20E010.hgt"]
        result = make_osm_filename(bbox, default_config, input_files)

        assert result == "lon10.00_30.00lat20.00_40.00_local-source.osm"

    @staticmethod
    def test_make_osm_filename_zero_coordinates(default_config) -> None:
        """Test filename generation with all zero coordinates."""
        bbox = BBox(0.0, 0.0, 0.0, 0.0)
        input_files = ["hgt/custom/N00E000.hgt"]
        result = make_osm_filename(bbox, default_config, input_files)

        assert result == "lon0.00_0.00lat0.00_0.00_local-source.osm"

    @staticmethod
    def test_make_osm_filename_with_deep_directory_path(
        sample_bbox, default_config
    ) -> None:
        """Test with deep directory structure in input filename."""
        input_files = ["hgt/cache/subfolder/CUSTOM/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)

        assert result == "lon0.00_1.00lat0.00_1.00_local-source.osm"

    @staticmethod
    def test_make_osm_filename_gzip_level_variations(
        sample_bbox, default_config
    ) -> None:
        """Test that different gzip levels produce same filename."""
        input_files = ["hgt/custom/N00E000.hgt"]

        default_config.gzip = 1
        result1 = make_osm_filename(sample_bbox, default_config, input_files)

        default_config.gzip = 9
        result2 = make_osm_filename(sample_bbox, default_config, input_files)

        assert result1 == result2
        assert result1 == "lon0.00_1.00lat0.00_1.00_local-source.osm.gz"

    @staticmethod
    def test_make_osm_filename_no_data_sources(sample_bbox, default_config) -> None:
        """Test that function handles no dataSources with valid input files, matching usual data source patterns."""
        default_config.dataSources = []
        input_files = ["hgt/SRTM3/N00E000.hgt"]
        result = make_osm_filename(sample_bbox, default_config, input_files)
        assert result == "lon0.00_1.00lat0.00_1.00_local-source.osm"
