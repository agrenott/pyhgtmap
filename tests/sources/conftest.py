"""Common pytest fixtures"""

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def gauth_mock() -> Generator[MagicMock, None, None]:
    """Mock pyhgtmap.sources.sonny.GoogleAuth"""
    with patch("pyhgtmap.sources.sonny.GoogleAuth") as gauth_mock:
        yield gauth_mock


@pytest.fixture
def gdrive_mock() -> Generator[MagicMock, None, None]:
    """Mock pyhgtmap.sources.sonny.GoogleDrive"""
    with patch("pyhgtmap.sources.sonny.GoogleDrive") as gdrive_mock:
        yield gdrive_mock
