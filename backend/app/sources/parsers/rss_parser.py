"""Scraper RSS multi-source pour les incidents de circulation à Abidjan.

Interroge les flux RSS des principaux médias ivoiriens, filtre les articles
contenant au moins un mot-clé lié à la circulation dans la zone portuaire,
et insère les nouvelles entrées dans la table `incidents`.

Règles de courtoisie (CLAUDE.md § 10.1) :
  - User-Agent identifié FLUIDIS
  - Délai 2 s entre appels vers le même domaine
  - Cache 25 min : on ne re-scrape pas si la dernière collecte est < 20 min
  - Aucune clé API requise
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import Incident


logger = logging.getLogger("paa.incidents.rss")

# ---------------------------------------------------------------------------
# Mots-clés de détection — double filtre (titre + résumé)
#
# Un article n'est retenu que s'il contient AU MOINS UN mot-clé de CHAQUE
# liste : un mot-clé TYPE (nature de l'incident) ET un mot-clé ZONE
# (localisation dans la zone portuaire d'Abidjan).
#
# Exemple d'article rejeté : « travaux à Yakassé-Feyassé » — le mot-clé
# TYPE «travaux» est présent mais aucun mot-clé ZONE ne correspond.
# ---------------------------------------------------------------------------

# Mots-clés décrivant la NATURE de l'incident — large pour la presse ivoirienne
# Inclut les termes génériques de trafic qui apparaissent souvent en introduction
MOTS_CLES_TYPE: list[str] = [
    # Incidents directs
    "accident", "collision", "accrochage", "carambolage", "dérapage",
    "renversement", "renversé", "capotage", "percuté", "heurté",
    # Victimes / urgence
    "blessé", "mort", "décès", "tué", "victime", "hospitalisé",
    "secours", "pompier", "ambulance", "urgence",
    # Trafic routier
    "embouteillage", "bouchon", "ralentissement", "circulation",
    "trafic", "route barrée", "voie coupée", "bloqué", "bloquée",
    "perturbation", "perturbé", "gêne", "déviation", "fermeture",
    "camion", "poids lourd", "convoi", "véhicule", "moto",
    "engin", "camionnette", "bus", "car",
    # Travaux / infrastructure
    "travaux", "chantier", "réfection", "réparation", "asphalte",
    "nid-de-poule", "effondrement", "affaissement",
    # Termes génériques de la presse CI
    "incident", "évènement", "événement", "fait divers",
    "opération", "intervention", "arrestation",
]

# Mots-clés de LOCALISATION — zone portuaire étendue
# (axes DEESP + Zone industrielle de Vridi + Port-Bouët)
MOTS_CLES_ZONE: list[str] = [
    # Axes surveillés DEESP
    "Treichville", "Plateau", "Zone 4",
    "Port d'Abidjan", "port autonome", "CARENA",
    "Palm Beach", "pont HB", "Houphouët",
    "pont Félix", "Seamen", "Boulevard de Marseille",
    "Avenue Christiani", "Grand Moulin", "Toyota CFAO",
    "SODECI", "Marcory", "Koumassi",
    # Zone industrielle de Vridi / Canal de Vridi / Port-Bouët
    "Vridi", "canal de Vridi", "zone industrielle de Vridi",
    "pont de Vridi", "Port-Bouët", "Gonzagueville",
    "terminal à conteneurs", "terminal portuaire",
    "accès au port", "entrée du port", "route de Vridi",
    "Petit-Bassam", "zone franche",
    # Communes / quartiers adjacents couvrant les axes DEESP
    "Abidjan", "Adjame", "Cocody", "Yopougon",
    "Abobo", "Attécoubé", "Grand-Bassam",
]

_RE_TYPE = re.compile(
    "|".join(re.escape(m) for m in MOTS_CLES_TYPE),
    re.IGNORECASE,
)
_RE_ZONE = re.compile(
    "|".join(re.escape(m) for m in MOTS_CLES_ZONE),
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Sources RSS configurées
# ---------------------------------------------------------------------------

SOURCES_RSS: list[dict[str, str]] = [
    {
        "url": "https://www.fraternitematin.ci/feed/",
        "nom": "fraternite_matin",
    },
    {
        "url": "https://news.abidjan.net/rss.php",
        "nom": "abidjan_net",
    },
    # AIP — Agence Ivoirienne de Presse (source officielle, stable)
    {
        "url": "https://www.aip.ci/feed/",
        "nom": "aip_ci",
    },
    # RFI Afrique — couvre les incidents majeurs à Abidjan
    {
        "url": "https://www.rfi.fr/fr/afrique/rss",
        "nom": "rfi_afrique",
    },
]

# Score de fiabilité par source (P8.5)
_FIABILITE_SOURCE: dict[str, float] = {
    "fraternite_matin": 0.9,
    "abidjan_net": 0.8,
    "aip_ci": 0.85,
    "rfi_afrique": 0.75,
    "koaci": 0.75,
    "linfodrome": 0.7,
    "soir_info": 0.7,
}

# Délai entre deux requêtes vers le même domaine (secondes)
_DELAI_INTER_REQUETE = 2.0

# Cache mémoire : {source_nom: timestamp_derniere_collecte}
_cache_derniere_collecte: dict[str, float] = {}

# Durée minimale entre deux collectes de la même source (secondes)
_CACHE_TTL = 20 * 60  # 20 minutes

_USER_AGENT = "FLUIDIS/1.0 (hackathon; contact:sakamemmanuel@gmail.com)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _nettoyer_html(texte: str | None) -> str:
    """Supprime les balises HTML d'un texte brut et normalise les espaces."""
    if not texte:
        return ""
    texte_propre = re.sub(r"<[^>]+>", " ", texte)
    texte_propre = re.sub(r"\s+", " ", texte_propre).strip()
    return texte_propre[:500]


def _extraire_date(entry: Any) -> datetime:
    """Retourne la date de publication d'une entrée feedparser en UTC.

    Essaie successivement `published`, `updated`, `created`. Si aucune
    n'est parsable, retourne l'heure courante UTC (trou de date non fatal).
    """
    for champ in ("published", "updated", "created"):
        valeur = getattr(entry, champ, None)
        if valeur:
            try:
                return parsedate_to_datetime(valeur).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(tz=timezone.utc)


def _contient_mot_cle(titre: str, resume: str) -> bool:
    """Retourne True si l'article appartient à la zone portuaire ET décrit un incident.

    Double filtre :
    - Au moins un mot-clé TYPE (accident, travaux, embouteillage…)
    - Au moins un mot-clé ZONE (Treichville, CARENA, pont HB…)
    Un article ne mentionnant que «travaux» sans localisation portuaire est rejeté.
    """
    texte = titre + " " + resume
    return bool(_RE_TYPE.search(texte)) and bool(_RE_ZONE.search(texte))


# ---------------------------------------------------------------------------
# Scraper principal
# ---------------------------------------------------------------------------


async def scraper_rss_source(
    url: str,
    source_nom: str,
    db: Session,
) -> int:
    """Scrappe un flux RSS et insère les incidents détectés dans la base.

    Retourne le nombre de nouvelles lignes insérées (0 si tout existait
    déjà ou si le flux est indisponible).
    """
    # Vérification du cache : ne pas re-scraper trop tôt
    derniere = _cache_derniere_collecte.get(source_nom, 0.0)
    if time.monotonic() - derniere < _CACHE_TTL:
        logger.debug("Source %s : cache valide, ignorée.", source_nom)
        return 0

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            contenu = response.text
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("RSS %s (%s) : erreur HTTP — %s", source_nom, url, exc)
        return 0

    # Mise à jour du cache immédiatement après le fetch réussi
    _cache_derniere_collecte[source_nom] = time.monotonic()

    # Pause de courtoisie entre sources du même domaine
    await asyncio.sleep(_DELAI_INTER_REQUETE)

    # Parsing feedparser (synchrone mais rapide — exécuté dans le thread courant)
    feed = feedparser.parse(contenu)

    if feed.bozo and not feed.entries:
        logger.warning("RSS %s : flux malformé ou vide.", source_nom)
        return 0

    nb_inseres = 0
    for entry in feed.entries:
        titre = _nettoyer_html(getattr(entry, "title", ""))
        resume = _nettoyer_html(getattr(entry, "summary", getattr(entry, "description", "")))
        lien = getattr(entry, "link", "")

        if not titre or not lien:
            continue

        # Filtre par mots-clés : écarte les articles hors périmètre portuaire
        if not _contient_mot_cle(titre, resume):
            continue

        horodatage = _extraire_date(entry)

        # Rejeter les articles de plus de 30 jours (Google News contient du contenu historique)
        age_jours = (datetime.now(tz=timezone.utc) - horodatage).total_seconds() / 86400
        if age_jours > 30:
            continue

        # Déduplication : INSERT … ON CONFLICT DO NOTHING (via SQLAlchemy core)
        stmt = (
            pg_insert(Incident)
            .values(
                titre=titre,
                resume=resume or None,
                source_url=lien,
                source_nom=source_nom,
                horodatage_publication=horodatage,
                fiabilite_source=_FIABILITE_SOURCE.get(source_nom, 0.5),
            )
            .on_conflict_do_nothing(constraint="uq_incidents_source_url")
        )
        result = db.execute(stmt)
        if result.rowcount:
            nb_inseres += 1

    if nb_inseres:
        db.commit()
        logger.info("RSS %s : %d nouvel(s) incident(s) inséré(s).", source_nom, nb_inseres)
    else:
        logger.debug("RSS %s : aucun nouvel incident.", source_nom)

    return nb_inseres


async def scraper_toutes_sources(db: Session) -> int:
    """Lance le scraping séquentiel de toutes les sources RSS actives.

    Depuis la migration 0014, les sources sont stockées dans la table
    `sources_incidents` et configurables via l'API `/incidents/sources`.
    Si la table est vide (ou inaccessible), un repli silencieux utilise la
    constante `SOURCES_RSS` historique pour garantir un fonctionnement
    nominal après déploiement.

    Séquentiel (pas concurrent) pour respecter le délai inter-requêtes et
    ne pas surcharger les serveurs des médias ivoiriens.

    Retourne le total d'incidents insérés pour ce cycle.
    """
    total = 0
    sources: list[tuple[str, str]] = []
    try:
        from app.models.models import SourceIncident
        from sqlalchemy import select as _select

        lignes = db.execute(
            _select(SourceIncident).where(
                SourceIncident.actif.is_(True),
                SourceIncident.type == "rss",
            )
        ).scalars().all()
        sources = [(s.url, s.nom) for s in lignes]
    except Exception:
        logger.warning(
            "Lecture des sources DB impossible — repli sur SOURCES_RSS statiques."
        )

    if not sources:
        sources = [(s["url"], s["nom"]) for s in SOURCES_RSS]

    for url, nom in sources:
        try:
            nb = await scraper_rss_source(url, nom, db)
            total += nb
        except Exception:
            logger.exception("Erreur inattendue lors du scraping de %s.", nom)
    return total
