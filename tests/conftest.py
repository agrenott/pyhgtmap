import pytest

from pyhgtmap.configuration import Configuration


@pytest.fixture
def configuration() -> Configuration:
    return Configuration()
