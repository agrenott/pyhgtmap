from __future__ import annotations

import os
import shutil
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import MagicMock, call, patch
from zipfile import ZipFile

import pytest

from pyhgtmap.sources.viewfinder import (
    ViewFinder,
    ViewFinderIndex,
    fetch_and_extract_zip,
)
from tests import TEST_DATA_PATH

# Ignoring accesses to private members, as it's sued to validate the caching mechanism
# ruff: noqa: SLF001


class TestViewFinderIndex:
    @staticmethod
    def test_load() -> None:
        with TemporaryDirectory() as temp_dir:
            shutil.copy(
                os.path.join(TEST_DATA_PATH, "viewfinderHgtIndex_3.txt"),
                os.path.join(temp_dir, "viewfinderHgtIndex_3.txt"),
            )
            index = ViewFinderIndex(temp_dir, 3)
            index.load()
            entries = index._entries
            assert len(entries) == 1127
            assert "http://viewfinderpanoramas.org/A21.zip" in entries
            assert "http://viewfinderpanoramas.org/dem3/U21.zip" in entries
            assert entries["http://viewfinderpanoramas.org/A21.zip"] == [
                "N00W055",
                "N00W056",
                "N00W057",
                "N00W058",
                "N00W059",
                "N00W060",
                "N01W055",
                "N01W056",
                "N01W057",
                "N01W058",
                "N01W059",
                "N01W060",
                "N02W055",
                "N02W056",
                "N02W057",
                "N02W058",
                "N02W059",
                "N02W060",
                "N03W055",
                "N03W056",
                "N03W057",
                "N03W058",
                "N03W059",
                "N03W060",
            ]

    @staticmethod
    def test_save() -> None:
        with TemporaryDirectory() as temp_dir:
            index = ViewFinderIndex(temp_dir, 1)
            index._entries["https://example.com/file1.zip"] = ["a", "b"]
            index._entries["https://example.com/file2.zip"] = []
            index._entries["https://example.com/file3.zip"] = [
                "c",
                "d",
                "e",
            ]
            index.save()

            with open(os.path.join(temp_dir, "viewfinderHgtIndex_1.txt")) as index_file:
                assert (
                    index_file.read()
                    == """# VIEW1 index file, VERSION=2
[https://example.com/file1.zip]
a
b
[https://example.com/file2.zip]
[https://example.com/file3.zip]
c
d
e
"""
                )

    @staticmethod
    @patch("pyhgtmap.sources.viewfinder.urlopen", autospec=True)
    def test_init_from_web(urlopen_mock: MagicMock) -> None:
        with TemporaryDirectory() as temp_dir:
            with open(
                os.path.join(
                    TEST_DATA_PATH,
                    "coverage_map_viewfinderpanoramas_org3.htm",
                ),
            ) as html_file:
                urlopen_mock.return_value.read.return_value = html_file.read()
            index = ViewFinderIndex(temp_dir, 3)

            index.init_from_web()

            urlopen_mock.assert_called_once_with(
                "http://viewfinderpanoramas.org/Coverage%20map%20viewfinderpanoramas_org3.htm",
            )
            urlopen_mock.return_value.read.assert_called_once_with()
            with open(os.path.join(temp_dir, "viewfinderHgtIndex_3.txt")) as index_file:
                content = index_file.read()
                assert (
                    "# VIEW3 index file, VERSION=4\n[http://viewfinderpanoramas.org/A21.zip]\nN00W055\nN00W056\n"
                    in content
                )
                assert (
                    "[http://viewfinderpanoramas.org/dem3/U47.zip]\nN80E096\nN80E097\nN80E098\nN80E099\nN80E100\n"
                    in content
                )

    @staticmethod
    def test_update_noop() -> None:
        """No actual index update"""
        index = ViewFinderIndex("temp_dir", 1)
        index._entries["https://example.com/file1.zip"] = ["a", "b"]
        index._entries["https://example.com/file2.zip"] = ["c"]
        index.save = MagicMock(spec=index.save)  # type: ignore[method-assign]
        index.update("https://example.com/file1.zip", ["b", "a"])
        index.save.assert_not_called()
        assert index._entries["https://example.com/file1.zip"] == ["a", "b"]

    @staticmethod
    def test_update() -> None:
        """No actual index update"""
        index = ViewFinderIndex("temp_dir", 1)
        index._entries["https://example.com/file1.zip"] = ["a", "b"]
        index._entries["https://example.com/file2.zip"] = ["c"]
        index.save = MagicMock(spec=index.save)  # type: ignore[method-assign]
        index.update("https://example.com/file1.zip", ["z"])
        index.save.assert_called_with()
        assert index._entries["https://example.com/file1.zip"] == ["z"]

    @staticmethod
    def test_get_urls_for_area() -> None:
        index = ViewFinderIndex("temp_dir", 1)
        index._entries["https://example.com/file1.zip"] = ["N01W060", "N01W061"]
        index._entries["https://example.com/file2.zip"] = []
        index._entries["https://example.com/file3.zip"] = [
            "N01W062",
            "N01W063",
            "N01W064",
        ]
        index._entries["https://example.com/file4.zip"] = [
            "N01W060",
            "N01W065",
        ]

        assert index.get_urls_for_area("N01W064") == ["https://example.com/file3.zip"]
        assert index.get_urls_for_area("N01W060") == [
            "https://example.com/file1.zip",
            "https://example.com/file4.zip",
        ]

    @staticmethod
    def test_entries_from_file() -> None:
        """Lazily load index from cache file"""
        index = ViewFinderIndex("temp_dir", 1)
        expected_index = {"some.zip": ["N01W064"]}

        def fill_index() -> None:
            index._entries = expected_index

        # Simulate a successful load from cache
        index.load = MagicMock(spec=index.load, side_effect=fill_index)  # type: ignore[method-assign]
        index.init_from_web = MagicMock(spec=index.init_from_web)  # type: ignore[method-assign]
        assert not index._entries
        assert index.entries == expected_index
        # Call it a second time to validate caching
        index.entries  # noqa: B018
        index.load.assert_called_once_with()
        # Load from file successful, no need to download from web
        index.init_from_web.assert_not_called()

    @staticmethod
    def test_entries_from_web() -> None:
        """Lazily init index from web"""
        index = ViewFinderIndex("temp_dir", 1)
        expected_index = {"some.zip": ["N01W064"]}

        def fill_index() -> None:
            index._entries = expected_index

        # Simulate a failed load from file and successful load from web
        index.load = MagicMock(spec=index.load, side_effect=FileNotFoundError)  # type: ignore[method-assign]
        index.init_from_web = MagicMock(  # type: ignore[method-assign]
            spec=index.init_from_web,
            side_effect=fill_index,
        )
        assert not index._entries
        assert index.entries == expected_index
        # Call it a second time to validate caching
        index.entries  # noqa: B018
        index.load.assert_called_once_with()
        index.init_from_web.assert_called_once_with()


def fake_view_zip_file(inner_files: list[str]) -> BytesIO:
    """Generate a fake viewfinder zone ZIP file with provided content."""
    output_file = BytesIO()
    with ZipFile(output_file, "w") as zip_file:
        for inner_file in inner_files:
            # We don't care about content
            zip_file.writestr(inner_file, data="some_data")
    # Ensure buffer is ready for .read()
    output_file.seek(0)
    return output_file


@patch("pyhgtmap.sources.viewfinder.urlopen", autospec=True)
def test_fetch_and_extract_zip(urlopen_mock: MagicMock) -> None:
    with TemporaryDirectory() as temp_dir:
        # Prepare
        urlopen_mock.return_value.read.return_value = fake_view_zip_file(
            [
                "README.txt",  # Must be ignored
                "L12/N01W064.hgt",
                "L12/N01W065.HGT",  # Uppercase extension
                "V42/Z55/N01W066.hgt",  # Sub-sub-directory
            ],
        ).read()

        # Test
        url = "http://example.com/zone.zip"
        extracted_areas: list[str] = fetch_and_extract_zip(url, temp_dir)

        # Check
        urlopen_mock.assert_called_once_with(url)
        urlopen_mock.return_value.read.assert_called_once_with()
        assert Path(temp_dir, "N01W064.hgt").is_file()
        assert Path(temp_dir, "N01W065.hgt").is_file()
        assert Path(temp_dir, "N01W066.hgt").is_file()
        assert extracted_areas == [
            "N01W064",
            "N01W065",
            "N01W066",
        ]


class TestViewFinder:
    @staticmethod
    @patch("pyhgtmap.sources.viewfinder.fetch_and_extract_zip", autospec=True)
    def test_download_missing_file_no_candidate(
        fetch_and_extract_zip_mock: MagicMock,
    ) -> None:
        """No candidate from index for requested area."""
        cache_dir_name = "cache_dir"
        source = ViewFinder(cache_dir_name, "conf_dir")
        area = "S43E007"
        index3 = MagicMock(spec=ViewFinderIndex)
        source._indexes = {3: cast(ViewFinderIndex, index3)}
        index3.get_urls_for_area.return_value = []

        with pytest.raises(FileNotFoundError):
            source.download_missing_file(
                area,
                3,
                os.path.join(cache_dir_name, f"{area}.hgt"),
            )

        index3.get_urls_for_area.assert_called_once_with(area)
        fetch_and_extract_zip_mock.assert_not_called()

    @staticmethod
    @patch("pyhgtmap.sources.viewfinder.urlopen", autospec=True)
    def test_download_missing_file_1st_zone(urlopen_mock: MagicMock) -> None:
        """Area found using 1st candidate zone."""
        with TemporaryDirectory() as temp_dir:
            # Prepare
            source = ViewFinder(temp_dir, "conf_dir")
            area = "S43E007"
            index3 = MagicMock(spec=ViewFinderIndex)
            source._indexes = {3: cast(ViewFinderIndex, index3)}
            index3.get_urls_for_area.return_value = ["http://url1", "http://url2"]
            urlopen_mock.return_value.read.return_value = fake_view_zip_file(
                ["A01/S43E007.hgt", "A01/S43E008.hgt"],
            ).read()

            # Test
            source.download_missing_file(area, 3, os.path.join(temp_dir, f"{area}.hgt"))

            # Check
            index3.get_urls_for_area.assert_called_once_with(area)
            # Index must be updated
            index3.update.assert_called_once_with("http://url1", ["S43E007", "S43E008"])
            urlopen_mock.assert_called_once_with("http://url1")
            # All files from zone are kept
            assert Path(temp_dir, "S43E007.hgt").is_file()
            assert Path(temp_dir, "S43E008.hgt").is_file()

    @staticmethod
    @patch("pyhgtmap.sources.viewfinder.urlopen", autospec=True)
    def test_download_missing_file_2nd_zone(urlopen_mock: MagicMock) -> None:
        """Area found using 2nd candidate zone."""
        with TemporaryDirectory() as temp_dir:
            # Prepare
            source = ViewFinder(temp_dir, "conf_dir")
            area = "S43E010"
            index3 = MagicMock(spec=ViewFinderIndex)
            source._indexes = {3: cast(ViewFinderIndex, index3)}
            index3.get_urls_for_area.return_value = ["http://url1", "http://url2"]
            urlopen_mock.return_value.read.side_effect = [
                fake_view_zip_file(["A01/S43E007.hgt", "A01/S43E008.hgt"]).read(),
                fake_view_zip_file(["B01/S43E009.hgt", "B01/S43E010.hgt"]).read(),
            ]

            # Test
            source.download_missing_file(area, 3, os.path.join(temp_dir, f"{area}.hgt"))

            # Check
            index3.get_urls_for_area.assert_called_once_with(area)
            # Index must be updated
            assert index3.update.call_args_list == [
                call("http://url1", ["S43E007", "S43E008"]),
                call("http://url2", ["S43E009", "S43E010"]),
            ]
            assert urlopen_mock.call_args_list == [
                call("http://url1"),
                call("http://url2"),
            ]
            # All files from zone are kept
            assert Path(temp_dir, "S43E007.hgt").is_file()
            assert Path(temp_dir, "S43E008.hgt").is_file()
            assert Path(temp_dir, "S43E009.hgt").is_file()
            assert Path(temp_dir, "S43E010.hgt").is_file()

    @staticmethod
    @patch("pyhgtmap.sources.viewfinder.urlopen", autospec=True)
    def test_download_missing_file_not_in_zone(urlopen_mock: MagicMock) -> None:
        """Area isn't actually available in any zone (invalid index)."""
        with TemporaryDirectory() as temp_dir:
            # Prepare
            source = ViewFinder(temp_dir, "conf_dir")
            area = "S43E007"
            index1 = MagicMock(spec=ViewFinderIndex)
            source._indexes = {1: cast(ViewFinderIndex, index1)}
            index1.get_urls_for_area.return_value = ["http://url1"]
            urlopen_mock.return_value.read.return_value = fake_view_zip_file(
                ["A01/S43E008.hgt"],
            ).read()

            # Test
            with pytest.raises(FileNotFoundError):
                source.download_missing_file(
                    area,
                    1,
                    os.path.join(temp_dir, f"{area}.hgt"),
                )

            # Check
            index1.get_urls_for_area.assert_called_once_with(area)
            # Index must be updated
            index1.update.assert_called_once_with("http://url1", ["S43E008"])
            urlopen_mock.assert_called_once_with("http://url1")
            # All files from zone are kept
            assert Path(temp_dir, "S43E008.hgt").is_file()
