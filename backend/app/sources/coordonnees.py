"""Coordonnées GPS des 4 points d'extrémité des 3 axes officiels.

Ces coordonnées servent à :
  1. Compléter automatiquement les colonnes lat_*/lon_* des `troncons` via OSRM
     (script `app/complete_troncons.py`).
  2. Reconstruire l'origine/destination à partir du nom d'un tronçon lors d'un
     appel /diag/*.

⚠️  **Source de vérité** : fichiers GPX terrain du 2026-06-22 (26 traces
    BasicAirData GPS Logger). Coordonnées recalibrées le 2026-07-05 pour
    être exactement SUR LA ROUTE (et non sur le bâtiment comme Google Maps).
"""

from typing import NamedTuple


class PointGPS(NamedTuple):
    """Point GPS — latitude, longitude (degrés décimaux WGS84)."""
    lat: float
    lon: float


# ---------------------------------------------------------------------------
# Points d'extrémité — Abidjan, Côte d'Ivoire
# Source : GPX terrain recalibrés 2026-07-05 (moyenne aller/retour)
# ---------------------------------------------------------------------------

CARENA_PLATEAU = PointGPS(lat=5.317375, lon=-4.024489)
"""CARENA — point GPS enregistré sur la route, départ du tracé GPX."""

TOYOTA_CFAO_TREICHVILLE = PointGPS(lat=5.294394, lon=-4.006206)
"""TOYOTA CFAO — point GPS enregistré sur la route (trace T1B)."""

SODECI_ZONE_4 = PointGPS(lat=5.293730, lon=-4.000654)
"""Agence SODECI — point GPS enregistré sur la route (trace T1D)."""

PHARMACIE_PALM_BEACH = PointGPS(lat=5.258348, lon=-3.981822)
"""Pharmacie Palm Beach — point GPS enregistré sur la route (moyenne aller/retour)."""


# ---------------------------------------------------------------------------
# Table de correspondance : libellé canonique → point GPS
#
# On utilise le libellé tel qu'il apparaît dans `troncons.nom`, ce qui permet
# de retrouver origine/destination par simple split sur " → ".
# ---------------------------------------------------------------------------

POINTS_PAR_LIBELLE: dict[str, PointGPS] = {
    "CARENA (Plateau)": CARENA_PLATEAU,
    "Toyota CFAO (Treichville)": TOYOTA_CFAO_TREICHVILLE,
    "Agence SODECI (Zone 4)": SODECI_ZONE_4,
    "Pharmacie Palm Beach": PHARMACIE_PALM_BEACH,
}


def origine_destination(nom_troncon: str) -> tuple[PointGPS, PointGPS]:
    """Sépare le libellé d'un tronçon en (origine, destination).

    Le séparateur est la flèche " → " utilisée par le seed.

    Raises:
        KeyError: si l'un des deux libellés n'est pas reconnu.
        ValueError: si le séparateur " → " est absent.
    """
    if " → " not in nom_troncon:
        raise ValueError(
            f"Libellé de tronçon non parseable (séparateur ' → ' manquant) : {nom_troncon!r}"
        )
    libelle_origine, libelle_destination = nom_troncon.split(" → ", 1)
    return POINTS_PAR_LIBELLE[libelle_origine.strip()], POINTS_PAR_LIBELLE[libelle_destination.strip()]
