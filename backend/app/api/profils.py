"""Routeur /profils — lecture des profils horaires agrégés.

Endpoints :
  - GET /profils/troncons/{id}?jour=…&fenetre_jours=… → 24 points (0–23 h)

L'écriture (recalcul nocturne) est gérée par `/agregation/run` (job APScheduler
+ endpoint manuel) — pas exposée ici pour ne pas mélanger lecture et écriture.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import ProfilHoraire, Troncon


router = APIRouter(prefix="/profils", tags=["profils"])


# Mapping FR → entier weekday() Python. Lundi = 0.
_JOURS_FR: dict[str, int] = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}

JourSemaine = Literal[
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"
]


@router.get(
    "/troncons/{troncon_id}",
    summary="Profil horaire d'un tronçon pour un jour de la semaine",
    description=(
        "Renvoie une courbe **heure par heure (0–23)** prête à tracer (Recharts). "
        "Chaque point contient les statistiques agrégées (moyenne, médiane, min, "
        "max, p95, nb_mesures) calculées sur la fenêtre glissante demandée. "
        "Les heures sans donnée sont matérialisées par des `null` — le frontend "
        "peut ainsi afficher un trou plutôt qu'une interpolation."
    ),
    responses={
        200: {
            "description": "Profil horaire avec 24 points.",
            "content": {"application/json": {"example": {
                "troncon": {
                    "id": 3,
                    "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
                    "distance_m": 8000,
                    "vitesse_ref_kmh": 50.0,
                    "temps_reference_s": 576.0,
                },
                "jour": "jeudi",
                "jour_index": 3,
                "fenetre_jours": 30,
                "points": [
                    {"heure": 19, "moyenne_s": 1642.0, "mediane_s": 1642.0,
                     "min_s": 1642.0, "max_s": 1642.0, "p95_s": 1642.0,
                     "nb_mesures": 1},
                ],
            }}}
        },
        400: {"description": "fenetre_jours hors {30, 60, 90}."},
        404: {"description": "Tronçon introuvable."},
    },
)
async def profil_horaire(
    troncon_id: int,
    jour: JourSemaine = Query(..., description="Jour de la semaine en français."),
    fenetre_jours: int = Query(30, description="30, 60 ou 90 jours."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if fenetre_jours not in (30, 60, 90):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fenetre_jours doit valoir 30, 60 ou 90.",
        )

    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )

    jour_int = _JOURS_FR[jour]
    profils = list(
        db.execute(
            select(ProfilHoraire)
            .where(
                ProfilHoraire.troncon_id == troncon_id,
                ProfilHoraire.jour_semaine == jour_int,
                ProfilHoraire.fenetre_jours == fenetre_jours,
            )
            .order_by(ProfilHoraire.heure)
        ).scalars()
    )
    profils_par_heure = {p.heure: p for p in profils}

    points = []
    for heure in range(24):
        p = profils_par_heure.get(heure)
        points.append({
            "heure": heure,
            "moyenne_s": p.moyenne if p else None,
            "mediane_s": p.mediane if p else None,
            "min_s": p.min if p else None,
            "max_s": p.max if p else None,
            "p95_s": p.p95 if p else None,
            "nb_mesures": p.nb_mesures if p else 0,
        })

    return {
        "troncon": {
            "id": troncon.id,
            "nom": troncon.nom,
            "distance_m": troncon.distance_m,
            "vitesse_ref_kmh": troncon.vitesse_ref_kmh,
            "temps_reference_s": round(troncon.temps_reference_s(), 1),
        },
        "jour": jour,
        "jour_index": jour_int,
        "fenetre_jours": fenetre_jours,
        "points": points,
    }
