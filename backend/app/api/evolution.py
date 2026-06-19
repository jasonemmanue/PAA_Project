"""Routeur /evolution — exposition de la table evolution_indicateur (P6.1).

Endpoints :
  - GET /evolution  → tous les enregistrements (filtres optionnels par axe / sens / type_jour)
  - GET /evolution/axes  → liste des axes / sens disponibles

La table evolution_indicateur est alimentée par l'import de la feuille
SYNTHESE COMPAREE du fichier FEVRIER_2026.xlsx (cf. app/import_evolution.py).
Elle contient les statistiques comparatives entre deux campagnes de mesure
(actuellement oct_2025 et fev_2026) — c'est la source du graphique d'évolution
pluriannuelle de l'indicateur « temps de traversée » exigé par l'article 4.4
du cahier des charges.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import EvolutionIndicateur


router = APIRouter(prefix="/evolution", tags=["évolution pluriannuelle"])


@router.get(
    "",
    summary="Liste les enregistrements de la table evolution_indicateur",
    description=(
        "Renvoie l'ensemble des statistiques pluriannuelles importées depuis "
        "la feuille `SYNTHESE COMPAREE` du fichier FEVRIER_2026.xlsx. Filtres "
        "optionnels par axe (libellé exact), sens (`Aller` ou `Retour`) et "
        "type_jour (`Jours ouvrables` ou `Week-ends`)."
    ),
)
async def lister_evolution(
    axe: str | None = Query(None, description="Filtrer sur un axe précis."),
    sens: str | None = Query(None, description="`Aller` ou `Retour`."),
    type_jour: str | None = Query(
        None, description="`Jours ouvrables` ou `Week-ends`."
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    requete = select(EvolutionIndicateur)
    if axe is not None:
        requete = requete.where(EvolutionIndicateur.axe == axe)
    if sens is not None:
        requete = requete.where(EvolutionIndicateur.sens == sens)
    if type_jour is not None:
        requete = requete.where(EvolutionIndicateur.type_jour == type_jour)
    requete = requete.order_by(
        EvolutionIndicateur.axe,
        EvolutionIndicateur.sens,
        EvolutionIndicateur.periode,
        EvolutionIndicateur.type_jour,
    )

    lignes = list(db.execute(requete).scalars())
    return {
        "nb_lignes": len(lignes),
        "lignes": [
            {
                "id": l.id,
                "axe": l.axe,
                "sens": l.sens,
                "periode": l.periode,
                "type_jour": l.type_jour,
                "temps_min_s": l.temps_min_s,
                "temps_moyen_s": l.temps_moyen_s,
                "temps_max_s": l.temps_max_s,
            }
            for l in lignes
        ],
    }


@router.get(
    "/axes",
    summary="Liste des axes/sens disponibles dans evolution_indicateur",
    description=(
        "Permet au frontend de peupler les listes déroulantes de sélection "
        "sans demander toutes les lignes au préalable."
    ),
)
async def lister_axes_evolution(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    requete = (
        select(EvolutionIndicateur.axe, EvolutionIndicateur.sens)
        .distinct()
        .order_by(EvolutionIndicateur.axe, EvolutionIndicateur.sens)
    )
    couples = list(db.execute(requete).all())
    return {
        "nb_axes_sens": len(couples),
        "axes_sens": [{"axe": c[0], "sens": c[1]} for c in couples],
    }
