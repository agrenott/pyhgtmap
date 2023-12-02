import logging
import os
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from pyhgtmap.sources import Source


class SomeTestSource(Source):
    """Fake test source, implementing abstract methods"""

    NICKNAME = "test"
    BANNER = "Please support my test banner!"

    def download_missing_file(
        self, area: str, resolution: int, output_file_name: str
    ) -> None:
        pass


class TestSource:
    @staticmethod
    def test_get_cache_dir() -> None:
        """Cache dir name generation is resolution specific."""
        source = SomeTestSource("cache_dir", "conf_dir")
        assert source.get_cache_dir(1) == os.path.join("cache_dir", "TEST1")

    @staticmethod
    def test_check_cached_file() -> None:
        source = SomeTestSource("cache_dir", "conf_dir")
        with TemporaryDirectory() as temp_dir:
            # Create fake file - size must match expected static size depending on resolution
            hgt_file_size = 2884802
            hgt_file_name = os.path.join(temp_dir, "N42E004.hgt")
            with open(hgt_file_name, "w") as hgt_file:
                hgt_file.write("0" * hgt_file_size)

            # Valid file -> Must NOT raise any exception
            source.check_cached_file(hgt_file_name, 3)

    @staticmethod
    def test_check_cached_file_invalid_size() -> None:
        """Exception raised on existing file with invalid size."""
        source = SomeTestSource("cache_dir", "conf_dir")
        with TemporaryDirectory() as temp_dir:
            # Create fake file with invalid size
            hgt_file_size = 2
            hgt_file_name = os.path.join(temp_dir, "N42E004.hgt")
            with open(hgt_file_name, "w") as hgt_file:
                hgt_file.write("0" * hgt_file_size)

            with pytest.raises(
                IOError,
                match=f"Wrong size: expected 25934402, found {hgt_file_size} for {hgt_file_name}",
            ):
                source.check_cached_file(hgt_file_name, 1)

    @staticmethod
    def test_check_cached_file_doesnt_exist() -> None:
        """Exception raised on missing file."""
        source = SomeTestSource("cache_dir", "conf_dir")
        with pytest.raises(IOError, match="No such file or directory: 'missing.hgt'"):
            source.check_cached_file("missing.hgt", 3)

    @staticmethod
    def test_get_file_from_cache() -> None:
        """Re-using file already existing in cache."""
        # Prepare
        source = SomeTestSource("cache_dir", "conf_dir")
        resolution = 3
        area = "N42E004"
        # Does nothing, but especially doesn't raise exception
        source.check_cached_file = MagicMock(spec=source.check_cached_file)  # type: ignore[method-assign]
        source.download_missing_file = MagicMock(spec=source.download_missing_file)  # type: ignore[method-assign]

        # Test
        file_name = source.get_file(area, resolution)

        # Check
        source.check_cached_file.assert_called_once_with(
            f"cache_dir/TEST3/{area}.hgt", 3
        )
        source.download_missing_file.assert_not_called()
        assert file_name == os.path.join(
            source.get_cache_dir(resolution), f"{area}.hgt"
        )

    @staticmethod
    def test_get_file_download() -> None:
        """Download missing cache file."""
        with TemporaryDirectory() as cache_dir:
            # Prepare
            source = SomeTestSource(cache_dir, "conf_dir")
            resolution = 3
            area = "N42E004"
            source.check_cached_file = MagicMock(  # type: ignore[method-assign]
                spec=source.check_cached_file,
                # First call raises exception, second one nothing as file should have been downloaded
                side_effect=[
                    IOError("File not found in cache"),
                    None,
                ],
            )
            source.download_missing_file = MagicMock(spec=source.download_missing_file)  # type: ignore[method-assign]

            # Test
            file_name = source.get_file(area, resolution)

            # Check
            assert os.path.isdir(os.path.join(cache_dir, "TEST3"))
            source.check_cached_file.assert_called_with(
                f"{cache_dir}/TEST3/{area}.hgt", 3
            )
            source.download_missing_file.assert_called_once_with(
                area, 3, f"{cache_dir}/TEST3/{area}.hgt"
            )
            assert file_name == os.path.join(
                source.get_cache_dir(resolution), f"{area}.hgt"
            )

    @staticmethod
    def test_get_file_download_corrupted() -> None:
        """Download missing cache file, but corrupted output."""
        # Prepare
        source = SomeTestSource("cache_dir", "conf_dir")
        resolution = 3
        area = "N42E004"
        source.check_cached_file = MagicMock(  # type: ignore[method-assign]
            spec=source.check_cached_file,
            # Called twice, failing for both as the downloaded file is corrupted
            side_effect=[
                IOError("File not found in cache"),
                IOError("Corrupted file"),
            ],
        )
        source.download_missing_file = MagicMock(spec=source.download_missing_file)  # type: ignore[method-assign]

        # Test
        file_name = source.get_file(area, resolution)

        # Check
        source.check_cached_file.assert_called_with(f"cache_dir/TEST3/{area}.hgt", 3)
        assert source.check_cached_file.call_count == 2
        source.download_missing_file.assert_called_once_with(
            area, 3, f"cache_dir/TEST3/{area}.hgt"
        )
        assert file_name is None

    @staticmethod
    def test_get_file_not_found() -> None:
        """File not in cache and can't be downloaded either."""
        # Prepare
        source = SomeTestSource("cache_dir", "conf_dir")
        resolution = 3
        area = "N42E004"
        source.check_cached_file = MagicMock(  # type: ignore[method-assign]
            spec=source.check_cached_file,
            side_effect=IOError("File not found in cache"),  # Raises exception
        )
        source.download_missing_file = MagicMock(  # type: ignore[method-assign]
            spec=source.download_missing_file,
            side_effect=FileNotFoundError("Can't download file"),
        )

        # Test
        file_name = source.get_file(area, resolution)

        # Check
        source.check_cached_file.assert_called_with(f"cache_dir/TEST3/{area}.hgt", 3)
        source.download_missing_file.assert_called_once_with(
            area, 3, f"cache_dir/TEST3/{area}.hgt"
        )
        assert file_name is None

    @staticmethod
    def test_show_banner(caplog: pytest.LogCaptureFixture) -> None:
        # Prepare
        source = SomeTestSource("cache_dir", "conf_dir")
        caplog.set_level(logging.INFO, logger="pyhgtmap.sources")

        source.check_cached_file = MagicMock(  # type: ignore[method-assign]
            spec=source.check_cached_file,
            side_effect=IOError("File not found in cache"),  # Raises exception
        )
        source.download_missing_file = MagicMock(  # type: ignore[method-assign]
            spec=source.download_missing_file,
            side_effect=[None, None],
        )

        # Test
        source.get_file("N42E004.hgt", 3)
        source.get_file("N42E005.hgt", 3)

        # Check
        # Banner must be shown only once
        assert caplog.text.count("Please support my test banner!") == 1
