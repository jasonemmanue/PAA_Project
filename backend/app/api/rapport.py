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
from datetime import date as DateType, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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


def _bornes_utc(
    campagne: str,
    debut_override: DateType | None,
    fin_override: DateType | None,
) -> tuple[datetime, datetime]:
    """Résout les bornes UTC en tenant compte des overrides optionnels debut/fin."""
    debut_utc, fin_utc = _parser_campagne(campagne)
    fuseau_local = ZoneInfo(get_settings().tz)
    if debut_override is not None:
        debut_utc = datetime.combine(debut_override, time.min, tzinfo=fuseau_local).astimezone(timezone.utc)
    if fin_override is not None:
        fin_utc = datetime.combine(fin_override, time.max, tzinfo=fuseau_local).astimezone(timezone.utc)
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
    debut: DateType | None = Query(None, description="Date de début (YYYY-MM-DD) — affine la fenêtre à l'intérieur du mois."),
    fin: DateType | None = Query(None, description="Date de fin (YYYY-MM-DD) — affine la fenêtre à l'intérieur du mois."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    debut_utc, fin_utc = _bornes_utc(campagne, debut, fin)
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
        "Couleur Google Maps lue par tronçon : ROUGE OU ORANGE ≥ 50 % → "
        "congestionné (cf. rapport DEESP/DEEF oct. 2025, section "
        "METHODOLOGIE)."
    ),
)
async def get_zones_congestionnees(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    debut: DateType | None = Query(None, description="Date de début (YYYY-MM-DD) — affine la fenêtre à l'intérieur du mois."),
    fin: DateType | None = Query(None, description="Date de fin (YYYY-MM-DD) — affine la fenêtre à l'intérieur du mois."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    debut_utc, fin_utc = _bornes_utc(campagne, debut, fin)
    cong = rapport_paa.troncons_congestionnes(db, debut_utc, fin_utc)
    nb_jours = max(1, (fin_utc - debut_utc).days + 1)
    seuil_j, seuil_s = rapport_paa.seuils_congestion(debut_utc, fin_utc)
    return {
        "campagne": campagne,
        "nb_jours_plage": nb_jours,
        "nb_entrees": len(cong),
        "regles": {
            "critere_mesure": (
                "Couleur Google Maps : ROUGE OU ORANGE sur ≥ 50 % du tronçon"
            ),
            "seuil_orange_long_pct": 50.0,
            "seuil_jour_effectif": seuil_j,
            "seuil_semaine_effectif": seuil_s,
            "regle_jour_indicatif": f"≥ {seuil_j} occurrence(s) sur le même jour de la semaine",
            "regle_semaine": f"≥ {seuil_s} occurrence(s) à la même heure dans la semaine",
            "adaptatif": nb_jours < 28,
        },
        "entrees": [
            {
                "troncon_id": c.troncon_id,
                "troncon_nom": c.troncon_nom,
                "sous_troncon_id": c.sous_troncon_id,
                "sous_troncon_code": c.sous_troncon_code,
                "sous_troncon_nom": c.sous_troncon_nom,
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
# GET /rapport/zones-congestionnees/pdf — téléchargement direct
# ---------------------------------------------------------------------------


@router.get(
    "/zones-congestionnees/pdf",
    summary="Tableau 16 au format PDF (téléchargement direct)",
    description=(
        "Génère un PDF A4 paysage contenant le Tableau 16. Le navigateur "
        "déclenchera un téléchargement immédiat grâce à l'en-tête "
        "Content-Disposition: attachment."
    ),
    response_class=Response,
)
async def get_zones_congestionnees_pdf(
    campagne: str = Query(..., description="Format 'AAAA-MM'."),
    debut: DateType | None = Query(None),
    fin: DateType | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    from fpdf import FPDF  # import local : évite de charger fpdf au démarrage

    debut_utc, fin_utc = _bornes_utc(campagne, debut, fin)
    cong = rapport_paa.troncons_congestionnes(db, debut_utc, fin_utc)
    seuil_j, seuil_s = rapport_paa.seuils_congestion(debut_utc, fin_utc)
    nb_jours = max(1, (fin_utc - debut_utc).days + 1)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()

    # En-tête
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, "Tableau 16 - Troncons congestionnes (regles DEESP)", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 5, f"Campagne : {campagne}    -    {nb_jours} jour(s) analyse(s)", ln=True)
    pdf.set_text_color(85, 85, 85)
    pdf.set_font("Helvetica", "", 8)
    desc = (
        f"Critere par mesure : couleur Google Maps - ROUGE OU ORANGE >= 50%. "
        f"Seuils appliques : >= {seuil_j} occurrence(s) / jour-indicatif OU "
        f">= {seuil_s} occurrence(s) / semaine."
    )
    pdf.multi_cell(0, 4, desc)
    pdf.ln(2)

    # En-tête du tableau
    pdf.set_fill_color(26, 54, 93)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    largeurs = [60, 35, 25, 18, 30, 110]  # mm — total = 278
    entetes = ["AXE", "SOUS-TRONCON", "TRANCHE", "NB/SEM.", "REGLE", "REPARTITION PAR JOUR"]
    for w, h in zip(largeurs, entetes):
        pdf.cell(w, 7, h, border=1, fill=True, align="L")
    pdf.ln()

    # Lignes
    pdf.set_text_color(17, 17, 17)
    pdf.set_font("Helvetica", "", 8)
    if not cong:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(sum(largeurs), 10, "Aucun troncon congestionne sur cette campagne.",
                 border=1, align="C")
    else:
        for i, c in enumerate(cong):
            if i % 2 == 1:
                pdf.set_fill_color(249, 250, 251)
                fill = True
            else:
                pdf.set_fill_color(255, 255, 255)
                fill = True
            sous = (
                f"{c.sous_troncon_code} - {c.sous_troncon_nom or ''}"
                if c.sous_troncon_code
                else "axe entier"
            )
            tranche = f"{c.heure:02d}h-{c.heure + 1:02d}h"
            regles = []
            if c.regle_jour_indicatif:
                regles.append(f">={seuil_j}/jour")
            if c.regle_semaine:
                regles.append(f">={seuil_s}/sem")
            regle_txt = " | ".join(regles) or "-"
            repartition = " ".join(
                f"{j[:3]}:{n}" for j, n in c.nb_jours_congestionnes_par_type.items()
            )

            ligne = [
                (largeurs[0], (c.troncon_nom or "")[:45]),
                (largeurs[1], sous[:25]),
                (largeurs[2], tranche),
                (largeurs[3], str(c.nb_total_semaine)),
                (largeurs[4], regle_txt),
                (largeurs[5], repartition[:80]),
            ]
            for w, txt in ligne:
                pdf.cell(w, 6, txt, border=1, fill=fill, align="L")
            pdf.ln()

    # Pied de page
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 4,
             "Genere par PAA-Traverse - Port Autonome d'Abidjan - "
             f"Methodologie DEESP rapport octobre 2025", ln=True)

    # Réponse — bytearray → bytes pour httpx/starlette
    contenu = bytes(pdf.output())
    nom = f"tableau16_{campagne}.pdf"
    return Response(
        content=contenu,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


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
