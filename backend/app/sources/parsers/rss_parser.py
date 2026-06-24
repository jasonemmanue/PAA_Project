"""Scraper RSS multi-source pour les incidents de circulation à Abidjan.

Interroge les flux RSS des principaux médias ivoiriens, filtre les articles
contenant au moins un mot-clé lié à la circulation dans la zone portuaire,
et insère les nouvelles entrées dans la table `incidents`.

Règles de courtoisie (CLAUDE.md § 10.1) :
  - User-Agent identifié PAA-Traverse
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
# Mots-clés de détection (titre + résumé)
# ---------------------------------------------------------------------------

MOTS_CLES_INCIDENTS: list[str] = [
    "accident", "collision", "accrochage", "carambolage",
    "embouteillage", "bouchon", "route barrée", "voie coupée",
    "camion renversé", "poids lourd", "convoi exceptionnel",
    "travaux", "Treichville", "Plateau", "Zone 4",
    "Port d'Abidjan", "CARENA", "Palm Beach", "pont HB",
    "Houphouët", "pont Félix", "Seamen",
]

# Regex compilée (insensible à la casse) pour perf
_RE_MOTS_CLES = re.compile(
    "|".join(re.escape(m) for m in MOTS_CLES_INCIDENTS),
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
    {
        "url": "https://koaci.com/rss.xml",
        "nom": "koaci",
    },
]

# Délai entre deux requêtes vers le même domaine (secondes)
_DELAI_INTER_REQUETE = 2.0

# Cache mémoire : {source_nom: timestamp_derniere_collecte}
_cache_derniere_collecte: dict[str, float] = {}

# Durée minimale entre deux collectes de la même source (secondes)
_CACHE_TTL = 20 * 60  # 20 minutes

_USER_AGENT = "PAA-Traverse/1.0 (hackathon; contact:sakamemmanuel@gmail.com)"

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
    """Retourne True si au moins un mot-clé de trafic est présent."""
    return bool(_RE_MOTS_CLES.search(titre + " " + resume))


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

        # Déduplication : INSERT … ON CONFLICT DO NOTHING (via SQLAlchemy core)
        stmt = (
            pg_insert(Incident)
            .values(
                titre=titre,
                resume=resume or None,
                source_url=lien,
                source_nom=source_nom,
                horodatage_publication=horodatage,
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
    """Lance le scraping séquentiel de toutes les sources RSS configurées.

    Séquentiel (pas concurrent) pour respecter le délai inter-requêtes et
    ne pas surcharger les serveurs des médias ivoiriens.

    Retourne le total d'incidents insérés pour ce cycle.
    """
    total = 0
    for source in SOURCES_RSS:
        try:
            nb = await scraper_rss_source(source["url"], source["nom"], db)
            total += nb
        except Exception:
            logger.exception(
                "Erreur inattendue lors du scraping de %s.", source["nom"]
            )
    return total
