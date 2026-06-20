"""Parser GPX → liste de points horodatés (lat, lon, timestamp UTC).

Utilise gpxpy (dépendance pure-Python, stable). On extrait UNIQUEMENT les
points qui possèdent un horodatage : un GPX terrain SANS horodatage est
inexploitable pour calculer une durée de parcours.

Convention :
  - Latitude et longitude en degrés décimaux (WGS84).
  - Horodatage en UTC (datetime tz-aware).
  - Les points sont triés par horodatage croissant à la sortie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import gpxpy
import gpxpy.gpx


@dataclass(frozen=True)
class PointTrace:
    """Un point horodaté d'une trace GPX terrain."""
    lat: float
    lon: float
    horodatage: datetime  # UTC, tz-aware

    @property
    def timestamp_unix(self) -> int:
        return int(self.horodatage.timestamp())


def parser_gpx_octets(contenu: bytes) -> list[PointTrace]:
    """Parse un GPX (bytes) → liste de PointTrace triés par horodatage UTC.

    Lève `ValueError` si :
      - Le fichier n'est pas un GPX valide
      - Aucun point horodaté n'a été trouvé
      - Moins de 2 points horodatés (impossible de calculer une durée)
    """
    try:
        document = gpxpy.parse(contenu.decode("utf-8", errors="replace"))
    except Exception as exc:  # gpxpy.gpx.GPXXMLSyntaxException et autres
        raise ValueError(f"GPX invalide : {exc}") from exc

    points = list(_extraire_points_horodates(_iterer_segments(document)))
    if len(points) < 2:
        raise ValueError(
            "Le GPX doit contenir au moins 2 points horodatés "
            f"(trouvés : {len(points)})."
        )

    points.sort(key=lambda p: p.horodatage)
    return points


def parser_gpx_fichier(chemin: Path) -> list[PointTrace]:
    """Variante avec lecture depuis le disque — utile pour les scripts CLI."""
    return parser_gpx_octets(Path(chemin).read_bytes())


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _iterer_segments(document: gpxpy.gpx.GPX) -> Iterable[gpxpy.gpx.GPXTrackPoint]:
    """Parcourt tous les points de tous les segments de toutes les traces."""
    for trace in document.tracks:
        for segment in trace.segments:
            yield from segment.points
    # On ne lit délibérément pas `document.waypoints` : ce sont des POI, pas
    # des points de passage chronologiques d'un trajet.


def _extraire_points_horodates(
    points_bruts: Iterable[gpxpy.gpx.GPXTrackPoint],
) -> Iterable[PointTrace]:
    for p in points_bruts:
        if p.time is None or p.latitude is None or p.longitude is None:
            continue
        horodatage = (
            p.time.astimezone(timezone.utc) if p.time.tzinfo else p.time.replace(tzinfo=timezone.utc)
        )
        yield PointTrace(lat=p.latitude, lon=p.longitude, horodatage=horodatage)
