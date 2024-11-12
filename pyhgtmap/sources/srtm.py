from __future__ import annotations

import io
import logging
import math
import os
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile, ZipInfo

import httpx
import numpy
import shapely.geometry
from lxml import etree

from pyhgtmap.configuration import NestedConfig
from pyhgtmap.latlon import DegreeLatLon

from . import ArgparsePassword, Source

if TYPE_CHECKING:
    import configargparse

    from pyhgtmap.configuration import Configuration


class SRTMConfiguration(NestedConfig):
    """SRTM plugin specific configuration"""

    user: str
    password: str


LOGGER: logging.Logger = logging.getLogger(__name__)

__all__ = ["SRTM"]


BASE_URLS = {
    1: "https://earthexplorer.usgs.gov/download/5e83a3efe0103743/SRTM1{:s}V3/EE",
    3: "https://earthexplorer.usgs.gov/download/5e83a43cb348f8ec/SRTM3{:s}V2/EE",
}


def get_url_for_tile(resolution: int, area: str) -> str:
    """Get the URL for a given tile."""
    return BASE_URLS[resolution].format(area)


# https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python
# or https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/
# https://cmr.earthdata.nasa.gov/search/concepts/C1000000240-LPDAAC_ECS.html
# https://lpdaac.usgs.gov/products/srtmgl1nv003/


def parse_srtm_coverage_kml(kml_content: bytes) -> shapely.geometry.MultiPolygon:
    """Parse SRTM coverage KML file and return a MultiPolygon. Included polygons may have holes."""
    root = etree.fromstring(kml_content, parser=None)  # noqa: S320 # let's trust the source

    # Short namespace alias
    ns = root.nsmap
    # Only one MultiGeometry expected
    multi_geometry = root.find(".//Document/Folder/Placemark/MultiGeometry", ns)

    polygons = multi_geometry.findall(".//Polygon", ns)
    out_polygons = []

    for polygon in polygons:
        # One outer boundary
        outer_coords = [
            # Keep only lon, lat
            tuple(map(float, x.split(",")[0:2]))
            for x in polygon.find(
                "./outerBoundaryIs/LinearRing/coordinates", ns
            ).text.split(" ")
        ]
        # Zero or more inner boundaries
        inner_coords = [
            [tuple(map(float, x.split(",")[0:2])) for x in y.text.split(" ")]
            for y in polygon.findall("./innerBoundaryIs/LinearRing/coordinates", ns)
        ]

        out_polygons.append(shapely.geometry.Polygon(outer_coords, inner_coords))
    out_multi_polygon = shapely.geometry.MultiPolygon(out_polygons)
    return out_multi_polygon


def areas_from_kml(kml_content: bytes) -> list[str]:
    """Extract areas from SRTM coverage KML file."""
    coverage: shapely.geometry.MultiPolygon = parse_srtm_coverage_kml(kml_content)
    # We can simply round because the coverage polygon very slightly exceeds the actual tiles boundaries
    min_lon, min_lat, max_lon, max_lat = coverage.bounds

    # Scan the whole area, checking whether the center of each tile is inside the coverage polygon
    # This is valid because the coverage map's polygons are following tiles boundaries
    centers = [
        shapely.geometry.Point(lon, lat)
        for lon in numpy.arange(min_lon + 0.5, max_lon, 1.0)
        for lat in numpy.arange(min_lat + 0.5, max_lat, 1.0)
    ]
    # Relying on STRtree for performance
    centers_index = shapely.STRtree(centers)
    covered_centers = centers_index.geometries.take(
        centers_index.query(coverage, "contains")
    )
    areas: list[str] = [
        DegreeLatLon(lon=math.floor(p.x), lat=math.floor(p.y)).to_string()
        for p in covered_centers
    ]

    return areas


class SrtmIndex:
    """
    Index of covered areas, avoiding to request non-existing ones repeatedly.
    """

    def __init__(self, cache_dir_root: str, resolution: int) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store index file
            resolution (int): Resolution (in arc second)
        """
        self._cache_dir_root: str = cache_dir_root
        self._resolution = resolution
        self._index_file_name = os.path.join(
            self._cache_dir_root,
            f"hgt/hgtIndex_{self._resolution}_v3.0.txt",
        )
        # ZIP file URL -> list of covered tiles
        self._entries: set[str] = set()

    def load(self) -> None:
        """Load index from local file."""
        with open(self._index_file_name) as index_file:
            for line in index_file:
                if line.startswith("#"):
                    continue
                self._entries.add(line.strip())

    def save(self) -> None:
        """Save index to local file, overwriting it."""
        with open(self._index_file_name, "w") as index_file:
            index_file.write(f"# SRTM{self._resolution}v3.0 index file, VERSION=2")
            # This is a set, already sorted
            index_file.write("\n".join(self._entries))

        LOGGER.info("Saved index to file: %s", self._index_file_name)

    def init_from_web(self) -> None:
        """Build index from SRTM's world coverage maps web page."""

        LOGGER.info("Building index from world coverage map...")
        self._entries.clear()
        hgtIndexUrl = "https://dds.cr.usgs.gov/ee-data/coveragemaps/kml/ee/srtm_v3_srtmgl{:d}.kml".format(
            self._resolution
        )
        index_kml_payload = httpx.get(hgtIndexUrl).read()

        self._entries = set(areas_from_kml(index_kml_payload))

        self.save()

    @property
    def entries(self) -> set[str]:
        """Return index entries, initializing it if needed"""
        if not self._entries:
            try:
                # Try loading from file
                self.load()
            except FileNotFoundError:
                self.init_from_web()
        return self._entries


class SRTM(Source):
    """Downloader for NASA Shuttle Radar Topography Mission v3.0"""

    NICKNAME = "srtm"

    BANNER = (
        "You're downloading from NASA Shuttle Radar Topography Mission v3.0. Please "
        "consider visiting https://www.earthdata.nasa.gov/news/nasa-shuttle-radar-topography-mission-srtm-version-3-0-global-1-arc-second-data-released-over-asia-and-australia to support the author."
    )

    def __init__(
        self, cache_dir_root: str, config_dir: str, configuration: Configuration
    ) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached HGT files
            config_dir (str): Root directory to store configuration (if any)
            configuration (Configuration): Common configuration object
        """
        super().__init__(cache_dir_root, config_dir, configuration)
        # Locally overridden for typing
        self.config: Configuration
        self.plugin_config: SRTMConfiguration = cast(
            SRTMConfiguration, self.config.alos
        )
        if self.plugin_config.user is None or self.plugin_config.password is None:
            raise ValueError("SRTM user and password are required")

    def download_missing_file(
        self,
        area: str,
        resolution: int,
        output_file_name: str,
    ) -> None:
        url = get_url_for_tile(resolution, area)
        # ALOS is quite slow to generate download file
        timeout = httpx.Timeout(10, read=120.0)
        client = httpx.Client(
            auth=(self.plugin_config.user, self.plugin_config.password),
            timeout=timeout,
            # TODO: enable SSL verification
            verify=False,  # noqa: S501
        )
        r = client.get(url)
        with ZipFile(
            io.BytesIO(cast(bytes, r.content)),
        ) as zip_archive:
            # Look for DSM file, which should be in the form "N017E045/ALPSMLC30_N017E045_DSM.tif"
            dsm_files: list[ZipInfo] = [
                x for x in zip_archive.filelist if x.filename.endswith("_DSM.tif")
            ]
            if not dsm_files:
                raise ValueError(f"DSM file not found in {url}")
            if len(dsm_files) > 1:
                raise ValueError(f"Multiple DSM files found in {url}")
            with (
                zip_archive.open(dsm_files[0]) as hgt_file_in,
                open(
                    output_file_name,
                    mode="wb",
                ) as hgt_file_out,
            ):
                hgt_file_out.write(hgt_file_in.read())
        # TODO

    @staticmethod
    def register_cli_options(
        parser: configargparse.ArgumentParser, root_config: NestedConfig
    ) -> None:
        """Register CLI options for this source"""

        group = parser.add_argument_group("SRTM")
        group.add_argument("--srtm-user", type=str, dest="srtm.user")
        group.add_argument(
            "--srtm-password", type=str, action=ArgparsePassword, dest="srtm.password"
        )
        root_config.add_sub_config("srtm", SRTMConfiguration())
