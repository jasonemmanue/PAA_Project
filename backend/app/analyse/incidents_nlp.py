"""Extraction NLP légère et géocodage des incidents de circulation (P8.2).

Pipeline appliqué à chaque incident inséré par le scraper RSS :
  1. Extraire le lieu mentionné dans le texte (dictionnaire ordonné).
  2. Classifier le type d'incident (accident / embouteillage / route_barree
     / travaux / autre) par regex.
  3. Classifier la sévérité (grave / moyen / mineur / inconnu) par regex.
  4. Géocoder le lieu extrait via Nominatim OSM + fallback Photon.
  5. Filtrer : si le point résolu est hors de la bbox portuaire, on garde
     le lieu textuel mais on laisse lat/lon à NULL.
  6. Attribuer `troncon_id` si le point géocodé est à < 300 m d'une
     extrémité d'un tronçon actif.

Aucune dépendance NLP lourde (pas de spaCy, pas de transformers).
L'ensemble est asynchrone pour s'insérer dans le scheduler APScheduler.

Cf. CLAUDE.md § 10.3.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Incident, SeveriteIncident, Troncon, TypeIncident
from app.sources.nominatim import geocoder


logger = logging.getLogger("paa.incidents.nlp")

# ---------------------------------------------------------------------------
# Bounding box portuaire (CLAUDE.md § 10.1)
# ---------------------------------------------------------------------------

_BBOX_LAT_MIN = 5.24
_BBOX_LAT_MAX = 5.37
_BBOX_LON_MIN = -4.05
_BBOX_LON_MAX = -3.96

# Rayon de proximité tronçon (mètres) pour l'attribution automatique
_RAYON_TRONCON_M = 300

# Délai entre deux appels Nominatim consécutifs (respect ToS OSM : 1 req/s)
_DELAI_GEOCODAGE_S = 1.2

# Taille des batches d'enrichissement (commits intermédiaires)
_BATCH_SIZE = 20

# ---------------------------------------------------------------------------
# Dictionnaire de lieux de référence (ordre : du plus spécifique au plus général)
# ---------------------------------------------------------------------------

LIEUX_ABIDJAN: dict[str, str] = {
    "carena": "CARENA",
    "pharmacie palm beach": "Palm Beach",
    "pharmacie du port": "Port d'Abidjan",
    "palm beach": "Palm Beach",
    "pont houphouët-boigny": "Pont Houphouët-Boigny",
    "pont houphouet": "Pont Houphouët-Boigny",
    "pont félix": "Pont Houphouët-Boigny",
    "pont felix": "Pont Houphouët-Boigny",
    "pont hb": "Pont Houphouët-Boigny",
    "seamen": "Seamen's Club",
    "toyota cfao": "Toyota CFAO",
    "cfao": "Toyota CFAO",
    "grand moulin": "Grand Moulin",
    "bd de marseille": "Boulevard de Marseille",
    "boulevard de marseille": "Boulevard de Marseille",
    "avenue christiani": "Avenue Christiani",
    "av christiani": "Avenue Christiani",
    "port d'abidjan": "Port d'Abidjan",
    "port autonome": "Port d'Abidjan",
    "sodeci": "Zone 4",
    "zone 4": "Zone 4",
    "zone4": "Zone 4",
    "treichville": "Treichville",
    "plateau": "Plateau",
    "marcory": "Marcory",
    "koumassi": "Koumassi",
    "autoroute du nord": "Autoroute du Nord",
}

# ---------------------------------------------------------------------------
# Patterns regex NLP
# ---------------------------------------------------------------------------

_RE_TYPE: dict[TypeIncident, re.Pattern] = {
    TypeIncident.accident: re.compile(
        r"accident|collision|accrochage|carambolage|renvers[eé]|percuté?|"
        r"choc frontal|d[ée]rapage",
        re.IGNORECASE,
    ),
    TypeIncident.travaux: re.compile(
        r"travaux|chantier|r[eé]fection|caniveau|bitumage|goudronnage",
        re.IGNORECASE,
    ),
    TypeIncident.route_barree: re.compile(
        r"route barr[eé]e?|voie coup[eé]e?|bloqu[eé]e?|ferm[eé]e?|"
        r"manifestation|barricade|mouvement d'humeur",
        re.IGNORECASE,
    ),
    TypeIncident.embouteillage: re.compile(
        r"embouteillage|bouchon|ralentissement|congestion|trafic dense|"
        r"files? de voiture|circulation difficile",
        re.IGNORECASE,
    ),
}

_RE_SEVERITE: dict[SeveriteIncident, re.Pattern] = {
    SeveriteIncident.grave: re.compile(
        r"mort|d[eé]c[eè]s|tu[eé]|grièvement|grave|urgence|"
        r"bless[eé]s? grave|ambulance|pompier|d[eé]c[eé]d[eé]",
        re.IGNORECASE,
    ),
    SeveriteIncident.moyen: re.compile(
        r"bless[eé]|hospitalis[eé]|transport[eé]|secours|SAMU|",
        re.IGNORECASE,
    ),
    SeveriteIncident.mineur: re.compile(
        r"l[eé]ger|mineur|accrochage|sans gravit[eé]|"
        r"d[eé]g[aâ]ts mat[eé]riels?",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Fonctions d'extraction
# ---------------------------------------------------------------------------


def extraire_lieu(texte: str) -> str | None:
    """Retourne le premier lieu de référence trouvé dans le texte.

    Cherche du plus spécifique au plus général (ordre du dictionnaire).
    Insensible à la casse, correspondance sur sous-chaîne.
    """
    texte_lower = texte.lower()
    for cle, libelle in LIEUX_ABIDJAN.items():
        if cle in texte_lower:
            return libelle
    return None


def classifier_type(texte: str) -> TypeIncident:
    """Classifie le type d'incident par ordre de priorité des patterns."""
    for type_inc, pattern in _RE_TYPE.items():
        if pattern.search(texte):
            return type_inc
    return TypeIncident.autre


def classifier_severite(texte: str) -> SeveriteIncident:
    """Classifie la sévérité par ordre de priorité des patterns."""
    for severite, pattern in _RE_SEVERITE.items():
        if pattern.search(texte):
            return severite
    return SeveriteIncident.inconnu


# ---------------------------------------------------------------------------
# Géocodage avec cache mémoire
# ---------------------------------------------------------------------------


# Cache mémoire : {lieu_normalisé: (lat, lon) | None}
_cache_geocodage: dict[str, tuple[float, float] | None] = {}


def _dans_bbox_portuaire(lat: float, lon: float) -> bool:
    """Retourne True si le point est dans la bounding box de la zone portuaire."""
    return (
        _BBOX_LAT_MIN <= lat <= _BBOX_LAT_MAX
        and _BBOX_LON_MIN <= lon <= _BBOX_LON_MAX
    )


async def geocoder_lieu(lieu: str) -> tuple[float, float] | None:
    """Géocode un lieu et retourne (lat, lon) ou None si hors bbox ou erreur.

    Utilise le client Nominatim existant (avec fallback Photon).
    Cache en mémoire : un lieu géocodé ne génère qu'un seul appel réseau.
    Respecte le délai ToS OSM (1 appel/seconde).
    """
    cle = lieu.strip().lower()
    if cle in _cache_geocodage:
        return _cache_geocodage[cle]

    await asyncio.sleep(_DELAI_GEOCODAGE_S)

    resultat = await geocoder(f"{lieu} Abidjan")
    if resultat is None:
        _cache_geocodage[cle] = None
        return None

    lat, lon = resultat.point.lat, resultat.point.lon
    if not _dans_bbox_portuaire(lat, lon):
        logger.debug(
            "Geocodage %r → (%.4f, %.4f) hors bbox portuaire — ignoré.",
            lieu, lat, lon,
        )
        _cache_geocodage[cle] = None
        return None

    coords = (lat, lon)
    _cache_geocodage[cle] = coords
    logger.info("Geocodage %r → (%.4f, %.4f) ✓", lieu, lat, lon)
    return coords


# ---------------------------------------------------------------------------
# Attribution du tronçon le plus proche
# ---------------------------------------------------------------------------


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance Haversine entre deux points GPS, en mètres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _troncon_le_plus_proche(
    lat: float,
    lon: float,
    troncons: list[Troncon],
) -> int | None:
    """Retourne l'id du tronçon dont une extrémité est à moins de 300 m du point.

    Compare avec les 4 extrémités (origine + destination) de chaque tronçon.
    Retourne None si aucun tronçon n'est assez proche.
    """
    meilleure_distance = _RAYON_TRONCON_M
    meilleur_id: int | None = None

    for troncon in troncons:
        for t_lat, t_lon in [
            (troncon.lat_origine, troncon.lon_origine),
            (troncon.lat_destination, troncon.lon_destination),
        ]:
            if t_lat is None or t_lon is None:
                continue
            dist = _haversine_m(lat, lon, t_lat, t_lon)
            if dist < meilleure_distance:
                meilleure_distance = dist
                meilleur_id = troncon.id

    return meilleur_id


# ---------------------------------------------------------------------------
# Enrichissement en lot
# ---------------------------------------------------------------------------


async def enrichir_incidents(db: Session) -> int:
    """Enrichit les incidents non encore classifiés.

    Pour chaque incident où `lieu_extrait IS NULL` ou `type_incident IS NULL` :
      1. Extrait le lieu, classifie type et sévérité depuis titre + résumé.
      2. Géocode le lieu extrait (avec cache + délai ToS).
      3. Attribue `troncon_id` si un tronçon est à < 300 m.
      4. Commit par batch de 20 incidents.

    Retourne le nombre d'incidents mis à jour.
    """
    # Charge les incidents non enrichis
    incidents: list[Incident] = list(
        db.execute(
            select(Incident).where(Incident.type_incident.is_(None))
        ).scalars()
    )

    if not incidents:
        logger.debug("Enrichissement : aucun incident à traiter.")
        return 0

    # Charge les tronçons actifs avec coordonnées (pour l'attribution)
    troncons: list[Troncon] = list(
        db.execute(
            select(Troncon).where(
                Troncon.actif.is_(True),
                Troncon.lat_origine.is_not(None),
                Troncon.lat_destination.is_not(None),
            )
        ).scalars()
    )

    nb_enrichis = 0

    for i, incident in enumerate(incidents):
        texte_complet = f"{incident.titre} {incident.resume or ''}"

        # 1. Extraction NLP
        lieu = extraire_lieu(texte_complet)
        type_inc = classifier_type(texte_complet)
        severite = classifier_severite(texte_complet)

        incident.lieu_extrait = lieu
        incident.type_incident = type_inc
        incident.severite = severite

        # 2. Géocodage (uniquement si un lieu a été extrait et pas déjà géocodé)
        if lieu and incident.lat is None:
            coords = await geocoder_lieu(lieu)
            if coords:
                incident.lat, incident.lon = coords

                # 3. Attribution du tronçon le plus proche
                incident.troncon_id = _troncon_le_plus_proche(
                    incident.lat, incident.lon, troncons
                )

        nb_enrichis += 1

        # Commit par batch pour éviter une transaction trop longue
        if (i + 1) % _BATCH_SIZE == 0:
            db.commit()
            logger.info(
                "Enrichissement : %d / %d incidents traités.", i + 1, len(incidents)
            )

    db.commit()
    logger.info(
        "Enrichissement terminé : %d incident(s) enrichi(s) sur %d.",
        nb_enrichis, len(incidents),
    )
    return nb_enrichis
