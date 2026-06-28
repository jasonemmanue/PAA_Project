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


# ---------------------------------------------------------------------------
# /import/evolution-csv — format CSV / Excel générique 7 colonnes
# ---------------------------------------------------------------------------


@router.post(
    "/evolution-csv",
    summary="Import générique CSV ou Excel pour evolution_indicateur",
    description=(
        "Accepte un fichier **CSV** ou **Excel** (.xlsx/.xls) à plat avec "
        "les colonnes suivantes (insensible à la casse, accents ignorés) : "
        "`axe`, `sens`, `periode`, `type_jour`, `temps_min_s`, "
        "`temps_moyen_s`, `temps_max_s`. Idempotent — UPSERT sur la clé "
        "(axe, sens, periode, type_jour). Le graphique pluriannuel est "
        "mis à jour automatiquement après l'import."
    ),
    status_code=status.HTTP_200_OK,
)
async def import_evolution_csv(
    fichier: UploadFile = File(..., description="CSV ou Excel à 7 colonnes"),
) -> dict:
    import io
    import pandas as pd
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.models import EvolutionIndicateur

    if not fichier.filename:
        raise HTTPException(status_code=422, detail="Nom de fichier manquant.")

    nom = fichier.filename.lower()
    contenu = await fichier.read()
    try:
        if nom.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contenu))
        elif nom.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contenu))
        else:
            raise HTTPException(status_code=422,
                                detail="Format non supporté : utilisez .csv, .xlsx ou .xls.")
    except Exception as exc:
        logger.exception("Lecture fichier impossible")
        raise HTTPException(status_code=422, detail=f"Lecture impossible : {exc}") from exc

    # Normalise les noms de colonnes (lowercase, sans espace)
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    colonnes_req = {"axe", "sens", "periode", "type_jour",
                    "temps_min_s", "temps_moyen_s", "temps_max_s"}
    manquantes = colonnes_req - set(df.columns)
    if manquantes:
        raise HTTPException(
            status_code=422,
            detail=f"Colonnes manquantes : {', '.join(sorted(manquantes))}",
        )

    session = SessionLocal()
    nb_ajoutes = 0
    nb_majs = 0
    try:
        for _, row in df.iterrows():
            cle = (str(row["axe"]).strip(), str(row["sens"]).strip(),
                   str(row["periode"]).strip(), str(row["type_jour"]).strip())
            existant = session.execute(
                select(EvolutionIndicateur).where(
                    EvolutionIndicateur.axe == cle[0],
                    EvolutionIndicateur.sens == cle[1],
                    EvolutionIndicateur.periode == cle[2],
                    EvolutionIndicateur.type_jour == cle[3],
                )
            ).scalar_one_or_none()
            valeurs = {
                "temps_min_s":   float(row["temps_min_s"])   if pd.notna(row["temps_min_s"])   else None,
                "temps_moyen_s": float(row["temps_moyen_s"]) if pd.notna(row["temps_moyen_s"]) else None,
                "temps_max_s":   float(row["temps_max_s"])   if pd.notna(row["temps_max_s"])   else None,
            }
            if existant is None:
                session.add(EvolutionIndicateur(
                    axe=cle[0], sens=cle[1], periode=cle[2], type_jour=cle[3],
                    **valeurs,
                ))
                nb_ajoutes += 1
            else:
                for k, v in valeurs.items():
                    setattr(existant, k, v)
                nb_majs += 1
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("Erreur insertion CSV évolution")
        raise HTTPException(status_code=500, detail=f"Erreur insertion : {exc}") from exc
    finally:
        session.close()

    return {
        "fichier": fichier.filename,
        "nb_lignes_lues": len(df),
        "nb_ajoutees": nb_ajoutes,
        "nb_majs": nb_majs,
        "message": f"{nb_ajoutes} nouvelle(s) ligne(s) + {nb_majs} mise(s) à jour.",
    }
