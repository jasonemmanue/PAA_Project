"""Coordonnées GPS des 4 points d'extrémité des 3 axes officiels.

Ces coordonnées servent à :
  1. Compléter automatiquement les colonnes lat_*/lon_* des `troncons` via OSRM
     (script `app/complete_troncons.py`).
  2. Reconstruire l'origine/destination à partir du nom d'un tronçon lors d'un
     appel /diag/*.

⚠️  **Source de vérité** : Google Maps. Ces coordonnées ont été ajustées sur
    la base d'observations terrain et sont alignées avec celles déployées en
    production Railway. Tout `git pull` qui ramènerait d'anciennes valeurs
    OSM approximatives doit être rejeté.
"""

from typing import NamedTuple


class PointGPS(NamedTuple):
    """Point GPS — latitude, longitude (degrés décimaux WGS84)."""
    lat: float
    lon: float


# ---------------------------------------------------------------------------
# Points d'extrémité — Abidjan, Côte d'Ivoire (source : Google Maps)
# ---------------------------------------------------------------------------
# Convention : 4 points uniques, partagés par les axes (Palm Beach commun aux 3).

CARENA_PLATEAU = PointGPS(lat=5.328119, lon=-4.028563)
"""CARENA (Compagnie Africaine de Réparations Navales) — Plateau, bord de lagune."""

TOYOTA_CFAO_TREICHVILLE = PointGPS(lat=5.295971, lon=-4.005131)
"""Concession Toyota / CFAO Motors — Boulevard Giscard d'Estaing, Treichville."""

SODECI_ZONE_4 = PointGPS(lat=5.293686, lon=-4.000390)
"""Agence SODECI — Zone 4 (Marcory), Boulevard de Marseille."""

PHARMACIE_PALM_BEACH = PointGPS(lat=5.258705, lon=-3.981960)
"""Pharmacie Palm Beach — Zone 4 / Port-Bouët, proche carrefour Vridi."""


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
