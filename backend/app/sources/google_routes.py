"""Client Google Routes API — source primaire de la chaîne de dégradation gracieuse.

Endpoint utilisé : `routes:computeRoutes` (POST), mode `TRAFFIC_AWARE_OPTIMAL`.
Doc : https://developers.google.com/maps/documentation/routes/compute_route_directions

⚠️  Le FieldMask est OBLIGATOIRE pour limiter les coûts API (Google facture
    selon les champs demandés). On ne demande que ce qui est strictement utile :
    duration, staticDuration, distanceMeters, polyline.encodedPolyline.
"""

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.sources.coordonnees import PointGPS


GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


@dataclass
class ReponseGoogleRoutes:
    """Résultat d'un appel computeRoutes en mode TRAFFIC_AWARE_OPTIMAL.

    duree_trafic_s     : temps réel observé avec trafic (champ `duration`).
    duree_sans_trafic_s: temps fluide théorique (champ `staticDuration`).
    distance_m         : distance officielle du tracé en mètres.
    polyline_encodee   : tracé encodé (Google polyline precision 5).
    """
    duree_trafic_s: int
    duree_sans_trafic_s: int
    distance_m: int
    polyline_encodee: str


def _parse_duration(valeur: str | int | None) -> int | None:
    """Convertit une durée Google ('123s' ou int) en secondes entières.

    Retourne None si la valeur est absente — pas d'invention de donnée.
    """
    if valeur is None:
        return None
    if isinstance(valeur, int):
        return valeur
    # Format texte attendu : "1234s"
    chaine = str(valeur).strip()
    if chaine.endswith("s"):
        chaine = chaine[:-1]
    try:
        return int(round(float(chaine)))
    except ValueError:
        return None


async def calcul_itineraire(
    origine: PointGPS,
    destination: PointGPS,
    *,
    timeout_s: float = 10.0,
) -> ReponseGoogleRoutes:
    """Appelle Google Routes en mode TRAFFIC_AWARE_OPTIMAL.

    Raises:
        RuntimeError: si la clé API n'est pas configurée.
        httpx.HTTPStatusError: si Google renvoie une erreur HTTP.
        RuntimeError: si la réponse ne contient aucun itinéraire.
    """
    cle_api = get_settings().google_routes_api_key
    if not cle_api:
        raise RuntimeError(
            "GOOGLE_ROUTES_API_KEY absent du backend/.env — "
            "source Google indisponible (dégradation gracieuse appliquée par l'appelant)."
        )

    corps_requete: dict = {
        "origin": {
            "location": {
                "latLng": {"latitude": origine.lat, "longitude": origine.lon},
            },
        },
        "destination": {
            "location": {
                "latLng": {"latitude": destination.lat, "longitude": destination.lon},
            },
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "polylineEncoding": "ENCODED_POLYLINE",
        "computeAlternativeRoutes": False,
        "languageCode": "fr-FR",
        "units": "METRIC",
        "regionCode": "CI",
    }

    # FieldMask minimal — réduit le coût et limite la surface de données échangées.
    entetes = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": cle_api,
        "X-Goog-FieldMask": (
            "routes.duration,routes.staticDuration,"
            "routes.distanceMeters,routes.polyline.encodedPolyline"
        ),
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        reponse = await client.post(
            GOOGLE_ROUTES_URL,
            json=corps_requete,
            headers=entetes,
        )
        reponse.raise_for_status()
        donnees = reponse.json()

    routes = donnees.get("routes") or []
    if not routes:
        raise RuntimeError(
            f"Google Routes n'a retourné aucun itinéraire — réponse brute : {donnees!r}"
        )

    premiere_route = routes[0]
    duree_trafic = _parse_duration(premiere_route.get("duration"))
    duree_fluide = _parse_duration(premiere_route.get("staticDuration"))
    distance = premiere_route.get("distanceMeters")
    polyline = (premiere_route.get("polyline") or {}).get("encodedPolyline")

    if duree_trafic is None or duree_fluide is None or distance is None or not polyline:
        raise RuntimeError(
            "Google Routes : champs manquants dans la réponse "
            f"(duration={duree_trafic}, staticDuration={duree_fluide}, "
            f"distanceMeters={distance}, polyline={'présent' if polyline else 'absent'})."
        )

    return ReponseGoogleRoutes(
        duree_trafic_s=duree_trafic,
        duree_sans_trafic_s=duree_fluide,
        distance_m=int(distance),
        polyline_encodee=polyline,
    )
