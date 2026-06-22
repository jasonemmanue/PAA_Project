"""Client Google Routes API — source primaire de la chaîne de dégradation gracieuse.

Endpoint utilisé : `routes:computeRoutes` (POST), mode `TRAFFIC_AWARE_OPTIMAL`.
Doc : https://developers.google.com/maps/documentation/routes/compute_route_directions

⚠️  Le FieldMask est OBLIGATOIRE pour limiter les coûts API (Google facture
    selon les champs demandés). On demande :
      - `duration`               → temps avec trafic (sert aux agrégats temps min/moyen/max).
      - `staticDuration`         → temps fluide théorique (conservé pour comparaison).
      - `distanceMeters`         → distance officielle du tracé.
      - `polyline.encodedPolyline` → tracé encodé pour la carte.
      - `travelAdvisory.speedReadingIntervals` → **segments colorés**
        (NORMAL/SLOW/TRAFFIC_JAM) — c'est avec ça qu'on reproduit le critère
        couleur DEESP (cf. CLAUDE.md § 4.5.2 et `rapport_oct2025.docx`).

Critère DEESP — rappel :
    🔴 Rouge (TRAFFIC_JAM) : congestionné, quelle que soit la longueur.
    🟠 Orange (SLOW) sur ≥ 50 % du tronçon : congestionné.
    🟠 Orange sur courte distance : fluide (arrêts feux/manœuvres).
    🟢 Vert (NORMAL) : fluide.
"""

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.sources.coordonnees import PointGPS
from app.sources.polyline import (
    decoder_polyline,
    distance_cumulee_m,
    distances_cumulees_m,
)


GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


@dataclass
class ReponseGoogleRoutes:
    """Résultat d'un appel computeRoutes en mode TRAFFIC_AWARE_OPTIMAL.

    Champs « temps » — conservés uniquement pour permettre les agrégats
    (temps min/moyen/max par jour/semaine/mois — cf. Tableaux 3-15 du
    rapport DEESP) :
      - duree_trafic_s      : durée observée avec trafic (champ `duration`).
      - duree_sans_trafic_s : durée fluide théorique (`staticDuration`).
      - distance_m          : distance officielle du tracé en mètres.
      - polyline_encodee    : tracé encodé (Google polyline precision 5).

    Champs « couleur » (DEESP) — c'est avec ceux-ci qu'on qualifie la
    congestion, conformément au rapport :
      - pourcentage_rouge   : part du tracé en TRAFFIC_JAM (0..100).
      - pourcentage_orange  : part du tracé en SLOW (0..100).
      - pourcentage_vert    : part du tracé en NORMAL (0..100).
      - est_congestionne    : règle DEESP appliquée (rouge>0 OU orange≥50%).
                              `None` si Google n'a pas renvoyé d'intervalles
                              (trou de couleur — on ne tranche pas).
    """
    duree_trafic_s: int
    duree_sans_trafic_s: int
    distance_m: int
    polyline_encodee: str
    pourcentage_rouge: float | None
    pourcentage_orange: float | None
    pourcentage_vert: float | None
    est_congestionne: bool | None


# Mapping de l'enum Google `Speed` (champ `speedReadingIntervals[].speed`)
# vers les 3 couleurs DEESP.
#   NORMAL       → vert
#   SLOW         → orange
#   TRAFFIC_JAM  → rouge
#   SPEED_UNSPECIFIED → ignoré (donnée non qualifiée)
_SPEED_VERS_COULEUR = {
    "NORMAL": "vert",
    "SLOW": "orange",
    "TRAFFIC_JAM": "rouge",
}

# Seuil DEESP — un tronçon est congestionné si la couleur ORANGE couvre
# au moins 50 % de sa longueur (rapport § METHODOLOGIE, "tronçons tracés
# en orange sur une longue distance (moitié du tronçon concerné)").
SEUIL_ORANGE_LONG_PCT = 50.0


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


def calculer_pourcentages_couleur(
    polyline_encodee: str,
    intervalles: list[dict] | None,
) -> tuple[float | None, float | None, float | None]:
    """Convertit la liste `speedReadingIntervals` Google en pourcentages.

    Chaque intervalle a `startPolylinePointIndex`, `endPolylinePointIndex`
    et `speed` (NORMAL/SLOW/TRAFFIC_JAM). On mesure la distance Haversine
    couverte par chaque intervalle puis on rapporte à la distance totale
    pour obtenir les 3 pourcentages couleur.

    Retourne `(None, None, None)` si pas d'intervalles exploitables — on ne
    fabrique aucune donnée (cf. CLAUDE.md § 5.3 : aucune valeur inventée).
    """
    if not intervalles or not polyline_encodee:
        return None, None, None

    points = decoder_polyline(polyline_encodee)
    if len(points) < 2:
        return None, None, None

    cumul = distances_cumulees_m(points)
    distance_totale = cumul[-1]
    if distance_totale <= 0:
        return None, None, None

    distances_par_couleur: dict[str, int] = {"vert": 0, "orange": 0, "rouge": 0}

    nb_points = len(points)
    for intervalle in intervalles:
        speed = intervalle.get("speed")
        couleur = _SPEED_VERS_COULEUR.get(speed)
        if couleur is None:
            continue  # SPEED_UNSPECIFIED → ignoré
        debut = int(intervalle.get("startPolylinePointIndex") or 0)
        fin = int(
            intervalle.get("endPolylinePointIndex")
            if intervalle.get("endPolylinePointIndex") is not None
            else nb_points - 1
        )
        # Garde-fou contre les indices hors-borne (Google peut renvoyer
        # endPolylinePointIndex = nb_points si l'intervalle va jusqu'au bout).
        debut = max(0, min(nb_points - 1, debut))
        fin = max(0, min(nb_points - 1, fin))
        if fin <= debut:
            continue
        distance_segment = cumul[fin] - cumul[debut]
        if distance_segment <= 0:
            continue
        distances_par_couleur[couleur] += distance_segment

    pct_vert = round(distances_par_couleur["vert"] * 100.0 / distance_totale, 2)
    pct_orange = round(distances_par_couleur["orange"] * 100.0 / distance_totale, 2)
    pct_rouge = round(distances_par_couleur["rouge"] * 100.0 / distance_totale, 2)

    # Si tout est à 0 (aucun intervalle exploitable), on signale "indéterminé"
    # plutôt que de prétendre que le tronçon est 100 % fluide.
    if pct_vert + pct_orange + pct_rouge <= 0:
        return None, None, None

    return pct_rouge, pct_orange, pct_vert


def evaluer_congestion_deesp(
    pourcentage_rouge: float | None,
    pourcentage_orange: float | None,
) -> bool | None:
    """Applique le critère couleur du rapport DEESP.

    Règles (rapport oct. 2025 — section METHODOLOGIE, NB juste avant le
    Tableau 2) :
      - Tout segment ROUGE → congestionné.
      - ORANGE sur ≥ 50 % du tronçon → congestionné (orange long).
      - ORANGE sur courte distance → fluide (feux, manœuvres).
      - VERT → fluide.

    Retourne `None` si les pourcentages sont indisponibles (pas
    d'invention de donnée).
    """
    if pourcentage_rouge is None and pourcentage_orange is None:
        return None
    if (pourcentage_rouge or 0) > 0:
        return True
    if (pourcentage_orange or 0) >= SEUIL_ORANGE_LONG_PCT:
        return True
    return False


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
        "polylineQuality": "HIGH_QUALITY",
        # Sans cette case, Google n'inclut pas speedReadingIntervals
        # (la lecture des couleurs est plus coûteuse et opt-in).
        "extraComputations": ["TRAFFIC_ON_POLYLINE"],
        "computeAlternativeRoutes": False,
        "languageCode": "fr-FR",
        "units": "METRIC",
        "regionCode": "CI",
    }

    # FieldMask : on demande désormais aussi les couleurs de trafic
    # (cf. critère DEESP § 4.5.2). Le surcoût Google est marginal — la
    # facturation reste sur le compteur Routes / Traffic-On-Polyline.
    entetes = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": cle_api,
        "X-Goog-FieldMask": (
            "routes.duration,routes.staticDuration,"
            "routes.distanceMeters,routes.polyline.encodedPolyline,"
            "routes.travelAdvisory.speedReadingIntervals"
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

    # speedReadingIntervals peut être absent si Google n'a pas pu colorer
    # le tracé (zone sans données trafic). Dans ce cas, on garde duree_trafic
    # mais on signale "indéterminé" côté couleurs — l'opérateur saura que
    # le statut de congestion ne peut pas être tranché selon la règle DEESP.
    travel_advisory = premiere_route.get("travelAdvisory") or {}
    intervalles = travel_advisory.get("speedReadingIntervals")

    pct_rouge, pct_orange, pct_vert = calculer_pourcentages_couleur(
        polyline, intervalles
    )
    est_congestionne = evaluer_congestion_deesp(pct_rouge, pct_orange)

    return ReponseGoogleRoutes(
        duree_trafic_s=duree_trafic,
        duree_sans_trafic_s=duree_fluide,
        distance_m=int(distance),
        polyline_encodee=polyline,
        pourcentage_rouge=pct_rouge,
        pourcentage_orange=pct_orange,
        pourcentage_vert=pct_vert,
        est_congestionne=est_congestionne,
    )
