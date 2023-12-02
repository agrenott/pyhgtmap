import io
import logging
import os
import pathlib
from typing import Dict, List, Optional, cast
from zipfile import ZipFile

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from pydrive2.files import GoogleDriveFile

from . import Source

LOGGER: logging.Logger = logging.getLogger(__name__)

__all__ = ["Sonny"]


class Sonny(Source):
    """Downloader for SONNY's LiDAR DIGITAL TERRAIN MODELS
    https://sonny.4lima.de/
    """

    NICKNAME = "sonn"

    BANNER = (
        "You're downloading from Sonny's LiDAR DEM source. Please "
        "consider visiting https://sonny.4lima.de/ to support the author."
    )

    # Root Sonny's Google Drive folders IDs for Europe DTMs, for various resolutions
    # TODO: does this change often? Should it be configurable/self-discovered from website?
    FOLDER_IDS: Dict[int, str] = {
        1: "0BxphPoRgwhnoWkRoTFhMbTM3RDA",
        3: "0BxphPoRgwhnoekRQZUZJT2ZRX2M",
    }

    def __init__(self, cache_dir_root: str, config_dir: str) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached HGT files
            config_dir (str): Root directory to store configuration (if any)
        """
        super().__init__(cache_dir_root, config_dir)
        self._gdrive: Optional[GoogleDrive] = None

    @property
    def gdrive(self) -> GoogleDrive:
        """Lazily connect to Google Drive API, using OAuth2."""
        # Ensure config drectory exists
        pathlib.Path(self.config_dir).mkdir(parents=True, exist_ok=True)

        if self._gdrive is None:
            # pydrive2 settings
            settings = {
                "client_config_file": os.path.join(
                    self.config_dir, "client-secret.json"
                ),
                "save_credentials": True,
                "save_credentials_backend": "file",
                "save_credentials_file": os.path.join(
                    self.config_dir, "gdrive-credentials.json"
                ),
                "get_refresh_token": True,
                # Sadly, "heavy" permissions are required to access public files...
                # ref. https://issuetracker.google.com/issues/168687448
                "oauth_scope": ["https://www.googleapis.com/auth/drive.readonly"],
            }
            gauth = GoogleAuth(settings=settings)
            gauth.CommandLineAuth()
            self._gdrive = GoogleDrive(gauth)
            LOGGER.debug("Connected to Google Drive API")

        return self._gdrive

    def download_missing_file(
        self, area: str, resolution: int, output_file_name: str
    ) -> None:
        # Find file by name (called title in GDrive), matching requested area
        files: List[GoogleDriveFile] = self.gdrive.ListFile(
            {
                "q": f"'{Sonny.FOLDER_IDS[resolution]}' in parents and "
                f"trashed=false and mimeType='application/x-zip-compressed' and title='{area}.zip'"
            }
        ).GetList()
        if not files:
            raise FileNotFoundError(f"No file available for area {area}")
        if len(files) > 1:
            # Hopefully shouldn't happen...
            LOGGER.warning(
                "More than one file matching for area %s; using first one...", area
            )

        # Actually download and extract file on the fly
        zipped_buffer = files[0].GetContentIOBuffer(remove_bom=True)
        with ZipFile(io.BytesIO(cast(bytes, zipped_buffer.read()))) as zip_archive:
            # We expect the name to match the archive & area one
            with zip_archive.open(f"{area}.hgt") as hgt_file_in:
                with open(output_file_name, mode="wb") as hgt_file_out:
                    hgt_file_out.write(hgt_file_in.read())
