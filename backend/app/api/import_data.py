"""Endpoints d'import des données historiques Excel (P6.1).

POST /import/base-nettoyee — importe Base_Nettoyee_PAA_Fev2025.xlsx
POST /import/evolution     — importe la feuille SYNTHESE COMPAREE de FEVRIER_2026.xlsx

Après import de base-nettoyee, le recalcul des profils horaires est
déclenché automatiquement afin que les 2016 mesures soient immédiatement
reflétées dans les indicateurs (TTI, PTI, BTI) et le prédicteur (P6.2).
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.agregation.profils import executer_agregation
from app.import_base_nettoyee import importer as importer_base
from app.import_evolution import importer as importer_evolution

logger = logging.getLogger("paa.api.import")

router = APIRouter(prefix="/import", tags=["import données historiques"])


@router.post(
    "/base-nettoyee",
    summary="Importe Base_Nettoyee_PAA_Fev2025.xlsx dans mesures",
    description=(
        "Charge la feuille **'1. Donnees nettoyees'** et insère les mesures dans "
        "`mesures` avec `source='historique_paa_2025'`. "
        "Script idempotent : les doublons (troncon_id, horodatage, source) sont ignorés. "
        "Déclenche automatiquement le recalcul des profils horaires après import."
    ),
    status_code=status.HTTP_200_OK,
)
async def import_base_nettoyee(
    fichier: UploadFile = File(..., description="Fichier Excel Base_Nettoyee_PAA_Fev2025.xlsx"),
) -> dict:
    """Importe les 2016 mesures terrain de la campagne Février 2025."""
    if not fichier.filename or not fichier.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier doit être au format Excel (.xlsx ou .xls).",
        )

    contenu = await fichier.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contenu)
        chemin_tmp = Path(tmp.name)

    try:
        resultat = importer_base(chemin_tmp)
    except Exception as exc:
        logger.exception("Erreur import base nettoyée.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'import : {exc}",
        ) from exc
    finally:
        chemin_tmp.unlink(missing_ok=True)

    # Recalcul immédiat des profils horaires pour refléter les nouvelles mesures
    try:
        executer_agregation()
        resultat["agregation_recalculee"] = True
        logger.info("Profils horaires recalculés après import base nettoyée.")
    except Exception as exc:
        logger.warning("Import OK mais agrégation échouée : %s", exc)
        resultat["agregation_recalculee"] = False
        resultat["agregation_erreur"] = str(exc)

    return resultat


@router.post(
    "/evolution",
    summary="Importe la SYNTHESE COMPAREE de FEVRIER_2026.xlsx",
    description=(
        "Lit uniquement la feuille **'SYNTHESE COMPAREE'** et insère les statistiques "
        "comparatives (min, moyen, max) par axe, sens, période et type de jour dans "
        "`evolution_indicateur`. Idempotent sur (axe, sens, periode, type_jour)."
    ),
    status_code=status.HTTP_200_OK,
)
async def import_evolution(
    fichier: UploadFile = File(
        ...,
        description="Fichier Excel ALLER-RETOUR_ED_TRAITEMENT_DES_DONNEES_FEVRIER_2026.xlsx",
    ),
) -> dict:
    """Importe les données comparatives pluriannuelles dans evolution_indicateur."""
    if not fichier.filename or not fichier.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier doit être au format Excel (.xlsx ou .xls).",
        )

    contenu = await fichier.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contenu)
        chemin_tmp = Path(tmp.name)

    try:
        resultat = importer_evolution(chemin_tmp)
    except Exception as exc:
        logger.exception("Erreur import évolution.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'import : {exc}",
        ) from exc
    finally:
        chemin_tmp.unlink(missing_ok=True)

    return resultat
