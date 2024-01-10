import contextlib
import importlib.util
from typing import Generator


@contextlib.contextmanager
def handle_optional_geotiff_support() -> Generator[None, None, None]:
    """
    Context manager handling the cases where optional GeoTiff support has an impact.
    Cases should run fully if geotiff dependencies are available, else specific exception is
    expected.
    """
    try:
        # Execute test case
        yield
    except ImportError as ex:
        if importlib.util.find_spec("osgeo") is not None:
            # GDAL module is available, do NOT ignore the exception
            raise
        # GDAL not available, ensure the proper errror message is raised
        assert (  # noqa: PT017 # Test is more complex
            ex.msg
            == "GeoTiff optional support not enabled; please install with 'pip install pyhgtmap[geotiff]'"
        )
