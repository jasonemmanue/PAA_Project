"""Encodeur Google Polyline (precision 5) + helpers géométriques.

Utilisé par P6.4 (administration — création de tronçons et sous-tronçons
sans avoir besoin d'OSRM).

L'algorithme Google Polyline encode efficacement une suite de coordonnées
en une chaîne ASCII. Réutilisé aussi par `complete_sans_osrm.py`.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt


def _encoder_signe(n: int) -> str:
    n = n << 1
    if n < 0:
        n = ~n
    chunks: list[str] = []
    while n >= 0x20:
        chunks.append(chr((0x20 | (n & 0x1F)) + 63))
        n >>= 5
    chunks.append(chr(n + 63))
    return "".join(chunks)


def encoder_polyline(points: list[tuple[float, float]]) -> str:
    """Encode une liste de (lat, lon) en chaîne Google polyline precision 5.

    Algorithme : https://developers.google.com/maps/documentation/utilities/polylinealgorithm
    """
    if not points:
        return ""
    result: list[str] = []
    prev_lat = 0
    prev_lon = 0
    for lat, lon in points:
        lat_int = round(lat * 1e5)
        lon_int = round(lon * 1e5)
        result.append(_encoder_signe(lat_int - prev_lat))
        result.append(_encoder_signe(lon_int - prev_lon))
        prev_lat = lat_int
        prev_lon = lon_int
    return "".join(result)


def distance_haversine_m(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> int:
    """Distance en mètres entre deux coordonnées GPS (formule de Haversine)."""
    R = 6_371_000.0  # rayon terrestre moyen
    lat1r, lat2r = radians(lat1), radians(lat2)
    dlat = lat2r - lat1r
    dlon = radians(lon2 - lon1)
    h = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlon / 2) ** 2
    return int(round(2 * R * asin(sqrt(h))))


def distance_cumulee_m(points: list[tuple[float, float]]) -> int:
    """Distance totale en mètres d'une polyligne (suite de Haversine)."""
    if len(points) < 2:
        return 0
    total = 0
    for i in range(1, len(points)):
        lat1, lon1 = points[i - 1]
        lat2, lon2 = points[i]
        total += distance_haversine_m(lat1, lon1, lat2, lon2)
    return total
