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


# Boîte englobante du Grand Abidjan utilisée comme `viewbox` Nominatim
# (lon_min, lat_max, lon_max, lat_min — convention Nominatim).
# Couvre approximativement Yopougon → Bingerville et Treichville → Cocody.
VIEWBOX_ABIDJAN = "-4.20,5.40,-3.85,5.18"


async def _appel_nominatim(
    params: dict[str, str | int],
    timeout_s: float,
) -> list[dict] | None:
    """Appel HTTP Nominatim avec gestion d'erreur silencieuse."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "fr",
        "Referer": "https://paa-traverse.up.railway.app/",
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            reponse = await client.get(
                f"{NOMINATIM_BASE_URL}/search",
                params=params,
                headers=headers,
            )
            reponse.raise_for_status()
            resultats = reponse.json()
        except (httpx.HTTPError, ValueError):
            return None
    return resultats if isinstance(resultats, list) else None


async def geocoder(
    requete: str,
    *,
    pays: str = "ci",
    timeout_s: float = 8.0,
) -> ResultatGeocodage | None:
    """Renvoie le 1er résultat Nominatim pour la requête (ou None si rien).

    Stratégie en cascade pour maximiser le taux de réussite :
      1. Requête bornée à Côte d'Ivoire (`countrycodes=ci`) avec viewbox Abidjan
      2. Si rien : retire le `countrycodes` mais garde le viewbox Abidjan
      3. Si rien : recherche libre mondiale (Nominatim trouvera l'usage le plus
         fréquent du nom, souvent suffisant)

    Args:
        requete: texte libre, ex. "Plateau, Abidjan" ou "Marcory"
        pays: code ISO du pays pour la 1re passe (défaut Côte d'Ivoire)
    """
    if not requete or not requete.strip():
        return None
    q = requete.strip()

    # 1) Côte d'Ivoire + viewbox Abidjan
    res = await _appel_nominatim(
        {
            "q": q, "format": "json", "limit": 1,
            "countrycodes": pays, "viewbox": VIEWBOX_ABIDJAN,
            "bounded": 0, "addressdetails": 0,
        },
        timeout_s,
    )
    if not res:
        # 2) Sans countrycodes, garde viewbox Abidjan
        res = await _appel_nominatim(
            {
                "q": q, "format": "json", "limit": 1,
                "viewbox": VIEWBOX_ABIDJAN, "bounded": 0,
                "addressdetails": 0,
            },
            timeout_s,
        )
    if not res:
        # 3) Recherche libre mondiale (dernier recours)
        res = await _appel_nominatim(
            {"q": q, "format": "json", "limit": 1, "addressdetails": 0},
            timeout_s,
        )
    if not res:
        return None

    premier = res[0]
    try:
        return ResultatGeocodage(
            libelle=str(premier.get("display_name") or q),
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
