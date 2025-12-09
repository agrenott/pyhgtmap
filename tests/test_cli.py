import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from pyhgtmap.cli import parse_command_line


# Existing tests for mutual exclusion
def test_exclusions_gzip_pbf(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_command_line(["--pbf", "--gzip", "1"])
    captured = capsys.readouterr()
    assert "error: argument --gzip: not allowed with argument --pbf" in captured.err


def test_exclusions_gzip_o5m(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_command_line(["--o5m", "--gzip", "1"])
    captured = capsys.readouterr()
    assert "error: argument --gzip: not allowed with argument --o5m" in captured.err


def test_exclusions_o5m_pbf(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_command_line(["--pbf", "--o5m"])
    captured = capsys.readouterr()
    assert "error: argument --o5m: not allowed with argument --pbf" in captured.err


# Tests for parse_command_line function
class TestParseCommandLine:
    """Test suite for parse_command_line function."""

    @staticmethod
    def test_parse_with_area_option() -> None:
        """Test parsing with --area option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1"])

        assert opts.area == "0:0:1:1"
        assert isinstance(opts.dataSources, list)

    @staticmethod
    def test_parse_with_area_and_pbf() -> None:
        """Test parsing with --area and --pbf options."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--pbf"])

        assert opts.area == "0:0:1:1"
        assert opts.pbf is True
        assert opts.gzip == 0
        assert opts.o5m is False

    @staticmethod
    def test_parse_with_area_and_gzip() -> None:
        """Test parsing with --area and --gzip options."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--gzip", "5"])

        assert opts.area == "0:0:1:1"
        assert opts.gzip == 5
        assert opts.pbf is False

    @staticmethod
    def test_parse_with_area_and_o5m() -> None:
        """Test parsing with --area and --o5m options."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--o5m"])

        assert opts.area == "0:0:1:1"
        assert opts.o5m is True
        assert opts.pbf is False
        assert opts.gzip == 0

    @staticmethod
    def test_parse_with_sources_option() -> None:
        """Test parsing with --sources option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--sources", "srtm1,view3"])

        assert opts.area == "0:0:1:1"
        assert opts.dataSources == ["srtm1", "view3"]

    @staticmethod
    def test_parse_with_single_source() -> None:
        """Test parsing with a single source."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--sources", "srtm3"])

        assert opts.dataSources == ["srtm3"]

    @staticmethod
    def test_parse_with_old_source_parameter() -> None:
        """Test backward compatibility with legacy --source parameter."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--source", "alos1"])

        assert opts.dataSources == ["alos1"]

    @staticmethod
    def test_parse_with_step_option() -> None:
        """Test parsing with --step option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--step", "50"])

        assert opts.contourStepSize == "50"

    @staticmethod
    def test_parse_with_feet_option() -> None:
        """Test parsing with --feet option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--feet"])

        assert opts.contourFeet is True

    @staticmethod
    def test_parse_with_output_prefix() -> None:
        """Test parsing with --output-prefix option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--output-prefix", "mymap"])

        assert opts.outputPrefix == "mymap"

    @staticmethod
    def test_parse_with_no_zero_contour() -> None:
        """Test parsing with --no-zero-contour option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--no-zero-contour"])

        assert opts.noZero is True

    @staticmethod
    def test_parse_with_download_only_and_area() -> None:
        """Test parsing with --download-only and --area options."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--download-only"])

        assert opts.downloadOnly is True
        assert opts.area == "0:0:1:1"

    @staticmethod
    def test_parse_with_corrx_and_corry() -> None:
        """Test parsing with --corrx and --corry options."""
        opts, _ = parse_command_line(
            ["--area", "0:0:1:1", "--corrx", "0.0005", "--corry", "0.0003"]
        )

        assert opts.srtmCorrx == 0.0005
        assert opts.srtmCorry == 0.0003

    @staticmethod
    def test_parse_with_hgtdir() -> None:
        """Test parsing with --hgtdir option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--hgtdir", "/custom/hgt"])

        assert opts.hgtdir == "/custom/hgt"

    @staticmethod
    def test_parse_with_max_nodes_per_tile() -> None:
        """Test parsing with --max-nodes-per-tile option."""
        opts, _ = parse_command_line(
            ["--area", "0:0:1:1", "--max-nodes-per-tile", "500000"]
        )

        assert opts.maxNodesPerTile == 500000

    @staticmethod
    def test_parse_with_max_nodes_per_way() -> None:
        """Test parsing with --max-nodes-per-way option."""
        opts, _ = parse_command_line(
            ["--area", "0:0:1:1", "--max-nodes-per-way", "1000"]
        )

        assert opts.maxNodesPerWay == 1000

    @staticmethod
    def test_parse_with_rdp_epsilon() -> None:
        """Test parsing with --simplifyContoursEpsilon option."""
        opts, _ = parse_command_line(
            ["--area", "0:0:1:1", "--simplifyContoursEpsilon", "0.0003"]
        )

        assert opts.rdpEpsilon == 0.0003

    @staticmethod
    def test_parse_with_disable_rdp() -> None:
        """Test parsing with --disableRDP option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--disableRDP"])

        assert opts.disableRdp is True
        assert opts.rdpEpsilon is None

    @staticmethod
    def test_parse_with_jobs_option() -> None:
        """Test parsing with --jobs option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--jobs", "4"])

        assert opts.nJobs == 4

    @staticmethod
    def test_parse_with_osm_version() -> None:
        """Test parsing with --osm-version option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--osm-version", "0.5"])

        assert opts.osmVersion == 0.5

    @staticmethod
    def test_parse_with_void_range_max() -> None:
        """Test parsing with --void-range-max option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--void-range-max=-500"])

        assert opts.voidMax == -500

    @staticmethod
    def test_parse_with_start_node_id() -> None:
        """Test parsing with --start-node-id option."""
        opts, _ = parse_command_line(
            ["--area", "0:0:1:1", "--start-node-id", "20000000"]
        )

        assert opts.startId == 20000000

    @staticmethod
    def test_parse_with_start_way_id() -> None:
        """Test parsing with --start-way-id option."""
        opts, _ = parse_command_line(
            ["--area", "0:0:1:1", "--start-way-id", "20000000"]
        )

        assert opts.startWayId == 20000000

    @staticmethod
    def test_parse_no_arguments_shows_help(
        capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that no arguments triggers help output and exits."""
        with pytest.raises(SystemExit):
            parse_command_line([])

        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    @staticmethod
    def test_parse_with_invalid_source(
        capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that invalid data source causes exit."""
        with pytest.raises(SystemExit):
            parse_command_line(["--area", "0:0:1:1", "--sources", "invalid_source"])

        captured = capsys.readouterr()
        assert "Unknown data source" in captured.out

    @staticmethod
    def test_parse_default_data_sources_value() -> None:
        """Test default data sources value."""
        opts, _ = parse_command_line(["--area", "0:0:1:1"])

        # Default should be "srtm3"
        assert opts.dataSources == ["srtm3"]

    @staticmethod
    def test_parse_with_write_timestamp() -> None:
        """Test parsing with --write-timestamp option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--write-timestamp"])

        assert opts.writeTimestamp is True

    @staticmethod
    def test_parse_multiple_options_combined() -> None:
        """Test parsing with multiple options combined."""
        opts, _ = parse_command_line(
            [
                "--area",
                "0:0:10:10",
                "--pbf",
                "--step",
                "50",
                "--feet",
                "--no-zero-contour",
                "--output-prefix",
                "test",
                "--jobs",
                "4",
                "--corrx",
                "0.0005",
            ]
        )

        assert opts.area == "0:0:10:10"
        assert opts.pbf is True
        assert opts.contourStepSize == "50"
        assert opts.contourFeet is True
        assert opts.noZero is True
        assert opts.outputPrefix == "test"
        assert opts.nJobs == 4
        assert opts.srtmCorrx == 0.0005

    @staticmethod
    def test_parse_returns_correct_types() -> None:
        """Test that parse_command_line returns correct tuple types."""
        result = parse_command_line(["--area", "0:0:1:1"])

        assert isinstance(result, tuple)
        assert len(result) == 2
        opts, filenames = result
        assert hasattr(opts, "area")
        assert isinstance(filenames, list)

    @staticmethod
    def test_parse_with_log_level_debug() -> None:
        """Test parsing with --log DEBUG option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--log", "DEBUG"])

        assert opts.logLevel == "DEBUG"

    @staticmethod
    def test_parse_with_log_level_warning() -> None:
        """Test parsing with --log WARNING option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--log", "WARNING"])

        assert opts.logLevel == "WARNING"

    @staticmethod
    def test_parse_default_log_level() -> None:
        """Test default log level is WARNING."""
        opts, _ = parse_command_line(["--area", "0:0:1:1"])

        assert opts.logLevel == "WARNING"

    @patch("pyhgtmap.cli.parse_polygons_file")
    def test_parse_with_valid_polygon_file(self, mock_parse_poly: MagicMock) -> None:
        """Test parsing with valid polygon file."""
        mock_parse_poly.return_value = ("0:0:1:1", [[0, 0], [1, 0], [1, 1], [0, 1]])

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".geojson", delete=False
        ) as f:
            f.write("{}")
            poly_file = f.name

        try:
            opts, _ = parse_command_line(["--polygon", poly_file])

            assert opts.area == "0:0:1:1"
            assert opts.polygons == [[0, 0], [1, 0], [1, 1], [0, 1]]
            mock_parse_poly.assert_called_once_with(poly_file)
        finally:
            os.unlink(poly_file)

    @staticmethod
    def test_parse_with_positive_area_coordinates() -> None:
        """Test parsing with positive area coordinates."""
        opts, _ = parse_command_line(["--area", "0:0:10:10"])

        assert opts.area == "0:0:10:10"

    @staticmethod
    def test_parse_with_float_area_coordinates() -> None:
        """Test parsing with float area coordinates."""
        opts, _ = parse_command_line(["--area", "10.5:20.3:30.7:40.1"])

        assert opts.area == "10.5:20.3:30.7:40.1"

    @staticmethod
    def test_parse_void_range_max_default() -> None:
        """Test default void range max value."""
        opts, _ = parse_command_line(["--area", "0:0:1:1"])

        assert opts.voidMax == -0x8000

    @staticmethod
    def test_parse_with_polygon_file_option() -> None:
        """Test parsing with polygon file option that doesn't exist exits."""
        with pytest.raises(SystemExit):
            parse_command_line(["--polygon", "/nonexistent/file.geojson"])

    @staticmethod
    def test_parse_download_only_with_area() -> None:
        """Test that --download-only with --area succeeds."""
        opts, _ = parse_command_line(["--download-only", "--area", "0:0:1:1"])

        assert opts.downloadOnly is True
        assert opts.area == "0:0:1:1"

    @staticmethod
    def test_parse_with_plot_prefix() -> None:
        """Test parsing with --plot option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--plot", "output"])

        assert opts.plotPrefix == "output"

    @staticmethod
    def test_parse_with_line_categories() -> None:
        """Test parsing with --line-cat option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--line-cat", "500,250"])

        assert opts.lineCats == "500,250"

    @staticmethod
    def test_parse_default_line_categories() -> None:
        """Test default line categories."""
        opts, _ = parse_command_line(["--area", "0:0:1:1"])

        assert opts.lineCats == "200,100"

    @staticmethod
    def test_parse_with_smooth_ratio() -> None:
        """Test parsing with --smooth option."""
        opts, _ = parse_command_line(["--area", "0:0:1:1", "--smooth", "2.5"])

        assert opts.smooth_ratio == 2.5

    @staticmethod
    def test_parse_default_smooth_ratio() -> None:
        """Test default smooth ratio."""
        opts, _ = parse_command_line(["--area", "0:0:1:1"])

        assert opts.smooth_ratio == 1.0
