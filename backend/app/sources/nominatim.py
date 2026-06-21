"""Client Nominatim (OpenStreetMap) pour le géocodage gratuit.

Référence : https://nominatim.openstreetmap.org/ui/search.html

Conditions d'utilisation :
  - User-Agent obligatoire identifiant clairement l'application
  - Max 1 req/seconde (suffisant pour un calcul d'heure optimale ponctuel)
  - Pas de bulk usage

Utilisé par P6.3 (heure optimale de départ) pour résoudre un nom de lieu
(« Plateau, Abidjan ») en coordonnées GPS.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.sources.coordonnees import PointGPS


NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
# Cf. politique d'usage Nominatim : User-Agent identifiant l'app
USER_AGENT = "paa-traverse/1.0 (Hackathon Port Autonome Abidjan — paa.ci)"


@dataclass(frozen=True)
class ResultatGeocodage:
    """Résultat d'une recherche Nominatim."""
    libelle: str       # adresse complète formatée
    point: PointGPS    # coordonnées GPS
    classe: str | None  # ex. "amenity", "place"


async def geocoder(
    requete: str,
    *,
    pays: str = "ci",
    timeout_s: float = 8.0,
) -> ResultatGeocodage | None:
    """Renvoie le 1er résultat Nominatim pour la requête (ou None si rien).

    Args:
        requete: texte libre, ex. "Plateau, Abidjan"
        pays: code ISO du pays pour borner la recherche (défaut Côte d'Ivoire)
    """
    if not requete or not requete.strip():
        return None

    # Pour bornes : essayons d'abord avec countrycodes, repli sans si rien
    parametres = {
        "q": requete.strip(),
        "format": "json",
        "limit": 1,
        "countrycodes": pays,
        "addressdetails": 0,
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "fr",
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            reponse = await client.get(
                f"{NOMINATIM_BASE_URL}/search",
                params=parametres,
                headers=headers,
            )
            reponse.raise_for_status()
            resultats = reponse.json()
        except (httpx.HTTPError, ValueError):
            return None

    if not isinstance(resultats, list) or not resultats:
        return None

    premier = resultats[0]
    try:
        return ResultatGeocodage(
            libelle=str(premier.get("display_name") or requete),
            point=PointGPS(
                lat=float(premier["lat"]),
                lon=float(premier["lon"]),
            ),
            classe=premier.get("class"),
        )
    except (KeyError, ValueError, TypeError):
        return None


def parser_latlon(texte: str) -> PointGPS | None:
    """Si le texte ressemble à 'lat,lon', retourne un PointGPS, sinon None."""
    if not texte or "," not in texte:
        return None
    try:
        a, b = (s.strip() for s in texte.split(",", 1))
        lat = float(a)
        lon = float(b)
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return PointGPS(lat=lat, lon=lon)
    except (ValueError, TypeError):
        return None
    return None
