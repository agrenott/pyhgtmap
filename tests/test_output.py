"""Validate the various output formats"""

import os
import tempfile
from contextlib import suppress
from typing import Any, Callable, Dict, Iterable, List, Tuple

import npyosmium
import npyosmium.io
import npyosmium.osm
import numpy
import numpy.typing
import pytest

from pyhgtmap.hgt.tile import TileContours
from pyhgtmap.output import make_elev_classifier, o5mUtil, osmUtil, pbfUtil


class OSMDecoder(npyosmium.SimpleHandler):
    """Basic OSM file decoder, relying on official osmium library."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: Dict[int, Any] = {}
        self.ways: Dict[int, Any] = {}

    def node(self, n: npyosmium.osm.Node) -> None:
        with suppress(Exception):
            self.nodes[n.id] = (n.location.lat, n.location.lon)

    def way(self, w: npyosmium.osm.Way) -> None:
        self.ways[w.id] = ([node.ref for node in w.nodes], [tag for tag in w.tags])


def arrays_from_lists(
    coordinates_lists: List[List[Tuple[int, int]]],
) -> List[numpy.typing.NDArray]:
    """Helper to convert list of lists into array of arrays."""
    return [
        numpy.array(
            [numpy.array(coordinates, dtype=numpy.float64) for coordinates in way]
        )
        for way in coordinates_lists
    ]


@pytest.fixture
def tile_contours() -> TileContours:
    return TileContours(
        nb_nodes=8,
        nb_ways=3,
        contours={
            # Elevation 0
            0: arrays_from_lists(
                [
                    # Closed loop
                    [(1, 1), (1, 2), (2, 2), (2, 1), (1, 1)],
                    # Open one
                    [(3, 1), (3, 2)],
                ]
            ),
            # Elevation 50
            50: arrays_from_lists([[(4, 1), (4, 2)]]),
            # Elevation 100
            100: [],
            # Elevation 150
            150: [],
        },
    )


@pytest.fixture
def bounding_box() -> Tuple[float, float, float, float]:
    """Bounding box of all fake data nodes"""
    return (1, 1, 4, 2)


@pytest.fixture
def elev_classifier() -> Callable[[int], str]:
    return make_elev_classifier(100, 50)


@pytest.fixture
def elevations() -> Iterable[int]:
    return [0, 50, 100, 150]


def check_osmium_result(osm_file_name: str) -> None:
    """Check results using osmium. Data corresponding to shared fixtures."""
    osm_decoder = OSMDecoder()
    reader = npyosmium.io.Reader(osm_file_name)
    header = reader.header()
    # Check header attributes
    assert header.box().bottom_left == npyosmium.osm.Location(1, 1)
    assert header.box().top_right == npyosmium.osm.Location(4, 2)
    if osm_file_name[-4:] != ".o5m":
        # Not implemented for o5m format
        assert header.get("generator") == "pyhgtmap 123"
    osm_decoder.apply_file(osm_file_name)

    # Check nodes
    assert osm_decoder.nodes == {
        1000: (1.0, 1.0),
        1001: (2.0, 1.0),
        1002: (2.0, 2.0),
        1003: (1.0, 2.0),
        1004: (1.0, 3.0),
        1005: (2.0, 3.0),
        1006: (1.0, 4.0),
        1007: (2.0, 4.0),
    }

    # Check ways
    assert osm_decoder.ways == {
        2000: (
            # Loop must be closed, re-using first ID
            [1000, 1001, 1002, 1003, 1000],
            [
                npyosmium.osm.Tag(k="ele", v="0"),
                npyosmium.osm.Tag(k="contour", v="elevation"),
                npyosmium.osm.Tag(k="contour_ext", v="elevation_major"),
            ],
        ),
        2001: (
            [1004, 1005],
            [
                npyosmium.osm.Tag(k="ele", v="0"),
                npyosmium.osm.Tag(k="contour", v="elevation"),
                npyosmium.osm.Tag(k="contour_ext", v="elevation_major"),
            ],
        ),
        2002: (
            [1006, 1007],
            [
                npyosmium.osm.Tag(k="ele", v="50"),
                npyosmium.osm.Tag(k="contour", v="elevation"),
                # Medium elevation expected
                npyosmium.osm.Tag(k="contour_ext", v="elevation_medium"),
            ],
        ),
    }


class TestOutputOsm:
    @staticmethod
    def test_produce_osm(tile_contours: TileContours, elev_classifier) -> None:
        """Generate OSM file out of mocked data and check content."""
        with tempfile.TemporaryDirectory() as tempdir:
            osm_file_name = os.path.join(tempdir, "output.osm")
            osm_output = osmUtil.Output(
                osm_file_name,
                osmVersion=0.6,
                pyhgtmap_version="123",
                boundsTag='<bounds minlat="1" minlon="1" maxlat="2" maxlon="4"/>',
                gzip=0,
                elevClassifier=elev_classifier,
                timestamp=False,
            )

            # Write OSM file
            next_node_id, ways = osm_output.write_nodes(
                tile_contours, ' time="some time"', 1000, 0.6
            )
            assert next_node_id == 1008
            osm_output.write_ways(ways, 2000)
            osm_output.done()

            # Check file output
            with open(osm_file_name) as osm_file:
                contents: str = osm_file.read()
            assert (
                contents
                == """<?xml version="1.0" encoding="utf-8"?>
<osm version="0.6" generator="pyhgtmap 123">
<bounds minlat="1" minlon="1" maxlat="2" maxlon="4"/>
<node id="1000" lat="1.0000000" lon="1.0000000" version="1" time="some time"/>
<node id="1001" lat="2.0000000" lon="1.0000000" version="1" time="some time"/>
<node id="1002" lat="2.0000000" lon="2.0000000" version="1" time="some time"/>
<node id="1003" lat="1.0000000" lon="2.0000000" version="1" time="some time"/>
<node id="1004" lat="1.0000000" lon="3.0000000" version="1" time="some time"/>
<node id="1005" lat="2.0000000" lon="3.0000000" version="1" time="some time"/>
<node id="1006" lat="1.0000000" lon="4.0000000" version="1" time="some time"/>
<node id="1007" lat="2.0000000" lon="4.0000000" version="1" time="some time"/>
<way id="2000" version="1"><nd ref="1000"/>
<nd ref="1001"/>
<nd ref="1002"/>
<nd ref="1003"/>
<nd ref="1000"/>
<tag k="ele" v="0"/><tag k="contour" v="elevation"/><tag k="contour_ext" v="elevation_major"/></way>
<way id="2001" version="1"><nd ref="1004"/>
<nd ref="1005"/>
<tag k="ele" v="0"/><tag k="contour" v="elevation"/><tag k="contour_ext" v="elevation_major"/></way>
<way id="2002" version="1"><nd ref="1006"/>
<nd ref="1007"/>
<tag k="ele" v="50"/><tag k="contour" v="elevation"/><tag k="contour_ext" v="elevation_medium"/></way>
</osm>
"""
            )

            # Check file with osmium
            check_osmium_result(osm_file_name)


class TestOutputPbf:
    @staticmethod
    def test_produce_pbf(
        tile_contours: TileContours,
        elev_classifier,
        bounding_box: Tuple[float, float, float, float],
    ) -> None:
        """Generate PBF file out of mocked data and check content."""
        with tempfile.TemporaryDirectory() as tempdir:
            osm_file_name = os.path.join(tempdir, "output.osm.pbf")
            osm_output = pbfUtil.Output(
                osm_file_name,
                osmVersion=0.6,
                pyhgtmap_version="123",
                bbox=bounding_box,
                elevClassifier=elev_classifier,
            )

            # Write OSM file
            next_node_id, ways = osm_output.write_nodes(
                tile_contours, ' time="some time"', 1000, 0.6
            )
            assert next_node_id == 1008
            osm_output.write_ways(ways, 2000)
            osm_output.done()

            # Check file content with osmium
            check_osmium_result(osm_file_name)

            # Check file size to ensure there's no major drop in efficiency (compression, dense encoding)
            assert os.stat(osm_file_name).st_size < 420

    @staticmethod
    def test_node_id_overflow(
        tile_contours: TileContours,
        elev_classifier,
        bounding_box: Tuple[float, float, float, float],
    ) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            osm_file_name = os.path.join(tempdir, "output.osm.pbf")
            osm_output = pbfUtil.Output(
                osm_file_name,
                osmVersion=0.6,
                pyhgtmap_version="123",
                bbox=bounding_box,
                elevClassifier=elev_classifier,
            )
            start = 2147483647
            next_node_id, ways = osm_output.write_nodes(
                tile_contours, ' time="some time"', start, 0.6
            )

            # Check int32 boundary has been passed without issue
            assert next_node_id == 2147483655


class TestOutputO5m:
    @staticmethod
    def test_produce_o5m(
        tile_contours: TileContours,
        elev_classifier,
        bounding_box: Tuple[float, float, float, float],
    ) -> None:
        """Generate PBF file out of mocked data and check content."""
        with tempfile.TemporaryDirectory() as tempdir:
            osm_file_name = os.path.join(tempdir, "output.osm.o5m")
            osm_output = o5mUtil.Output(
                osm_file_name,
                osmVersion=0.6,
                pyhgtmap_version="123",
                bbox=bounding_box,
                elevClassifier=elev_classifier,
            )

            # Write OSM file
            next_node_id, ways = osm_output.write_nodes(
                tile_contours, ' time="some time"', 1000, 0.6
            )
            assert next_node_id == 1008
            osm_output.write_ways(ways, 2000)
            osm_output.done()

            # Check file with osmium
            check_osmium_result(osm_file_name)
