from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import configargparse
import pytest

from pyhgtmap.configuration import Configuration


@pytest.fixture
def configuration() -> Configuration:
    return Configuration()


@pytest.fixture(autouse=True)
def _disable_config_file() -> Generator[None, Any, None]:
    """Disable the configuration file for the tests."""
    with patch.object(
        configargparse.ArgumentParser, "_open_config_files"
    ) as _open_config_files_mock:
        _open_config_files_mock.return_value = []
        yield
