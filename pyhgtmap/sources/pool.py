from __future__ import annotations

import importlib
import os
import pkgutil
from collections.abc import Generator, Iterator
from itertools import chain
from typing import TYPE_CHECKING, cast

from class_registry import ClassRegistry, ClassRegistryInstanceCache

from pyhgtmap.sources import SOURCES_TYPES_REGISTRY, Source

if TYPE_CHECKING:
    from pyhgtmap.configuration import Configuration

__all__ = ["Pool"]


class Pool:
    """
    Pool of HGT sources.
    Source are lazily instantiated on first use and kept in cache.
    """

    # Keep a reference on the source registry as the cached version
    # do not expose all methods...
    _inner_registry: ClassRegistry = SOURCES_TYPES_REGISTRY

    def __init__(
        self, cache_dir_root: str, config_dir: str, configuration: Configuration
    ) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached HGT files
            config_dir (str): Root directory to store configuration (if any)
        """
        # Set common source parameters to be used on instantiation
        self._cached_registry = ClassRegistryInstanceCache(
            self._inner_registry,
            cache_dir_root=cache_dir_root,
            config_dir=config_dir,
            configuration=configuration,
        )

    def get_source(self, nickname: str) -> Source:
        """Get the source by nickname."""
        return cast(Source, self._cached_registry[nickname])

    def available_sources_names(self) -> Generator[str, None, None]:
        """Returns available sources' nicknames."""
        return (str(key) for key in self._inner_registry)

    @classmethod
    def available_sources_options(cls) -> list[str]:
        """Returns available sources' nickname+resolution combinations for CLI validation."""
        return list(
            chain(
                *[
                    source.supported_source_options()
                    for k, source in cls._inner_registry.items()
                ]
            )
        )

    def __iter__(self) -> Iterator[Source]:
        yield from cast(Iterator[Source], self._cached_registry)

    @classmethod
    def registered_sources(cls) -> Generator[type[Source], None, None]:
        """Returns a registered sources types."""
        return cls._inner_registry.values()


# Force import of all implementations to register them in the pool
current_package = ".".join(__name__.split(".")[:-1])
for module_info in pkgutil.iter_modules([os.path.dirname(__file__)]):
    full_module_name = f"{current_package}.{module_info.name}"
    if full_module_name == __name__:
        continue
    importlib.import_module(full_module_name)
