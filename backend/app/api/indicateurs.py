"""Routeur /indicateurs — séries temporelles et heures de pointe.

Note d'organisation : le **snapshot** d'indicateurs sur une période vit sous
`GET /troncons/{id}/indicateurs?periode=7j` (proche de la ressource tronçon).
Ce routeur regroupe les vues transversales restantes :

  - GET /indicateurs/troncons/{id}/serie         → courbe temps de traversée
  - GET /indicateurs/troncons/{id}/heures-pointe → heures de pointe détectées
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analyse.indicateurs import (
    Granularite,
    SeuilsCongestion,
    detecter_heures_pointe,
    serie_temporelle,
)
from app.core.config import get_settings
from app.db.session import get_db


router = APIRouter(prefix="/indicateurs", tags=["indicateurs"])


# ---------------------------------------------------------------------------
# GET /indicateurs/troncons/{id}/serie
# ---------------------------------------------------------------------------


@router.get(
    "/troncons/{troncon_id}/serie",
    summary="Série temporelle du temps de traversée (article 4 du cahier des charges)",
    description=(
        "Renvoie une série temporelle agrégée du temps de parcours, à granularité "
        "horaire (`hour`) ou journalière (`day`). Chaque point contient la moyenne, "
        "la médiane, le P95, le TTI et la classe de congestion correspondante. "
        "Par défaut la série couvre les 7 derniers jours locaux."
    ),
    responses={
        200: {
            "description": "Série temporelle prête à tracer.",
            "content": {"application/json": {"example": {
                "troncon_id": 3,
                "troncon_nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
                "granularite": "hour",
                "temps_reference_s": 576.0,
                "nb_points": 1,
                "points": [{
                    "instant_local": "2026-06-18T19:00:00+00:00",
                    "moyenne_s": 1642.0,
                    "p95_s": 1642.0,
                    "tti": 2.851,
                    "classe_congestion": "congestionne",
                    "nb_mesures": 1,
                }],
            }}}
        },
        404: {"description": "Tronçon introuvable."},
    },
)
async def serie_indicateurs(
    troncon_id: int,
    debut: date | None = Query(None, description="Date locale de début (YYYY-MM-DD)."),
    fin: date | None = Query(None, description="Date locale de fin (YYYY-MM-DD)."),
    granularite: Granularite = Query("hour", description="`hour` ou `day`."),
    inclure_aberrantes: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fuseau_local = ZoneInfo(get_settings().tz)
    fin_jour = fin or datetime.now(tz=fuseau_local).date()
    debut_jour = debut or (fin_jour - timedelta(days=7))
    debut_utc = datetime.combine(debut_jour, time.min, tzinfo=fuseau_local).astimezone(timezone.utc)
    fin_utc = datetime.combine(fin_jour, time.max, tzinfo=fuseau_local).astimezone(timezone.utc)

    try:
        return serie_temporelle(
            db, troncon_id, debut_utc, fin_utc,
            granularite=granularite,
            inclure_aberrantes=inclure_aberrantes,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# GET /indicateurs/troncons/{id}/heures-pointe
# ---------------------------------------------------------------------------


@router.get(
    "/troncons/{troncon_id}/heures-pointe",
    summary="Heures de pointe détectées par jour de la semaine",
    description=(
        "Pour chaque jour de la semaine, identifie les heures où la moyenne "
        "horaire dépasse `seuil_tti × T_ref(50 km/h)`. La valeur par défaut "
        "du seuil provient de `TTI_SEUIL_HEURE_POINTE` (`.env`)."
    ),
    responses={
        200: {
            "description": "Liste des heures de pointe par jour.",
            "content": {"application/json": {"example": {
                "troncon_id": 3,
                "troncon_nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
                "fenetre_jours": 30,
                "temps_reference_50kmh_s": 576.0,
                "seuil_heure_pointe_s": 864.0,
                "seuil_heure_pointe_tti": 1.5,
                "heures_de_pointe": {
                    "lundi": [], "mardi": [], "mercredi": [],
                    "jeudi": [19], "vendredi": [],
                    "samedi": [], "dimanche": [],
                },
            }}}
        }
    },
)
async def heures_pointe_indicateurs(
    troncon_id: int,
    fenetre_jours: int = Query(30, description="30, 60 ou 90."),
    seuil_tti: float | None = Query(
        None,
        description="TTI seuil pour qu'une heure soit dite « de pointe » (défaut `.env`).",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if fenetre_jours not in (30, 60, 90):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fenetre_jours doit valoir 30, 60 ou 90.",
        )
    base = SeuilsCongestion.depuis_settings()
    seuils = SeuilsCongestion(
        dense=base.dense,
        congestionne=base.congestionne,
        heure_pointe=seuil_tti if seuil_tti is not None else base.heure_pointe,
    )
    try:
        return detecter_heures_pointe(
            db, troncon_id,
            fenetre_jours=fenetre_jours,
            seuils=seuils,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc
