import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from pyhgtmap import main

from . import TEST_DATA_PATH

if TYPE_CHECKING:
    import optparse


@patch("pyhgtmap.main.NASASRTMUtil")
@patch("pyhgtmap.main.HgtFilesProcessor")
def test_main_download_from_poly(
    HgtFilesProcessor_mock: MagicMock,
    NASASRTMUtil_mock: MagicMock,
) -> None:
    """Only polygon option is used, without files; download tiles."""
    # Prepare
    sys_args = [
        "--pbf",
        "--source=view1",
        f"--polygon={os.path.join(TEST_DATA_PATH, 'france.poly')}",
    ]
    NASASRTMUtil_mock.getFiles.return_value = [
        ("hgt/VIEW1/N45E006.hgt", True),
        ("hgt/VIEW1/N46E006.hgt", True),
    ]

    # Test
    main.main_internal(sys_args)

    # Check
    NASASRTMUtil_mock.getFiles.assert_called_once()
    assert (
        NASASRTMUtil_mock.getFiles.call_args[0][0]
        == "-6.9372070:41.2386600:9.9000000:51.4288000"
    )
    assert NASASRTMUtil_mock.getFiles.call_args[0][1][0][0:5] == [
        (9.9, 42.43788),
        (9.9, 41.41346),
        (9.328765, 41.32062),
        (9.286847, 41.28319),
        (8.798805, 41.23866),
    ]
    assert NASASRTMUtil_mock.getFiles.call_args[0][2] == 0
    assert NASASRTMUtil_mock.getFiles.call_args[0][3] == 0
    assert NASASRTMUtil_mock.getFiles.call_args[0][4] == ["view1"]

    HgtFilesProcessor_mock.assert_called_once()
    parsed_options: optparse.Values = HgtFilesProcessor_mock.call_args.args[3]
    assert parsed_options.area == "-6.9372070:41.2386600:9.9000000:51.4288000"

    HgtFilesProcessor_mock.return_value.process_files.assert_called_once_with(
        [("hgt/VIEW1/N45E006.hgt", True), ("hgt/VIEW1/N46E006.hgt", True)],
    )


@patch("pyhgtmap.main.NASASRTMUtil")
@patch("pyhgtmap.main.HgtFilesProcessor")
def test_main_manual_input_poly(
    HgtFilesProcessor_mock: MagicMock,
    NASASRTMUtil_mock: MagicMock,
) -> None:
    """Polygon option is used, with manual files; polygon must be applied to files."""
    # Prepare
    sys_args = [
        "--pbf",
        "--source=view1",
        f"--polygon={os.path.join(TEST_DATA_PATH, 'france.poly')}",
        "N45E007.hgt",
        "N46E007.hgt",
        "N47E007.hgt",
    ]

    # Test
    main.main_internal(sys_args)

    # Check
    NASASRTMUtil_mock.getFiles.assert_not_called()

    HgtFilesProcessor_mock.assert_called_once()
    parsed_options: optparse.Values = HgtFilesProcessor_mock.call_args.args[3]
    # area must be properly computed from files names
    assert parsed_options.area == "7:45:8:48"
    # Polygon check must be enabled for all files
    HgtFilesProcessor_mock.return_value.process_files.assert_called_once_with(
        [("N45E007.hgt", True), ("N46E007.hgt", True), ("N47E007.hgt", True)],
    )


@patch("pyhgtmap.main.configUtil")
@patch("pyhgtmap.main.NASASRTMUtil")
@patch("pyhgtmap.main.HgtFilesProcessor")
def test_main_manual_input_poly_no_source(
    HgtFilesProcessor_mock: MagicMock,
    NASASRTMUtil_mock: MagicMock,
    configUtil_mock: MagicMock,
) -> None:
    """Earthexplorer credentials shouldn't be required when providing tiles in input with a polygon."""
    # Prepare
    sys_args = [
        f"--polygon={os.path.join(TEST_DATA_PATH, 'france.poly')}",
        "N45E007.hgt",
        "N46E007.hgt",
        "N47E007.hgt",
    ]

    # Test
    main.main_internal(sys_args)

    # Check
    configUtil_mock.Config.assert_not_called()
    NASASRTMUtil_mock.getFiles.assert_not_called()

    HgtFilesProcessor_mock.assert_called_once()
    parsed_options: optparse.Values = HgtFilesProcessor_mock.call_args.args[3]
    # area must be properly computed from files names
    assert parsed_options.area == "7:45:8:48"
    # Polygon check must be enabled for all files
    HgtFilesProcessor_mock.return_value.process_files.assert_called_once_with(
        [("N45E007.hgt", True), ("N46E007.hgt", True), ("N47E007.hgt", True)],
    )


@patch("pyhgtmap.main.NASASRTMUtil")
@patch("pyhgtmap.main.HgtFilesProcessor")
def test_main_manual_input_no_poly(
    HgtFilesProcessor_mock: MagicMock,
    NASASRTMUtil_mock: MagicMock,
) -> None:
    """Polygon option is NOT used, with manual files."""
    # Prepare
    sys_args = [
        "--pbf",
        "N45E007.hgt",
        "N46E007.hgt",
        "N47E007.hgt",
    ]

    # Test
    main.main_internal(sys_args)

    # Check
    NASASRTMUtil_mock.getFiles.assert_not_called()

    HgtFilesProcessor_mock.assert_called_once()
    parsed_options: optparse.Values = HgtFilesProcessor_mock.call_args.args[3]
    # area must be properly computed from files names
    assert parsed_options.area == "7:45:8:48"
    # Polygon check must NOT be enabled for any files
    HgtFilesProcessor_mock.return_value.process_files.assert_called_once_with(
        [("N45E007.hgt", False), ("N46E007.hgt", False), ("N47E007.hgt", False)],
    )
