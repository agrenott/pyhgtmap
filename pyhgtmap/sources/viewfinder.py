from __future__ import annotations

import io
import logging
import os
from pathlib import Path, PurePath
from urllib.request import urlopen
from zipfile import ZipFile

from bs4 import BeautifulSoup

from . import Source

LOGGER: logging.Logger = logging.getLogger(__name__)

__all__ = ["ViewFinder"]


def inner_areas(coord_tag: str) -> list[str]:
    """
    Return list of 1° areas names contained in the zone defined by
    viewfinder's map coordinates

    Args:
        coord_tag (str): viewfinder's map coordinates for given zone

    Returns:
        List[str]: list of 1° areas names contained in the zone
    """
    # Map size is 1800x900 px, to map 360 x 180°
    # Width of the map widget in the web page
    MAP_WIDTH = 1800
    viewfinder_map_ratio: float = MAP_WIDTH / 360.0
    left, top, right, bottom = (int(c) for c in coord_tag.split(","))
    # TODO: what is this "+0.5"? If it's to get a slightly wider are, shouldn't it be +/-?
    west = int(left / viewfinder_map_ratio + 0.5) - 180
    east = int(right / viewfinder_map_ratio + 0.5) - 180
    south = 90 - int(bottom / viewfinder_map_ratio + 0.5)
    north = 90 - int(top / viewfinder_map_ratio + 0.5)
    names: list[str] = []
    for lon in range(west, east):
        for lat in range(south, north):
            lon_name = f"W{-lon:0>3d}" if lon < 0 else f"E{lon:0>3d}"
            lat_name = f"S{-lat:0>2d}" if south < 0 else f"N{lat:0>2d}"

            name = f"{lat_name}{lon_name}"
            names.append(name)
    return names


def validate_safe_url(url: str) -> str:
    """
    Validate that the url is a safe url
    """
    if not url.startswith(("http:", "https:")):
        raise ValueError(f"URL must start with 'http:' or 'https:': {url}")
    return url


COVERAGE_MAP_URLS: dict[int, str] = {
    1: "http://viewfinderpanoramas.org/Coverage%20map%20viewfinderpanoramas_org1.htm",
    3: "http://viewfinderpanoramas.org/Coverage%20map%20viewfinderpanoramas_org3.htm",
}

# Version per resolution - kept for backward compatibility
DESIRED_INDEX_VERSION: dict[int, int] = {
    1: 2,
    3: 4,
}


class ViewFinderIndex:
    """
    Viewfinder panoramas HGT files are grouped into zip files covering bigger areas.
    Mapping is done by parsing the world coverage maps web pages. This first index is optimistic,
    as depending on the sea coverage inside a zone, many tiles may be inexisting in the
    actual ZIP file.

    **Beware: some zones overlap!
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
            f"viewfinderHgtIndex_{self._resolution}.txt",
        )
        # ZIP file URL -> list of covered tiles
        self._entries: dict[str, list[str]] = {}

    def load(self) -> None:
        """Load index from local file"""
        with open(self._index_file_name) as index_file:
            current_url = None
            for line in index_file:
                if line.startswith("#"):
                    continue
                if line.startswith("["):
                    # ZIP file name used as section header
                    current_url = line.strip()[1:-1]
                    if current_url not in self._entries:
                        self._entries[current_url] = []
                else:
                    # ZIP file content inside section
                    if current_url is None:
                        raise ValueError("Invalid syntax, current_url expected")
                    # Ignore trailing "\n"
                    self._entries[current_url].append(line.strip())

    def save(self) -> None:
        """Save index to local file"""
        with open(self._index_file_name, "w") as index_file:
            index_file.write(
                "# VIEW{:d} index file, VERSION={:d}\n".format(
                    self._resolution,
                    DESIRED_INDEX_VERSION[self._resolution],
                ),
            )
            for zip_file_url in sorted(self._entries):
                index_file.write(f"[{zip_file_url}]\n")
                for area_name in self._entries[zip_file_url]:
                    index_file.write(f"{area_name}\n")
        LOGGER.info("Saved index to file: %s", self._index_file_name)

    def init_from_web(self) -> None:
        """Build index from viewfinder's world coverage maps web page."""

        LOGGER.info("Building index from world coverage map...")
        self._entries = {}
        url = validate_safe_url(COVERAGE_MAP_URLS[self._resolution])
        for a in BeautifulSoup(urlopen(url).read(), "lxml").findAll("area"):  # noqa: S310 # https://github.com/astral-sh/ruff/issues/7918
            area_names = inner_areas(a["coords"])
            zip_file_url = a["href"].strip()
            if zip_file_url not in self._entries:
                self._entries[zip_file_url] = []
            self._entries[zip_file_url].extend(
                sorted([area.upper() for area in area_names]),
            )
        self.save()

    def update(self, zip_url: str, covered_areas: list[str]) -> None:
        """Check and update given index if actually covered areas are different
        from the currently indexed ones.
        Used as the coverage map provides big zones, for which some tiles might
        not exist (eg. sea areas).

        Args:
            zip_url (str): Zone ZIP file URL
            covered_areas (List[str]): Actual areas contained in this ZIP file
        """
        sorted_covered_areas = sorted(covered_areas)
        if sorted(self.entries.get(zip_url, [])) != sorted_covered_areas:
            LOGGER.info("Updating index for %s", zip_url)
            self.entries[zip_url] = sorted_covered_areas
            self.save()

    @property
    def entries(self) -> dict[str, list[str]]:
        """Return index entries, initializing it if needed"""
        if not self._entries:
            try:
                # Try loading from file
                self.load()
            except FileNotFoundError:
                self.init_from_web()
        return self._entries

    def get_urls_for_area(self, area_name: str) -> list[str]:
        """Return a list of ZIP file URLs potentially containing the requested area.

        Args:
            area_name (str): area name (eg. N46E001)

        Returns:
            List[str]: List of ZIP files URLs
        """
        return sorted(
            [url for url, areas in self.entries.items() if area_name in areas],
        )


def fetch_and_extract_zip(zip_url: str, output_dir_name) -> list[str]:
    """Fetch requested ZIP file and extract all contained HGT files into the
    provided directory (without keeping ZIP folders hierarchy).

    Args:
        zip_url (str): URL of the ZIP file to process
        output_dir_name (_type_): Directory to extract HGT files to

    Returns:
        List[Path]: Original paths of the extracted files
    """
    LOGGER.info("Downloading %s", zip_url)
    with ZipFile(io.BytesIO(urlopen(validate_safe_url(zip_url)).read())) as zip_archive:  # noqa: S310 # https://github.com/astral-sh/ruff/issues/7918
        file_names: list[PurePath] = [
            PurePath(file_name)
            for file_name in zip_archive.namelist()
            if file_name.lower().endswith(".hgt")
        ]
        # Extract all files - might be needed later anyway
        for file_name in file_names:
            # HGT files are in sub-directories of the archive (eg. 'L40/N47E056.hgt')
            with open(
                os.path.join(
                    output_dir_name,
                    f"{file_name.stem}.hgt",
                ),
                "wb",
            ) as hgt_file_out:
                hgt_file_out.write(zip_archive.read(str(file_name)))
    return [file_name.stem for file_name in file_names]


class ViewFinder(Source):
    """Downloader for Viewfinder panoramas DEM
    http://viewfinderpanoramas.org/dem3.html
    """

    NICKNAME = "view"

    BANNER = (
        "You're downloading from Viewfinder panoramas' DEM source. Please "
        "consider visiting http://viewfinderpanoramas.org/dem3.html to support the author."
    )

    def __init__(self, cache_dir_root: str, config_dir: str) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached HGT files
            config_dir (str): Root directory to store configuration (if any)
        """
        super().__init__(cache_dir_root, config_dir)
        self._indexes = {
            resolution: ViewFinderIndex(cache_dir_root, resolution)
            for resolution in ViewFinder.SUPPORTED_RESOLUTIONS
        }

    def download_missing_file(
        self,
        area: str,
        resolution: int,
        output_file_name: str,
    ) -> None:
        for zip_url in self._indexes[resolution].get_urls_for_area(area):
            # Zones covered by ZIP files may overlap; try all the possible ones
            try:
                extracted_areas: list[str] = fetch_and_extract_zip(
                    zip_url,
                    os.path.dirname(output_file_name),
                )
                # Update index, as actual zip content might not contain all tiles for
                # a given zone (sea areas)
                self._indexes[resolution].update(zip_url, extracted_areas)
            except Exception as e:
                LOGGER.warning(
                    "Exception raised while trying to fetch %s: %s", zip_url, e
                )
            if Path(output_file_name).is_file():
                break
            LOGGER.debug("%s not found in %s, trying next file", area, zip_url)
        else:
            LOGGER.debug("%s not found", area)
            raise FileNotFoundError
