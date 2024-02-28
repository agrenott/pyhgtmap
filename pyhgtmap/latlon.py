from __future__ import annotations

import re

DMS_REGEX = re.compile(
    r"(?P<lat_flag>[NS])(?P<lat_deg>[0-9]{2,3})(?P<lon_flag>[EW])(?P<lon_deg>[0-9]{3})"
)

MULTIPLIER: dict[str, int] = {"N": 1, "S": -1, "E": 1, "W": -1}


class DegreeLatLon:
    """Degree-precision latitude-longitude helper class."""

    def __init__(self, lat: int, lon: int):
        self.lat: int = lat
        self.lon: int = lon

    def to_string(self, lat_padding: int = 2) -> str:
        """
        Converts latitude and longitude values to a string representation.

        Args:
            lat_padding (int): The number of digits to pad the latitude value to.

        Returns:
            str: The string representation of the latitude and longitude values.
        """
        lon_flag = "W" if self.lon < 0 else "E"
        lat_flag = "S" if self.lat < 0 else "N"
        return f"{lat_flag:s}{abs(self.lat):0>{lat_padding}d}{lon_flag:s}{abs(self.lon):0>3d}"

    def __str__(self):
        return self.to_string()

    @classmethod
    def from_string(cls, latlon: str) -> DegreeLatLon:
        """
        Creates a new DegreeLatLon object from a string representation (e.g. "N45W122").
        """
        match = DMS_REGEX.match(latlon)
        if not match:
            raise ValueError(f"Invalid latlon string: {latlon:s}")
        lat_flag: str = match.group(1)
        lat_deg: int = int(match.group(2)) * MULTIPLIER[lat_flag]
        lon_flag: str = match.group(3)
        lon_deg: int = int(match.group(4)) * MULTIPLIER[lon_flag]

        return cls(lat_deg, lon_deg)

    def round_to(self, multiple: int) -> DegreeLatLon:
        """
        Rounds the latitude and longitude values of the DegreeLatLon object to the nearest multiple of the specified value.

        Parameters:
            multiple (int): The value to which the latitude and longitude values should be rounded.

        Returns:
            DegreeLatLon: A new DegreeLatLon object with the rounded latitude and longitude values.
        """
        rounded_lat: int = self.lat // multiple * multiple
        rounded_lon: int = self.lon // multiple * multiple
        return DegreeLatLon(rounded_lat, rounded_lon)
