import os
import shutil
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, NamedTuple
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from pyhgtmap.sources.srtm import SRTM, SrtmIndex, areas_from_kml, get_url_for_tile
from tests import TEST_DATA_PATH

if TYPE_CHECKING:
    from pyhgtmap.configuration import Configuration

BASE_URLS = {
    1: "https://earthexplorer.usgs.gov/download/5e83a3efe0103743/SRTM1{:s}V3/EE",
    3: "https://earthexplorer.usgs.gov/download/5e83a43cb348f8ec/SRTM3{:s}V2/EE",
}


@pytest.mark.parametrize(
    ("resolution", "area", "expected_url"),
    [
        (
            1,
            "N43E006",
            "https://earthexplorer.usgs.gov/download/5e83a3efe0103743/SRTM1N43E006V3/EE",
        ),
        (
            3,
            "N43E006",
            "https://earthexplorer.usgs.gov/download/5e83a43cb348f8ec/SRTM3N43E006V2/EE",
        ),
        (
            3,
            "S02W123",
            "https://earthexplorer.usgs.gov/download/5e83a43cb348f8ec/SRTM3S02W123V2/EE",
        ),
    ],
)
def test_get_url_for_tile(resolution: int, area: str, expected_url: str) -> None:
    """Get the URL for a given tile."""
    assert get_url_for_tile(resolution, area) == expected_url


@pytest.fixture
def inside_temp_dir() -> Generator[str, Any, None]:
    with TemporaryDirectory() as temp_dir:
        # HGT dir is expected to be created by the caller
        (Path(temp_dir) / "hgt").mkdir()
        yield temp_dir


@pytest.fixture
def coverage_kml_content() -> bytes:
    with open(os.path.join(TEST_DATA_PATH, "srtm_v3_srtmgl3.kml"), "rb") as file:
        return file.read()


@pytest.fixture
def index_content() -> bytes:
    """Return a simple index file content."""
    return b"# SRTM3v3.0 index file, VERSION=2\nN00E006\nN00E009\n"


class FakeCredential(NamedTuple):
    user: str
    password: str


@pytest.fixture
def fake_credential() -> FakeCredential:
    return FakeCredential(user="testuser", password="testpass")  # noqa: S106


@pytest.fixture
def httpx_mock_successful_srtm_login(
    httpx_mock: HTTPXMock, fake_credential: FakeCredential
) -> HTTPXMock:
    """Mock successful SRTM login to EROS Registration System."""
    login_html = """
    <html>
        <title>Login - EROS Registration System</title>
        <form id="loginForm">
            <input type="hidden" name="csrf_token" value="test_token"/>
        </form>
    </html>
    """
    httpx_mock.add_response(
        url="https://ers.cr.usgs.gov/",
        method="GET",
        text=login_html,
    )
    httpx_mock.add_response(
        url="https://ers.cr.usgs.gov/",
        method="POST",
        match_content=b"username=testuser&password=testpass&csrf_token=test_token",
        text="Login successful",
    )

    return httpx_mock


def test_areas_from_kml(coverage_kml_content: bytes) -> None:
    areas = areas_from_kml(coverage_kml_content)
    assert len(areas) == 14297

    # Check few random tiles
    assert "N43E006" in areas
    assert "N55E158" in areas
    assert "N48E000" in areas
    assert "N48W001" in areas
    assert "N00E016" in areas
    assert "S01E016" in areas
    assert "S11E179" in areas
    assert "N51W180" in areas
    assert "N57W014" in areas
    assert "S08E072" in areas

    # This one corresponds to a hole in the coverage map
    assert "S16W142" not in areas
    # Check adjacent tiles
    assert "S16W143" in areas
    assert "S16W141" in areas
    assert "S15W142" in areas
    assert "S17W142" in areas
    # Another hole, north-east
    assert "N43E014" not in areas
    assert "N44E014" in areas
    assert "N45E014" in areas
    assert "N42E014" in areas
    assert "N43E013" in areas
    assert "N43E015" in areas


class TestSrtmIndex:
    @staticmethod
    def test_init_from_web(
        inside_temp_dir: str, httpx_mock: HTTPXMock, coverage_kml_content: bytes
    ) -> None:
        """Test the SRTM index can be initialized from the web."""
        # Prepare
        httpx_mock.add_response(
            url="https://dds.cr.usgs.gov/ee-data/coveragemaps/kml/ee/srtm_v3_srtmgl1.kml",
            method="GET",
            content=coverage_kml_content,
        )
        index = SrtmIndex(inside_temp_dir, 1)

        # Test
        with patch.object(index, "save") as save_mock:
            index.init_from_web()

            # Check
            save_mock.assert_called_once()
            # Use a local variable to disable warning only once
            entries = index._entries  # noqa: SLF001
            assert len(entries) == 14297

            # Only check one tile; dedicated test for areas_from_kml
            assert "N43E006" in entries

    @staticmethod
    def test_load(inside_temp_dir: str) -> None:
        shutil.copy(
            os.path.join(TEST_DATA_PATH, "hgtIndex_3_v3.0.txt"),
            os.path.join(inside_temp_dir, "hgtIndex_3_v3.0.txt"),
        )
        index = SrtmIndex(inside_temp_dir, 3)
        index.load()
        entries = index._entries  # noqa: SLF001
        assert len(entries) == 14297
        assert "N00E006" in entries
        assert "N42W092" in entries
        assert "S56W072" in entries

    @staticmethod
    def test_save(inside_temp_dir: str) -> None:
        index = SrtmIndex(inside_temp_dir, 1)

        entries = index._entries  # noqa: SLF001
        entries.add("N00E006")
        entries.add("N42W092")
        entries.add("S56W072")

        index.save()

        with open(os.path.join(inside_temp_dir, "hgtIndex_1_v3.0.txt")) as index_file:
            assert (
                index_file.read()
                == """# SRTM1v3.0 index file, VERSION=2
N00E006
N42W092
S56W072
"""
            )

    @staticmethod
    def test_entries_load() -> None:
        """Entries loaded from file"""
        index = SrtmIndex("", 1)

        def fake_load(self) -> None:
            self._entries.add("N00E006")

        with (
            patch.object(SrtmIndex, "load", fake_load),
            patch.object(SrtmIndex, "init_from_web") as init_from_web_mock,
        ):
            entries = index.entries
            assert entries == {"N00E006"}
            init_from_web_mock.assert_not_called()

    @staticmethod
    def test_entries_init_from_web() -> None:
        """Entries initialized from web"""
        index = SrtmIndex("", 1)

        def fake_init_from_web(self) -> None:
            self._entries.add("S00W006")

        with (
            patch.object(SrtmIndex, "load") as load_mock,
            patch.object(SrtmIndex, "init_from_web", fake_init_from_web),
        ):
            load_mock.side_effect = FileNotFoundError
            entries = index.entries
            assert entries == {"S00W006"}
            load_mock.assert_called_once()


class TestSRTM:
    """Tests for SRTM source class."""

    @pytest.fixture
    def srtm_instance(
        self, test_configuration: "Configuration", fake_credential: FakeCredential
    ) -> Generator[SRTM, Any, None]:
        """Create a SRTM instance with mocked credentials."""
        from pyhgtmap.sources.srtm import SRTMConfiguration

        with TemporaryDirectory() as temp_dir:
            # Set up required configuration
            test_configuration.add_sub_config("srtm", SRTMConfiguration())
            test_configuration.srtm.user = fake_credential.user
            test_configuration.srtm.password = fake_credential.password

            srtm = SRTM(temp_dir, temp_dir, test_configuration)
            yield srtm

    @staticmethod
    def test_srtm_init_success(
        test_configuration: "Configuration",
        fake_credential: FakeCredential,
    ) -> None:
        """SRTM instance initializes successfully with credentials."""
        from pyhgtmap.sources.srtm import SRTMConfiguration

        with TemporaryDirectory() as temp_dir:
            test_configuration.add_sub_config("srtm", SRTMConfiguration())
            test_configuration.srtm.user = fake_credential.user
            test_configuration.srtm.password = fake_credential.password

            srtm = SRTM(temp_dir, temp_dir, test_configuration)

            assert srtm.NICKNAME == "srtm"
            assert srtm.FILE_EXTENSION == "tif"
            assert srtm.cache_dir_root == temp_dir
            assert srtm.config_dir == temp_dir
            assert len(srtm._indexes) == 2  # noqa: SLF001
            assert 1 in srtm._indexes  # noqa: SLF001
            assert 3 in srtm._indexes  # noqa: SLF001

    @staticmethod
    def test_srtm_init_missing_user(
        test_configuration: "Configuration", fake_credential: FakeCredential
    ) -> None:
        """SRTM initialization fails when user is missing."""
        from pyhgtmap.sources.srtm import SRTMConfiguration

        with TemporaryDirectory() as temp_dir:
            test_configuration.add_sub_config("srtm", SRTMConfiguration())
            test_configuration.srtm.user = None
            test_configuration.srtm.password = fake_credential.password

            with pytest.raises(ValueError, match="SRTM user and password are required"):
                SRTM(temp_dir, temp_dir, test_configuration)

    @staticmethod
    def test_srtm_init_missing_password(
        test_configuration: "Configuration", fake_credential: FakeCredential
    ) -> None:
        """SRTM initialization fails when password is missing."""
        from pyhgtmap.sources.srtm import SRTMConfiguration

        with TemporaryDirectory() as temp_dir:
            test_configuration.add_sub_config("srtm", SRTMConfiguration())
            test_configuration.srtm.user = fake_credential.user
            test_configuration.srtm.password = None

            with pytest.raises(ValueError, match="SRTM user and password are required"):
                SRTM(temp_dir, temp_dir, test_configuration)

    @staticmethod
    def test_srtm_nickname() -> None:
        """SRTM has correct nickname."""
        assert SRTM.NICKNAME == "srtm"

    @staticmethod
    def test_srtm_file_extension() -> None:
        """SRTM has correct file extension."""
        assert SRTM.FILE_EXTENSION == "tif"

    @staticmethod
    def test_srtm_banner_exists() -> None:
        """SRTM has a banner message."""
        assert SRTM.BANNER
        assert "NASA" in SRTM.BANNER
        assert "https://www.earthdata.nasa.gov" in SRTM.BANNER

    @staticmethod
    def test_srtm_supported_resolutions() -> None:
        """SRTM supports 1 and 3 arc-second resolutions."""
        assert SRTM.SUPPORTED_RESOLUTIONS == (1, 3)

    @staticmethod
    def test_client_initialization(
        srtm_instance: SRTM,
        httpx_mock_successful_srtm_login: HTTPXMock,
    ) -> None:
        """SRTM client initializes with login."""
        client = srtm_instance.client

        assert client is not None
        assert isinstance(client, type(srtm_instance._client))  # noqa: SLF001

    @staticmethod
    def test_client_initialization_failure_wrong_page(
        srtm_instance: SRTM,
        httpx_mock: HTTPXMock,
    ) -> None:
        """SRTM client initialization fails with unexpected page."""
        # Mock wrong page response
        httpx_mock.add_response(
            url="https://ers.cr.usgs.gov/",
            method="GET",
            text="<html><title>Wrong Page</title></html>",
        )

        with pytest.raises(ValueError, match="Expected login page"):
            _ = srtm_instance.client

    @staticmethod
    def test_client_caching(
        srtm_instance: SRTM,
        httpx_mock_successful_srtm_login: HTTPXMock,
    ) -> None:
        """SRTM client is cached after first access."""
        # Access client twice
        client1 = srtm_instance.client
        client2 = srtm_instance.client

        # Should be the same instance
        assert client1 is client2

    @staticmethod
    def test_download_missing_file_tile_exists(
        srtm_instance: SRTM,
        httpx_mock_successful_srtm_login: HTTPXMock,
    ) -> None:
        """Download file for existing tile."""
        with TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "N43E006.tif")

            # Mock the tile download
            tile_content = b"fake tiff data"
            httpx_mock_successful_srtm_login.add_response(
                url="https://earthexplorer.usgs.gov/download/5e83a3efe0103743/SRTM1N43E006V3/EE",
                method="GET",
                content=tile_content,
                headers={"Content-Type": "image/tiff"},
            )

            # Mock the _entries set directly (private attribute)
            srtm_instance._indexes[1]._entries = {"N43E006"}  # noqa: SLF001

            srtm_instance.download_missing_file("N43E006", 1, output_file)

            # Check file was written
            assert os.path.exists(output_file)
            with open(output_file, "rb") as f:
                assert f.read() == tile_content

    @staticmethod
    def test_download_missing_file_tile_not_in_index(
        srtm_instance: SRTM,
    ) -> None:
        """Download fails for tile not in index."""
        with TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "N99E099.tif")

            # Mock the _entries set directly (private attribute)
            srtm_instance._indexes[1]._entries = {"N43E006"}  # noqa: SLF001

            with pytest.raises(FileNotFoundError):
                srtm_instance.download_missing_file("N99E099", 1, output_file)

    @staticmethod
    def test_download_missing_file_wrong_content_type(
        srtm_instance: SRTM,
        httpx_mock_successful_srtm_login: HTTPXMock,
    ) -> None:
        """Download fails with wrong content type."""
        with TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "N43E006.tif")

            # Mock wrong content type
            httpx_mock_successful_srtm_login.add_response(
                url="https://earthexplorer.usgs.gov/download/5e83a3efe0103743/SRTM1N43E006V3/EE",
                method="GET",
                content=b"fake data",
                headers={"Content-Type": "text/plain"},
            )

            # Mock the _entries set directly (private attribute)
            srtm_instance._indexes[1]._entries = {"N43E006"}  # noqa: SLF001

            with pytest.raises(ValueError, match="Unexpected content type"):
                srtm_instance.download_missing_file("N43E006", 1, output_file)

    @pytest.mark.parametrize(
        ("json_content", "expected_exception"),
        [
            (
                '{"errorMessage": "Invalid scene or product", "isPending": false, "url": null}',
                FileNotFoundError,
            ),
            (
                '{"url": null, "errorMessage": "Invalid scene or product", "isPending": false}',
                FileNotFoundError,
            ),
            (
                '{"errorMessage": "Invalid scene or product",  "isPending": false, "url": null}',
                FileNotFoundError,
            ),
            ("Another payload", ValueError),
        ],
    )
    def test_download_missing_file_invalid_scene_json(
        self,
        srtm_instance: SRTM,
        httpx_mock_successful_srtm_login: HTTPXMock,
        json_content: str,
        expected_exception: type[Exception],
    ) -> None:
        """Download raises FileNotFoundError on known invalid scene JSON."""
        with TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "N42E049.tif")

            # Mock invalid scene JSON response
            httpx_mock_successful_srtm_login.add_response(
                url="https://earthexplorer.usgs.gov/download/5e83a3efe0103743/SRTM1N42E049V3/EE",
                method="GET",
                text=json_content,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

            # Mock the _entries set directly (private attribute)
            srtm_instance._indexes[1]._entries = {"N42E049"}  # noqa: SLF001

            with pytest.raises(expected_exception):
                srtm_instance.download_missing_file("N42E049", 1, output_file)

    @staticmethod
    def test_register_cli_options() -> None:
        """SRTM registers CLI options."""
        import configargparse

        parser = configargparse.ArgumentParser()
        from pyhgtmap.configuration import NestedConfig

        root_config = NestedConfig()

        SRTM.register_cli_options(parser, root_config)

        # Check that parser has the expected arguments
        args = parser.parse_args(
            ["--srtm-user", "myuser", "--srtm-password", "mypassword"]
        )
        # configargparse stores nested attributes with dots
        assert getattr(args, "srtm.user", None) == "myuser"
        assert getattr(args, "srtm.password", None) == "mypassword"

    @staticmethod
    def test_multiple_resolutions(srtm_instance: SRTM) -> None:
        """SRTM creates indexes for all supported resolutions."""

        for resolution in SRTM.SUPPORTED_RESOLUTIONS:
            assert resolution in srtm_instance._indexes  # noqa: SLF001
            assert isinstance(srtm_instance._indexes[resolution], SrtmIndex)  # noqa: SLF001
