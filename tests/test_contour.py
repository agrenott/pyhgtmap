from __future__ import annotations

from typing import TYPE_CHECKING

import numpy
import pytest

from pyhgtmap.hgt import contour

if TYPE_CHECKING:
    from pyhgtmap import Polygon


@pytest.mark.parametrize(
    ("input_path", "rdp_epsilon", "expected_path"),
    [
        # Simplest path: nothing to remove, even with huge rdp_epsilon
        pytest.param([(0, 0), (1, 1)], 10, [(0, 0), (1, 1)], id="Simplest"),
        # Dupe points, removed even with 0 rdp_epsilon
        pytest.param(
            [(0, 0), (0, 0), (1, 1), (1, 1), (1, 1)],
            0.0,
            [(0, 0), (1, 1)],
            id="Dupe points",
        ),
        # Closed path with dupe points
        pytest.param(
            [(0, 0), (0, 0), (1, 1), (1, 1), (1, 1), (1, 0), (1, 0), (0, 0), (0, 0)],
            0.0,
            [(0, 0), (1, 1), (1, 0), (0, 0)],
            id="Closed path with dupe points",
        ),
        # Straight line: remove middle points
        pytest.param(
            [(0, 0), (0.2, 0.2), (0.4, 0.4), (0.7, 0.7), (1, 1)],
            0.0,
            [(0, 0), (1, 1)],
            id="Straight line",
        ),
        # Overall corner shape must be kept
        pytest.param(
            [(0, 0), (0.5, 0.5), (1, 1), (1.09, 0.2), (1, 0)],
            0.1,
            [(0, 0), (1, 1), (1, 0)],
            id="Corner",
        ),
        # Overall corner shape must be kept - some details above threshold must be kept
        pytest.param(
            [(0, 0), (0.5, 0.5), (1, 1), (1.1, 0.2), (1, 0)],
            0.1,
            [(0, 0), (1, 1), (1.1, 0.2), (1, 0)],
            id="Corner with details",
        ),
    ],
)
def test_simplify_path(
    input_path: Polygon,
    rdp_epsilon: float,
    expected_path: Polygon,
) -> None:
    numpy.testing.assert_array_equal(
        contour.simplify_path(numpy.array(input_path), rdp_epsilon),
        expected_path,  # type: ignore[reportGeneralTypeIssues] # pylance
    )


class TestContour:
    pass
