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


def calculer_sens_par_axe(
    axe_lat_origine: float, axe_lon_origine: float,
    sous_lat_debut: float, sous_lon_debut: float,
    sous_lat_fin: float, sous_lon_fin: float,
) -> str:
    """Détermine le sens de circulation d'un sous-tronçon pour un axe parent.

    Retourne "direct" (lat_debut → lat_fin) si l'origine de l'axe est plus
    proche de `lat_debut` que de `lat_fin`, sinon "inverse". Un même
    sous-tronçon partagé entre 2 axes de sens opposés est ainsi mesuré
    dans les deux directions à chaque cycle de collecte.
    """
    d_debut = distance_haversine_m(
        axe_lat_origine, axe_lon_origine, sous_lat_debut, sous_lon_debut,
    )
    d_fin = distance_haversine_m(
        axe_lat_origine, axe_lon_origine, sous_lat_fin, sous_lon_fin,
    )
    return "direct" if d_debut <= d_fin else "inverse"


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


def decoder_polyline(encoded: str) -> list[tuple[float, float]]:
    """Décode une chaîne Google polyline precision 5 en liste de (lat, lon).

    Algorithme inverse de `encoder_polyline` — utilisé pour calculer la
    distance couverte par chaque `speedReadingInterval` Google (cf. règle
    DEESP § 4.5.2 : un tronçon est congestionné si rouge ou si orange sur
    ≥ 50 % de sa longueur).
    """
    if not encoded:
        return []
    points: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    longueur = len(encoded)

    while index < longueur:
        # Latitude
        b = 0
        shift = 0
        result = 0
        while True:
            if index >= longueur:
                return points
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Longitude
        shift = 0
        result = 0
        while True:
            if index >= longueur:
                return points
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if (result & 1) else (result >> 1)
        lon += dlon

        points.append((lat / 1e5, lon / 1e5))
    return points


def distances_cumulees_m(points: list[tuple[float, float]]) -> list[int]:
    """Renvoie la distance cumulée en mètres à chaque sommet (point 0 → 0).

    Permet de localiser à quelle position kilométrique se trouve l'index
    d'un sommet — utilisé pour mesurer la longueur d'un
    `speedReadingInterval` (Google donne des indices de polyline, pas des
    distances).
    """
    if not points:
        return []
    cumul = [0]
    total = 0
    for i in range(1, len(points)):
        lat1, lon1 = points[i - 1]
        lat2, lon2 = points[i]
        total += distance_haversine_m(lat1, lon1, lat2, lon2)
        cumul.append(total)
    return cumul
