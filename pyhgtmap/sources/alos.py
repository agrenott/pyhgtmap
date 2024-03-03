from __future__ import annotations

import argparse
import getpass
import io
import logging
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile, ZipInfo

import httpx

from pyhgtmap.configuration import NestedConfig
from pyhgtmap.latlon import DegreeLatLon

from . import Source

if TYPE_CHECKING:
    import configargparse

    from pyhgtmap.configuration import Configuration


# Locally override Configuration to add plugin-specific attributes
# Available only in the current module, but it should be used only there anyway
class AlosConfiguration(NestedConfig):
    user: str
    password: str


LOGGER: logging.Logger = logging.getLogger(__name__)

__all__ = ["Alos"]

# From https://www.eorc.jaxa.jp/ALOS/en/aw3d30/data/html_v2303/js/dsm_dl_select_v2303.js?ver=20230327
BASE_URL = "https://www.eorc.jaxa.jp/ALOS/aw3d30/data/release_v2303/{}/{}.zip"


class Password(argparse.Action):
    """Custom argparse action to handle password input"""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        if values is None:
            values = getpass.getpass()

        setattr(namespace, self.dest, values)


def get_url_for_tile(tile_name: str) -> str:
    """ALOS groups tile by (5x5/tile). Build the proper URL."""
    tile_lat_lon = DegreeLatLon.from_string(tile_name)
    group_name = tile_lat_lon.round_to(5).to_string(lat_padding=3)
    return BASE_URL.format(group_name, tile_lat_lon.to_string(lat_padding=3))


class Alos(Source):
    """Downloader for ALOS Global Digital Surface Model
    https://www.eorc.jaxa.jp/ALOS/en/dataset/aw3d30/aw3d30_e.htm
    """

    NICKNAME = "alos"

    # ALOS has only 1" resolution
    SUPPORTED_RESOLUTIONS = (1,)

    FILE_EXTENSION = "tif"

    BANNER = (
        "You're downloading from ALOS Global Digital Surface Model source. Please "
        "consider visiting https://www.eorc.jaxa.jp/ALOS/en/dataset/aw3d30/aw3d30_e.htm to support the author."
    )

    def __init__(
        self, cache_dir_root: str, config_dir: str, configuration: Configuration
    ) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached TIF files
            config_dir (str): Root directory to store configuration (if any)
        """
        super().__init__(cache_dir_root, config_dir, configuration)
        # Locally overridden for typing
        self.config: Configuration  # type: ignore[reportIncompatibleVariableOverride] # pylance
        self.plugin_config: AlosConfiguration = cast(
            AlosConfiguration, self.config.alos
        )
        if self.plugin_config.user is None or self.plugin_config.password is None:
            raise ValueError("ALOS user and password are required")

    def download_missing_file(
        self,
        area: str,
        resolution: int,
        output_file_name: str,
    ) -> None:
        url = get_url_for_tile(area)
        # ALOS is quite slow to generate download file
        timeout = httpx.Timeout(10, read=120.0)
        client = httpx.Client(
            auth=(self.plugin_config.user, self.plugin_config.password),
            timeout=timeout,
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

        group = parser.add_argument_group("ALOS")
        group.add_argument("--alos-user", type=str, dest="alos.user")
        group.add_argument(
            "--alos-password", type=str, action=Password, dest="alos.password"
        )
        root_config.add_sub_config("alos", AlosConfiguration())
