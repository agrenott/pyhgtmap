"""Common HGT sources utilities: Source base class and registry."""

from __future__ import annotations

import logging
import os
import pathlib
from abc import ABC, abstractmethod

from class_registry import AutoRegister, ClassRegistry

__all__: list[str] = []

LOGGER: logging.Logger = logging.getLogger(__name__)


# This registry will return a new instance for each get
SOURCES_TYPES_REGISTRY = ClassRegistry(attr_name="NICKNAME", unique=True)


class Source(ABC, metaclass=AutoRegister(SOURCES_TYPES_REGISTRY)):  # type: ignore[misc] # Mypy does not understand dynamically-computed metaclasses
    """HGT source base class"""

    # Source's 'nickname', used to identify it from the command line and
    # cache folders management.
    # MUST be 4 alphanum for backward compatibility.
    NICKNAME: str

    # Banner to encourage users to support original HGT sources
    BANNER: str

    # Resolutions supported by this source in arc-seconds
    SUPPORTED_RESOLUTIONS: tuple[int, ...] = (1, 3)

    def __init__(self, cache_dir_root: str, config_dir: str) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached HGT files
            config_dir (str): Root directory to store configuration (if any)
        """
        if len(self.NICKNAME) != 4:
            raise ValueError("Downloader nickname must be exactly 4 char long")
        self.cache_dir_root: str = cache_dir_root
        self.config_dir: str = config_dir
        self._banner_showed: bool = False

    def get_cache_dir(self, resolution: int) -> str:
        """Get the cache directory for given resolution"""
        return os.path.join(self.cache_dir_root, f"{self.NICKNAME.upper()}{resolution}")

    def check_cached_file(self, file_name: str, resolution: int) -> None:
        """
        Check HGT file exists and its size corresponds to current resolution.
        Raises exception if not.
        """
        wanted_size: int = 2 * (3600 // resolution + 1) ** 2
        found_size: int = os.path.getsize(file_name)
        if found_size != wanted_size:
            raise OSError(
                f"Wrong size: expected {wanted_size}, found {found_size} for {file_name}",
            )

    def get_file(self, area: str, resolution: int) -> str | None:
        """Get HGT file corresponding to requested area, from cache if already downloaded.

        Args:
            area (str): Area to cover, eg. "N42E004"
            resolution (int): Resolution (in arc second)

        Returns:
            str | None: file name of the corresponding file if available, None otherwise
        """
        file_name = os.path.join(self.get_cache_dir(resolution), f"{area}.hgt")
        try:
            # Check if file already exists in cache and is valid
            self.check_cached_file(file_name, resolution)
            LOGGER.debug("%s: using existing file %s.", area, file_name)

        except OSError:
            try:
                # Missing file or corrupted, download it
                pathlib.Path(self.get_cache_dir(resolution)).mkdir(
                    parents=True,
                    exist_ok=True,
                )
                self.show_banner()
                self.download_missing_file(area, resolution, file_name)
                self.check_cached_file(file_name, resolution)
            except (OSError, FileNotFoundError):
                LOGGER.warning(
                    "No file found for area %s with resolution %d in '%s' source",
                    area,
                    resolution,
                    self.NICKNAME,
                )
                return None

        return file_name

    def show_banner(self) -> None:
        """Show banner referencing original source, only once per session."""
        if not self._banner_showed:
            LOGGER.info(self.BANNER)
            self._banner_showed = True

    @abstractmethod
    def download_missing_file(
        self,
        area: str,
        resolution: int,
        output_file_name: str,
    ) -> None:
        """Actually download and save HGT file into cache.

        Args:
            area (str): Area to cover, eg. "N42E004"
            resolution (int): Resolution (in arc second)
            output_file_name (str): file name to save the content to
        """
        raise NotImplementedError
