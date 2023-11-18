"""Common HGT sources utilities: Source base class and registry."""

import logging
import os
import pathlib
from abc import ABC, abstractmethod
from typing import List, Optional

from class_registry import AutoRegister, ClassRegistry

__all__: List[str] = []

LOGGER: logging.Logger = logging.getLogger(__name__)


# This registry will return a new instance for each get
SOURCES_TYPES_REGISTRY = ClassRegistry(attr_name="NICKNAME", unique=True)


class Source(ABC, metaclass=AutoRegister(SOURCES_TYPES_REGISTRY)):  # type: ignore # Mypy does not understand dynamically-computed metaclasses
    """HGT source base class"""

    # Source's 'nickname', used to identify it from the command line and
    # cache folders management.
    # MUST be 4 alphanum for backward compatibility.
    NICKNAME: str

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
            raise IOError(
                f"Wrong size: expected {wanted_size}, found {found_size} for {file_name}"
            )

    def get_file(self, area: str, resolution: int) -> Optional[str]:
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

        except IOError:
            try:
                # Missing file or corrupted, download it
                pathlib.Path(self.get_cache_dir(resolution)).mkdir(
                    parents=True, exist_ok=True
                )
                self.download_missing_file(area, resolution, file_name)
                self.check_cached_file(file_name, resolution)
            except (FileNotFoundError, IOError):
                return None

        return file_name

    @abstractmethod
    def download_missing_file(
        self, area: str, resolution: int, output_file_name: str
    ) -> None:
        """Actually download and save HGT file into cache.

        Args:
            area (str): Area to cover, eg. "N42E004"
            resolution (int): Resolution (in arc second)
            output_file_name (str): file name to save the content to
        """
        raise NotImplementedError
