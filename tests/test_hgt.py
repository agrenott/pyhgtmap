import os
from types import SimpleNamespace
from typing import List, Optional

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
    # Test contours generation with several rdp_espilon values
    # Results must be close enough not to trigger an exception with mpl plugin
    @pytest.mark.parametrize(
        "rdp_epsilon",
        [
            None,
            0.0,
            0.00001,
        ],
    )
    @pytest.mark.mpl_image_compare(baseline_dir="data", filename="toulon_ref.png")
    def test_draw_contours_Toulon(
        toulon_tiles: List[hgt.hgtTile], rdp_epsilon: Optional[float]
    ) -> plt.Figure:
        """Rather an end-to-end test.
        Print contours in Toulons area to assert overall result, even if contours are not exactly the same (eg. algo evolution).
        To compare output, run `pytest --mpl`
        """
        elevations, contour_data = toulon_tiles[0].contourLines(rdpEpsilon=rdp_epsilon)
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


def test_polygon_mask() -> None:
    x_data = numpy.array([0, 1, 2, 3, 4, 5])
    y_data = numpy.array([0, 1, 2, 3, 4, 5])

    # Mask matching exactly the border of the data
    # Result is a bit strange as the behabior on boundary is unpredictable
    polygon_full = [(0, 0), (0, 5), (5, 5), (5, 0), (0, 0)]
    mask_full = hgt.polygon_mask(x_data, y_data, [polygon_full], None)
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
            ]
        ),
    )

    # Polygon bigger than data
    polygon_bigger = [(-1, -1), (-1, 6), (6, 6), (6, -1), (-1, -1)]
    mask_bigger = hgt.polygon_mask(x_data, y_data, [polygon_bigger], None)
    numpy.testing.assert_array_equal(
        mask_bigger, numpy.full((x_data.size, y_data.size), False)
    )

    # Polygon splitting data
    polygon_split = [(-1, -1), (-1, 6), (2, 6), (5, -1), (-1, -1)]
    mask_split = hgt.polygon_mask(x_data, y_data, [polygon_split], None)
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
            ]
        ),
    )

    # Polygon resulting in several intersection polygons
    polygon_multi = [
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
    mask_multi = hgt.polygon_mask(x_data, y_data, [polygon_multi], None)
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
            ]
        ),
    )

    # Polygon not intersecting data
    polygon_out = [(-1, -1), (-1, -2), (6, -2), (6, -1), (-1, -1)]
    mask_out = hgt.polygon_mask(x_data, y_data, [polygon_out], None)
    numpy.testing.assert_array_equal(mask_out, numpy.full((1), True))
