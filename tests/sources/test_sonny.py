import os
import pathlib
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest

from pyhgtmap.sources.sonny import Sonny


def get_hgt_zipped_file(file_base_name: str, file_size: int) -> BytesIO:
    """Generate and zip a fake .HGT file"""
    # We don't care about content
    raw_original_bytes: bytes = b"0" * file_size
    output_file = BytesIO()
    with ZipFile(output_file, "w") as zip_file:
        zip_file.writestr(f"{file_base_name}.hgt", data=raw_original_bytes)
    # Ensure buffer is ready for .read()
    output_file.seek(0)
    return output_file


class TestSonny:
    @staticmethod
    # Test both supported resolutions
    @pytest.mark.parametrize(
        "resolution, folder_id",
        [(1, "0BxphPoRgwhnoWkRoTFhMbTM3RDA"), (3, "0BxphPoRgwhnoekRQZUZJT2ZRX2M")],
    )
    @patch("pyhgtmap.sources.sonny.GoogleAuth")
    @patch("pyhgtmap.sources.sonny.GoogleDrive")
    def test_download_missing_file(
        gdrive_mock: MagicMock, gauth_mock: MagicMock, resolution: int, folder_id: str
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            # Prepare
            conf_dir = os.path.join(temp_dir, "conf")
            hgt_dir = os.path.join(temp_dir, "hgt")
            # HGT dir is expected to be created by the caller
            pathlib.Path(hgt_dir).mkdir()
            out_file_name = os.path.join(hgt_dir, "N42E004.hgt")
            gdrive_file_mock = MagicMock()
            hgt_size = 100
            gdrive_file_mock.GetContentIOBuffer.return_value = get_hgt_zipped_file(
                "N42E004", hgt_size
            )
            gdrive_mock.return_value.ListFile.return_value.GetList.return_value = [
                gdrive_file_mock
            ]

            # Test
            sonny = Sonny(hgt_dir, conf_dir)
            sonny.download_missing_file("N42E004", resolution, out_file_name)

            # Check
            assert os.path.isdir(conf_dir)
            assert os.path.isfile(out_file_name)
            with open(out_file_name) as out_file:
                assert out_file.read() == "0" * hgt_size
            gauth_mock.assert_called_once_with(
                settings={
                    "client_config_file": os.path.join(conf_dir, "client-secret.json"),
                    "save_credentials": True,
                    "save_credentials_backend": "file",
                    "save_credentials_file": os.path.join(
                        conf_dir, "gdrive-credentials.json"
                    ),
                    "get_refresh_token": True,
                    "oauth_scope": ["https://www.googleapis.com/auth/drive.readonly"],
                }
            )
            gdrive_mock.assert_called_once_with(gauth_mock.return_value)
            gdrive_mock.return_value.ListFile.assert_called_once_with(
                {
                    "q": f"'{folder_id}' in parents and trashed=false "
                    "and mimeType='application/x-zip-compressed' and title='N42E004.zip'"
                }
            )

    @staticmethod
    @patch("pyhgtmap.sources.sonny.GoogleAuth")
    @patch("pyhgtmap.sources.sonny.GoogleDrive")
    def test_download_missing_file_not_found(
        gdrive_mock: MagicMock, gauth_mock: MagicMock
    ) -> None:
        """Exception to be raised when file not found."""
        with TemporaryDirectory() as temp_dir:
            # Prepare
            conf_dir = os.path.join(temp_dir, "conf")
            hgt_dir = os.path.join(temp_dir, "hgt")
            # HGT dir is expected to be created by the caller
            pathlib.Path(hgt_dir).mkdir()
            out_file_name = os.path.join(hgt_dir, "N42E004.hgt")
            # Not found -> empty list returned by gdrive API
            gdrive_mock.return_value.ListFile.return_value.GetList.return_value = []

            # Test
            sonny = Sonny(hgt_dir, conf_dir)
            with pytest.raises(
                FileNotFoundError, match="No file available for area N42E004"
            ):
                sonny.download_missing_file("N42E004", 1, out_file_name)

            # Check
            assert not os.path.exists(out_file_name)
            gdrive_mock.assert_called_once_with(gauth_mock.return_value)
            gdrive_mock.return_value.ListFile.assert_called_once_with(
                {
                    "q": "'0BxphPoRgwhnoWkRoTFhMbTM3RDA' in parents and trashed=false "
                    "and mimeType='application/x-zip-compressed' and title='N42E004.zip'"
                }
            )
