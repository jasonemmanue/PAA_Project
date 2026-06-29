"""Routeur /evolution — exposition de la table evolution_indicateur (P6.1).

Endpoints :
  - GET /evolution                   → tous les enregistrements (filtres optionnels)
  - GET /evolution/axes              → liste des axes / sens disponibles
  - GET /evolution/troncon/{id}      → campagnes historiques + mois courant live
"""

from __future__ import annotations

import statistics
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import EvolutionIndicateur, Mesure, SourceMesure, Troncon


router = APIRouter(prefix="/evolution", tags=["évolution pluriannuelle"])

# ---------------------------------------------------------------------------
# Mapping tronçon id → (axe, sens) dans la table evolution_indicateur.
# Correspond aux libellés exacts importés depuis la feuille SYNTHESE COMPAREE.
# ---------------------------------------------------------------------------
_TRONCON_VERS_AXE_SENS: dict[int, tuple[str, str]] = {
    1: ("CARENA → Pharmacie Palm Beach", "Aller"),
    2: ("CARENA → Pharmacie Palm Beach", "Retour"),
    3: ("Toyota CFAO → Pharmacie Palm Beach", "Aller"),
    4: ("Toyota CFAO → Pharmacie Palm Beach", "Retour"),
    5: ("Agence SODECI → Pharmacie Palm Beach", "Aller"),
    6: ("Agence SODECI → Pharmacie Palm Beach", "Retour"),
}

_MOIS_NUM: dict[str, int] = {
    "jan": 1, "fev": 2, "mar": 3, "avr": 4, "mai": 5, "jun": 6,
    "jul": 7, "jui": 7, "aou": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_MOIS_LABEL_FR: dict[str, str] = {
    "jan": "Jan", "fev": "Fév", "mar": "Mar", "avr": "Avr", "mai": "Mai",
    "jun": "Juin", "jul": "Juil", "jui": "Juil", "aou": "Août",
    "sep": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Déc",
}


def _periode_sort_key(periode: str) -> int:
    """'oct_2025' → 202510, 'fev_2026' → 202602 — tri chronologique."""
    parts = periode.lower().split("_")
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1]) * 100 + _MOIS_NUM.get(parts[0][:3], 0)
    return 0


def _periode_label(periode: str) -> str:
    """'oct_2025' → 'Oct 2025', 'fev_2026' → 'Fév 2026'."""
    parts = periode.lower().split("_")
    if len(parts) == 2 and parts[1].isdigit():
        mois = _MOIS_LABEL_FR.get(parts[0][:3], parts[0].capitalize())
        return f"{mois} {parts[1]}"
    return periode


def _code_mois_courant(fuseau: ZoneInfo) -> str:
    """Retourne le code periode du mois courant, ex. 'jun_2026'."""
    maintenant = datetime.now(tz=fuseau)
    mois_abbr = ["jan", "fev", "mar", "avr", "mai", "jun",
                 "jul", "aou", "sep", "oct", "nov", "dec"]
    return f"{mois_abbr[maintenant.month - 1]}_{maintenant.year}"


def _stats_mois_courant_par_troncon(
    db: Session, troncon_id: int
) -> dict[str, Any]:
    """Stats min/moyen/max depuis le 1er du mois courant, par type de jour."""
    fuseau = ZoneInfo(get_settings().tz)
    maintenant_local = datetime.now(tz=fuseau)
    maintenant_utc = maintenant_local.astimezone(timezone.utc)

    debut_mois_date = maintenant_local.date().replace(day=1)
    debut_mois_utc = datetime.combine(
        debut_mois_date, time(0, 0), tzinfo=fuseau
    ).astimezone(timezone.utc)

    rows = list(
        db.execute(
            select(Mesure.duree_trafic_s, Mesure.horodatage)
            .where(
                Mesure.troncon_id == troncon_id,
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.is_not(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_mois_utc,
                Mesure.horodatage <= maintenant_utc,
            )
        ).all()
    )

    par_type: dict[str, list[float]] = {"jour_ouvrable": [], "week_end": []}
    for duree_s, horodatage in rows:
        if duree_s is None:
            continue
        h_local = (
            horodatage.astimezone(fuseau)
            if horodatage.tzinfo
            else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
        )
        tj = "week_end" if h_local.weekday() >= 5 else "jour_ouvrable"
        par_type[tj].append(duree_s / 60.0)

    def _calc(valeurs: list[float]) -> dict | None:
        if not valeurs:
            return None
        return {
            "min_mn": round(min(valeurs), 1),
            "moyen_mn": round(statistics.fmean(valeurs), 1),
            "max_mn": round(max(valeurs), 1),
            "nb_mesures": len(valeurs),
        }

    return {
        "debut": debut_mois_date.isoformat(),
        "fin": maintenant_local.date().isoformat(),
        "jour_ouvrable": _calc(par_type["jour_ouvrable"]),
        "week_end": _calc(par_type["week_end"]),
        "nb_mesures_total": len(rows),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/troncon/{troncon_id}",
    summary="Évolution pluriannuelle par tronçon — historique + mois courant",
    description=(
        "Retourne les campagnes de mesure passées (depuis `evolution_indicateur`) "
        "pour le tronçon sélectionné, triées chronologiquement, plus les statistiques "
        "du mois calendaire courant calculées en temps réel depuis la table `mesures`. "
        "Le frontend affiche les 2 campagnes complètes les plus récentes + le mois courant."
    ),
)
async def evolution_par_troncon(
    troncon_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tronçon id={troncon_id} introuvable.",
        )

    fuseau = ZoneInfo(get_settings().tz)

    # --- Données historiques (table evolution_indicateur) ---
    campagnes_historiques: list[dict] = []
    mapping = _TRONCON_VERS_AXE_SENS.get(troncon_id)
    if mapping is not None:
        axe_nom, sens_nom = mapping
        lignes = list(
            db.execute(
                select(EvolutionIndicateur)
                .where(
                    EvolutionIndicateur.axe == axe_nom,
                    EvolutionIndicateur.sens == sens_nom,
                )
                .order_by(EvolutionIndicateur.periode, EvolutionIndicateur.type_jour)
            ).scalars()
        )

        # Regroupe par période → { type_jour: {min, moyen, max} }
        par_periode: dict[str, dict] = {}
        for l in lignes:
            if l.periode not in par_periode:
                par_periode[l.periode] = {"jours_ouvrables": None, "week_ends": None}
            bloc = {
                "min_mn": round(l.temps_min_s / 60, 1) if l.temps_min_s is not None else None,
                "moyen_mn": round(l.temps_moyen_s / 60, 1) if l.temps_moyen_s is not None else None,
                "max_mn": round(l.temps_max_s / 60, 1) if l.temps_max_s is not None else None,
            }
            if l.type_jour == "Jours ouvrables":
                par_periode[l.periode]["jours_ouvrables"] = bloc
            elif l.type_jour == "Week-ends":
                par_periode[l.periode]["week_ends"] = bloc

        # Tri chronologique
        for periode, blocs in sorted(par_periode.items(), key=lambda x: _periode_sort_key(x[0])):
            campagnes_historiques.append({
                "periode": periode,
                "periode_label": _periode_label(periode),
                "source": "historique",
                "jours_ouvrables": blocs["jours_ouvrables"],
                "week_ends": blocs["week_ends"],
            })

    # --- Mois courant (table mesures, temps réel) ---
    code_mois = _code_mois_courant(fuseau)
    stats_live = _stats_mois_courant_par_troncon(db, troncon_id)

    campagne_live = {
        "periode": code_mois,
        "periode_label": f"{_periode_label(code_mois)} (en cours)",
        "source": "live",
        "debut": stats_live["debut"],
        "fin": stats_live["fin"],
        "nb_mesures_total": stats_live["nb_mesures_total"],
        "jours_ouvrables": stats_live["jour_ouvrable"],
        "week_ends": stats_live["week_end"],
    }

    return {
        "troncon_id": troncon_id,
        "troncon_nom": troncon.nom,
        "a_donnees_historiques": len(campagnes_historiques) > 0,
        "campagnes": campagnes_historiques + [campagne_live],
    }


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
