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
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Incident, SeveriteIncident, Troncon, TypeIncident, TypesIncident
from app.sources.nominatim import geocoder


logger = logging.getLogger("paa.incidents.nlp")

# ---------------------------------------------------------------------------
# Bounding box portuaire (CLAUDE.md § 10.1)
# ---------------------------------------------------------------------------

_BBOX_LAT_MIN = 5.20   # étendu vers le sud pour couvrir Vridi / Port-Bouët
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
    # ── Landmarks spécifiques DEESP (du plus précis au plus général) ──
    "carena": "CARENA",
    "chantier naval": "CARENA",
    "pharmacie palm beach": "Palm Beach",
    "pharmacie du port": "Pharmacie du port",
    "palm beach": "Palm Beach",
    "gma": "Grand Moulin",
    "grand moulin": "Grand Moulin",
    "grands moulins": "Grand Moulin",
    "cimivoire": "CIMIVOIRE",
    "ciments de côte d'ivoire": "CIMIVOIRE",
    "seamen": "Seamen's Club",
    "unilever": "Unilever",
    "atc comafrique": "ATC Comafrique",
    "comafrique": "ATC Comafrique",
    "sgbci": "SGBCI",
    "dgi": "DGI",
    "libya oil": "Libya Oil",
    "gare sotra": "Gare SOTRA Terminus 19",
    "terminus 19": "Gare SOTRA Terminus 19",
    "sotra 19": "Gare SOTRA Terminus 19",
    # ── Ponts et ouvrages d'art ──
    "pont houphouët-boigny": "Pont Houphouët-Boigny",
    "pont houphouet": "Pont Houphouët-Boigny",
    "pont félix": "Pont Houphouët-Boigny",
    "pont felix": "Pont Houphouët-Boigny",
    "pont hb": "Pont Houphouët-Boigny",
    "pont de gaulle": "Pont De Gaulle",
    "pont charles de gaulle": "Pont De Gaulle",
    "pont henri konan bédié": "Pont HKB",
    "pont hkb": "Pont HKB",
    "pont de vridi": "Pont de Vridi",
    "pont de cocody": "Pont de Cocody",
    # ── Voies principales ──
    "bd de marseille": "Boulevard de Marseille",
    "boulevard de marseille": "Boulevard de Marseille",
    "avenue christiani": "Avenue Christiani",
    "av christiani": "Avenue Christiani",
    "boulevard vgd": "Boulevard VGE",
    "bd vge": "Boulevard VGE",
    "boulevard valéry giscard": "Boulevard VGE",
    "autoroute du nord": "Autoroute du Nord",
    "voie express": "Voie express",
    "boulevard de la république": "Boulevard de la République",
    "boulevard nangui abrogoua": "Boulevard Nangui Abrogoua",
    "boulevard lagunaire": "Boulevard Lagunaire",
    "route de bassam": "Route de Bassam",
    "route d'abidjan-bassam": "Route de Bassam",
    # ── Toyota CFAO / SODECI ──
    "toyota cfao": "Toyota CFAO",
    "cfao": "Toyota CFAO",
    "sodeci": "Zone 4",
    "zone 4": "Zone 4",
    "zone4": "Zone 4",
    # ── Port et terminaux ──
    "port d'abidjan": "Port d'Abidjan",
    "port autonome": "Port d'Abidjan",
    "terminal à conteneurs": "Terminal à Conteneurs",
    "terminal portuaire": "Port d'Abidjan",
    "terminal roulier": "Terminal roulier",
    "terminal minéralier": "Terminal minéralier",
    "terminal céréalier": "Terminal céréalier",
    "terminal pétrolier": "Terminal pétrolier",
    "accès au port": "Port d'Abidjan",
    "entrée du port": "Port d'Abidjan",
    "zone portuaire": "Port d'Abidjan",
    "enceinte portuaire": "Port d'Abidjan",
    "quai portuaire": "Port d'Abidjan",
    "dock": "Port d'Abidjan",
    "entrepôt portuaire": "Port d'Abidjan",
    "capitainerie": "Port d'Abidjan",
    "pilotage portuaire": "Port d'Abidjan",
    # ── Opérateurs portuaires ──
    "agl": "AGL Terminal",
    "agl terminal": "AGL Terminal",
    "bolloré": "AGL Terminal",
    "abidjan terminal": "Abidjan Terminal",
    "setv": "SETV",
    "msc": "Port d'Abidjan",
    "maersk": "Port d'Abidjan",
    "cma cgm": "Port d'Abidjan",
    # ── Douane / sécurité portuaire ──
    "commissariat du port": "Commissariat du port",
    "commissariat spécial": "Commissariat du port",
    "commissariat special": "Commissariat du port",
    "douane portuaire": "Douane portuaire",
    "douane du port": "Douane portuaire",
    "gendarmerie du port": "Gendarmerie du port",
    "gendarmerie maritime": "Gendarmerie du port",
    # ── Zone industrielle de Vridi ──
    "zone industrielle de vridi": "Zone industrielle de Vridi",
    "zone industrielle": "Zone industrielle de Vridi",
    "zone franche de vridi": "Zone franche de Vridi",
    "zone franche": "Zone franche de Vridi",
    "vridi": "Vridi",
    "canal de vridi": "Canal de Vridi",
    "route de vridi": "Route de Vridi",
    "raffinerie": "SIR Vridi",
    "sir": "SIR Vridi",
    "gestoci": "GESTOCI Vridi",
    "dépôt pétrolier": "GESTOCI Vridi",
    # ── Communes du périmètre portuaire ──
    "treichville": "Treichville",
    "plateau": "Plateau",
    "marcory": "Marcory",
    "koumassi": "Koumassi",
    "port-bouët": "Port-Bouët",
    "port bouet": "Port-Bouët",
    "port bouët": "Port-Bouët",
    "gonzagueville": "Gonzagueville",
    "petit-bassam": "Petit-Bassam",
    "petit bassam": "Petit-Bassam",
    "île de petit-bassam": "Petit-Bassam",
    "biétry": "Biétry",
    "bietry": "Biétry",
    "cité portuaire": "Cité portuaire",
    # ── Communes adjacentes (transit vers le port) ──
    "adjamé": "Adjamé",
    "adjame": "Adjamé",
    "cocody": "Cocody",
    "yopougon": "Yopougon",
    "abobo": "Abobo",
    "attécoubé": "Attécoubé",
    "attecoube": "Attécoubé",
    "grand-bassam": "Grand-Bassam",
    "grand bassam": "Grand-Bassam",
    # ── Fallback générique : "abidjan" seul → Vridi (zone portuaire) ──
    "abidjan": "Vridi",
}

# ---------------------------------------------------------------------------
# Patterns regex NLP
# ---------------------------------------------------------------------------

# Patterns par défaut (clés = slugs string) — utilisés si la table
# types_incidents est vide ou inaccessible
_RE_TYPE_DEFAUT: dict[str, re.Pattern] = {
    "accident": re.compile(
        r"accident|collision|accrochage|carambolage|renvers[eé]|percuté?|"
        r"choc frontal|d[ée]rapage",
        re.IGNORECASE,
    ),
    "route_barree": re.compile(
        r"route barr[eé]e?|voie coup[eé]e?|bloqu[eé]e?|ferm[eé]e?|"
        r"manifestation|barricade|mouvement d'humeur",
        re.IGNORECASE,
    ),
    "travaux": re.compile(
        r"travaux|chantier|r[eé]fection|caniveau|bitumage|goudronnage",
        re.IGNORECASE,
    ),
    "embouteillage": re.compile(
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


def classifier_type(
    texte: str,
    types_config: list[tuple[str, str]] | None = None,
) -> str:
    """Classifie le type d'incident et retourne le slug correspondant.

    types_config : liste de (slug, regex_str) chargée depuis types_incidents.
    Si None ou vide, utilise les patterns par défaut _RE_TYPE_DEFAUT.
    Le slug 'autre' ne peut pas être matché — il est retourné en fallback.
    """
    if types_config:
        for slug, regex_str in types_config:
            if slug == "autre":
                continue
            try:
                if re.search(regex_str, texte, re.IGNORECASE):
                    return slug
            except re.error:
                logger.warning("Regex invalide pour le type %r : %r", slug, regex_str)
        return "autre"

    # Fallback : patterns par défaut
    for slug, pattern in _RE_TYPE_DEFAUT.items():
        if pattern.search(texte):
            return slug
    return "autre"


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

# Coordonnées fixes pour les lieux génériques dont Nominatim est imprécis.
# "abidjan" seul → zone industrielle de Vridi (cœur de la zone portuaire).
# Ces valeurs bypasse Nominatim — elles sont issues du relevé terrain 2026-06-22.
_COORDS_FIXES: dict[str, tuple[float, float]] = {
    # ── Landmarks DEESP (coords GPX terrain 2026-06-22) ──
    "CARENA": (5.3174, -4.0245),
    "Grand Moulin": (5.3066, -4.0214),
    "CIMIVOIRE": (5.2986, -4.0152),
    "Seamen's Club": (5.2937, -4.0083),
    "Pharmacie du port": (5.2891, -4.0083),
    "Unilever": (5.2829, -4.0084),
    "ATC Comafrique": (5.2759, -4.0085),
    "SGBCI": (5.2686, -4.0041),
    "DGI": (5.2648, -3.9999),
    "Gare SOTRA Terminus 19": (5.2563, -3.9972),
    "Libya Oil": (5.2575, -3.9863),
    "Palm Beach": (5.2583, -3.9818),
    "Toyota CFAO": (5.2944, -4.0062),
    "Commissariat du port": (5.3039, -4.0230),
    # ── Port et terminaux ──
    "Port d'Abidjan": (5.2903, -4.0086),
    "Terminal à Conteneurs": (5.2850, -4.0050),
    "Terminal roulier": (5.2820, -4.0020),
    "Terminal minéralier": (5.2900, -4.0120),
    "Terminal céréalier": (5.2870, -4.0060),
    "Terminal pétrolier": (5.2650, -4.0000),
    "AGL Terminal": (5.2890, -4.0070),
    "Abidjan Terminal": (5.2860, -4.0040),
    "SETV": (5.2830, -4.0030),
    "Douane portuaire": (5.2880, -4.0060),
    "Gendarmerie du port": (5.2870, -4.0050),
    "Cité portuaire": (5.2800, -4.0000),
    # ── Zone industrielle de Vridi ──
    "Vridi": (5.2603, -3.9969),
    "Canal de Vridi": (5.2550, -4.0050),
    "Zone industrielle de Vridi": (5.2603, -3.9969),
    "Zone franche de Vridi": (5.2620, -3.9950),
    "Route de Vridi": (5.2650, -4.0020),
    "SIR Vridi": (5.2580, -4.0100),
    "GESTOCI Vridi": (5.2600, -4.0080),
    "Pont de Vridi": (5.2520, -4.0120),
    # ── Ponts ──
    "Pont Houphouët-Boigny": (5.3100, -4.0150),
    "Pont De Gaulle": (5.3180, -4.0200),
    "Pont HKB": (5.3200, -3.9900),
    "Pont de Cocody": (5.3250, -3.9850),
    # ── Voies principales ──
    "Boulevard de Marseille": (5.3100, -4.0180),
    "Avenue Christiani": (5.2950, -4.0100),
    "Boulevard VGE": (5.3000, -3.9950),
    "Boulevard de la République": (5.3150, -4.0170),
    "Boulevard Nangui Abrogoua": (5.3200, -4.0250),
    "Boulevard Lagunaire": (5.3050, -4.0170),
    "Autoroute du Nord": (5.3300, -4.0200),
    "Voie express": (5.3100, -4.0100),
    "Route de Bassam": (5.2500, -3.9600),
    # ── Communes du périmètre ──
    "Treichville": (5.3000, -4.0100),
    "Plateau": (5.3200, -4.0200),
    "Zone 4": (5.2937, -4.0007),
    "Marcory": (5.3000, -3.9900),
    "Koumassi": (5.2900, -3.9750),
    "Port-Bouët": (5.2550, -3.9700),
    "Gonzagueville": (5.2400, -3.9650),
    "Petit-Bassam": (5.2700, -4.0100),
    "Biétry": (5.2950, -3.9800),
    # ── Communes adjacentes ──
    "Adjamé": (5.3400, -4.0300),
    "Cocody": (5.3350, -3.9950),
    "Attécoubé": (5.3300, -4.0400),
    "Yopougon": (5.3500, -4.0700),
    "Abobo": (5.4100, -4.0200),
    "Grand-Bassam": (5.2100, -3.7400),
}


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

    # Bypass Nominatim pour les lieux dont les coordonnées sont hardcodées
    for nom_fixe, coords_fixes in _COORDS_FIXES.items():
        if nom_fixe.lower() == cle:
            logger.info("Geocodage %r → coords fixes (%.4f, %.4f) ✓", lieu, *coords_fixes)
            _cache_geocodage[cle] = coords_fixes
            return coords_fixes

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

    # Charge les types depuis la table types_incidents (fallback si vide)
    types_config: list[tuple[str, str]] = []
    try:
        types_config = [
            (t.slug, t.regex)
            for t in db.execute(
                select(TypesIncident)
                .where(TypesIncident.actif.is_(True))
                .order_by(TypesIncident.id)
            ).scalars()
        ]
        logger.debug("Enrichissement : %d types chargés depuis la DB.", len(types_config))
    except Exception:
        logger.warning("Impossible de charger les types depuis la DB — utilisation des patterns par défaut.")

    nb_enrichis = 0

    for i, incident in enumerate(incidents):
        texte_complet = f"{incident.titre} {incident.resume or ''}"

        # 1. Extraction NLP
        lieu = extraire_lieu(texte_complet)
        type_inc = classifier_type(texte_complet, types_config or None)
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

    # Déduplication cross-sources après enrichissement
    nb_doublons = _dedupliquer_incidents(db)
    if nb_doublons:
        logger.info("Déduplication : %d doublon(s) marqué(s).", nb_doublons)

    return nb_enrichis


# ---------------------------------------------------------------------------
# Déduplication cross-sources (P8.5)
# ---------------------------------------------------------------------------


def _mots_significatifs(titre: str) -> set[str]:
    """Extrait les mots de plus de 3 lettres d'un titre (insensible à la casse)."""
    return {w.lower() for w in re.findall(r"\b\w{4,}\b", titre)}


def _dedupliquer_incidents(db: Session) -> int:
    """Détecte et marque les doublons cross-sources.

    Un doublon probable remplit les 3 critères :
      1. Même `troncon_id` (non NULL) ET même `type_incident`
      2. `horodatage_publication` à ±2h de l'incident de référence
      3. Au moins 3 mots significatifs (> 3 lettres) en commun dans les titres

    On conserve le plus ancien (premier inséré). Les suivants reçoivent :
      - titre préfixé de « [DOUBLON] »
      - type_incident → TypeIncident.autre
      - verifie → False (reset pour signaler le changement)

    Retourne le nombre de doublons marqués.
    """
    # Ne considère que les incidents enrichis (type connu, tronçon attribué)
    enrichis: list[Incident] = list(
        db.execute(
            select(Incident)
            .where(
                Incident.type_incident.is_not(None),
                Incident.troncon_id.is_not(None),
                ~Incident.titre.like("[DOUBLON]%"),
            )
            .order_by(Incident.horodatage_publication.asc())
        ).scalars()
    )

    nb_doublons = 0
    # Index rapide : (troncon_id, type_incident) → liste d'incidents déjà vus
    vu: dict[tuple, list[Incident]] = {}

    for inc in enrichis:
        cle = (inc.troncon_id, inc.type_incident)
        candidats = vu.get(cle, [])
        mots_inc = _mots_significatifs(inc.titre)
        est_doublon = False

        for ref in candidats:
            # Critère 2 : fenêtre ±2h
            pub_ref = ref.horodatage_publication.replace(tzinfo=timezone.utc) \
                if ref.horodatage_publication.tzinfo is None \
                else ref.horodatage_publication
            pub_inc = inc.horodatage_publication.replace(tzinfo=timezone.utc) \
                if inc.horodatage_publication.tzinfo is None \
                else inc.horodatage_publication
            if abs((pub_inc - pub_ref).total_seconds()) > 7_200:
                continue

            # Critère 3 : ≥ 3 mots communs
            mots_ref = _mots_significatifs(ref.titre)
            if len(mots_inc & mots_ref) >= 3:
                est_doublon = True
                break

        if est_doublon:
            inc.titre = f"[DOUBLON] {inc.titre}"
            inc.type_incident = "autre"
            nb_doublons += 1
        else:
            candidats.append(inc)
            vu[cle] = candidats

    if nb_doublons:
        db.commit()

    return nb_doublons
