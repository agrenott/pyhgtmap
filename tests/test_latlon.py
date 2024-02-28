import pytest

from pyhgtmap.latlon import DegreeLatLon


class TestDegreeLatLon:
    @staticmethod
    def test_init() -> None:
        # Test the initialization of DegreeLatLon
        lat = 45
        lon = -122
        degree_lat_lon = DegreeLatLon(lat, lon)
        assert degree_lat_lon.lat == lat
        assert degree_lat_lon.lon == lon

    @staticmethod
    def test_from_string() -> None:
        # Test the from_string constructor

        degree_lat_lon = DegreeLatLon.from_string("N45W122")
        assert degree_lat_lon.lat == 45
        assert degree_lat_lon.lon == -122

    @staticmethod
    def test_positive() -> None:
        # Test the __str__ method with positive latitude and longitude
        lat = 45
        lon = -122
        degree_lat_lon = DegreeLatLon(lat, lon)
        assert degree_lat_lon.lat == 45
        assert degree_lat_lon.lon == -122
        assert str(degree_lat_lon) == "N45W122"

    @staticmethod
    def test_negative() -> None:
        # Test the __str__ method with negative latitude and longitude
        lat = -45
        lon = 122
        degree_lat_lon = DegreeLatLon(lat, lon)
        assert degree_lat_lon.lat == -45
        assert degree_lat_lon.lon == 122
        assert str(degree_lat_lon) == "S45E122"

    @staticmethod
    def test_limits() -> None:
        assert DegreeLatLon(0, 0).to_string() == "N00E000"
        assert DegreeLatLon.from_string("S00W000").to_string() == "N00E000"
        assert DegreeLatLon(90, 180).to_string() == "N90E180"
        assert DegreeLatLon(-90, -180).to_string() == "S90W180"

    @staticmethod
    def test_string_padding() -> None:
        assert DegreeLatLon(1, 7).to_string(2) == "N01E007"
        assert DegreeLatLon(1, 7).to_string(3) == "N001E007"
        assert DegreeLatLon(-999, -888).to_string(3) == "S999W888"

    @staticmethod
    def test_from_string_invalid() -> None:
        # Test the from_string method with an invalid string representation
        string = "4532N 12259W"
        with pytest.raises(ValueError, match="Invalid latlon string"):
            DegreeLatLon.from_string(string)

    @staticmethod
    def test_round_to_multiple() -> None:
        # Test rounding to a multiple of 10
        lat_lon = DegreeLatLon(35, 45)
        rounded_lat_lon = lat_lon.round_to(10)
        assert rounded_lat_lon.lat == 30
        assert rounded_lat_lon.lon == 40

        # Test rounding to a multiple of 5
        lat_lon = DegreeLatLon(37, 48)
        rounded_lat_lon = lat_lon.round_to(5)
        assert rounded_lat_lon.lat == 35
        assert rounded_lat_lon.lon == 45

        # Test rounding to a multiple of 15
        lat_lon = DegreeLatLon(40, 50)
        rounded_lat_lon = lat_lon.round_to(15)
        assert rounded_lat_lon.lat == 30
        assert rounded_lat_lon.lon == 45

        # Test rounding to a multiple of 5, negative values
        lat_lon = DegreeLatLon(-32, -49)
        rounded_lat_lon = lat_lon.round_to(5)
        assert rounded_lat_lon.lat == -35
        assert rounded_lat_lon.lon == -50
