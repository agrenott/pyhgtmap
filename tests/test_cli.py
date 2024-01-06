import pytest

from pyhgtmap.cli import parse_command_line


def test_exclusions_gzip_pbf(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_command_line(["--pbf", "--gzip", "1"])
    captured = capsys.readouterr()
    assert "error: argument --gzip: not allowed with argument --pbf" in captured.err


def test_exclusions_gzip_o5m(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_command_line(["--o5m", "--gzip", "1"])
    captured = capsys.readouterr()
    assert "error: argument --gzip: not allowed with argument --o5m" in captured.err


def test_exclusions_o5m_pbf(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_command_line(["--pbf", "--o5m"])
    captured = capsys.readouterr()
    assert "error: argument --o5m: not allowed with argument --pbf" in captured.err
