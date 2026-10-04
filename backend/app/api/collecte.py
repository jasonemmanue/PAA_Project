"""Endpoints de pilotage du mode planifié (phase P2).

Trois routes simples :

  - POST /collecte/start   → démarre (ou réarme) le job APScheduler
  - POST /collecte/stop    → arrête le job et le scheduler
  - GET  /collecte/status  → prochaine exécution + nombre de mesures du jour
  - GET/PUT /collecte/plage → plage horaire de collecte réglable (§ 39)

Le « nombre de mesures du jour » est calculé sur la **date locale d'Abidjan** ;
les mesures sont stockées en UTC mais l'affichage se fait dans le fuseau métier.
"""

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collecte.plage import (
    PlageCollecte,
    enregistrer_plage_collecte,
    lire_plage_collecte,
    valider_plage,
)
from app.collecte.plan_axes import appels_google_par_cycle, construire_plan_collecte
from app.collecte.scheduler import (
    QUOTA_GOOGLE_JOUR_MAX,
    appliquer_plage_collecte,
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

    nb_troncons_actifs_total = db.scalar(
        select(func.count(Troncon.id)).where(Troncon.actif.is_(True))
    ) or 0

    # Plan du cycle : une requête Google par axe (étapes intermédiaires), cf. § 39
    plan = construire_plan_collecte(db)
    plage = lire_plage_collecte(db)

    settings = get_settings()
    estimation_quota = estimer_requetes_par_jour(settings, plan.nb_appels, plage)

    return {
        **etat_scheduler(),
        "fuseau": settings.tz,
        "config": {
            "intervalle_min": settings.collect_interval_minutes,
            "plage_horaire": plage.libelle,
            "heure_debut": plage.heure_debut,
            "heure_fin": plage.heure_fin,
            "estimation_requetes_google_par_jour": estimation_quota,
            "plafond_google_par_jour": QUOTA_GOOGLE_JOUR_MAX,
        },
        "compteurs_jour": {
            "nb_mesures_total": nb_mesures_jour,
            "nb_succes": nb_succes_jour,
            "nb_trous": nb_trous_jour,
            "nb_troncons_actifs": nb_troncons_actifs_total,
            "nb_appels_google_par_cycle": plan.nb_appels,
            "nb_resultats_par_cycle": plan.nb_resultats,
        },
    }


# ---------------------------------------------------------------------------
# GET / PUT /collecte/plage — plage horaire de collecte réglable (§ 39)
# ---------------------------------------------------------------------------


class PlageCollecteEntree(BaseModel):
    """Nouvelle plage de collecte, heures locales Africa/Abidjan."""
    heure_debut: int = Field(..., ge=0, le=23, description="Heure de début (incluse)")
    heure_fin: int = Field(..., ge=1, le=24, description="Heure de fin (exclue)")


class PlageCollecteSortie(BaseModel):
    """Plage de collecte en vigueur et son impact sur le quota Google."""
    heure_debut: int
    heure_fin: int
    libelle: str
    appels_google_par_cycle: int
    estimation_requetes_google_par_jour: int
    plafond_google_par_jour: int
    prochaine_execution: str | None = None


def _sortie_plage(db: Session, plage: PlageCollecte, prochaine: str | None) -> PlageCollecteSortie:
    nb_appels = appels_google_par_cycle(db)
    return PlageCollecteSortie(
        heure_debut=plage.heure_debut,
        heure_fin=plage.heure_fin,
        libelle=plage.libelle,
        appels_google_par_cycle=nb_appels,
        estimation_requetes_google_par_jour=estimer_requetes_par_jour(
            get_settings(), nb_appels, plage,
        ),
        plafond_google_par_jour=QUOTA_GOOGLE_JOUR_MAX,
        prochaine_execution=prochaine,
    )


@router.get(
    "/plage",
    summary="Plage horaire de collecte en vigueur",
    description=(
        "Fenêtre horaire locale `[heure_debut, heure_fin[` pendant laquelle le "
        "scheduler interroge Google Routes. Hors de cette plage, aucune requête "
        "n'est émise. Renvoie aussi l'estimation de requêtes par jour."
    ),
    response_model=PlageCollecteSortie,
)
async def get_plage_collecte(db: Session = Depends(get_db)) -> PlageCollecteSortie:
    prochaine = etat_scheduler().get("prochaine_execution")
    return _sortie_plage(db, lire_plage_collecte(db), prochaine if isinstance(prochaine, str) else None)


@router.put(
    "/plage",
    summary="Modifie la plage horaire de collecte",
    description=(
        "Enregistre la nouvelle plage en base (survit aux redéploiements) puis "
        "replanifie immédiatement le cycle de collecte, sans redémarrage. "
        "Exemple : `{\"heure_debut\": 7, \"heure_fin\": 19}` → collecte de "
        "07:00 à 18:59, aucune requête Google la nuit."
    ),
    response_model=PlageCollecteSortie,
)
async def put_plage_collecte(
    entree: PlageCollecteEntree, db: Session = Depends(get_db),
) -> PlageCollecteSortie:
    try:
        plage = valider_plage(entree.heure_debut, entree.heure_fin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    enregistrer_plage_collecte(db, plage)
    prochaine = appliquer_plage_collecte(plage)
    return _sortie_plage(db, plage, prochaine)


# ---------------------------------------------------------------------------
# POST /collecte/run-once — déclencheur manuel pour les tests
# ---------------------------------------------------------------------------


@router.post(
    "/run-once",
    summary="Déclenche un cycle de collecte immédiat (hors planning)",
    description=(
        "Utile en démo ou en test pour vérifier la chaîne de bout en bout "
        "sans attendre le prochain tic du scheduler. Hors de la plage de "
        "collecte, le cycle ne fait aucun appel Google."
    ),
)
async def run_once() -> dict[str, Any]:
    resume = await cycle_de_collecte()
    return {"etat": "cycle_execute", **resume}
