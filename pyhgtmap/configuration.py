from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyhgtmap import PolygonsList


class NestedConfig(Namespace):
    """
    A configuration with nested sub-configurations, relying on dot-notation.
    Sub configurations must be explicitly added before being used.
    """

    def __setattr__(self, name: str, value: Any) -> None:
        """Set a value in the configuration, possibly into a sub-configuration."""
        if "." in name:
            group, name = name.split(".", 1)
            # Sub-config MUST have been added explicitly using add_sub_config
            ns = getattr(self, group)
            setattr(ns, name, value)
            self.__dict__[group] = ns
        else:
            self.__dict__[name] = value

    def add_sub_config(self, config_name: str, sub_config: NestedConfig) -> None:
        """Add a sub-configuration to the current configuration."""
        if config_name in self.__dict__:
            raise ValueError(f"Sub-config {config_name} already exists")
        self.__dict__[config_name] = sub_config


class Configuration(NestedConfig):
    """Configuration for pyhgtmap."""

    # Work-around to get typing without a full refactoring of the parser, while
    # providing typing.
    # Sadly some parts have to be duplicated...

    area: str | None
    polygon_file: str | None
    polygon: PolygonsList | None = None
    downloadOnly: bool = False
    contourStepSize: str = "20"
    contourFeet: bool = False
    noZero: bool = False
    outputPrefix: str | None
    plotPrefix: str | None
    lineCats: str = "200,100"
    nJobs: int = 1
    osmVersion: float = 0.6
    writeTimestamp: bool = False
    startId: int = 10000000
    startWayId: int = 10000000
    maxNodesPerTile: int = 1000000
    maxNodesPerWay: int = 2000
    rdpEpsilon: float | None = 0.0
    disableRdp: bool | None
    smooth_ratio: float = 1.0
    gzip: int = 0
    pbf: bool = False
    o5m: bool = False
    srtmResolution: int = 3
    srtmVersion: float = 3.0
    earthexplorerUser: str | None
    earthexplorerPassword: str | None
    viewfinder: int = 0
    dataSource: list[str] | None
    srtmCorrx: float = 0.0
    srtmCorry: float = 0.0
    hgtdir: str | None
    rewriteIndices: bool = False
    voidMax: int = -0x8000
    logLevel: str = "WARNING"
    filenames: list[str]
