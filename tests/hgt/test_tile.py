from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import Mock

import matplotlib.pyplot as plt
import numpy
import pytest

from pyhgtmap.cli import Configuration
from pyhgtmap.hgt.file import HgtFile
from tests import TEST_DATA_PATH

if TYPE_CHECKING:
    from pyhgtmap.hgt.tile import HgtTile, TileContours

HGT_SIZE: int = 1201


def toulon_tiles(
    smooth_ratio: float,
    custom_options: Configuration | None = None,
    file_name: str = "N43E006.hgt",
) -> list[HgtTile]:
    hgt_file = HgtFile(
        os.path.join(TEST_DATA_PATH, file_name),
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


@pytest.fixture()
def toulon_tiles_transformed() -> list[HgtTile]:
    """Toulon tiles in 3857 transformed coordinates."""
    # Skip any test using this fixture if GDAL is not installed
    pytest.importorskip("osgeo")
    return toulon_tiles(smooth_ratio=1, file_name="N43E006_3857.tiff")


class TestHgtTile:
    @staticmethod
    def test_contourLines(toulon_tiles_raw: list[HgtTile]) -> None:
        """Test contour lines extraction from hgt file."""
        assert toulon_tiles_raw
        elevations, contour_data = toulon_tiles_raw[0].contourLines()
        assert elevations == range(0, 1940, 20)
        assert contour_data
        # Get the contours for 20m elevation
        contour_list_20 = contour_data.trace(20)[0]
        assert len(contour_list_20) == 145
        assert len(contour_list_20[0]) == 5

        # Get the contours for 1920m elevation
        contour_list_1920 = contour_data.trace(1920)[0]
        assert len(contour_list_1920) == 1
        # Float numbers are not strictly equals
        numpy.testing.assert_allclose(
            contour_list_1920[0],
            numpy.array(
                [
                    [6.63732143, 43.89583333],
                    [6.6375, 43.89591954],
                    [6.63833333, 43.89583333],
                    [6.63777778, 43.895],
                    [6.6375, 43.8948913],
                    [6.63714286, 43.895],
                    [6.63732143, 43.89583333],
                ],
            ),
        )

    @staticmethod
    def test_get_contours(toulon_tiles_raw: list[HgtTile]) -> None:
        """Test contour lines extraction from hgt file."""
        assert toulon_tiles_raw
        tile_contours: TileContours = toulon_tiles_raw[0].get_contours()

        assert tile_contours.nb_nodes == 1264395
        assert tile_contours.nb_ways == 10798
        assert tile_contours.contours
        # Get the contours for 20m elevation
        contour_list_20 = tile_contours.contours[20]
        assert len(contour_list_20) == 145
        assert len(contour_list_20[0]) == 5

        # Get the contours for 1920m elevation
        contour_list_1920 = tile_contours.contours[1920]
        assert len(contour_list_1920) == 1
        # Float numbers are not strictly equals
        numpy.testing.assert_allclose(
            contour_list_1920[0],
            numpy.array(
                [
                    [6.63732143, 43.89583333],
                    [6.6375, 43.89591954],
                    [6.63833333, 43.89583333],
                    [6.63777778, 43.895],
                    [6.6375, 43.8948913],
                    [6.63714286, 43.895],
                    [6.63732143, 43.89583333],
                ],
            ),
        )

    @staticmethod
    def test_get_contours_cache(toulon_tiles_raw: list[HgtTile]) -> None:
        """Ensure get_contours caching works properly."""
        # tile = hgtTile()
        assert toulon_tiles_raw
        tile = toulon_tiles_raw[0]
        # Encapsulate the method in a mock, delegating to the actual method
        tile.contourLines = Mock(side_effect=tile.contourLines)  # type: ignore[method-assign]
        # Call get_contours twice
        toulon_tiles_raw[0].get_contours()
        toulon_tiles_raw[0].get_contours()
        # contourLines must be called only once thanks to caching
        tile.contourLines.assert_called_once_with(20, 0, False, None, None, None)

    @staticmethod
    # Test contours generation with several rdp_epsilon values
    # Results must be close enough not to trigger an exception with mpl plugin
    @pytest.mark.parametrize(
        "rdp_epsilon",
        [
            None,
            0.0,
            0.00001,
        ],
    )
    @pytest.mark.mpl_image_compare(
        baseline_dir=TEST_DATA_PATH,
        filename="toulon_ref.png",
    )
    def test_draw_contours_Toulon(
        toulon_tiles_raw: list[HgtTile],
        rdp_epsilon: float | None,
    ) -> plt.Figure:  # type: ignore[reportPrivateImportUsage]  # not supported by pylance
        """Rather an end-to-end test.
        Print contours in Toulon's area to assert overall result, even if contours are not exactly the same (eg. algo evolution).
        To compare output, run `pytest --mpl`
        """
        return TestHgtTile._test_draw_contours(toulon_tiles_raw, rdp_epsilon)

    @staticmethod
    @pytest.mark.mpl_image_compare(
        baseline_dir=TEST_DATA_PATH,
        # Transformed tiff result is slightly different from original HGT one
        filename="toulon_ref_transformed.png",
    )
    def test_draw_contours_Toulon_transform(
        toulon_tiles_transformed: list[HgtTile],
    ) -> plt.Figure:  # type: ignore[reportPrivateImportUsage]  # not supported by pylance
        """Rather an end-to-end test.
        Print contours in Toulon's area to assert overall result, even if contours are not exactly the same (eg. algo evolution).
        To compare output, run `pytest --mpl`
        """
        return TestHgtTile._test_draw_contours(toulon_tiles_transformed, None)

    @staticmethod
    @pytest.mark.mpl_image_compare(
        baseline_dir=TEST_DATA_PATH,
        filename="toulon_ref_smoothed.png",
    )
    def test_draw_contours_smoothed_Toulon(
        toulon_tiles_smoothed: list[HgtTile],
    ) -> plt.Figure:  # type: ignore[reportPrivateImportUsage]  # not supported by pylance
        """Rather an end-to-end test.
        Print contours in Toulon's area to assert overall result, even if contours are not exactly the same (eg. algo evolution).
        To compare output, run `pytest --mpl`
        """
        return TestHgtTile._test_draw_contours(toulon_tiles_smoothed, 0.00001)

    @staticmethod
    def _test_draw_contours(
        tiles: list[HgtTile],
        rdp_epsilon: float | None,
    ) -> plt.Figure:  # type: ignore[reportPrivateImportUsage]  # not supported by pylance
        """Internal contour testing method."""
        tile = tiles[0]
        elevations, contour_data = tile.contourLines(rdpEpsilon=rdp_epsilon)
        dpi = 100
        # Get graph space close to original data size
        out_size = HGT_SIZE
        fig = plt.figure(figsize=(out_size / dpi, out_size / dpi), dpi=dpi)
        plt.axis("on")
        # Fix the axes limits to the bbox
        tile_bbox = tile.bbox()
        plt.xlim(tile_bbox.min_lon, tile_bbox.max_lon)
        plt.ylim(tile_bbox.min_lat, tile_bbox.max_lat)
        plt.ticklabel_format(useOffset=False)
        plt.tight_layout(pad=0)
        for elev in range(0, 500, 100):
            for contour in contour_data.trace(elev)[0]:
                x, y = zip(*contour)
                plt.plot(x, y, color="black")
        # plt.savefig(os.path.join(TEST_DATA_PATH, "toulon_out.png"))
        return fig
