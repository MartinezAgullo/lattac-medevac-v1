"""
cmop_observer/utils

Pure utility functions (geographic calculations, etc.).
"""

from math import asin, cos, radians, sin, sqrt


def haversine_distance(
    lon1: float, lat1: float, lon2: float, lat2: float
) -> float:
    """
    Calculate distance between two points on Earth in meters.

    Uses the Haversine formula for great-circle distance.

    Args:
        lon1: Longitude of point 1 (WGS84 degrees).
        lat1: Latitude of point 1 (WGS84 degrees).
        lon2: Longitude of point 2 (WGS84 degrees).
        lat2: Latitude of point 2 (WGS84 degrees).

    Returns:
        Distance in meters.
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    earth_radius_m = 6_371_000
    return c * earth_radius_m


def estimate_ground_eta(distance_m: float, speed_kmh: float = 60.0) -> int:
    """
    Estimate ground travel time in minutes.

    Args:
        distance_m: Distance in meters.
        speed_kmh: Average speed in km/h (default 60 for ground ambulance).

    Returns:
        Estimated travel time in minutes (minimum 1).
    """
    distance_km = distance_m / 1_000
    hours = distance_km / speed_kmh
    return max(1, int(hours * 60))