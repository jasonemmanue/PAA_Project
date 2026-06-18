"""Endpoints d'export Excel / CSV des mesures et des profils horaires.

Deux exports :

  - GET /export/mesures?troncon_id=&debut=&fin=&format=csv|xlsx
      → liste plate des mesures, filtrée par tronçon et par plage de dates locales
        (Africa/Abidjan). En-têtes en français, encodage UTF‑8 BOM pour
        ouverture directe dans Excel Windows.

  - GET /export/profils?format=xlsx[&fenetre_jours=30|60|90]
      → un classeur XLSX, **une feuille par tronçon**, sous forme d'un tableau
        croisé heure (lignes 0–23) × jour de la semaine (colonnes lundi→dimanche).
        Les cellules contiennent la **moyenne en minutes** (arrondie à 0,1 min),
        format métier attendu par les gestionnaires PAA.
        Une première feuille « Synthèse » liste les tronçons et leurs distances.

Conventions :
  - Toutes les durées stockées sont en secondes (CLAUDE.md § 5.3) ;
    on les convertit en minutes uniquement à l'affichage (XLSX).
  - Les horodatages UTC sont reconvertis en heure locale Africa/Abidjan
    pour l'export — c'est ce que l'utilisateur final attend.
  - Le tableau pivot est construit avec pandas.DataFrame.pivot_table.
"""

from __future__ import annotations

import io
from datetime import date, datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Mesure, ProfilHoraire, Troncon


router = APIRouter(prefix="/export", tags=["export"])


# Noms des jours de la semaine en français, indexés sur Python weekday() (0=lundi).
_JOURS_FR: tuple[str, ...] = (
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
)


# ---------------------------------------------------------------------------
# Helpers communs
# ---------------------------------------------------------------------------


def _bornes_utc(
    debut: date | None,
    fin: date | None,
) -> tuple[datetime | None, datetime | None]:
    """Convertit (debut, fin) locaux Africa/Abidjan en UTC pour le filtrage SQL.

    `debut` = début de journée locale (00:00:00), `fin` = fin de journée locale (23:59:59.999).
    """
    fuseau = ZoneInfo(get_settings().tz)
    debut_utc: datetime | None = None
    fin_utc: datetime | None = None
    if debut is not None:
        debut_utc = datetime.combine(debut, time.min, tzinfo=fuseau).astimezone(timezone.utc)
    if fin is not None:
        fin_utc = datetime.combine(fin, time.max, tzinfo=fuseau).astimezone(timezone.utc)
    return debut_utc, fin_utc


def _nom_fichier_horodate(prefixe: str, extension: str) -> str:
    """Construit un nom de fichier suffixé par l'horodatage UTC compact."""
    suffixe = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefixe}_{suffixe}.{extension}"


def _entete_telechargement(nom_fichier: str) -> dict[str, str]:
    """Retourne le header HTTP Content-Disposition pour forcer le téléchargement."""
    return {
        "Content-Disposition": f'attachment; filename="{nom_fichier}"',
    }


# ---------------------------------------------------------------------------
# GET /export/mesures
# ---------------------------------------------------------------------------


@router.get(
    "/mesures",
    summary="Exporte les mesures brutes au format CSV ou XLSX",
    description=(
        "Filtres optionnels : `troncon_id`, `debut` et `fin` (dates ISO YYYY-MM-DD, "
        "interprétées dans le fuseau Africa/Abidjan). Le format CSV est encodé "
        "en UTF-8 avec BOM pour s'ouvrir directement dans Excel Windows."
    ),
)
async def export_mesures(
    troncon_id: int | None = Query(None, description="Filtrer sur un tronçon précis."),
    debut: date | None = Query(None, description="Date locale de début (YYYY-MM-DD)."),
    fin: date | None = Query(None, description="Date locale de fin (YYYY-MM-DD)."),
    format: Literal["csv", "xlsx"] = Query("csv", description="csv ou xlsx."),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    debut_utc, fin_utc = _bornes_utc(debut, fin)

    # Construction de la requête : SELECT mesures JOIN troncons pour le nom
    requete = (
        select(
            Mesure.id,
            Mesure.troncon_id,
            Troncon.nom,
            Mesure.horodatage,
            Mesure.source,
            Mesure.duree_trafic_s,
            Mesure.duree_sans_trafic_s,
            Mesure.vitesse_moyenne_kmh,
            Mesure.aberrante,
        )
        .join(Troncon, Troncon.id == Mesure.troncon_id)
        .order_by(Mesure.horodatage.desc())
    )
    if troncon_id is not None:
        requete = requete.where(Mesure.troncon_id == troncon_id)
    if debut_utc is not None:
        requete = requete.where(Mesure.horodatage >= debut_utc)
    if fin_utc is not None:
        requete = requete.where(Mesure.horodatage <= fin_utc)

    lignes = db.execute(requete).all()

    # Conversion en DataFrame avec en-têtes en français
    fuseau_local = ZoneInfo(get_settings().tz)
    donnees = [
        {
            "id_mesure": ligne.id,
            "id_troncon": ligne.troncon_id,
            "troncon": ligne.nom,
            "horodatage_local": (
                ligne.horodatage.astimezone(fuseau_local).strftime("%Y-%m-%d %H:%M:%S")
                if ligne.horodatage else None
            ),
            "source": ligne.source.value if ligne.source else None,
            "duree_trafic_s": ligne.duree_trafic_s,
            "duree_sans_trafic_s": ligne.duree_sans_trafic_s,
            "vitesse_moyenne_kmh": ligne.vitesse_moyenne_kmh,
            "aberrante": "oui" if ligne.aberrante else "non",
        }
        for ligne in lignes
    ]
    df = pd.DataFrame(donnees, columns=[
        "id_mesure", "id_troncon", "troncon", "horodatage_local",
        "source", "duree_trafic_s", "duree_sans_trafic_s",
        "vitesse_moyenne_kmh", "aberrante",
    ])

    # --- Sérialisation au format demandé ---
    if format == "csv":
        tampon_texte = io.StringIO()
        df.to_csv(tampon_texte, index=False, sep=";", decimal=",")
        # On encode en UTF-8 avec BOM : Excel Windows reconnaît alors les accents
        # et le séparateur point-virgule (locale française).
        contenu = ("﻿" + tampon_texte.getvalue()).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(contenu),
            media_type="text/csv; charset=utf-8",
            headers=_entete_telechargement(_nom_fichier_horodate("mesures", "csv")),
        )

    # format == "xlsx"
    tampon_binaire = io.BytesIO()
    with pd.ExcelWriter(tampon_binaire, engine="openpyxl") as ecrivain:
        df.to_excel(ecrivain, sheet_name="Mesures", index=False)
    tampon_binaire.seek(0)
    return StreamingResponse(
        tampon_binaire,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=_entete_telechargement(_nom_fichier_horodate("mesures", "xlsx")),
    )


# ---------------------------------------------------------------------------
# GET /export/profils
# ---------------------------------------------------------------------------


@router.get(
    "/profils",
    summary="Exporte les profils horaires au format XLSX (tableau heure × jour)",
    description=(
        "Le classeur contient une feuille « Synthèse » suivie d'une feuille par "
        "tronçon actif. Chaque feuille présente la moyenne des temps de parcours "
        "en minutes, en lignes les heures (0–23) et en colonnes les jours de la "
        "semaine (lundi → dimanche). Format pensé pour les gestionnaires PAA."
    ),
)
async def export_profils(
    format: Literal["xlsx"] = Query("xlsx", description="Seul xlsx est supporté."),
    fenetre_jours: int = Query(
        30,
        description="Largeur de la fenêtre glissante utilisée : 30, 60 ou 90 jours.",
    ),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if fenetre_jours not in (30, 60, 90):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fenetre_jours doit valoir 30, 60 ou 90.",
        )

    # 1. Chargement des tronçons actifs (ordre stable par id)
    troncons: list[Troncon] = list(
        db.execute(
            select(Troncon)
            .where(Troncon.actif.is_(True))
            .order_by(Troncon.id)
        ).scalars()
    )
    if not troncons:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun tronçon actif à exporter.",
        )

    # 2. Chargement de tous les profils pour la fenêtre demandée
    profils: list[ProfilHoraire] = list(
        db.execute(
            select(ProfilHoraire)
            .where(ProfilHoraire.fenetre_jours == fenetre_jours)
        ).scalars()
    )
    if not profils:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Aucun profil horaire calculé pour la fenêtre {fenetre_jours} j. "
                "Lancer d'abord POST /agregation/run."
            ),
        )

    # Indexation rapide : (troncon_id, jour, heure) -> ProfilHoraire
    index_profils: dict[tuple[int, int, int], ProfilHoraire] = {
        (p.troncon_id, p.jour_semaine, p.heure): p for p in profils
    }

    # 3. Construction du classeur — feuille « Synthèse » + une feuille par tronçon
    tampon_binaire = io.BytesIO()
    with pd.ExcelWriter(tampon_binaire, engine="openpyxl") as ecrivain:

        # --- Feuille « Synthèse » : liste des tronçons ---
        synthese = pd.DataFrame(
            [
                {
                    "id": t.id,
                    "tronçon": t.nom,
                    "distance_m": t.distance_m,
                    "vitesse_référence_km_h": t.vitesse_ref_kmh,
                    "temps_référence_s": round(t.temps_reference_s(), 1),
                    "actif": "oui" if t.actif else "non",
                }
                for t in troncons
            ]
        )
        synthese.to_excel(ecrivain, sheet_name="Synthèse", index=False)

        # --- Une feuille par tronçon : tableau heure × jour (moyenne en minutes) ---
        for troncon in troncons:
            # Construction d'un DataFrame 24 lignes × 7 colonnes
            tableau = pd.DataFrame(
                index=range(24),                # heures 0..23
                columns=list(_JOURS_FR),        # Lundi..Dimanche
                dtype="float64",
            )
            tableau.index.name = "Heure"

            for jour_idx, jour_nom in enumerate(_JOURS_FR):
                for heure in range(24):
                    p = index_profils.get((troncon.id, jour_idx, heure))
                    if p is None or p.moyenne is None:
                        continue
                    # secondes → minutes (1 chiffre après la virgule)
                    tableau.at[heure, jour_nom] = round(p.moyenne / 60.0, 1)

            # Nom de feuille : Excel limite à 31 caractères, on tronque proprement
            nom_feuille = f"T{troncon.id} - {troncon.nom}"[:31]
            # Excel interdit aussi certains caractères dans les noms de feuilles
            for caractere_interdit in "[]:*?/\\":
                nom_feuille = nom_feuille.replace(caractere_interdit, " ")

            tableau.to_excel(ecrivain, sheet_name=nom_feuille)

    tampon_binaire.seek(0)
    return StreamingResponse(
        tampon_binaire,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=_entete_telechargement(
            _nom_fichier_horodate(f"profils_fenetre_{fenetre_jours}j", "xlsx")
        ),
    )
