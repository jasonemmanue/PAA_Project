"""Routeur `/rapport/officiel` — Rapport DEESP au format officiel.

Chaîne complète pilotée depuis la page Rapport du frontend :

  1. `GET  /rapport/officiel/parametres`     — état courant (période, données saisies)
  2. `GET  /rapport/officiel/modele-excel`   — classeur à compléter par le rédacteur
  3. `POST /rapport/officiel/importer-excel` — dépôt du classeur complété
  4. `POST /rapport/officiel/rafraichir`     — recalcul des chiffres et des textes
  5. `GET  /rapport/officiel/word`           — document Word final

Les étapes 2 et 3 concernent les seules données que l'application ne collecte
pas. Tout ce qui relève des temps de traversée est recalculé à chaque appel
depuis les mesures, sur la période et le créneau horaire transmis.
"""

from __future__ import annotations

import logging
from datetime import date as DateType
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.rapport import _bornes_utc
from app.db.session import get_db
from app.rapport_officiel import donnees as mod_donnees
from app.rapport_officiel import generateur, parametres as mod_parametres


logger = logging.getLogger("paa.rapport.officiel")

router = APIRouter(prefix="/rapport/officiel", tags=["rapport DEESP officiel"])

TYPE_DOCX = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------


class EtatParametres(BaseModel):
    """État de préparation du rapport pour une campagne."""

    campagne: str
    importe: bool
    nom_fichier: str | None = None
    nb_textes: int
    nb_valeurs_comparatif: int
    nb_donnees_directes: int
    nb_lignes_annexes: int
    sens_disponibles: list[str]


class ResumeRafraichissement(BaseModel):
    """Chiffres et libellés recalculés, renvoyés pour affichage immédiat."""

    campagne: str
    periode: str
    creneau: str
    nb_mesures: int
    nb_sens: int
    nb_axes: int
    nb_troncons_congestionnes: int
    temps_moyen_par_sens: dict[str, dict[str, int | None]]
    tendance_comparatif: str
    avertissements: list[str]


class ReponseImport(BaseModel):
    campagne: str
    message: str
    avertissements: list[str]
    nb_textes: int
    nb_valeurs_comparatif: int
    nb_donnees_directes: int
    nb_lignes_annexes: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sens_disponibles(db: Session) -> list[str]:
    return [s.libelle for s in mod_donnees.construire_sens_circulation(db)]


def _compter(params: dict[str, Any]) -> dict[str, int]:
    return {
        "nb_textes": len(params.get("textes") or {}),
        "nb_valeurs_comparatif": len((params.get("comparatif") or {}).get("valeurs") or {}),
        "nb_donnees_directes": len(params.get("donnees_directes") or {}),
        "nb_lignes_annexes": len(params.get("annexes") or []),
    }


# ---------------------------------------------------------------------------
# GET /rapport/officiel/parametres
# ---------------------------------------------------------------------------


@router.get(
    "/parametres",
    response_model=EtatParametres,
    summary="État de préparation du rapport pour une campagne",
    description=(
        "Indique si un classeur Excel a déjà été importé pour cette campagne et "
        "combien d'éléments il apporte. Permet à l'interface d'afficher l'état "
        "d'avancement avant génération."
    ),
)
def get_parametres(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    db: Session = Depends(get_db),
) -> EtatParametres:
    params = mod_parametres.charger_parametres(db, campagne)
    return EtatParametres(
        campagne=campagne,
        importe=bool(params.get("_importe")),
        nom_fichier=None,
        sens_disponibles=_sens_disponibles(db),
        **_compter(params),
    )


# ---------------------------------------------------------------------------
# GET /rapport/officiel/modele-excel
# ---------------------------------------------------------------------------


@router.get(
    "/modele-excel",
    summary="Télécharger le classeur Excel à compléter",
    description=(
        "Produit le classeur des données hors application : métadonnées, textes "
        "rédigés, campagne de référence du tableau comparatif, surcharges "
        "manuelles, relevés terrain des annexes et signataires. Le classeur est "
        "pré-rempli avec les valeurs déjà connues pour la campagne."
    ),
    response_class=Response,
)
def get_modele_excel(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    db: Session = Depends(get_db),
) -> Response:
    params = mod_parametres.charger_parametres(db, campagne)
    try:
        contenu = mod_parametres.construire_modele_excel(
            campagne, params, _sens_disponibles(db)
        )
    except Exception as exc:
        logger.exception("Echec construction du modèle Excel — campagne=%s", campagne)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de construire le classeur : {exc}",
        )
    nom = f"rapport_deesp_donnees_{campagne}.xlsx"
    return Response(
        content=contenu,
        media_type=TYPE_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


# ---------------------------------------------------------------------------
# POST /rapport/officiel/importer-excel
# ---------------------------------------------------------------------------


@router.post(
    "/importer-excel",
    response_model=ReponseImport,
    summary="Importer le classeur Excel complété",
    description=(
        "Lit le classeur et persiste son contenu pour la campagne. Un import "
        "sur une campagne déjà renseignée remplace les valeurs précédentes. "
        "Les feuilles absentes ou les lignes incomplètes sont signalées en "
        "avertissement sans faire échouer l'import."
    ),
)
async def importer_excel(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    fichier: UploadFile = File(..., description="Classeur .xlsx complété."),
    db: Session = Depends(get_db),
) -> ReponseImport:
    nom = fichier.filename or "classeur.xlsx"
    if not nom.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format attendu : .xlsx (classeur Excel).",
        )
    contenu = await fichier.read()
    try:
        document, avertissements = mod_parametres.lire_classeur(contenu)
    except Exception as exc:
        logger.exception("Echec lecture du classeur — campagne=%s fichier=%s", campagne, nom)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Classeur illisible : {exc}",
        )

    mod_parametres.enregistrer_parametres(db, campagne, document, nom)
    fusionne = mod_parametres.fusionner_avec_defauts(document)
    compteurs = _compter(fusionne)
    logger.info("Classeur importé — campagne=%s fichier=%s %s", campagne, nom, compteurs)
    return ReponseImport(
        campagne=campagne,
        message=f"Classeur « {nom} » importé pour la campagne {campagne}.",
        avertissements=avertissements,
        **compteurs,
    )


# ---------------------------------------------------------------------------
# POST /rapport/officiel/rafraichir
# ---------------------------------------------------------------------------


@router.post(
    "/rafraichir",
    response_model=ResumeRafraichissement,
    summary="Recalculer les chiffres et les textes du rapport",
    description=(
        "Relit les mesures de la période et du créneau demandés, applique les "
        "surcharges saisies dans le classeur et renvoie une synthèse des "
        "valeurs qui seront portées dans le document Word. N'écrit rien : "
        "sert à vérifier le contenu avant génération."
    ),
)
def rafraichir(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    debut: DateType | None = Query(None, description="Début de la période analysée."),
    fin: DateType | None = Query(None, description="Fin de la période analysée."),
    heure_debut: int = Query(7, ge=0, le=23, description="Début du créneau horaire."),
    heure_fin: int = Query(19, ge=1, le=24, description="Fin du créneau horaire."),
    db: Session = Depends(get_db),
) -> ResumeRafraichissement:
    debut_utc, fin_utc = _bornes_utc(campagne, debut, fin)
    contexte = mod_donnees.construire_contexte(
        db, campagne, debut_utc, fin_utc, heure_debut, heure_fin
    )
    params = mod_parametres.charger_parametres(db, campagne)
    generateur._appliquer_donnees_directes(contexte, params)

    avertissements: list[str] = []
    if contexte.nb_mesures_total == 0:
        avertissements.append(
            "Aucune mesure sur cette période et ce créneau — les tableaux de temps "
            "seront vides."
        )
    if not params.get("_importe"):
        avertissements.append(
            "Aucun classeur importé : les textes de référence et des annexes vides "
            "seront utilisés."
        )
    if not (params.get("comparatif") or {}).get("valeurs"):
        avertissements.append(
            "Campagne de référence non renseignée — le Tableau 19 comparatif restera "
            "partiellement vide."
        )

    moyennes: dict[str, dict[str, int | None]] = {}
    for sens in contexte.sens_circulation:
        moyennes[sens.libelle] = {
            "jour_ouvrable": contexte.valeur(sens.libelle, "moyen", "jour_ouvrable"),
            "week_end": contexte.valeur(sens.libelle, "moyen", "week_end"),
        }

    nb_congestion = sum(len(v) for v in contexte.congestion_par_sens.values())
    return ResumeRafraichissement(
        campagne=campagne,
        periode=contexte.libelle_periode(),
        creneau=contexte.libelle_creneau(),
        nb_mesures=contexte.nb_mesures_total,
        nb_sens=len(contexte.sens_circulation),
        nb_axes=len(contexte.axes),
        nb_troncons_congestionnes=nb_congestion,
        temps_moyen_par_sens=moyennes,
        tendance_comparatif=_tendance(contexte, params),
        avertissements=avertissements,
    )


def _tendance(contexte: mod_donnees.ContexteRapport, params: dict[str, Any]) -> str:
    """Sens de variation du temps moyen au retour par rapport à la référence."""
    valeurs_ref = (params.get("comparatif") or {}).get("valeurs") or {}
    ecarts: list[int] = []
    for sens in contexte.sens_circulation:
        if sens.sens != "retour":
            continue
        courant = contexte.valeur(sens.libelle, "moyen", "jour_ouvrable")
        precedent = valeurs_ref.get(f"{sens.libelle}|moyen|jour_ouvrable")
        if courant is not None and precedent is not None:
            ecarts.append(courant - precedent)
    if not ecarts:
        return "indeterminee"
    if all(e < 0 for e in ecarts):
        return "baisse"
    if all(e > 0 for e in ecarts):
        return "hausse"
    return "contrastee"


# ---------------------------------------------------------------------------
# GET /rapport/officiel/word
# ---------------------------------------------------------------------------


@router.get(
    "/word",
    summary="Télécharger le Rapport DEESP officiel (.docx)",
    description=(
        "Génère le rapport au format exact de la DEESP : page de garde, bloc "
        "qualité, table des matières à jour, 19 tableaux et 12 graphiques. Les "
        "temps de traversée proviennent des mesures de la période et du créneau "
        "demandés ; les contenus rédactionnels et les annexes proviennent du "
        "classeur importé."
    ),
    response_class=Response,
)
def get_word(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    debut: DateType | None = Query(None, description="Début de la période analysée."),
    fin: DateType | None = Query(None, description="Fin de la période analysée."),
    heure_debut: int = Query(7, ge=0, le=23, description="Début du créneau horaire."),
    heure_fin: int = Query(19, ge=1, le=24, description="Fin du créneau horaire."),
    db: Session = Depends(get_db),
) -> Response:
    debut_utc, fin_utc = _bornes_utc(campagne, debut, fin)
    try:
        contenu = generateur.generer_rapport(
            db, campagne, debut_utc, fin_utc, heure_debut, heure_fin
        )
    except FileNotFoundError:
        logger.exception("Modèle Word absent du déploiement.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Le modèle du rapport officiel est absent du serveur "
                "(app/rapport_officiel/modele/rapport_modele.docx)."
            ),
        )
    except Exception as exc:
        logger.exception("Echec génération du rapport officiel — campagne=%s", campagne)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Echec de génération du rapport : {exc}",
        )

    nom = f"EVALUATION_DU_TEMPS_DE_TRAVERSEE_{campagne}.docx"
    return Response(
        content=contenu,
        media_type=TYPE_DOCX,
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )
