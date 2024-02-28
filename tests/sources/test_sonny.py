import os
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest
from pydrive2.auth import RefreshError

from pyhgtmap.configuration import Configuration
from pyhgtmap.sources.sonny import CLIENT_SECRET_FILE, SAVED_CREDENTIALS_FILE, Sonny


@pytest.fixture()
def gauth_mock() -> Generator[MagicMock, None, None]:
    """Mock pyhgtmap.sources.sonny.GoogleAuth"""
    with patch("pyhgtmap.sources.sonny.GoogleAuth") as gauth_mock:
        yield gauth_mock


@pytest.fixture()
def gdrive_mock() -> Generator[MagicMock, None, None]:
    """Mock pyhgtmap.sources.sonny.GoogleDrive"""
    with patch("pyhgtmap.sources.sonny.GoogleDrive") as gdrive_mock:
        yield gdrive_mock


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
        ("resolution", "folder_id"),
        [(1, "0BxphPoRgwhnoWkRoTFhMbTM3RDA"), (3, "0BxphPoRgwhnoekRQZUZJT2ZRX2M")],
    )
    def test_download_missing_file(
        gdrive_mock: MagicMock,
        gauth_mock: MagicMock,
        resolution: int,
        folder_id: str,
        configuration: Configuration,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            # Prepare
            conf_dir = os.path.join(temp_dir, "conf")
            hgt_dir = os.path.join(temp_dir, "hgt")
            # HGT dir is expected to be created by the caller
            Path(hgt_dir).mkdir()
            out_file_name = os.path.join(hgt_dir, "N42E004.hgt")
            gdrive_file_mock = MagicMock()
            hgt_size = 100
            gdrive_file_mock.GetContentIOBuffer.return_value = get_hgt_zipped_file(
                "N42E004",
                hgt_size,
            )
            gdrive_mock.return_value.ListFile.return_value.GetList.return_value = [
                gdrive_file_mock,
            ]

            # Test
            sonny = Sonny(hgt_dir, conf_dir, configuration)
            sonny.download_missing_file("N42E004", resolution, out_file_name)

            # Check
            assert os.path.isdir(conf_dir)
            assert os.path.isfile(out_file_name)
            with open(out_file_name) as out_file:
                assert out_file.read() == "0" * hgt_size
            gauth_mock.assert_called_once_with(
                settings={
                    "client_config_file": os.path.join(conf_dir, CLIENT_SECRET_FILE),
                    "save_credentials": True,
                    "save_credentials_backend": "file",
                    "save_credentials_file": os.path.join(
                        conf_dir,
                        SAVED_CREDENTIALS_FILE,
                    ),
                    "get_refresh_token": True,
                    "oauth_scope": ["https://www.googleapis.com/auth/drive.readonly"],
                },
            )
            gdrive_mock.assert_called_once_with(gauth_mock.return_value)
            gdrive_mock.return_value.ListFile.assert_called_once_with(
                {
                    "q": f"'{folder_id}' in parents and trashed=false "
                    "and mimeType='application/x-zip-compressed' and title='N42E004.zip'",
                },
            )

    @staticmethod
    def test_download_missing_file_not_found(
        gdrive_mock: MagicMock,
        gauth_mock: MagicMock,
        configuration: Configuration,
    ) -> None:
        """Exception to be raised when file not found."""
        with TemporaryDirectory() as temp_dir:
            # Prepare
            conf_dir = os.path.join(temp_dir, "conf")
            hgt_dir = os.path.join(temp_dir, "hgt")
            # HGT dir is expected to be created by the caller
            Path(hgt_dir).mkdir()
            out_file_name = os.path.join(hgt_dir, "N42E004.hgt")
            # Not found -> empty list returned by gdrive API
            gdrive_mock.return_value.ListFile.return_value.GetList.return_value = []

            # Test
            sonny = Sonny(hgt_dir, conf_dir, configuration)
            with pytest.raises(
                FileNotFoundError,
                match="No file available for area N42E004",
            ):
                sonny.download_missing_file("N42E004", 1, out_file_name)

            # Check
            assert not os.path.exists(out_file_name)
            gdrive_mock.assert_called_once_with(gauth_mock.return_value)
            gdrive_mock.return_value.ListFile.assert_called_once_with(
                {
                    "q": "'0BxphPoRgwhnoWkRoTFhMbTM3RDA' in parents and trashed=false "
                    "and mimeType='application/x-zip-compressed' and title='N42E004.zip'",
                },
            )

    @staticmethod
    def test_auth_expired_token(
        gdrive_mock: MagicMock,
        gauth_mock: MagicMock,
        caplog: pytest.LogCaptureFixture,
        configuration: Configuration,
    ) -> None:
        # First call is an exception due to expired token
        gauth_mock.return_value.CommandLineAuth.side_effect = [
            RefreshError("Access token refresh failed: invalid_grant: Bad Request"),
            True,
        ]
        with TemporaryDirectory() as temp_dir:
            # Prepare
            conf_dir = os.path.join(temp_dir, "conf")
            # Create fake saved credentials file
            Path(conf_dir).mkdir()
            Path(conf_dir, SAVED_CREDENTIALS_FILE).touch()
            hgt_dir = os.path.join(temp_dir, "hgt")
            sonny = Sonny(hgt_dir, conf_dir, configuration)

            # Test
            _ = sonny.gdrive

            # Check
            # Ensure auth retried
            assert gauth_mock.call_count == 2
            assert gauth_mock.return_value.CommandLineAuth.call_count == 2
            # The mock didn't recreate the file
            assert not Path(conf_dir, SAVED_CREDENTIALS_FILE).exists()
            assert "GDrive API token expired?" in caplog.text
