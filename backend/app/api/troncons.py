"""Endpoints publics sur les tronçons : profil horaire prêt à tracer.

L'endpoint principal renvoie la courbe heure par heure (0–23) pour un
jour de la semaine donné et une fenêtre glissante choisie. Format pensé
pour Recharts côté frontend : une liste plate d'objets ordonnés par heure.
"""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import ProfilHoraire, Troncon


router = APIRouter(prefix="/troncons", tags=["troncons"])


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
    "/{troncon_id}/profil",
    summary="Profil horaire d'un tronçon pour un jour de la semaine",
    description=(
        "Renvoie une courbe heure par heure (0–23) prête à tracer. "
        "Chaque point contient les statistiques agrégées (moyenne, médiane, "
        "min, max, p95, nb_mesures) calculées sur la fenêtre glissante "
        "choisie (30, 60 ou 90 jours)."
    ),
)
async def profil_horaire(
    troncon_id: int,
    jour: JourSemaine = Query(
        ...,
        description="Jour de la semaine en français (lundi…dimanche).",
    ),
    fenetre_jours: int = Query(
        30,
        description="Largeur de la fenêtre glissante : 30, 60 ou 90 jours.",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # Validation des bornes (les fenêtres supportées par l'agrégation)
    if fenetre_jours not in (30, 60, 90):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fenetre_jours doit valoir 30, 60 ou 90.",
        )

    # Existence du tronçon
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )

    jour_int = _JOURS_FR[jour]

    # Chargement des 24 lignes possibles (une par heure) pour ce bucket
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

    # On renvoie systématiquement 24 points (heures 0–23). Les heures
    # sans donnée sont matérialisées par des stats à NULL : le frontend
    # peut afficher un trou plutôt qu'une interpolation.
    points: list[dict[str, Any]] = []
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

    # Temps de référence à vitesse 50 km/h, utile pour tracer une ligne
    # horizontale repère sur le graphe côté frontend.
    temps_reference_s = round(troncon.temps_reference_s(), 1)

    return {
        "troncon": {
            "id": troncon.id,
            "nom": troncon.nom,
            "distance_m": troncon.distance_m,
            "vitesse_ref_kmh": troncon.vitesse_ref_kmh,
            "temps_reference_s": temps_reference_s,
        },
        "jour": jour,
        "jour_index": jour_int,
        "fenetre_jours": fenetre_jours,
        "points": points,
    }
