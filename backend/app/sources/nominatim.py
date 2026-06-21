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

import logging
from dataclasses import dataclass

import httpx

from app.sources.coordonnees import PointGPS


logger = logging.getLogger("paa.geocoder")


NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
# Photon — alternative gratuite à Nominatim, basée sur les mêmes données OSM,
# gérée par Komoot, beaucoup plus permissive pour les hébergeurs cloud
# (Nominatim bannit régulièrement les IP de Railway/AWS/GCP).
PHOTON_BASE_URL = "https://photon.komoot.io/api"
# Cf. politique d'usage Nominatim : User-Agent identifiant l'app.
# IMPORTANT : Pure ASCII obligatoire — les headers HTTP refusent les
# caractères Unicode comme l'em dash (—, U+2014). Bug subtil : httpx lève
# un UnicodeEncodeError silencieux lors de l'envoi du header.
USER_AGENT = "paa-traverse/1.0 (Hackathon Port Autonome Abidjan - paa.ci)"


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
    """Appel HTTP Nominatim avec gestion d'erreur loggée."""
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
            logger.info(
                "Nominatim q=%r → HTTP %d (len=%d)",
                params.get("q"), reponse.status_code, len(reponse.content),
            )
            reponse.raise_for_status()
            resultats = reponse.json()
        except httpx.TimeoutException as exc:
            logger.warning("Nominatim TIMEOUT q=%r : %s", params.get("q"), exc)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Nominatim HTTPError q=%r : %s", params.get("q"), exc)
            return None
        except UnicodeEncodeError as exc:
            # Headers HTTP doivent être ASCII — un User-Agent / Referer
            # contenant des caractères Unicode lèvera cette erreur.
            logger.error(
                "Nominatim UnicodeEncodeError (header non-ASCII) q=%r : %s",
                params.get("q"), exc,
            )
            return None
        except ValueError as exc:
            logger.warning("Nominatim JSON invalide q=%r : %s", params.get("q"), exc)
            return None
    if isinstance(resultats, list):
        logger.info("Nominatim q=%r → %d résultat(s)", params.get("q"), len(resultats))
        return resultats
    logger.warning("Nominatim q=%r → réponse non-liste : %r", params.get("q"), type(resultats))
    return None


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
    logger.info("== Géocodage demandé : %r ==", q)

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
        # 3) Recherche libre mondiale (dernier recours sur Nominatim)
        res = await _appel_nominatim(
            {"q": q, "format": "json", "limit": 1, "addressdetails": 0},
            timeout_s,
        )

    if res:
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
            pass

    # 4) Fallback Photon (Komoot) — fiable depuis les hébergeurs cloud
    return await _geocoder_photon(q, timeout_s)


async def _geocoder_photon(
    requete: str,
    timeout_s: float,
) -> ResultatGeocodage | None:
    """Géocodage via Photon (Komoot) en repli si Nominatim ne répond pas.

    Photon est basé sur les mêmes données OSM mais avec une politique
    d'usage beaucoup plus permissive — il n'est pas bloqué depuis les IP
    Railway/AWS/GCP comme Nominatim peut l'être.

    API : https://photon.komoot.io/api/?q=<requete>&limit=1
    Réponse : GeoJSON FeatureCollection.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "fr",
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            reponse = await client.get(
                PHOTON_BASE_URL,
                params={"q": requete, "limit": 1, "lang": "fr"},
                headers=headers,
            )
            logger.info(
                "Photon q=%r → HTTP %d (len=%d)",
                requete, reponse.status_code, len(reponse.content),
            )
            reponse.raise_for_status()
            donnees = reponse.json()
        except httpx.TimeoutException as exc:
            logger.warning("Photon TIMEOUT q=%r : %s", requete, exc)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Photon HTTPError q=%r : %s", requete, exc)
            return None
        except UnicodeEncodeError as exc:
            logger.error(
                "Photon UnicodeEncodeError (header non-ASCII) q=%r : %s",
                requete, exc,
            )
            return None
        except ValueError as exc:
            logger.warning("Photon JSON invalide q=%r : %s", requete, exc)
            return None

    features = donnees.get("features") if isinstance(donnees, dict) else None
    logger.info(
        "Photon q=%r → %d feature(s)",
        requete, len(features) if isinstance(features, list) else 0,
    )
    if not features or not isinstance(features, list):
        return None

    feature = features[0]
    try:
        coords = feature["geometry"]["coordinates"]  # [lon, lat]
        lon, lat = float(coords[0]), float(coords[1])
        props = feature.get("properties", {})
        libelle_parts = [
            props.get("name"),
            props.get("city"),
            props.get("state"),
            props.get("country"),
        ]
        libelle = ", ".join(p for p in libelle_parts if p) or requete
        logger.info("Photon q=%r → %s (%.4f, %.4f)", requete, libelle, lat, lon)
        return ResultatGeocodage(
            libelle=str(libelle),
            point=PointGPS(lat=lat, lon=lon),
            classe=props.get("osm_value"),
        )
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        logger.warning("Photon parsing échoué q=%r : %s", requete, exc)
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
