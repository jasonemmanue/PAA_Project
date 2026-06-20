"""Découpage automatique d'une trace GPX terrain par tronçon surveillé.

Pour chaque tronçon T (origine S_T, destination E_T) et une trace horodatée
de N points P0, P1, ... PN :

  1. Cherche l'index i_debut tel que P_i_debut est le point de la trace le
     plus proche de S_T (distance Haversine ≤ RAYON_SEUIL_M).
  2. Cherche l'index i_fin > i_debut tel que P_i_fin est le point le plus
     proche de E_T (même seuil).
  3. Si les deux sont trouvés et que `i_fin > i_debut`, le tronçon est
     considéré comme parcouru. On retourne :
       - durée mesurée = horodatage(P_i_fin) - horodatage(P_i_debut)
       - horodatage médian = milieu temporel du passage
       - sous-trace (points P_i_debut..P_i_fin inclus) — utile pour OSRM Match

Convention OSRM : on appelle Match SUR LA SOUS-TRACE et non sur la trace
entière, pour obtenir une confiance ciblée par tronçon.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import asin, cos, radians, sin, sqrt

from app.models.models import Troncon
from app.sources.gpx_parser import PointTrace


# Rayon de recherche autour des extrémités d'un tronçon : si aucun point de la
# trace n'est à moins de 80 m de l'origine OU de la destination, on considère
# que le tronçon n'a pas été parcouru.
# 80 m couvre l'imprécision GPS (~5-15 m) + le fait qu'un véhicule s'arrête
# rarement exactement sur le point seed.
RAYON_SEUIL_M = 80.0


@dataclass(frozen=True)
class SegmentTroncon:
    """Un segment de la trace correspondant à un tronçon surveillé."""
    troncon_id: int
    index_debut: int
    index_fin: int
    horodatage_debut: datetime
    horodatage_fin: datetime
    duree_s: int
    horodatage_passage: datetime  # milieu temporel
    distance_m_trace: float  # distance cumulée de la sous-trace (validation)

    @property
    def sous_trace(self) -> tuple[int, int]:
        return (self.index_debut, self.index_fin)


def distance_haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en mètres entre deux points GPS via formule de Haversine."""
    R = 6_371_000.0  # rayon terrestre moyen en mètres
    lat1r, lat2r = radians(lat1), radians(lat2)
    dlat = lat2r - lat1r
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _index_plus_proche(
    trace: list[PointTrace],
    cible_lat: float,
    cible_lon: float,
    *,
    index_min: int = 0,
    rayon_seuil_m: float = RAYON_SEUIL_M,
) -> int | None:
    """Cherche dans `trace[index_min:]` l'index du point le plus proche de la cible.

    Retourne None si aucun point n'est à moins de `rayon_seuil_m`.
    """
    meilleur_index: int | None = None
    meilleure_distance = float("inf")
    for i in range(index_min, len(trace)):
        p = trace[i]
        d = distance_haversine_m(p.lat, p.lon, cible_lat, cible_lon)
        if d < meilleure_distance:
            meilleure_distance = d
            meilleur_index = i
    if meilleur_index is None or meilleure_distance > rayon_seuil_m:
        return None
    return meilleur_index


def _distance_cumulee_m(trace: list[PointTrace], i_debut: int, i_fin: int) -> float:
    total = 0.0
    for i in range(i_debut, i_fin):
        a, b = trace[i], trace[i + 1]
        total += distance_haversine_m(a.lat, a.lon, b.lat, b.lon)
    return total


def decouper_trace_par_troncon(
    trace: list[PointTrace],
    troncons: list[Troncon],
    *,
    rayon_seuil_m: float = RAYON_SEUIL_M,
) -> list[SegmentTroncon]:
    """Détecte dans `trace` les segments correspondant à chaque tronçon.

    L'opérateur peut avoir parcouru 1, 2, …, ou les 6 tronçons en une session.
    L'algorithme essaie chaque tronçon indépendamment. Les segments retournés
    peuvent donc se chevaucher temporellement si la trace passe deux fois au
    même endroit, mais pour le cas nominal (trajet linéaire) cela ne se
    produit pas.
    """
    segments: list[SegmentTroncon] = []

    for troncon in troncons:
        if (
            troncon.lat_origine is None or troncon.lon_origine is None
            or troncon.lat_destination is None or troncon.lon_destination is None
        ):
            continue  # tronçon non résolu — on ne peut pas le matcher

        i_debut = _index_plus_proche(
            trace,
            troncon.lat_origine, troncon.lon_origine,
            rayon_seuil_m=rayon_seuil_m,
        )
        if i_debut is None:
            continue

        i_fin = _index_plus_proche(
            trace,
            troncon.lat_destination, troncon.lon_destination,
            index_min=i_debut + 1,
            rayon_seuil_m=rayon_seuil_m,
        )
        if i_fin is None or i_fin <= i_debut:
            continue

        p_debut = trace[i_debut]
        p_fin = trace[i_fin]
        duree_s = int((p_fin.horodatage - p_debut.horodatage).total_seconds())
        if duree_s <= 0:
            continue

        # Instant médian du passage — utilisé pour apparier la mesure API.
        milieu_ts = p_debut.horodatage.timestamp() + (
            p_fin.horodatage.timestamp() - p_debut.horodatage.timestamp()
        ) / 2.0
        horodatage_milieu = datetime.fromtimestamp(milieu_ts, tz=p_debut.horodatage.tzinfo)

        segments.append(SegmentTroncon(
            troncon_id=troncon.id,
            index_debut=i_debut,
            index_fin=i_fin,
            horodatage_debut=p_debut.horodatage,
            horodatage_fin=p_fin.horodatage,
            duree_s=duree_s,
            horodatage_passage=horodatage_milieu,
            distance_m_trace=_distance_cumulee_m(trace, i_debut, i_fin),
        ))

    return segments
