import pytest
from class_registry.registry import RegistryKeyError

from pyhgtmap.sources import Source
from pyhgtmap.sources.pool import Pool


class DummySource(Source):
    """Fake test source, to be registered with other ones"""

    NICKNAME = "dumm"

    def download_missing_file(
        self, area: str, resolution: int, output_file_name: str
    ) -> None:
        pass


def test_missing_nickname() -> None:
    """Source implementation MUST have NICKNAME set."""
    with pytest.raises(
        AttributeError, match="type object 'InvalidSource' has no attribute 'NICKNAME'"
    ):

        class InvalidSource(Source):
            """Fake test source"""

            def download_missing_file(
                self, area: str, resolution: int, output_file_name: str
            ) -> None:
                pass


def test_dupe_nickname() -> None:
    """NICKNAME MUST be unique in the registry."""
    with pytest.raises(
        RegistryKeyError, match="InvalidSource with key 'dumm' is already registered."
    ):

        class InvalidSource(Source):
            """Fake test source"""

            NICKNAME = "dumm"

            def download_missing_file(
                self, area: str, resolution: int, output_file_name: str
            ) -> None:
                pass


@pytest.fixture
def pool() -> Pool:
    return Pool("root_dir", "cfg_dir")


class TestPool:
    @staticmethod
    def test_sources_registration(pool: Pool) -> None:
        # Don't test the full list, as some other unit test may register
        # some instances as well
        assert "sonn" in list(pool.available_sources())
        assert "dumm" in list(pool.available_sources())

    @staticmethod
    def test_get_source(pool: Pool) -> None:
        assert isinstance(pool.get_source("dumm"), DummySource)

    @staticmethod
    def test_source_caching(pool: Pool) -> None:
        """Same source must be re-used on sub-sequent calls, per pool."""
        assert id(pool.get_source("dumm")) == id(pool.get_source("dumm"))
        # Objects from a new pool will be different
        assert id(Pool("root_dir", "cfg_dir").get_source("dumm")) != id(
            pool.get_source("dumm")
        )
