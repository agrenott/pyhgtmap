import pytest
from class_registry.registry import RegistryKeyError

from pyhgtmap.configuration import Configuration
from pyhgtmap.sources import Source
from pyhgtmap.sources.pool import Pool


class DummySource(Source):
    """Fake test source, to be registered with other ones"""

    NICKNAME = "dumm"

    def download_missing_file(
        self,
        area: str,
        resolution: int,
        output_file_name: str,
    ) -> None:
        pass


def test_missing_nickname() -> None:
    """Source implementation MUST have NICKNAME set."""
    with pytest.raises(
        AttributeError,
        match="type object 'InvalidSource' has no attribute 'NICKNAME'",
    ):

        class InvalidSource(Source):
            """Fake test source"""

            def download_missing_file(
                self,
                area: str,
                resolution: int,
                output_file_name: str,
            ) -> None:
                pass


def test_dupe_nickname() -> None:
    """NICKNAME MUST be unique in the registry."""
    with pytest.raises(
        RegistryKeyError,
        match="InvalidSource with key 'dumm' is already registered.",
    ):

        class InvalidSource(Source):
            """Fake test source"""

            NICKNAME = "dumm"

            def download_missing_file(
                self,
                area: str,
                resolution: int,
                output_file_name: str,
            ) -> None:
                pass


@pytest.fixture
def pool(configuration: Configuration) -> Pool:
    return Pool("root_dir", "cfg_dir", configuration)


class TestPool:
    @staticmethod
    def test_sources_registration(pool: Pool) -> None:
        # Don't test the full list, as some other unit test may register
        # some instances as well
        assert "sonn" in list(pool.available_sources_names())
        assert "dumm" in list(pool.available_sources_names())

    @staticmethod
    def test_get_source(pool: Pool) -> None:
        assert isinstance(pool.get_source("dumm"), DummySource)

    @staticmethod
    def test_source_caching(pool: Pool, configuration: Configuration) -> None:
        """Same source must be re-used on sub-sequent calls, per pool."""
        assert id(pool.get_source("dumm")) == id(pool.get_source("dumm"))
        # Objects from a new pool will be different
        assert id(Pool("root_dir", "cfg_dir", configuration).get_source("dumm")) != id(
            pool.get_source("dumm"),
        )

    @staticmethod
    def test_available_sources_options(pool: Pool) -> None:
        # Don't test the full list, as some other unit test may register
        # some instances as well
        assert "dumm1" in pool.available_sources_options()
        assert "dumm3" in pool.available_sources_options()
        assert "alos1" in pool.available_sources_options()
        assert "alos3" not in pool.available_sources_options()

    @staticmethod
    def test_registered_sources() -> None:
        # Don't test the full list, as some other unit test may register
        # some instances as well
        assert len(list(Pool.registered_sources())) > 1
        assert DummySource in Pool.registered_sources()
        sources_names = [source.NICKNAME for source in Pool.registered_sources()]
        assert "sonn" in sources_names
        assert "dumm" in sources_names
        assert "alos" in sources_names
