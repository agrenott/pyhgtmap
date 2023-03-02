import os
import numpy
from types import SimpleNamespace
from typing import List

from phyghtmap import hgt

TEST_DATA_PATH = os.path.join(os.path.dirname(os.path.relpath(__file__)), "data")


class TestTile:
    @staticmethod
    def test_contourLines():
        """Test contour lines extraction from hgt file."""
        hgt_file = hgt.hgtFile(os.path.join(TEST_DATA_PATH, "N43E006.hgt"), 0, 0)
        # Fake command line parser output
        options = SimpleNamespace(area=None, maxNodesPerTile=0, contourStepSize=20)
        tiles: List[hgt.hgtTile] = hgt_file.makeTiles(options)
        assert tiles
        elevations, contour_data = tiles[0].contourLines()
        assert elevations == range(0, 1940, 20)
        assert contour_data
        # Get the countours for 20m elevation
        contour_list_20 = contour_data.trace(20)[0]
        assert len(contour_list_20) == 102
        assert len(contour_list_20[0]) == 6618

        # Get the countours for 1920m elevation
        contour_list_1920 = contour_data.trace(1920)[0]
        assert len(contour_list_1920) == 1
        # Float numbers are not striclty equals
        numpy.testing.assert_allclose(
            contour_list_1920[0],
            numpy.array(
                [
                    [6.6375, 43.89591954],
                    [6.63833333, 43.89583333],
                    [6.63777778, 43.895],
                    [6.6375, 43.8948913],
                    [6.63714286, 43.895],
                    [6.63732143, 43.89583333],
                    [6.6375, 43.89591954],
                ]
            ),
        )
