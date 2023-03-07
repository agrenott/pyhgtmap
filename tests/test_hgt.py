import os
from types import SimpleNamespace
from typing import List

import matplotlib.pyplot as plt
import numpy
import pytest

from phyghtmap import hgt

TEST_DATA_PATH = os.path.join(os.path.dirname(os.path.relpath(__file__)), "data")
HGT_SIZE: int = 1201


@pytest.fixture
def toulon_tiles() -> List[hgt.hgtTile]:
    hgt_file = hgt.hgtFile(os.path.join(TEST_DATA_PATH, "N43E006.hgt"), 0, 0)
    # Fake command line parser output
    options = SimpleNamespace(area=None, maxNodesPerTile=0, contourStepSize=20)
    tiles: List[hgt.hgtTile] = hgt_file.makeTiles(options)
    return tiles


class TestTile:
    @staticmethod
    def test_contourLines(toulon_tiles: List[hgt.hgtTile]) -> None:
        """Test contour lines extraction from hgt file."""
        assert toulon_tiles
        elevations, contour_data = toulon_tiles[0].contourLines()
        assert elevations == range(0, 1940, 20)
        assert contour_data
        # Get the countours for 20m elevation
        contour_list_20 = contour_data.trace(20)[0]
        assert len(contour_list_20) == 145
        assert len(contour_list_20[0]) == 5

        # Get the countours for 1920m elevation
        contour_list_1920 = contour_data.trace(1920)[0]
        assert len(contour_list_1920) == 1
        # Float numbers are not striclty equals
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
                ]
            ),
        )

    @staticmethod
    @pytest.mark.mpl_image_compare(baseline_dir="data", filename="toulon_ref.png")
    def test_draw_contours_Toulon(toulon_tiles: List[hgt.hgtTile]) -> plt.Figure:
        """Rather an end-to-end test.
        Print contours in Toulons area to assert overall result, even if contours are not exactly the same (eg. algo evolution).
        To compare output, run `pytest --mpl`
        """
        elevations, contour_data = toulon_tiles[0].contourLines()
        dpi = 100
        # Add some space for axises, while trying to get graph space close to original data size
        out_size = HGT_SIZE + 300
        fig = plt.figure(figsize=(out_size / dpi, out_size / dpi), dpi=dpi)
        for elev in range(0, 500, 100):
            for contour in contour_data.trace(elev)[0]:
                x, y = zip(*contour)
                plt.plot(x, y, color="black")
        # plt.savefig(os.path.join(TEST_DATA_PATH, "toulon_out.png"))
        return fig
