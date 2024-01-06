import importlib
import os
import pkgutil
from typing import Generator, cast

from class_registry import ClassRegistry, ClassRegistryInstanceCache

from pyhgtmap.sources import SOURCES_TYPES_REGISTRY, Source

__all__ = ["Pool"]


class Pool:
    """
    Pool of HGT sources.
    Source are lazily instantiated on first use and kept in cache.
    """

    def __init__(self, cache_dir_root: str, config_dir: str) -> None:
        """
        Args:
            cache_dir_root (str): Root directory to store cached HGT files
            config_dir (str): Root directory to store configuration (if any)
        """
        # Keep a reference on the source registry as the cached version
        # do not expose all methods...
        self._inner_registry: ClassRegistry = SOURCES_TYPES_REGISTRY
        # Set common source parameters to be used on instantiation
        self._cached_registry = ClassRegistryInstanceCache(
            self._inner_registry,
            cache_dir_root=cache_dir_root,
            config_dir=config_dir,
        )

    def get_source(self, nickname: str) -> Source:
        """Get the source by nickname."""
        return cast(Source, self._cached_registry[nickname])

    def available_sources(self) -> Generator[str, None, None]:
        """Returns available sources' nicknames."""
        return (str(key) for key in self._inner_registry)


# Force import of all implementations to register them in the pool
current_package = ".".join(__name__.split(".")[:-1])
for module_info in pkgutil.iter_modules([os.path.dirname(__file__)]):
    full_module_name = f"{current_package}.{module_info.name}"
    if full_module_name == __name__:
        continue
    importlib.import_module(full_module_name)
