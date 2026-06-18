"""Endpoints de pilotage du mode planifié (phase P2).

Trois routes simples :

  - POST /collecte/start   → démarre (ou réarme) le job APScheduler
  - POST /collecte/stop    → arrête le job et le scheduler
  - GET  /collecte/status  → prochaine exécution + nombre de mesures du jour

Le « nombre de mesures du jour » est calculé sur la **date locale d'Abidjan** ;
les mesures sont stockées en UTC mais l'affichage se fait dans le fuseau métier.
"""

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collecte.scheduler import (
    arreter_scheduler,
    cycle_de_collecte,
    demarrer_scheduler,
    estimer_requetes_par_jour,
    etat_scheduler,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Mesure, Troncon


router = APIRouter(prefix="/collecte", tags=["collecte"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bornes_utc_du_jour_local() -> tuple[datetime, datetime]:
    """Retourne (debut_utc, fin_utc) du jour calendrier local Africa/Abidjan."""
    fuseau = ZoneInfo(get_settings().tz)
    maintenant_local = datetime.now(tz=fuseau)
    debut_local = datetime.combine(maintenant_local.date(), time.min, tzinfo=fuseau)
    fin_local = datetime.combine(maintenant_local.date(), time.max, tzinfo=fuseau)
    return debut_local.astimezone(timezone.utc), fin_local.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# POST /collecte/start
# ---------------------------------------------------------------------------


@router.post(
    "/start",
    summary="Démarre le mode planifié de collecte",
    description=(
        "Active le job APScheduler qui interroge Google Routes pour chaque "
        "tronçon actif, selon la cadence et la plage horaire définies dans .env."
    ),
)
async def start_collecte() -> dict[str, Any]:
    return demarrer_scheduler()


# ---------------------------------------------------------------------------
# POST /collecte/stop
# ---------------------------------------------------------------------------


@router.post(
    "/stop",
    summary="Arrête le mode planifié de collecte",
)
async def stop_collecte() -> dict[str, Any]:
    return arreter_scheduler()


# ---------------------------------------------------------------------------
# GET /collecte/status
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    summary="État du scheduler et compteurs de la journée en cours",
)
async def status_collecte(db: Session = Depends(get_db)) -> dict[str, Any]:
    debut_utc, fin_utc = _bornes_utc_du_jour_local()

    nb_mesures_jour = db.scalar(
        select(func.count(Mesure.id)).where(
            Mesure.horodatage >= debut_utc,
            Mesure.horodatage <= fin_utc,
        )
    ) or 0

    nb_succes_jour = db.scalar(
        select(func.count(Mesure.id)).where(
            Mesure.horodatage >= debut_utc,
            Mesure.horodatage <= fin_utc,
            Mesure.duree_trafic_s.is_not(None),
        )
    ) or 0

    nb_trous_jour = nb_mesures_jour - nb_succes_jour

    nb_troncons_actifs = db.scalar(
        select(func.count(Troncon.id)).where(Troncon.actif.is_(True))
    ) or 0

    settings = get_settings()
    estimation_quota = estimer_requetes_par_jour(settings, nb_troncons_actifs)

    return {
        **etat_scheduler(),
        "fuseau": settings.tz,
        "config": {
            "intervalle_min": settings.collect_interval_minutes,
            "plage_horaire": f"{settings.collect_start_hour}h-{settings.collect_end_hour}h",
            "estimation_requetes_google_par_jour": estimation_quota,
            "plafond_google_par_jour": 250,
        },
        "compteurs_jour": {
            "nb_mesures_total": nb_mesures_jour,
            "nb_succes": nb_succes_jour,
            "nb_trous": nb_trous_jour,
            "nb_troncons_actifs": nb_troncons_actifs,
        },
    }


# ---------------------------------------------------------------------------
# POST /collecte/run-once — déclencheur manuel pour les tests
# ---------------------------------------------------------------------------


@router.post(
    "/run-once",
    summary="Déclenche un cycle de collecte immédiat (hors planning)",
    description=(
        "Utile en démo ou en test pour vérifier la chaîne de bout en bout "
        "sans attendre le prochain tic du scheduler."
    ),
)
async def run_once() -> dict[str, Any]:
    resume = await cycle_de_collecte()
    return {"etat": "cycle_execute", **resume}
