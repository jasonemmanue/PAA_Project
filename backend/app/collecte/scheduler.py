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

⚠️  Plafond Google : 250 requêtes/jour. Une vérification du quota théorique
    est faite au démarrage et journalisée — l'opérateur doit ajuster
    COLLECT_INTERVAL_MINUTES / plage horaire si la limite est dépassée.
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
from sqlalchemy import func, select

from app.agregation.profils import executer_agregation
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.etat.carte import construire_etat_carte
from app.models.models import Mesure, SourceMesure, Troncon
from app.realtime.diffusion import get_diffuseur
from app.sources import google_routes
from app.sources.coordonnees import PointGPS


logger = logging.getLogger("paa.collecte")

# Identifiants uniques des jobs APScheduler — un seul de chaque type à la fois
_JOB_ID = "collecte_temps_reel"
_JOB_ID_AGREGATION = "agregation_profils_horaires"


# ---------------------------------------------------------------------------
# Modèle interne du résultat d'une tentative par source
# ---------------------------------------------------------------------------


@dataclass
class ResultatSource:
    """Issue d'un appel à une source pour un tronçon donné.

    `succes=False` ⇒ on enregistre un trou de mesure (durées NULL).
    """
    source: SourceMesure
    troncon_id: int
    succes: bool
    duree_trafic_s: int | None = None
    duree_sans_trafic_s: int | None = None
    distance_m: int | None = None
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
    """Interroge Google Routes pour un tronçon et renvoie un ResultatSource."""

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
        )

    return await _appel_avec_backoff(
        _operation,
        source=SourceMesure.google,
        troncon_id=troncon.id,
    )


# Map source → adaptateur. Ajouter ici toute nouvelle source temps réel.
# TomTom retiré (CLAUDE.md § 2.5) — la chaîne ne contient plus que Google.
_ADAPTATEURS_SOURCES: dict[SourceMesure, Callable[[Troncon], Awaitable[ResultatSource]]] = {
    SourceMesure.google: _collecter_google_pour_troncon,
}


# ---------------------------------------------------------------------------
# Persistance d'une mesure (succès ou trou)
# ---------------------------------------------------------------------------


def _persister_mesures(resultats: list[ResultatSource], horodatage_utc: datetime) -> None:
    """Insère en base une ligne `mesures` par résultat.

    - Succès : durées renseignées + vitesse moyenne calculée.
    - Échec  : ligne créée avec source connue et durées NULL → trou explicite.
    Les distances sont prises sur la réponse de la source si disponible,
    sinon sur `troncon.distance_m` (référence officielle) pour le calcul vitesse.
    """
    if not resultats:
        return

    session = SessionLocal()
    try:
        # On précharge les distances officielles pour le calcul de vitesse
        ids = list({r.troncon_id for r in resultats})
        distances_par_troncon = {
            t.id: t.distance_m
            for t in session.execute(
                select(Troncon).where(Troncon.id.in_(ids))
            ).scalars()
        }

        for resultat in resultats:
            if resultat.succes and resultat.duree_trafic_s and resultat.duree_trafic_s > 0:
                distance_m = resultat.distance_m or distances_par_troncon.get(
                    resultat.troncon_id
                )
                vitesse_kmh: float | None = None
                if distance_m is not None and resultat.duree_trafic_s > 0:
                    # vitesse = (m / s) × 3.6
                    vitesse_kmh = round(
                        (distance_m / resultat.duree_trafic_s) * 3.6, 2
                    )
                mesure = Mesure(
                    troncon_id=resultat.troncon_id,
                    horodatage=horodatage_utc,
                    duree_trafic_s=resultat.duree_trafic_s,
                    duree_sans_trafic_s=resultat.duree_sans_trafic_s,
                    source=resultat.source,
                    vitesse_moyenne_kmh=vitesse_kmh,
                )
            else:
                # Trou de mesure explicite : la ligne existe (preuve qu'on a tenté),
                # mais aucune valeur n'est inventée — durées et vitesse à NULL.
                mesure = Mesure(
                    troncon_id=resultat.troncon_id,
                    horodatage=horodatage_utc,
                    duree_trafic_s=None,
                    duree_sans_trafic_s=None,
                    source=resultat.source,
                    vitesse_moyenne_kmh=None,
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


async def cycle_de_collecte() -> dict[str, int]:
    """Un cycle complet : appels parallèles + persistance + journalisation.

    Retourne un résumé `{nb_succes, nb_trous, nb_troncons, nb_appels}` utile
    pour les endpoints de status et pour les tests manuels.
    """
    horodatage_utc = datetime.now(tz=timezone.utc)
    settings = get_settings()

    # 1. Chargement des tronçons actifs (avec coordonnées résolues)
    session = SessionLocal()
    try:
        troncons_actifs: list[Troncon] = list(
            session.execute(
                select(Troncon).where(
                    Troncon.actif.is_(True),
                    Troncon.lat_origine.is_not(None),
                    Troncon.lon_origine.is_not(None),
                    Troncon.lat_destination.is_not(None),
                    Troncon.lon_destination.is_not(None),
                )
            ).scalars()
        )
    finally:
        session.close()

    if not troncons_actifs:
        logger.warning("Cycle de collecte : aucun tronçon actif et résolu.")
        return {"nb_succes": 0, "nb_trous": 0, "nb_troncons": 0, "nb_appels": 0}

    # 2. Décision des sources interrogées
    sources_actives: list[SourceMesure] = []
    if settings.google_routes_api_key:
        sources_actives.append(SourceMesure.google)
    else:
        logger.error(
            "GOOGLE_ROUTES_API_KEY absente : aucune source temps réel disponible — "
            "trous de mesure pour ce cycle."
        )

    # 3. Construction et exécution des tâches en parallèle
    taches: list[Awaitable[ResultatSource]] = []
    for troncon in troncons_actifs:
        for src in sources_actives:
            adaptateur = _ADAPTATEURS_SOURCES[src]
            taches.append(adaptateur(troncon))

    # Si aucune source n'est dispo, on génère quand même des trous pour la traçabilité
    if not sources_actives:
        resultats: list[ResultatSource] = [
            ResultatSource(
                source=SourceMesure.google,
                troncon_id=t.id,
                succes=False,
                message_erreur="aucune source temps réel configurée",
            )
            for t in troncons_actifs
        ]
    else:
        resultats = list(await asyncio.gather(*taches, return_exceptions=False))

    # 4. Persistance (dans un thread pour ne pas bloquer la boucle)
    await asyncio.to_thread(_persister_mesures, resultats, horodatage_utc)

    nb_succes = sum(1 for r in resultats if r.succes)
    nb_trous = len(resultats) - nb_succes
    logger.info(
        "Cycle terminé à %s — %d tronçons, %d appels, %d réussites, %d trous.",
        horodatage_utc.isoformat(),
        len(troncons_actifs),
        len(resultats),
        nb_succes,
        nb_trous,
    )

    # 5. Push WebSocket : on diffuse le nouvel état carte à tous les abonnés.
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
        "nb_troncons": len(troncons_actifs),
        "nb_appels": len(resultats),
    }


# ---------------------------------------------------------------------------
# Garde-fou quota Google (≤ 250 req/jour)
# ---------------------------------------------------------------------------


# Plafond imposé par le cahier des charges (CLAUDE.md — contraintes)
QUOTA_GOOGLE_JOUR_MAX = 250


def estimer_requetes_par_jour(settings: Settings, nb_troncons_actifs: int) -> int:
    """Estime le nombre de requêtes Google par jour pour la config courante."""
    nb_heures_actives = max(0, settings.collect_end_hour - settings.collect_start_hour)
    if settings.collect_interval_minutes <= 0 or nb_heures_actives <= 0:
        return 0
    nb_cycles = (nb_heures_actives * 60) // settings.collect_interval_minutes
    return nb_cycles * nb_troncons_actifs


def _verifier_quota_au_demarrage() -> None:
    """Journalise un avertissement si la config dépasserait le quota Google."""
    settings = get_settings()
    session = SessionLocal()
    try:
        nb_actifs = session.scalar(
            select(func.count(Troncon.id)).where(Troncon.actif.is_(True))
        ) or 0
    finally:
        session.close()

    estimation = estimer_requetes_par_jour(settings, nb_actifs)
    logger.info(
        "Quota Google estimé : %d req/jour (cycles toutes les %d min, %dh→%dh, "
        "%d tronçons actifs).",
        estimation,
        settings.collect_interval_minutes,
        settings.collect_start_hour,
        settings.collect_end_hour,
        nb_actifs,
    )
    if estimation > QUOTA_GOOGLE_JOUR_MAX:
        logger.warning(
            "⚠️  Configuration au-dessus du plafond Google de %d req/jour "
            "(estimation : %d). Augmenter COLLECT_INTERVAL_MINUTES ou réduire la "
            "plage horaire pour rester sous la limite.",
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


def _construire_trigger(settings: Settings) -> CronTrigger:
    """Construit un CronTrigger restreint à la plage horaire active.

    Exemple : interval 15 min, plage 7h→19h, fuseau Africa/Abidjan
      → minute='*/15', hour='7-18' (19 exclu pour ne pas tirer à 19h00).
    """
    interval = max(1, settings.collect_interval_minutes)
    # `7-18` couvre 07:00..18:59 ; on n'inclut pas l'heure de fin pour éviter
    # un cycle juste après la fermeture de la fenêtre.
    plage_heures = f"{settings.collect_start_hour}-{max(settings.collect_start_hour, settings.collect_end_hour - 1)}"
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

    # Affichage spécial pour la collecte 24h/24 (start=0 et end=24).
    couvre_journee_complete = (
        settings.collect_start_hour == 0 and settings.collect_end_hour == 24
    )
    plage_horaire = (
        f"24h/24 ({settings.tz})"
        if couvre_journee_complete
        else f"{settings.collect_start_hour}h-{settings.collect_end_hour}h ({settings.tz})"
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
