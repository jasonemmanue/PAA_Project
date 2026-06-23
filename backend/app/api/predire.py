"""Routeur `/predire` — temps de traversée par période.

Endpoint unique :
  - GET /predire/resume?troncon_id= → 3 blocs temporels (courante / semaine / mois)

La précision de l'estimation courante est améliorée par les relevés GPX terrain
importés via POST /terrain/import (page Fiabilité). Le facteur de calibration
issu des `releves_terrain.ecart_relatif` est appliqué uniquement si des relevés
réels (source_reelle=True) sont disponibles.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.predicteur.profils import predire, _stats_mesures_periode


router = APIRouter(prefix="/predire", tags=["temps de traversée par période"])


@router.get(
    "/resume",
    summary="Temps de traversée sur 3 périodes — courante, semaine, mois",
    description=(
        "Retourne en un seul appel les 3 blocs temporels affichés sur la page "
        "Temps de traversée :\n\n"
        "- **courante** : estimation pour l'instant présent (cascade Google → "
        "profils horaires 60 j → référence 50 km/h). Calibrée par les relevés "
        "GPX terrain si des relevés réels sont disponibles.\n"
        "- **semaine** : stats observées (min/moyen/max) depuis le lundi de la "
        "semaine en cours, séparées jours-ouvrables/week-ends.\n"
        "- **mois** : stats observées depuis le 1er du mois courant, "
        "séparées jours-ouvrables/week-ends.\n\n"
        "Les blocs `semaine` et `mois` s'appuient sur les mesures Google réelles "
        "déjà collectées — pas sur le prédicteur."
    ),
)
async def get_resume(
    troncon_id: int = Query(..., description="ID du tronçon"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fuseau = ZoneInfo(get_settings().tz)
    maintenant_local = datetime.now(tz=fuseau)
    maintenant_utc = maintenant_local.astimezone(timezone.utc)

    # Estimation courante — cascade complète
    try:
        pred = predire(db, troncon_id, maintenant_local)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    # Fenêtre semaine — lundi local à 00:00 → maintenant
    debut_semaine_date = maintenant_local.date() - timedelta(days=maintenant_local.weekday())
    debut_semaine_utc = (
        datetime.combine(debut_semaine_date, time(0, 0), tzinfo=fuseau)
        .astimezone(timezone.utc)
    )

    # Fenêtre mois — 1er du mois local à 00:00 → maintenant
    debut_mois_date = maintenant_local.date().replace(day=1)
    debut_mois_utc = (
        datetime.combine(debut_mois_date, time(0, 0), tzinfo=fuseau)
        .astimezone(timezone.utc)
    )

    stats_semaine = _stats_mesures_periode(db, troncon_id, debut_semaine_utc, maintenant_utc)
    stats_mois = _stats_mesures_periode(db, troncon_id, debut_mois_utc, maintenant_utc)

    return {
        "troncon_id": pred.troncon_id,
        "troncon_nom": pred.troncon_nom,
        "courante": {
            "instant_local": pred.instant_local,
            "type_jour": pred.type_jour,
            "prediction": {
                "min_mn": pred.min_mn,
                "moyen_mn": pred.moyen_mn,
                "max_mn": pred.max_mn,
            },
            "source": pred.source,
            "confiance": round(pred.confiance, 3),
            "calibration_appliquee": pred.calibration_appliquee,
            "avertissement": pred.avertissement,
        },
        "semaine": {
            "debut": debut_semaine_date.isoformat(),
            "fin": maintenant_local.date().isoformat(),
            "nb_mesures_total": stats_semaine["nb_mesures_total"],
            "jours_ouvrables": stats_semaine["jour_ouvrable"],
            "week_ends": stats_semaine["week_end"],
        },
        "mois": {
            "debut": debut_mois_date.isoformat(),
            "fin": maintenant_local.date().isoformat(),
            "nb_mesures_total": stats_mois["nb_mesures_total"],
            "jours_ouvrables": stats_mois["jour_ouvrable"],
            "week_ends": stats_mois["week_end"],
        },
    }
