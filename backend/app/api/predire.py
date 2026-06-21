"""Routeur `/predire` — prédicteur DEESP + cascade gracieuse.

Référence : CLAUDE.md § 4.5, mes_prompts_finaux.md § 6.2.

Endpoints :
  - GET /predire?troncon_id=&date=&heure= → prédiction au format DEESP
  - GET /predire/qualite                 → MAE du prédicteur (7 derniers jours)
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.predicteur.profils import evaluer_qualite, predire


router = APIRouter(prefix="/predire", tags=["prédicteur"])


# ---------------------------------------------------------------------------
# GET /predire
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="Prédiction DEESP du temps de traversée pour un tronçon × instant",
    description=(
        "Renvoie la prédiction au format DEESP (`min_mn`, `moyen_mn`, "
        "`max_mn`, ...) pour un instant cible. La cascade gracieuse est :\n\n"
        "1. **Google Routes** si la clé est disponible et l'instant cible est "
        "proche du présent (±15 min)\n"
        "2. **Prédicteur profils horaires** (60 jours par défaut) calibré "
        "(uniquement si relevés terrain réels disponibles)\n"
        "3. **Référence 50 km/h** déterministe\n\n"
        "Le champ `source` indique le niveau de la cascade utilisé."
    ),
)
async def get_predire(
    troncon_id: int = Query(..., description="ID du tronçon"),
    date_cible: date | None = Query(
        None, alias="date",
        description="Date locale (Africa/Abidjan), défaut aujourd'hui",
    ),
    heure: int | None = Query(
        None, ge=0, le=23,
        description="Heure locale 0..23, défaut heure courante",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fuseau = ZoneInfo(get_settings().tz)
    maintenant_local = datetime.now(tz=fuseau)
    if date_cible is None:
        date_cible = maintenant_local.date()
    if heure is None:
        heure = maintenant_local.hour

    instant_local = datetime.combine(date_cible, time(heure, 0), tzinfo=fuseau)

    try:
        pred = predire(db, troncon_id, instant_local)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    return {
        "troncon_id": pred.troncon_id,
        "troncon_nom": pred.troncon_nom,
        "instant_local": pred.instant_local,
        "type_jour": pred.type_jour,
        "prediction": {
            "min_mn": pred.min_mn,
            "mediane_mn": pred.mediane_mn,
            "moyen_mn": pred.moyen_mn,
            "max_mn": pred.max_mn,
            "p95_mn": pred.p95_mn,
            "fourchette_p25_p75_mn": list(pred.fourchette_p25_p75_mn) if pred.fourchette_p25_p75_mn else None,
        },
        "source": pred.source,
        "confiance": round(pred.confiance, 3),
        "calibration_appliquee": pred.calibration_appliquee,
        "avertissement": pred.avertissement,
    }


# ---------------------------------------------------------------------------
# GET /predire/qualite
# ---------------------------------------------------------------------------


@router.get(
    "/qualite",
    summary="MAE du prédicteur sur les N derniers jours",
    description=(
        "Renvoie la Mean Absolute Error du prédicteur de profils horaires "
        "comparé aux mesures Google réelles des derniers jours. Le format "
        "DEESP impose la métrique en MINUTES, séparée par type-jour."
    ),
)
async def get_qualite(
    fenetre_jours: int = Query(
        7, ge=1, le=90,
        description="Fenêtre d'évaluation en jours (1..90)",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return evaluer_qualite(db, nb_jours=fenetre_jours)
