import os
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from pyhgtmap.sources.srtm import SrtmIndex, areas_from_kml, get_url_for_tile
from tests import TEST_DATA_PATH

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


@pytest.fixture()
def inside_temp_dir() -> Generator[str, Any, None]:
    with TemporaryDirectory() as temp_dir:
        # HGT dir is expected to be created by the caller
        (Path(temp_dir) / "hgt").mkdir()
        yield temp_dir


@pytest.fixture()
def coverage_kml_content() -> bytes:
    with open(os.path.join(TEST_DATA_PATH, "srtm_v3_srtmgl3.kml"), "rb") as file:
        return file.read()


@pytest.fixture()
def index_content() -> bytes:
    """Return a simple index file content."""
    return b"# SRTM3v3.0 index file, VERSION=2\nN00E006\nN00E009\n"


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
