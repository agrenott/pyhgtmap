import os
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest
from pytest_httpx import HTTPXMock

from pyhgtmap.configuration import Configuration
from pyhgtmap.sources.alos import Alos, AlosConfiguration, get_url_for_tile

ROOT_URL = "https://www.eorc.jaxa.jp/ALOS/aw3d30/data/release_v2303"


def test_get_url_for_tile() -> None:
    assert get_url_for_tile("N45E006") == f"{ROOT_URL}/N045E005/N045E006.zip"
    assert get_url_for_tile("S03E101") == f"{ROOT_URL}/S005E100/S003E101.zip"
    assert get_url_for_tile("S75W123") == f"{ROOT_URL}/S075W125/S075W123.zip"
    # East/west of 0 degree meridian
    assert get_url_for_tile("N48W001") == f"{ROOT_URL}/N045W005/N048W001.zip"
    assert get_url_for_tile("N49E000") == f"{ROOT_URL}/N045E000/N049E000.zip"
    # East/west of 180 degrees meridian
    assert get_url_for_tile("N71E179") == f"{ROOT_URL}/N070E175/N071E179.zip"
    assert get_url_for_tile("N68W180") == f"{ROOT_URL}/N065W180/N068W180.zip"


def get_alos_zipped_file(alos_area: str) -> BytesIO:
    """Generate a fake ALOS zip file"""
    # Content from an actual file:
    # 0: <ZipInfo filename='N017E045/' filemode='drwxr-xr-x' external_attr=0x10>
    # 1: <ZipInfo filename='N017E045/ALPSMLC30_N017E045_LST.txt' compress_type=deflate filemode='-rw-r--r--' file_size=7280 compress_size=1071>
    # 2: <ZipInfo filename='N017E045/ALPSMLC30_N017E045_HDR.txt' compress_type=deflate filemode='-rw-r--r--' file_size=1108 compress_size=253>
    # 3: <ZipInfo filename='N017E045/ALPSMLC30_N017E045_MSK.tif' compress_type=deflate filemode='-rw-r--r--' file_size=12974766 compress_size=355892>
    # 4: <ZipInfo filename='N017E045/ALPSMLC30_N017E045_QAI.txt' compress_type=deflate filemode='-rw-r--r--' file_size=2610 compress_size=764>
    # 5: <ZipInfo filename='N017E045/ALPSMLC30_N017E045_STK.tif' compress_type=deflate filemode='-rw-r--r--' file_size=12989173 compress_size=1612296>
    # 6: <ZipInfo filename='N017E045/ALPSMLC30_N017E045_DSM.tif' compress_type=deflate filemode='-rw-r--r--' file_size=25949185 compress_size=8953708>

    # We don't care about content
    file_size = 5
    raw_original_bytes: bytes = b"0" * file_size
    output_file = BytesIO()
    with ZipFile(output_file, "w") as zip_file:
        for suffix in (
            "LST.txt",
            "HDR.txt",
            "MSK.tif",
            "QAI.txt",
            "STK.tif",
            "DSM.tif",
        ):
            zip_file.writestr(
                f"{alos_area}/ALPSMLC30_{alos_area}_{suffix}",
                data=raw_original_bytes,
            )

    # Ensure buffer is ready for .read()
    output_file.seek(0)
    return output_file


@pytest.fixture
def alos_configuration(configuration: Configuration) -> Configuration:
    alos_specific = AlosConfiguration()
    configuration.add_sub_config("alos", alos_specific)
    alos_specific.user = "user"
    alos_specific.password = "password"  # noqa: S105
    return configuration


class TestAlos:
    @staticmethod
    def test_download_missing_file(
        httpx_mock: HTTPXMock,
        alos_configuration: Configuration,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            # Prepare
            conf_dir = os.path.join(temp_dir, "conf")
            hgt_dir = os.path.join(temp_dir, "hgt")
            # HGT dir is expected to be created by the caller
            Path(hgt_dir).mkdir()
            out_file_name = os.path.join(hgt_dir, "N42E004.hgt")

            httpx_mock.add_response(
                url=get_url_for_tile("N42E004"),
                method="GET",
                content=get_alos_zipped_file("N042E004").read(),
            )

            # Test
            sonny = Alos(hgt_dir, conf_dir, alos_configuration)
            sonny.download_missing_file("N42E004", 1, out_file_name)

            # Check
            assert os.path.isfile(out_file_name)
            with open(out_file_name) as out_file:
                assert out_file.read() == "0" * 5

    @staticmethod
    def test_download_missing_file_not_found(
        httpx_mock: HTTPXMock,
        alos_configuration: Configuration,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            # Prepare
            conf_dir = os.path.join(temp_dir, "conf")
            hgt_dir = os.path.join(temp_dir, "hgt")
            # HGT dir is expected to be created by the caller
            Path(hgt_dir).mkdir()
            out_file_name = os.path.join(hgt_dir, "N55E003.hgt")

            # When tile doesn't exist, ALOS returns a redirect HTML page
            httpx_mock.add_response(
                url=get_url_for_tile("N55E003"),
                method="GET",
                html='<p>The document has moved <a href="https://www.eorc.jaxa.jp/ALOS/url_change_info.htm">here</a>.</p>',
                status_code=302,
            )

            # Test
            sonny = Alos(hgt_dir, conf_dir, alos_configuration)
            with pytest.raises(
                FileNotFoundError,
                match="Unable to download https://www.eorc.jaxa.jp/ALOS/aw3d30/data/release_v2303/N055E000/N055E003.zip; HTTP code 302",
            ):
                sonny.download_missing_file("N55E003", 1, out_file_name)
