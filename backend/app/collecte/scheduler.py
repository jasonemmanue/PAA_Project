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
from app.models.models import Mesure, SourceMesure, SousTroncon, Troncon
from app.realtime.diffusion import get_diffuseur
from app.sources import google_routes
from app.sources.coordonnees import PointGPS
from app.sources.parsers.rss_parser import scraper_toutes_sources


logger = logging.getLogger("paa.collecte")

# Identifiants uniques des jobs APScheduler — un seul de chaque type à la fois
_JOB_ID = "collecte_temps_reel"
_JOB_ID_AGREGATION = "agregation_profils_horaires"
_JOB_ID_INCIDENTS = "collecte_incidents"


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


async def _collecter_google_pour_sous_troncon(
    sous_troncon: SousTroncon,
) -> ResultatSource:
    """Interroge Google Routes pour un sous-tronçon (portion fine T1A, T1B…).

    Le `troncon_id` retourné est celui du parent — par cohérence d'historique
    et pour faciliter l'agrégation au niveau axe.
    """

    async def _operation() -> ResultatSource:
        origine = PointGPS(lat=sous_troncon.lat_debut, lon=sous_troncon.lon_debut)
        destination = PointGPS(
            lat=sous_troncon.lat_fin, lon=sous_troncon.lon_fin
        )
        reponse = await google_routes.calcul_itineraire(origine, destination)
        return ResultatSource(
            source=SourceMesure.google,
            troncon_id=sous_troncon.troncon_id,
            sous_troncon_id=sous_troncon.id,
            succes=True,
            duree_trafic_s=reponse.duree_trafic_s,
            duree_sans_trafic_s=reponse.duree_sans_trafic_s,
            distance_m=reponse.distance_m,
            pourcentage_rouge=reponse.pourcentage_rouge,
            pourcentage_orange=reponse.pourcentage_orange,
            pourcentage_vert=reponse.pourcentage_vert,
            est_congestionne=reponse.est_congestionne,
        )

    # On utilise un id "virtuel" négatif pour les logs (le sous-tronçon n'a
    # pas son propre champ dans ResultatSource utilisé par _appel_avec_backoff).
    return await _appel_avec_backoff(
        _operation,
        source=SourceMesure.google,
        troncon_id=sous_troncon.troncon_id,
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


async def cycle_de_collecte() -> dict[str, int]:
    """Un cycle complet : appels parallèles + persistance + journalisation.

    Règle DEESP : si un tronçon parent a au moins un sous-tronçon actif,
    on mesure **uniquement** les sous-tronçons (granularité fine, codification
    T1A/T1B/T1C…). Sinon on mesure le parent dans son intégralité.

    Retourne un résumé `{nb_succes, nb_trous, nb_troncons, nb_sous_troncons,
    nb_appels}` utile pour les endpoints de status.
    """
    horodatage_utc = datetime.now(tz=timezone.utc)
    settings = get_settings()

    # 1. Chargement des tronçons actifs (avec coordonnées résolues) ET de leurs
    #    sous-tronçons actifs.
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
        sous_troncons_actifs: list[SousTroncon] = list(
            session.execute(
                select(SousTroncon).where(SousTroncon.actif.is_(True))
            ).scalars()
        )
    finally:
        session.close()

    if not troncons_actifs and not sous_troncons_actifs:
        logger.warning("Cycle de collecte : aucun tronçon/sous-tronçon actif.")
        return {
            "nb_succes": 0, "nb_trous": 0,
            "nb_troncons": 0, "nb_sous_troncons": 0, "nb_appels": 0,
        }

    # Quels parents ont déjà des sous-tronçons actifs ? Ces parents seront
    # exclus du cycle (la granularité fine prend le relais).
    parents_avec_sous = {st.troncon_id for st in sous_troncons_actifs}
    troncons_a_mesurer = [
        t for t in troncons_actifs if t.id not in parents_avec_sous
    ]

    # 2. Décision des sources interrogées
    sources_actives: list[SourceMesure] = []
    if settings.google_routes_api_key:
        sources_actives.append(SourceMesure.google)
    else:
        logger.error(
            "GOOGLE_ROUTES_API_KEY absente : aucune source temps réel disponible — "
            "trous de mesure pour ce cycle."
        )

    # 3. Construction des tâches : parents seuls + sous-tronçons
    taches: list[Awaitable[ResultatSource]] = []
    for troncon in troncons_a_mesurer:
        for src in sources_actives:
            adaptateur = _ADAPTATEURS_SOURCES[src]
            taches.append(adaptateur(troncon))
    for sous in sous_troncons_actifs:
        if SourceMesure.google in sources_actives:
            taches.append(_collecter_google_pour_sous_troncon(sous))

    # Si aucune source n'est dispo, on génère quand même des trous
    if not sources_actives:
        resultats: list[ResultatSource] = []
        for t in troncons_a_mesurer:
            resultats.append(ResultatSource(
                source=SourceMesure.google, troncon_id=t.id, succes=False,
                message_erreur="aucune source temps réel configurée",
            ))
        for s in sous_troncons_actifs:
            resultats.append(ResultatSource(
                source=SourceMesure.google,
                troncon_id=s.troncon_id, sous_troncon_id=s.id, succes=False,
                message_erreur="aucune source temps réel configurée",
            ))
    else:
        resultats = list(await asyncio.gather(*taches, return_exceptions=False))

    # 4. Persistance (dans un thread pour ne pas bloquer la boucle)
    await asyncio.to_thread(_persister_mesures, resultats, horodatage_utc)

    nb_succes = sum(1 for r in resultats if r.succes)
    nb_trous = len(resultats) - nb_succes
    logger.info(
        "Cycle terminé à %s — %d tronçons + %d sous-tronçons, "
        "%d appels, %d réussites, %d trous.",
        horodatage_utc.isoformat(),
        len(troncons_a_mesurer),
        len(sous_troncons_actifs),
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
        "nb_troncons": len(troncons_a_mesurer),
        "nb_sous_troncons": len(sous_troncons_actifs),
        "nb_appels": len(resultats),
    }


# ---------------------------------------------------------------------------
# Garde-fou quota Google (≤ 250 req/jour)
# ---------------------------------------------------------------------------


# Plafond imposé par le cahier des charges (CLAUDE.md — contraintes)
QUOTA_GOOGLE_JOUR_MAX = 250


def estimer_requetes_par_jour(settings: Settings, nb_entites_mesurees: int) -> int:
    """Estime le nombre de requêtes Google par jour pour la config courante.

    `nb_entites_mesurees` = (nb_troncons sans sous-tronçon) + (nb_sous_troncons).
    """
    nb_heures_actives = max(0, settings.collect_end_hour - settings.collect_start_hour)
    if settings.collect_interval_minutes <= 0 or nb_heures_actives <= 0:
        return 0
    nb_cycles = (nb_heures_actives * 60) // settings.collect_interval_minutes
    return nb_cycles * nb_entites_mesurees


def _verifier_quota_au_demarrage() -> None:
    """Journalise un avertissement si la config dépasserait le quota Google."""
    settings = get_settings()
    session = SessionLocal()
    try:
        # Compte les parents actifs qui n'ont PAS de sous-tronçon actif +
        # tous les sous-tronçons actifs (granularité réelle de mesure).
        parents_avec_sous = {
            tid for (tid,) in session.execute(
                select(SousTroncon.troncon_id).where(SousTroncon.actif.is_(True)).distinct()
            ).all()
        }
        ids_parents_actifs = [
            tid for (tid,) in session.execute(
                select(Troncon.id).where(Troncon.actif.is_(True))
            ).all()
        ]
        nb_parents_a_mesurer = sum(1 for t in ids_parents_actifs if t not in parents_avec_sous)
        nb_sous_actifs = session.scalar(
            select(func.count(SousTroncon.id)).where(SousTroncon.actif.is_(True))
        ) or 0
        nb_actifs = nb_parents_a_mesurer + nb_sous_actifs
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

    Exemples :
      - interval 15 min, plage 7h→19h → minute='*/15', hour='7-18'
      - interval 60 min, plage 0h→24h → **minute=0, hour='0-23'**
        (APScheduler refuse `*/60` car le champ minute va de 0 à 59 —
         step > range : `ValueError`. Sémantiquement équivalent à "1 cycle
         par heure pleine".)
    """
    interval = max(1, settings.collect_interval_minutes)
    # `7-18` couvre 07:00..18:59 ; on n'inclut pas l'heure de fin pour éviter
    # un cycle juste après la fermeture de la fenêtre.
    plage_heures = f"{settings.collect_start_hour}-{max(settings.collect_start_hour, settings.collect_end_hour - 1)}"

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
            nb = await scraper_toutes_sources(session)
            logger.info("Collecte incidents : %d nouvel(s) incident(s).", nb)
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
