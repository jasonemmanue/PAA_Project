"""Robot de collecte planifiée des mesures de temps de parcours (phase P2).

Le scheduler s'appuie sur APScheduler (AsyncIOScheduler, fuseau Africa/Abidjan)
et exécute un cycle toutes les `COLLECT_INTERVAL_MINUTES`, uniquement entre
`COLLECT_START_HOUR` et `COLLECT_END_HOUR`. À chaque cycle :

  1. Charge la liste des tronçons actifs (suppression logique respectée).
  2. Appelle Google Routes en parallèle pour chaque tronçon (httpx async),
     avec backoff exponentiel (3 essais) en cas d'échec transitoire.
  3. Insère une ligne dans `mesures` par (tronçon, source) :
     - succès → duree_trafic_s, duree_sans_trafic_s, vitesse_moyenne_kmh
     - échec  → ligne avec source = 'google' et toutes les durées NULL
       (trou de mesure explicite, conformément à CLAUDE.md § 5.3).
  4. Journalise le résumé du cycle (réussites / trous).

⚠️  TomTom a été retiré du projet faute de couverture cartographique à Abidjan
    (CLAUDE.md § 2.5). Seule Google reste interrogée à ce stade. Lorsqu'une
    seconde source temps réel sera intégrée, il suffira d'ajouter sa coroutine
    à la liste `_taches_par_troncon`.

⚠️  Plafond Google : 200 requêtes/jour. Une requête par axe (étapes
    intermédiaires = bornes des tronçons, cf. `plan_axes.py`). La plage
    horaire de collecte est réglable depuis l'interface (`plage.py`) ;
    hors de cette plage, aucune requête n'est émise.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.agregation.profils import executer_agregation
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.etat.carte import construire_etat_carte
from app.models.models import Mesure, SourceMesure, SousTroncon, Troncon
from app.collecte.plage import PlageCollecte, lire_plage_collecte
from app.collecte.plan_axes import (
    PlanAxe,
    appels_google_par_cycle,
    construire_plan_collecte,
)
from app.realtime.diffusion import get_diffuseur
from app.sources import google_routes
from app.sources.coordonnees import PointGPS
from app.analyse.incidents_nlp import enrichir_incidents
from app.sources.parsers.rss_parser import scraper_toutes_sources
from app.sources.parsers.html_parser import scraper_toutes_sources_html


logger = logging.getLogger("paa.collecte")

# Identifiants uniques des jobs APScheduler — un seul de chaque type à la fois
_JOB_ID = "collecte_temps_reel"
_JOB_ID_AGREGATION = "agregation_profils_horaires"
_JOB_ID_INCIDENTS = "collecte_incidents"
_JOB_ID_RETENTION = "retention_mesures"


# ---------------------------------------------------------------------------
# Modèle interne du résultat d'une tentative par source
# ---------------------------------------------------------------------------


@dataclass
class ResultatSource:
    """Issue d'un appel à une source pour un tronçon (ou sous-tronçon).

    `succes=False` ⇒ on enregistre un trou de mesure (durées + couleurs NULL).

    Les pourcentages couleur (rouge/orange/vert) viennent du critère DEESP
    (cf. CLAUDE.md § 4.5.2) et restent NULL si Google n'a pas qualifié le
    tracé via `speedReadingIntervals`.

    `sous_troncon_id` est renseigné quand la mesure porte sur une portion
    fine (codification DEESP T1A, T1B…). `troncon_id` est TOUJOURS celui
    du parent — par cohérence d'historique.
    """
    source: SourceMesure
    troncon_id: int
    succes: bool
    sous_troncon_id: int | None = None
    duree_trafic_s: int | None = None
    duree_sans_trafic_s: int | None = None
    distance_m: int | None = None
    pourcentage_rouge: float | None = None
    pourcentage_orange: float | None = None
    pourcentage_vert: float | None = None
    est_congestionne: bool | None = None
    message_erreur: str | None = None


# ---------------------------------------------------------------------------
# Appel d'une source avec backoff exponentiel
# ---------------------------------------------------------------------------


async def _appel_avec_backoff(
    operation: Callable[[], Awaitable[ResultatSource]],
    *,
    source: SourceMesure,
    troncon_id: int,
    nb_essais_max: int = 3,
    delai_initial_s: float = 1.0,
) -> ResultatSource:
    """Exécute `operation` jusqu'à `nb_essais_max` fois avec backoff exponentiel.

    Délais successifs : 1 s, 2 s, 4 s. Retourne un `ResultatSource(succes=False)`
    si tous les essais échouent — l'appelant doit alors enregistrer un trou.
    """
    derniere_erreur: str = ""
    for tentative in range(1, nb_essais_max + 1):
        try:
            return await operation()
        except (httpx.HTTPError, RuntimeError, asyncio.TimeoutError) as exc:
            derniere_erreur = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Source %s tronçon %d : tentative %d/%d échouée (%s)",
                source.value, troncon_id, tentative, nb_essais_max, derniere_erreur,
            )
            if tentative < nb_essais_max:
                await asyncio.sleep(delai_initial_s * (2 ** (tentative - 1)))

    return ResultatSource(
        source=source,
        troncon_id=troncon_id,
        succes=False,
        message_erreur=derniere_erreur or "échec inconnu",
    )


# ---------------------------------------------------------------------------
# Adaptateurs : un par source temps réel
# ---------------------------------------------------------------------------


async def _collecter_google_pour_troncon(troncon: Troncon) -> ResultatSource:
    """Interroge Google Routes pour un tronçon parent (axe complet)."""

    async def _operation() -> ResultatSource:
        origine = PointGPS(lat=troncon.lat_origine, lon=troncon.lon_origine)
        destination = PointGPS(
            lat=troncon.lat_destination, lon=troncon.lon_destination
        )
        reponse = await google_routes.calcul_itineraire(origine, destination)
        return ResultatSource(
            source=SourceMesure.google,
            troncon_id=troncon.id,
            succes=True,
            duree_trafic_s=reponse.duree_trafic_s,
            duree_sans_trafic_s=reponse.duree_sans_trafic_s,
            distance_m=reponse.distance_m,
            pourcentage_rouge=reponse.pourcentage_rouge,
            pourcentage_orange=reponse.pourcentage_orange,
            pourcentage_vert=reponse.pourcentage_vert,
            est_congestionne=reponse.est_congestionne,
        )

    return await _appel_avec_backoff(
        _operation,
        source=SourceMesure.google,
        troncon_id=troncon.id,
    )


# ---------------------------------------------------------------------------
# Persistance d'une mesure (succès ou trou)
# ---------------------------------------------------------------------------


def _persister_mesures(resultats: list[ResultatSource], horodatage_utc: datetime) -> None:
    """Insère en base une ligne `mesures` par résultat.

    - Succès : durées renseignées + vitesse moyenne calculée.
    - Échec  : ligne créée avec source connue et durées NULL → trou explicite.
    - Si `sous_troncon_id` est posé : la distance officielle vient du
      `SousTroncon.distance_m` (portion fine), pas du parent.
    """
    if not resultats:
        return

    session = SessionLocal()
    try:
        # Préchargement des distances officielles (parents ET sous-tronçons)
        ids_troncons = list({r.troncon_id for r in resultats if r.sous_troncon_id is None})
        ids_sous = list({r.sous_troncon_id for r in resultats if r.sous_troncon_id is not None})

        distances_par_troncon = {
            t.id: t.distance_m
            for t in session.execute(
                select(Troncon).where(Troncon.id.in_(ids_troncons))
            ).scalars()
        } if ids_troncons else {}
        distances_par_sous = {
            s.id: s.distance_m
            for s in session.execute(
                select(SousTroncon).where(SousTroncon.id.in_(ids_sous))
            ).scalars()
        } if ids_sous else {}

        for resultat in resultats:
            # Distance de référence pour le calcul vitesse — priorité au
            # niveau le plus fin (sous-tronçon si présent).
            if resultat.sous_troncon_id is not None:
                distance_officielle = distances_par_sous.get(resultat.sous_troncon_id)
            else:
                distance_officielle = distances_par_troncon.get(resultat.troncon_id)

            if resultat.succes and resultat.duree_trafic_s and resultat.duree_trafic_s > 0:
                distance_m = resultat.distance_m or distance_officielle
                vitesse_kmh: float | None = None
                if distance_m is not None and resultat.duree_trafic_s > 0:
                    vitesse_kmh = round(
                        (distance_m / resultat.duree_trafic_s) * 3.6, 2
                    )
                mesure = Mesure(
                    troncon_id=resultat.troncon_id,
                    sous_troncon_id=resultat.sous_troncon_id,
                    horodatage=horodatage_utc,
                    duree_trafic_s=resultat.duree_trafic_s,
                    duree_sans_trafic_s=resultat.duree_sans_trafic_s,
                    source=resultat.source,
                    vitesse_moyenne_kmh=vitesse_kmh,
                    pourcentage_rouge=resultat.pourcentage_rouge,
                    pourcentage_orange=resultat.pourcentage_orange,
                    pourcentage_vert=resultat.pourcentage_vert,
                    est_congestionne=resultat.est_congestionne,
                )
            else:
                # Trou de mesure explicite — durées et couleurs NULL.
                mesure = Mesure(
                    troncon_id=resultat.troncon_id,
                    sous_troncon_id=resultat.sous_troncon_id,
                    horodatage=horodatage_utc,
                    duree_trafic_s=None,
                    duree_sans_trafic_s=None,
                    source=resultat.source,
                    vitesse_moyenne_kmh=None,
                    pourcentage_rouge=None,
                    pourcentage_orange=None,
                    pourcentage_vert=None,
                    est_congestionne=None,
                )
            session.add(mesure)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Cycle de collecte (cœur du job APScheduler)
# ---------------------------------------------------------------------------


async def _collecter_google_pour_axe(plan: PlanAxe) -> list[ResultatSource]:
    """Mesure tous les tronçons codifiés d'un axe avec une requête par chaîne.

    Un échec (après les 3 tentatives) produit un trou de mesure pour chaque
    tronçon de la chaîne concernée — aucune valeur n'est inventée (§ 5.3).
    """
    resultats: list[ResultatSource] = []
    for appel in plan.appels:
        derniere_erreur = ""
        mesures: list[ResultatSource] | None = None
        for tentative in range(1, 4):
            try:
                reponses = await google_routes.calcul_itineraire_multi(appel.points)
                mesures = [
                    ResultatSource(
                        source=SourceMesure.google,
                        troncon_id=plan.axe_id,
                        sous_troncon_id=sous_id,
                        succes=True,
                        duree_trafic_s=reponse.duree_trafic_s,
                        duree_sans_trafic_s=reponse.duree_sans_trafic_s,
                        distance_m=reponse.distance_m,
                        pourcentage_rouge=reponse.pourcentage_rouge,
                        pourcentage_orange=reponse.pourcentage_orange,
                        pourcentage_vert=reponse.pourcentage_vert,
                        est_congestionne=reponse.est_congestionne,
                    )
                    for sous_id, reponse in zip(appel.legs, reponses)
                    if sous_id is not None  # None = raccord entre tronçons disjoints
                ]
                break
            except (httpx.HTTPError, RuntimeError, ValueError, asyncio.TimeoutError) as exc:
                derniere_erreur = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Source google axe %d : tentative %d/3 échouée (%s)",
                    plan.axe_id, tentative, derniere_erreur,
                )
                if tentative < 3:
                    await asyncio.sleep(2 ** (tentative - 1))

        if mesures is None:
            mesures = [
                ResultatSource(
                    source=SourceMesure.google, troncon_id=plan.axe_id,
                    sous_troncon_id=sous_id, succes=False,
                    message_erreur=derniere_erreur or "échec inconnu",
                )
                for sous_id in appel.legs if sous_id is not None
            ]
        resultats.extend(mesures)
    return resultats


async def cycle_de_collecte() -> dict[str, int]:
    """Un cycle complet : appels parallèles + persistance + journalisation.

    Règle DEESP : si un axe a au moins un tronçon codifié actif, on mesure
    **uniquement** ses tronçons (granularité fine). Depuis le 2026-10-04,
    tous les tronçons d'un axe sont mesurés par une seule requête Google à
    étapes (`plan_axes.py`, CLAUDE.md § 39). Un axe sans tronçon est mesuré
    d'un bout à l'autre comme avant.

    Garde-fou : hors de la plage de collecte, le cycle ne fait rien.
    """
    horodatage_utc = datetime.now(tz=timezone.utc)
    settings = get_settings()
    resume_vide = {
        "nb_succes": 0, "nb_trous": 0, "nb_troncons": 0, "nb_sous_troncons": 0,
        "nb_appels_google_reels": 0, "nb_resultats_persistes": 0,
    }

    plage = lire_plage_collecte()
    heure_locale = horodatage_utc.astimezone(ZoneInfo(settings.tz)).hour
    if not plage.contient(heure_locale):
        logger.info(
            "Cycle ignoré : %dh hors de la plage de collecte %s.", heure_locale, plage.libelle,
        )
        return resume_vide

    # 1. Plan du cycle (axes sans tronçon + chaînes par axe)
    session = SessionLocal()
    try:
        plan = construire_plan_collecte(session)
    finally:
        session.close()

    if not plan.axes_sans_troncon and not plan.plans_axes:
        logger.warning("Cycle de collecte : aucun axe actif.")
        return resume_vide

    nb_couples = sum(len(p.sous_troncon_ids) for p in plan.plans_axes)

    # 2. Appels Google (ou trous explicites si la clé est absente)
    resultats: list[ResultatSource] = []
    if not settings.google_routes_api_key:
        logger.error(
            "GOOGLE_ROUTES_API_KEY absente : aucune source temps réel disponible — "
            "trous de mesure pour ce cycle."
        )
        for axe in plan.axes_sans_troncon:
            resultats.append(ResultatSource(
                source=SourceMesure.google, troncon_id=axe.id, succes=False,
                message_erreur="aucune source temps réel configurée",
            ))
        for plan_axe in plan.plans_axes:
            for sous_id in plan_axe.sous_troncon_ids:
                resultats.append(ResultatSource(
                    source=SourceMesure.google, troncon_id=plan_axe.axe_id,
                    sous_troncon_id=sous_id, succes=False,
                    message_erreur="aucune source temps réel configurée",
                ))
        nb_appels_google = 0
    else:
        taches_axes = [_collecter_google_pour_troncon(axe) for axe in plan.axes_sans_troncon]
        taches_chaines = [_collecter_google_pour_axe(p) for p in plan.plans_axes]
        resultats.extend(await asyncio.gather(*taches_axes))
        for lot in await asyncio.gather(*taches_chaines):
            resultats.extend(lot)
        nb_appels_google = plan.nb_appels

    # 3. Persistance (dans un thread pour ne pas bloquer la boucle)
    await asyncio.to_thread(_persister_mesures, resultats, horodatage_utc)

    nb_succes = sum(1 for r in resultats if r.succes)
    nb_trous = len(resultats) - nb_succes
    logger.info(
        "Cycle terminé à %s — %d axe(s) entiers + %d couple(s) axe/tronçon "
        "(%d appels Google, %d résultats persistés, %d réussites, %d trous).",
        horodatage_utc.isoformat(),
        len(plan.axes_sans_troncon),
        nb_couples,
        nb_appels_google,
        len(resultats),
        nb_succes,
        nb_trous,
    )

    # 4. Push WebSocket : on diffuse le nouvel état carte à tous les abonnés.
    #    Une erreur de diffusion ne doit JAMAIS faire échouer le cycle de collecte.
    try:
        diffuseur = get_diffuseur()
        if diffuseur.nb_abonnes > 0:
            etat = await asyncio.to_thread(construire_etat_carte)
            nb_envoyes = await diffuseur.diffuser({"type": "maj", "donnees": etat})
            logger.info("WS — état diffusé à %d abonné(s).", nb_envoyes)
    except Exception:
        logger.exception("Échec de la diffusion WebSocket post-cycle.")

    return {
        "nb_succes": nb_succes,
        "nb_trous": nb_trous,
        "nb_troncons": len(plan.axes_sans_troncon),
        "nb_sous_troncons": nb_couples,
        "nb_appels_google_reels": nb_appels_google,
        "nb_resultats_persistes": len(resultats),
    }


# ---------------------------------------------------------------------------
# Garde-fou quota Google (≤ 200 req/jour)
# ---------------------------------------------------------------------------


# Plafond quotidien visé : rester dans le volume gratuit Google (CLAUDE.md § 39)
QUOTA_GOOGLE_JOUR_MAX = 200


def estimer_requetes_par_jour(
    settings: Settings, nb_appels_par_cycle: int, plage: PlageCollecte | None = None,
) -> int:
    """Estime le nombre de requêtes Google par jour.

    `nb_appels_par_cycle` vient de `plan_axes.appels_google_par_cycle` — une
    requête par axe (étapes intermédiaires) + une par axe sans tronçon.
    """
    plage = plage or lire_plage_collecte()
    if settings.collect_interval_minutes <= 0 or plage.nb_heures <= 0:
        return 0
    nb_cycles = (plage.nb_heures * 60) // settings.collect_interval_minutes
    return nb_cycles * nb_appels_par_cycle


def _verifier_quota_au_demarrage() -> None:
    """Journalise un avertissement si la config dépasserait le quota Google."""
    settings = get_settings()
    session = SessionLocal()
    try:
        nb_appels = appels_google_par_cycle(session)
        plage = lire_plage_collecte(session)
    finally:
        session.close()

    estimation = estimer_requetes_par_jour(settings, nb_appels, plage)
    logger.info(
        "Quota Google estimé : %d req/jour (%d appel(s)/cycle, toutes les %d min, %s).",
        estimation, nb_appels, settings.collect_interval_minutes, plage.libelle,
    )
    if estimation > QUOTA_GOOGLE_JOUR_MAX:
        logger.warning(
            "⚠️  Configuration au-dessus du plafond Google de %d req/jour "
            "(estimation : %d). Réduire la plage de collecte ou augmenter "
            "COLLECT_INTERVAL_MINUTES.",
            QUOTA_GOOGLE_JOUR_MAX,
            estimation,
        )


# ---------------------------------------------------------------------------
# Singleton du scheduler — exposé pour les endpoints /collecte/*
# ---------------------------------------------------------------------------


_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Retourne (et instancie au besoin) l'AsyncIOScheduler unique du process."""
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.tz))
    return _scheduler


def _construire_trigger(settings: Settings, plage: PlageCollecte | None = None) -> CronTrigger:
    """Construit un CronTrigger restreint à la plage horaire active.

    Exemples :
      - interval 15 min, plage 7h→19h → minute='*/15', hour='7-18'
      - interval 60 min, plage 0h→24h → **minute=0, hour='0-23'**
        (APScheduler refuse `*/60` car le champ minute va de 0 à 59 —
         step > range : `ValueError`. Sémantiquement équivalent à "1 cycle
         par heure pleine".)
    """
    interval = max(1, settings.collect_interval_minutes)
    plage = plage or lire_plage_collecte()
    # `7-18` couvre 07:00..18:59 ; on n'inclut pas l'heure de fin pour éviter
    # un cycle juste après la fermeture de la fenêtre.
    plage_heures = f"{plage.heure_debut}-{max(plage.heure_debut, plage.heure_fin - 1)}"

    if interval >= 60:
        # 1 cycle / heure (ou plus rare) — tir à la minute 0 de chaque heure
        # active. APScheduler refuse `*/N` pour N ≥ 60 sur le champ minute.
        return CronTrigger(
            minute=0,
            hour=plage_heures,
            timezone=ZoneInfo(settings.tz),
        )

    return CronTrigger(
        minute=f"*/{interval}",
        hour=plage_heures,
        timezone=ZoneInfo(settings.tz),
    )


def _ajouter_job_agregation_nocturne(scheduler: AsyncIOScheduler, settings: Settings) -> None:
    """Planifie l'agrégation des profils horaires chaque nuit à 23h00 locale.

    Job idempotent (replace_existing=True) — sûr d'appeler plusieurs fois.
    L'exécution réelle est délocalisée dans un thread car
    `executer_agregation` est synchrone (SQLAlchemy sync + statistics).
    """
    async def _tache():
        await asyncio.to_thread(executer_agregation)

    scheduler.add_job(
        _tache,
        trigger=CronTrigger(hour=23, minute=0, timezone=ZoneInfo(settings.tz)),
        id=_JOB_ID_AGREGATION,
        name="Agrégation nocturne des profils horaires",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,  # 1h de grâce — le job nocturne n'est pas critique à la minute
        replace_existing=True,
    )


def _ajouter_job_incidents(scheduler: AsyncIOScheduler, settings: Settings) -> None:
    """Planifie la collecte des incidents toutes les 30 min, 24h/24.

    Séparé du cycle de collecte Google pour ne pas alourdir ce dernier et
    pouvoir ajuster la fréquence indépendamment du quota Google.
    Jamais levé d'exception si le scraping échoue — log + continue.
    """
    async def _tache():
        session = SessionLocal()
        try:
            # Technique 1 — RSS (feedparser)
            nb_rss = await scraper_toutes_sources(session)
            logger.info("Collecte incidents RSS : %d nouvel(s) incident(s).", nb_rss)
            # Technique 2+3 — JSON embed + BeautifulSoup HTML
            nb_html = await scraper_toutes_sources_html(session)
            logger.info("Collecte incidents HTML : %d nouvel(s) incident(s).", nb_html)
            # Enrichissement NLP : extraction lieu, classification type/sévérité, géocodage.
            nb_enrichis = await enrichir_incidents(session)
            logger.info("Enrichissement incidents : %d incident(s) traité(s).", nb_enrichis)
        except Exception:
            logger.exception("Erreur inattendue dans le job collecte_incidents.")
        finally:
            session.close()

    scheduler.add_job(
        _tache,
        trigger=CronTrigger(
            minute="*/30",
            timezone=ZoneInfo(settings.tz),
        ),
        id=_JOB_ID_INCIDENTS,
        name="Collecte incidents presse (RSS)",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=600,
        replace_existing=True,
    )


def _ajouter_job_retention(scheduler: AsyncIOScheduler, settings: Settings) -> None:
    """Purge les mesures plus anciennes que RETENTION_MESURES_JOURS (défaut 365 j).

    Tourne chaque nuit à 23h30 (après l'agrégation de 23h00).
    """
    async def _tache():
        from datetime import datetime, timedelta, timezone
        session = SessionLocal()
        try:
            seuil = datetime.now(tz=timezone.utc) - timedelta(
                days=settings.retention_mesures_jours,
            )
            result = session.execute(
                Mesure.__table__.delete().where(Mesure.horodatage < seuil)
            )
            nb = result.rowcount
            session.commit()
            if nb:
                logger.info(
                    "Rétention : %d mesure(s) antérieure(s) à %s supprimée(s).",
                    nb, seuil.date().isoformat(),
                )
        except Exception:
            session.rollback()
            logger.exception("Erreur dans le job de rétention des mesures.")
        finally:
            session.close()

    scheduler.add_job(
        _tache,
        trigger=CronTrigger(hour=23, minute=30, timezone=ZoneInfo(settings.tz)),
        id=_JOB_ID_RETENTION,
        name="Purge des mesures anciennes",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
        replace_existing=True,
    )


def demarrer_scheduler() -> dict[str, str | int | None]:
    """Démarre le scheduler s'il ne tourne pas déjà.

    Retourne un état lisible utilisable par l'endpoint /collecte/start.
    """
    scheduler = get_scheduler()
    settings = get_settings()

    _verifier_quota_au_demarrage()

    if not scheduler.running:
        scheduler.start()

    job = scheduler.get_job(_JOB_ID)
    if job is None:
        scheduler.add_job(
            cycle_de_collecte,
            trigger=_construire_trigger(settings),
            id=_JOB_ID,
            name="Collecte temps réel des tronçons PAA",
            coalesce=True,           # un seul tir si on a accumulé du retard
            max_instances=1,         # jamais deux cycles en parallèle
            misfire_grace_time=120,  # tolérance de 2 min sur un cycle raté
            replace_existing=True,
        )
        job = scheduler.get_job(_JOB_ID)

    # Job d'agrégation nocturne — toujours réinstallé au démarrage
    _ajouter_job_agregation_nocturne(scheduler, settings)
    job_agregation = scheduler.get_job(_JOB_ID_AGREGATION)

    # Job de collecte incidents (scraping RSS toutes les 30 min)
    _ajouter_job_incidents(scheduler, settings)

    # Job de rétention — purge des mesures anciennes (23h30)
    _ajouter_job_retention(scheduler, settings)

    plage = lire_plage_collecte()
    plage_horaire = (
        f"24h/24 ({settings.tz})" if plage.est_24h
        else f"{plage.libelle} ({settings.tz})"
    )

    return {
        "etat": "demarre",
        "prochaine_execution": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "prochaine_agregation": (
            job_agregation.next_run_time.isoformat()
            if job_agregation and job_agregation.next_run_time
            else None
        ),
        "intervalle_min": settings.collect_interval_minutes,
        "plage_horaire": plage_horaire,
    }


def arreter_scheduler() -> dict[str, str]:
    """Retire le job et stoppe le scheduler s'il tourne."""
    scheduler = get_scheduler()
    if scheduler.get_job(_JOB_ID) is not None:
        scheduler.remove_job(_JOB_ID)
    if scheduler.running:
        scheduler.shutdown(wait=False)
    # Force un nouvel instancement au prochain démarrage
    global _scheduler
    _scheduler = None
    return {"etat": "arrete"}


def appliquer_plage_collecte(plage: PlageCollecte) -> str | None:
    """Replanifie le cycle de collecte sur une nouvelle plage, sans redémarrage.

    Retourne la date ISO du prochain cycle (None si le scheduler est arrêté).
    """
    scheduler = get_scheduler()
    if scheduler.get_job(_JOB_ID) is None:
        return None
    scheduler.reschedule_job(_JOB_ID, trigger=_construire_trigger(get_settings(), plage))
    job = scheduler.get_job(_JOB_ID)
    logger.info("Plage de collecte appliquée : %s.", plage.libelle)
    return job.next_run_time.isoformat() if job and job.next_run_time else None


def etat_scheduler() -> dict[str, object]:
    """Retourne l'état courant du scheduler pour /collecte/status."""
    scheduler = get_scheduler()
    job = scheduler.get_job(_JOB_ID)
    job_agregation = scheduler.get_job(_JOB_ID_AGREGATION)
    return {
        "actif": scheduler.running and job is not None,
        "prochaine_execution": (
            job.next_run_time.isoformat() if job and job.next_run_time else None
        ),
        "prochaine_agregation": (
            job_agregation.next_run_time.isoformat()
            if job_agregation and job_agregation.next_run_time
            else None
        ),
    }
