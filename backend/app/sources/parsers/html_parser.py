"""Scraper HTML pour les sites d'actualité sans flux RSS (Technique 2 + 3).

Techniques implémentées :
  Technique 2 — Reverse API interne : cherche les données JSON embarquées dans
    les balises <script> (window.__INITIAL_DATA__, application/json, etc.).
    Avantage : données structurées, insensible aux changements de CSS.

  Technique 3 — Parsing HTML statique BeautifulSoup4 :
    Extraction via balises sémantiques (article, h2, h3, time, p…).
    Repli si Technique 2 ne trouve rien.

Technique 4 — Navigateur headless Playwright : NON ACTIVÉE par défaut.
  Requiert ~400 Mo de dépendances (Chromium + Playwright).
  Voir le bloc commentaire en fin de fichier pour activer.

Sources HTML configurées :
  - news.abidjan.net/trafic/   — trafic temps réel Abidjan.net
  - www.soir-info.ci/          — Soir Info Côte d'Ivoire
  - www.linfodrome.ci/vie-pratique/  — L'Infodrome

Pour ajouter une source HTML via l'interface Administration :
  POST /incidents/sources  {"nom": "...", "url": "...", "type": "html"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.models import Incident
from app.sources.parsers.rss_parser import (
    _CACHE_TTL,
    _DELAI_INTER_REQUETE,
    _FIABILITE_SOURCE,
    _USER_AGENT,
    _cache_derniere_collecte,
    _contient_mot_cle,
    _nettoyer_html,
)


logger = logging.getLogger("paa.incidents.html")

# ---------------------------------------------------------------------------
# Sources HTML statiques (repli si table sources_incidents vide)
# ---------------------------------------------------------------------------

SOURCES_HTML: list[dict] = [
    {
        "url": "https://news.abidjan.net/trafic/",
        "nom": "abidjan_net_trafic",
        "fiabilite": 0.80,
        "strategies": ["abidjan_net"],
    },
    {
        "url": "https://www.soir-info.ci/",
        "nom": "soir_info",
        "fiabilite": 0.70,
        "strategies": ["generic"],
    },
    {
        "url": "https://www.linfodrome.ci/vie-pratique/",
        "nom": "linfodrome",
        "fiabilite": 0.70,
        "strategies": ["generic"],
    },
]


# ---------------------------------------------------------------------------
# Technique 2 — Reverse API : détection de JSON embarqué dans <script>
# ---------------------------------------------------------------------------


def _detecter_json_embed(html: str) -> list[dict]:
    """Cherche des données JSON dans les balises <script> de la page.

    Certains CMS modernes (React, Vue, Next.js) embarquent un objet JSON
    dans le DOM pour initialiser l'état côté client.
    Exemples : window.__INITIAL_DATA__, <script type="application/json">,
               window.initialState, __NEXT_DATA__.

    Retourne une liste d'articles extraits, vide si aucun JSON utile trouvé.
    """
    articles: list[dict] = []

    patterns = [
        # Next.js / Nuxt.js
        r'window\.__INITIAL(?:_DATA|_STATE|_PROPS)__\s*=\s*(\{.+?\});',
        r'window\.__PRELOADED_STATE__\s*=\s*(\{.+?\});',
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(\{.+?\})</script>',
        # CMS génériques
        r'<script[^>]+type=["\']application/json["\'][^>]*>(\{.+?\})</script>',
        r'window\.initialState\s*=\s*(\{.+?\});',
        r'window\.APP_STATE\s*=\s*(\{.+?\});',
        # Tableau JSON direct (liste d'articles)
        r'"articles"\s*:\s*(\[.+?\])',
        r'"posts"\s*:\s*(\[.+?\])',
        r'"items"\s*:\s*(\[.+?\])',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            continue
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue

        # Chercher une liste d'articles dans la structure
        candidates: list = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            for cle in ("articles", "items", "posts", "news", "results", "data"):
                val = data.get(cle)
                if isinstance(val, list) and val:
                    candidates = val
                    break
                # Un niveau de plus (ex. data.props.pageProps.articles)
                if isinstance(val, dict):
                    for sous_cle in ("articles", "items", "posts"):
                        sous_val = val.get(sous_cle)
                        if isinstance(sous_val, list) and sous_val:
                            candidates = sous_val
                            break

        for item in candidates[:30]:
            if not isinstance(item, dict):
                continue
            titre = str(item.get("title") or item.get("titre") or "").strip()
            resume = str(item.get("excerpt") or item.get("resume") or
                         item.get("description") or item.get("content") or "").strip()[:500]
            lien = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
            if titre and lien:
                articles.append({
                    "titre": titre[:300],
                    "resume": _nettoyer_html(resume),
                    "lien": lien,
                    "horodatage": datetime.now(tz=timezone.utc),
                })

        if articles:
            logger.info(
                "Technique 2 (Reverse API JSON embed) : %d articles détectés.", len(articles)
            )
            return articles

    return articles


# ---------------------------------------------------------------------------
# Technique 3 — Parsing HTML statique
# ---------------------------------------------------------------------------


def _normaliser_url(lien: str, url_base: str) -> str:
    """Convertit un lien relatif en URL absolue."""
    if not lien:
        return ""
    if lien.startswith("http"):
        return lien
    if lien.startswith("//"):
        return "https:" + lien
    return url_base.rstrip("/") + "/" + lien.lstrip("/")


def _extraire_horodatage(tag) -> datetime:
    """Extrait une date depuis un élément HTML (balise time ou span.date)."""
    time_el = tag.find("time")
    if time_el:
        for attr in ("datetime", "data-date"):
            val = time_el.get(attr, "")
            if val:
                try:
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                except Exception:
                    pass
        # Fallback : texte brut de la balise time
        try:
            return parsedate_to_datetime(time_el.get_text(strip=True))
        except Exception:
            pass
    # Cherche un span/div portant une classe date-like
    date_el = tag.find(["span", "div", "p"],
                        class_=re.compile(r"date|time|published|pubdate", re.I))
    if date_el:
        try:
            return parsedate_to_datetime(date_el.get_text(strip=True))
        except Exception:
            pass
    return datetime.now(tz=timezone.utc)


def _extraire_abidjan_net(soup: BeautifulSoup, url_base: str) -> list[dict]:
    """Extraction adaptée à la structure HTML d'Abidjan.net."""
    articles: list[dict] = []

    # Stratégie 1 : balises <article>
    for tag in soup.find_all("article", limit=30):
        titre_el = tag.find(["h1", "h2", "h3", "h4"])
        if not titre_el:
            continue
        titre = titre_el.get_text(strip=True)
        lien_el = titre_el.find("a") or tag.find("a")
        lien = _normaliser_url(lien_el.get("href", "") if lien_el else "", url_base)
        resume_el = tag.find("p")
        resume = _nettoyer_html(resume_el.get_text(strip=True)) if resume_el else ""
        horodatage = _extraire_horodatage(tag)
        if titre and lien:
            articles.append({"titre": titre, "resume": resume, "lien": lien,
                              "horodatage": horodatage})

    # Stratégie 2 : divs portant une classe news-item / article-item
    if not articles:
        for tag in soup.find_all(
            "div",
            class_=re.compile(r"news.?item|article.?item|actu|story|post", re.I),
            limit=30,
        ):
            titre_el = tag.find(["h2", "h3", "h4"])
            if not titre_el:
                continue
            titre = titre_el.get_text(strip=True)
            lien_el = tag.find("a")
            lien = _normaliser_url(lien_el.get("href", "") if lien_el else "", url_base)
            if titre and lien:
                articles.append({
                    "titre": titre, "resume": "",
                    "lien": lien, "horodatage": datetime.now(tz=timezone.utc),
                })

    # Stratégie 3 : liens portant un titre explicite (fallback large)
    if not articles:
        for a_tag in soup.find_all("a", href=True, limit=50):
            titre = a_tag.get_text(strip=True)
            if len(titre) < 20:
                continue
            lien = _normaliser_url(a_tag["href"], url_base)
            if "/articles/" in lien or "/news/" in lien or "/trafic" in lien:
                articles.append({
                    "titre": titre, "resume": "",
                    "lien": lien, "horodatage": datetime.now(tz=timezone.utc),
                })

    return articles


def _extraire_generique(soup: BeautifulSoup, url_base: str) -> list[dict]:
    """Extraction générique pour les sites d'actualité au CMS standard."""
    articles: list[dict] = []

    # Cherche les conteneurs d'articles (balises sémantiques prioritaires)
    for tag in soup.find_all(
        ["article", "div", "li"],
        class_=re.compile(r"article|post|news|actu|item|story|entry|card", re.I),
        limit=40,
    ):
        titre_el = tag.find(["h1", "h2", "h3", "h4"])
        if not titre_el:
            continue
        titre = titre_el.get_text(strip=True)
        if len(titre) < 15:
            continue
        lien_el = titre_el.find("a") or tag.find("a")
        lien = _normaliser_url(lien_el.get("href", "") if lien_el else "", url_base)
        resume_el = tag.find("p")
        resume = _nettoyer_html(resume_el.get_text(strip=True)) if resume_el else ""
        horodatage = _extraire_horodatage(tag)
        if titre and lien:
            articles.append({"titre": titre, "resume": resume, "lien": lien,
                              "horodatage": horodatage})

    return articles[:30]


# ---------------------------------------------------------------------------
# Scraper HTML principal
# ---------------------------------------------------------------------------


async def scraper_html_source(
    url: str,
    source_nom: str,
    db: Session,
    strategies: list[str] | None = None,
    fiabilite: float = 0.7,
) -> int:
    """Scrappe une page HTML d'actualités et insère les incidents détectés.

    Ordre d'essai :
      1. Technique 2 — JSON embed dans <script> (Reverse API)
      2. Technique 3 — Parsing HTML statique BeautifulSoup4

    Retourne le nombre de nouveaux incidents insérés.
    """
    derniere = _cache_derniere_collecte.get(source_nom, 0.0)
    if time.monotonic() - derniere < _CACHE_TTL:
        logger.debug("HTML %s : cache valide, ignorée.", source_nom)
        return 0

    strategies = strategies or ["generic"]
    url_base = "/".join(url.split("/")[:3])

    try:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9",
                "Cache-Control": "no-cache",
            },
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("HTML %s (%s) : erreur réseau — %s", source_nom, url, exc)
        return 0

    _cache_derniere_collecte[source_nom] = time.monotonic()
    await asyncio.sleep(_DELAI_INTER_REQUETE)

    # Technique 2 : Reverse API JSON embed
    articles = _detecter_json_embed(html)

    # Technique 3 : Parsing HTML statique
    if not articles:
        soup = BeautifulSoup(html, "lxml")
        if "abidjan_net" in strategies:
            articles = _extraire_abidjan_net(soup, url_base)
        if not articles:
            articles = _extraire_generique(soup, url_base)

    if not articles:
        logger.debug("HTML %s : aucun article extrait.", source_nom)
        return 0

    logger.info("HTML %s : %d articles candidats extraits.", source_nom, len(articles))

    nb_inseres = 0
    for art in articles:
        titre = art["titre"].strip()
        resume = art.get("resume", "").strip()
        lien = art.get("lien", "").strip()

        if not titre or not lien:
            continue

        # Double filtre TYPE + ZONE (même règle que le scraper RSS)
        if not _contient_mot_cle(titre, resume):
            continue

        stmt = (
            pg_insert(Incident)
            .values(
                titre=titre[:500],
                resume=resume or None,
                source_url=lien,
                source_nom=source_nom,
                horodatage_publication=art["horodatage"],
                fiabilite_source=fiabilite,
            )
            .on_conflict_do_nothing(constraint="uq_incidents_source_url")
        )
        result = db.execute(stmt)
        if result.rowcount:
            nb_inseres += 1

    if nb_inseres:
        db.commit()
        logger.info("HTML %s : %d nouvel(s) incident(s) inséré(s).", source_nom, nb_inseres)

    return nb_inseres


async def scraper_toutes_sources_html(db: Session) -> int:
    """Lance le scraping séquentiel de toutes les sources HTML actives.

    Lit en priorité les sources HTML configurées dans la table `sources_incidents`
    (type='html'). Repli sur SOURCES_HTML statiques si la table est vide.
    Appelé depuis le scheduler juste après scraper_toutes_sources() RSS.
    """
    total = 0
    sources: list[dict] = []

    try:
        from app.models.models import SourceIncident
        from sqlalchemy import select as _select

        lignes = db.execute(
            _select(SourceIncident).where(
                SourceIncident.actif.is_(True),
                SourceIncident.type == "html",
            )
        ).scalars().all()
        sources = [
            {
                "url": s.url,
                "nom": s.nom,
                "fiabilite": s.fiabilite,
                "strategies": ["generic"],
            }
            for s in lignes
        ]
    except Exception:
        logger.warning("Lecture des sources HTML depuis la DB impossible — repli statique.")

    if not sources:
        sources = SOURCES_HTML

    for src in sources:
        try:
            nb = await scraper_html_source(
                url=src["url"],
                source_nom=src["nom"],
                db=db,
                strategies=src.get("strategies"),
                fiabilite=src.get("fiabilite", 0.7),
            )
            total += nb
        except Exception:
            logger.exception("Erreur HTML scraper %s.", src["nom"])

    return total


# ---------------------------------------------------------------------------
# Technique 4 — Playwright navigateur headless (NON ACTIVÉE par défaut)
# ---------------------------------------------------------------------------
#
# Pour les sites avec protections anti-bot (Cloudflare JS Challenge, détection
# de bots, contenu chargé uniquement en JavaScript) :
#
# Prérequis (à ajouter dans requirements.txt) :
#   playwright>=1.44,<2.0
#
# Installation :
#   pip install playwright
#   playwright install chromium   # ~170 Mo pour le binaire Chromium
#
# Exemple d'implémentation (décommenter et adapter) :
#
# async def _scraper_playwright(url: str) -> tuple[str, list[dict]]:
#     """Retourne (html_page, api_responses_json) après exécution complète du JS.
#
#     Intercepte tous les appels XHR/fetch via page.on("response") pour
#     capturer les APIs internes JSON en temps réel — technique particulièrement
#     efficace sur les sites React/Vue/Angular qui chargent leurs données
#     depuis une API séparée pendant le rendu de la page.
#     """
#     from playwright.async_api import async_playwright
#     json_responses: list[dict] = []
#
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)
#         context = await browser.new_context(
#             user_agent=_USER_AGENT,
#             locale="fr-FR",
#         )
#         page = await context.new_page()
#
#         async def on_response(response):
#             if "application/json" in response.headers.get("content-type", ""):
#                 try:
#                     data = await response.json()
#                     json_responses.append({"url": response.url, "data": data})
#                 except Exception:
#                     pass
#
#         page.on("response", on_response)
#
#         await page.goto(url, wait_until="networkidle", timeout=30_000)
#         html = await page.content()
#         await browser.close()
#
#     # Chercher les articles dans les réponses JSON interceptées
#     articles = []
#     for resp in json_responses:
#         data = resp["data"]
#         candidates = (
#             data if isinstance(data, list)
#             else data.get("articles") or data.get("items") or []
#             if isinstance(data, dict) else []
#         )
#         for item in candidates:
#             titre = str(item.get("title") or item.get("titre") or "").strip()
#             lien = str(item.get("url") or item.get("link") or "").strip()
#             if titre and lien:
#                 articles.append({"titre": titre, "resume": "", "lien": lien,
#                                   "horodatage": datetime.now(tz=timezone.utc)})
#
#     return html, articles
