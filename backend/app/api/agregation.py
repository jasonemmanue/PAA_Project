"""Endpoint de déclenchement manuel de l'agrégation des profils horaires.

L'agrégation est planifiée chaque nuit à 23h00 (cf. scheduler.py) mais peut
être déclenchée à la demande pour les démos ou après import de données.
"""

import asyncio
from typing import Any

from fastapi import APIRouter

from app.agregation.profils import executer_agregation


router = APIRouter(prefix="/agregation", tags=["agregation"])


@router.post(
    "/run",
    summary="Déclenche immédiatement le recalcul des profils horaires",
    description=(
        "Exécute le même traitement que le job nocturne : détection IQR, "
        "marquage des mesures aberrantes et recalcul des fenêtres glissantes "
        "30 / 60 / 90 j de la table profils_horaires."
    ),
)
async def run_agregation() -> dict[str, Any]:
    # Le calcul est synchrone (SQLAlchemy sync + statistics) — délégation
    # dans un thread pour ne pas bloquer la boucle async pendant la passe.
    resume = await asyncio.to_thread(executer_agregation)
    return {"etat": "agregation_executee", **resume}
