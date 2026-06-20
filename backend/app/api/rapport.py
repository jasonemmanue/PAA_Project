"""Routeur `/rapport` — endpoints alignés sur la méthodologie DEESP/DEEF.

Reproduit les 17 tableaux + 12 graphiques du rapport officiel
*« Evaluation du temps de traversée — octobre 2025 »* du PAA.

Endpoints :
  - GET /rapport/temps-theoriques       → Tableau 1
  - GET /rapport/temps-traversee?campagne=AAAA-MM → Tableaux 3-17
  - GET /rapport/zones-congestionnees?campagne=AAAA-MM → Tableau 16
  - GET /rapport/graphique/{troncon_id}?agregat=min|max&campagne=AAAA-MM
                                        → données pour BarChart 1-12
  - GET /rapport/comparaison?campagne_a=AAAA-MM&campagne_b=AAAA-MM → Tableau 19

Le paramètre `campagne` accepte un format `AAAA-MM` (ex. `2026-02`) et est
résolu en (1er du mois, dernier jour du mois) côté serveur.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analyse import rapport_paa
from app.core.config import get_settings
from app.db.session import get_db


router = APIRouter(prefix="/rapport", tags=["rapport DEESP"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_REGEX_CAMPAGNE = re.compile(r"^(\d{4})-(\d{2})$")


def _parser_campagne(libelle: str) -> tuple[datetime, datetime]:
    """Convertit 'AAAA-MM' en (debut_utc, fin_utc) couvrant le mois entier."""
    m = _REGEX_CAMPAGNE.match(libelle)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format attendu : 'AAAA-MM' (ex. '2026-02').",
        )
    annee, mois = int(m.group(1)), int(m.group(2))
    if not (1 <= mois <= 12):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le mois doit être compris entre 1 et 12.",
        )
    debut, fin = rapport_paa.fenetre_campagne(annee, mois)
    fuseau_local = ZoneInfo(get_settings().tz)
    debut_utc = datetime.combine(debut, time.min, tzinfo=fuseau_local).astimezone(timezone.utc)
    fin_utc = datetime.combine(fin, time.max, tzinfo=fuseau_local).astimezone(timezone.utc)
    return debut_utc, fin_utc


# ---------------------------------------------------------------------------
# GET /rapport/temps-theoriques
# ---------------------------------------------------------------------------


@router.get(
    "/temps-theoriques",
    summary="Tableau 1 — Temps théoriques 50 km/h par axe",
    description=(
        "Renvoie le Tableau 1 du rapport : distance et temps théorique à "
        "50 km/h pour chacun des 3 axes officiels. Données statiques "
        "dérivées du seed des tronçons."
    ),
)
async def get_temps_theoriques(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lignes = rapport_paa.temps_theoriques(db)
    return {
        "tableau": "Tableau 1 — Temps de traversée normal pour 50 km/h",
        "lignes": [
            {
                "axe": tt.axe,
                "distance_km": tt.distance_km,
                "temps_50kmh_s": tt.temps_50kmh_s,
                "temps_50kmh": tt.temps_50kmh_str,
            }
            for tt in lignes
        ],
    }


# ---------------------------------------------------------------------------
# GET /rapport/temps-traversee
# ---------------------------------------------------------------------------


@router.get(
    "/temps-traversee",
    summary="Tableaux 3-17 — Min/Moyen/Max par tronçon × type-jour",
    description=(
        "Renvoie pour chaque tronçon et chaque type de jour "
        "(`jour_ouvrable` / `week_end`) les temps minimal, moyen et maximal "
        "en minutes sur la campagne demandée. C'est la base de tous les "
        "tableaux 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 et 17."
    ),
)
async def get_temps_traversee(
    campagne: str = Query(
        ..., description="Format 'AAAA-MM', ex. '2026-02' pour février 2026",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    debut_utc, fin_utc = _parser_campagne(campagne)
    stats = rapport_paa.temps_traversee_par_troncon(db, debut_utc, fin_utc)
    return {
        "campagne": campagne,
        "debut_utc": debut_utc.isoformat(),
        "fin_utc": fin_utc.isoformat(),
        "nb_lignes": len(stats),
        "lignes": [
            {
                "troncon_id": s.troncon_id,
                "troncon_nom": s.troncon_nom,
                "type_jour": s.type_jour,
                "nb_mesures": s.nb_mesures,
                "temps_min_mn": s.temps_min_mn,
                "temps_moyen_mn": s.temps_moyen_mn,
                "temps_max_mn": s.temps_max_mn,
            }
            for s in stats
        ],
    }


# ---------------------------------------------------------------------------
# GET /rapport/zones-congestionnees
# ---------------------------------------------------------------------------


@router.get(
    "/zones-congestionnees",
    summary="Tableau 16 — Tronçons congestionnés selon règles DEESP",
    description=(
        "Applique les règles du § 4.5.3 du CLAUDE.md (extraites du rapport) :\n\n"
        "- **Règle JOUR** : tronçon congestionné si ≥ 3 fois sur un même "
        "  jour-indicatif (ex. 3 lundis sur 4) à la même heure.\n"
        "- **Règle SEMAINE** : tronçon congestionné si ≥ 4 fois à la même "
        "  heure dans la semaine, tous jours confondus.\n\n"
        "Le critère de congestion d'une mesure individuelle est "
        "`duree_trafic_s > 1.5 × T_ref_50kmh` (équivalent rouge ou "
        "orange-long Google Maps)."
    ),
)
async def get_zones_congestionnees(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    debut_utc, fin_utc = _parser_campagne(campagne)
    cong = rapport_paa.troncons_congestionnes(db, debut_utc, fin_utc)
    return {
        "campagne": campagne,
        "nb_entrees": len(cong),
        "regles": {
            "ratio_congestion_min": rapport_paa.RATIO_CONGESTION_MIN,
            "regle_jour_indicatif": "≥ 3 occurrences sur le même jour de la semaine",
            "regle_semaine": "≥ 4 occurrences à la même heure dans la semaine",
        },
        "entrees": [
            {
                "troncon_id": c.troncon_id,
                "troncon_nom": c.troncon_nom,
                "heure": c.heure,
                "tranche": f"{c.heure:02d}h-{c.heure + 1:02d}h",
                "nb_par_jour_semaine": c.nb_jours_congestionnes_par_type,
                "nb_total_semaine": c.nb_total_semaine,
                "regle_jour_indicatif": c.regle_jour_indicatif,
                "regle_semaine": c.regle_semaine,
            }
            for c in cong
        ],
    }


# ---------------------------------------------------------------------------
# GET /rapport/graphique/{troncon_id}
# ---------------------------------------------------------------------------


@router.get(
    "/graphique/{troncon_id}",
    summary="Données BarChart pour Graphiques 1-12 (min ou max par jour)",
    description=(
        "Renvoie une série prête à tracer en BarChart Recharts. Chaque "
        "point = un jour de la campagne, hauteur = temps min ou max observé "
        "ce jour-là sur ce tronçon. C'est le format attendu pour les "
        "Graphiques 1, 3, 5 (temps min sens aller), 2, 4, 6 (temps min "
        "sens retour), 7, 9, 11 (temps max aller) et 8, 10, 12 (temps max "
        "retour) du rapport."
    ),
)
async def get_graphique(
    troncon_id: int,
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    agregat: str = Query("min", description="`min` ou `max`."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if agregat not in ("min", "max"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`agregat` doit valoir 'min' ou 'max'.",
        )
    debut_utc, fin_utc = _parser_campagne(campagne)
    serie = rapport_paa.serie_graphique(
        db, troncon_id, debut_utc, fin_utc, agregat=agregat,
    )
    return {
        "troncon_id": troncon_id,
        "campagne": campagne,
        "agregat": agregat,
        "axe_y_unite": "minutes",
        "nb_points": len(serie),
        "points": [
            {
                "date": p.date_locale,
                "libelle_jour": p.libelle_jour,
                "temps_mn": p.temps_mn,
            }
            for p in serie
        ],
    }


# ---------------------------------------------------------------------------
# GET /rapport/comparaison
# ---------------------------------------------------------------------------


@router.get(
    "/comparaison",
    summary="Tableau 19 — Comparaison pluriannuelle entre 2 campagnes",
    description=(
        "Reproduit le Tableau 19 du rapport (comparaison fév 2025 vs "
        "oct 2025). Pour chaque tronçon × type-jour, renvoie min/moyen/max "
        "des deux campagnes et le delta du temps moyen."
    ),
)
async def get_comparaison(
    campagne_a: str = Query(
        ..., description="Campagne de référence, format 'AAAA-MM'.",
    ),
    campagne_b: str = Query(
        ..., description="Campagne comparée, format 'AAAA-MM'.",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    debut_a_utc, fin_a_utc = _parser_campagne(campagne_a)
    debut_b_utc, fin_b_utc = _parser_campagne(campagne_b)
    # rapport_paa.comparaison_campagnes attend des dates locales — on
    # reconstruit depuis nos UTC.
    fuseau_local = ZoneInfo(get_settings().tz)
    debut_a = debut_a_utc.astimezone(fuseau_local).date()
    fin_a = fin_a_utc.astimezone(fuseau_local).date()
    debut_b = debut_b_utc.astimezone(fuseau_local).date()
    fin_b = fin_b_utc.astimezone(fuseau_local).date()
    lignes = rapport_paa.comparaison_campagnes(
        db, (debut_a, fin_a), (debut_b, fin_b),
    )
    return {
        "campagne_a": campagne_a,
        "campagne_b": campagne_b,
        "nb_lignes": len(lignes),
        "lignes": lignes,
    }
