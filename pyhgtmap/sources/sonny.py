from __future__ import annotations

import io
import logging
import os
import pathlib
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile

from pydrive2.auth import GoogleAuth, RefreshError
from pydrive2.drive import GoogleDrive

from . import Source

if TYPE_CHECKING:
    from pydrive2.files import GoogleDriveFile


LOGGER: logging.Logger = logging.getLogger(__name__)

__all__ = ["Sonny"]

CLIENT_SECRET_FILE = "client-secret.json"  # noqa: S105 # This is NOT a password!
SAVED_CREDENTIALS_FILE = "gdrive-credentials.json"


# Root Sonny's Google Drive folders IDs for Europe DTMs, for various resolutions
# TODO: does this change often? Should it be configurable/self-discovered from website?
FOLDER_IDS: dict[int, str] = {
    1: "0BxphPoRgwhnoWkRoTFhMbTM3RDA",
    3: "0BxphPoRgwhnoekRQZUZJT2ZRX2M",
}


class Sonny(Source):
    """Downloader for SONNY's LiDAR DIGITAL TERRAIN MODELS
    https://sonny.4lima.de/
    """

    NICKNAME = "sonn"

    BANNER = (
        "You're downloading from Sonny's LiDAR DEM source. Please "
        "consider visiting https://sonny.4lima.de/ to support the author."
    )

    def __init__(self, cache_dir_root: str, config_dir: str) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached HGT files
            config_dir (str): Root directory to store configuration (if any)
        """
        super().__init__(cache_dir_root, config_dir)
        self._gdrive: GoogleDrive | None = None

    @property
    def gdrive(self) -> GoogleDrive:
        """Lazily connect to Google Drive API, using OAuth2."""
        # Ensure config drectory exists
        pathlib.Path(self.config_dir).mkdir(parents=True, exist_ok=True)

        if self._gdrive is None:
            credentials_file = os.path.join(self.config_dir, SAVED_CREDENTIALS_FILE)
            # pydrive2 settings
            settings = {
                "client_config_file": os.path.join(self.config_dir, CLIENT_SECRET_FILE),
                "save_credentials": True,
                "save_credentials_backend": "file",
                "save_credentials_file": credentials_file,
                "get_refresh_token": True,
                # Sadly, "heavy" permissions are required to access public files...
                # ref. https://issuetracker.google.com/issues/168687448
                "oauth_scope": ["https://www.googleapis.com/auth/drive.readonly"],
            }
            try:
                gauth = GoogleAuth(settings=settings)
                gauth.CommandLineAuth()
            except RefreshError:
                if not pathlib.Path(credentials_file).exists():
                    # Credentials not stored, not the expected root cause
                    raise

                # Google test tokens expire after 7 days. See:
                # - https://github.com/iterative/PyDrive2/issues/184
                # - https://stackoverflow.com/questions/76006880/why-does-pydrive-stop-refreshing-the-access-token-after-a-while
                LOGGER.warning(
                    "GDrive API token expired? Trying to delete saved credentials and force new authentication",
                )
                # Delete saved credentials and retry full auth
                pathlib.Path.unlink(pathlib.Path(credentials_file))
                # Must start from a new instance to force configuration refresh
                gauth = GoogleAuth(settings=settings)
                gauth.CommandLineAuth()

            self._gdrive = GoogleDrive(gauth)
            LOGGER.debug("Connected to Google Drive API")

        return self._gdrive

    def download_missing_file(
        self,
        area: str,
        resolution: int,
        output_file_name: str,
    ) -> None:
        # Find file by name (called title in GDrive), matching requested area
        files: list[GoogleDriveFile] = self.gdrive.ListFile(
            {
                "q": f"'{FOLDER_IDS[resolution]}' in parents and "
                f"trashed=false and mimeType='application/x-zip-compressed' and title='{area}.zip'",
            },
        ).GetList()
        if not files:
            raise FileNotFoundError(f"No file available for area {area}")
        if len(files) > 1:
            # Hopefully shouldn't happen...
            LOGGER.warning(
                "More than one file matching for area %s; using first one...",
                area,
            )

        # Actually download and extract file on the fly
        zipped_buffer = files[0].GetContentIOBuffer(remove_bom=True)
        # We expect the name to match the archive & area one
        with ZipFile(
            io.BytesIO(cast(bytes, zipped_buffer.read())),
        ) as zip_archive, zip_archive.open(f"{area}.hgt") as hgt_file_in, open(
            output_file_name,
            mode="wb",
        ) as hgt_file_out:
            hgt_file_out.write(hgt_file_in.read())
