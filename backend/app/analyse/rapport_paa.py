"""Analyse selon la méthodologie DEESP/DEEF (rapport oct. 2025).

Référence : CLAUDE.md § 4.5.

Ce module remplace les calculs FHWA (TTI/PTI/BTI) pour produire les 17
tableaux et 12 graphiques attendus par le rapport DEESP :

  - Tableau 1   → temps théoriques 50 km/h (statique, depuis seed)
  - Tableaux 3-6  → temps minimal par axe × sens × type-jour
  - Tableau 7   → récap min sur les 3 axes
  - Tableaux 8-10 → temps moyen par axe
  - Tableau 11  → récap moyen
  - Tableaux 12-14 → temps maximal par axe
  - Tableau 15  → récap max
  - Tableau 16  → tronçons congestionnés (règles 3-jour-indicatif & 4-semaine)
  - Tableau 17  → récap général des temps de traversée
  - Tableau 19  → comparaison pluriannuelle (2 campagnes)

Critère DEESP de congestion (cf. § 4.5.2) :
    congestionné ⟺ duree_trafic_s > 1.5 × T_ref_50_kmh
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import Mesure, SourceMesure, Troncon


# ---------------------------------------------------------------------------
# Types et constantes
# ---------------------------------------------------------------------------

# Seuils traduisant les couleurs Google Maps (cf. CLAUDE.md § 4.5.2)
RATIO_FLUIDE_MAX = 1.2          # vert
RATIO_ORANGE_COURT_MAX = 1.5    # orange court — encore fluide
RATIO_CONGESTION_MIN = 1.5      # orange long ou rouge → congestionné

TypeJour = Literal["jour_ouvrable", "week_end"]


def _type_jour(d: date) -> TypeJour:
    """Lundi-vendredi → jour_ouvrable ; samedi-dimanche → week_end."""
    return "jour_ouvrable" if d.weekday() < 5 else "week_end"


# ---------------------------------------------------------------------------
# Tableau 1 — Temps théoriques 50 km/h (statique, dérivé du seed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TempsTheorique:
    axe: str
    distance_km: float
    temps_50kmh_s: int
    temps_50kmh_str: str  # ex. "17 mn 53 s"


def temps_theoriques(db: Session) -> list[TempsTheorique]:
    """Reproduit le Tableau 1 du rapport — temps théoriques par axe à 50 km/h."""
    # On déduplique par axe (chaque axe a 2 troncons aller/retour).
    troncons = list(
        db.execute(select(Troncon).where(Troncon.actif.is_(True))).scalars()
    )
    par_axe: dict[str, Troncon] = {}
    for t in troncons:
        # Nom canonique de l'axe = libellé du sens "Origine → ... → Palm Beach"
        nom_axe = _libelle_axe(t.nom)
        if nom_axe not in par_axe:
            par_axe[nom_axe] = t

    resultats: list[TempsTheorique] = []
    for nom, t in par_axe.items():
        temps_s = int(round(t.temps_reference_s()))
        resultats.append(TempsTheorique(
            axe=nom,
            distance_km=round(t.distance_m / 1000.0, 1),
            temps_50kmh_s=temps_s,
            temps_50kmh_str=_format_mn_s(temps_s),
        ))
    return resultats


def _libelle_axe(nom_troncon: str) -> str:
    """Convertit "CARENA → Palm Beach" ou inverse en "CARENA - Palm Beach"."""
    parts = nom_troncon.split(" → ")
    if len(parts) != 2:
        return nom_troncon
    a, b = parts[0].strip(), parts[1].strip()
    # Palm Beach est commun aux 3 axes → on met l'autre en tête
    if "Palm Beach" in a:
        a, b = b, a
    return f"{a} - {b}"


def _format_mn_s(secondes: int) -> str:
    """Formate des secondes en "X mn YY s" (style rapport DEESP)."""
    mn = secondes // 60
    sec = secondes % 60
    return f"{mn} mn {sec:02d} s"


# ---------------------------------------------------------------------------
# Tableaux 3-7 — Temps MINIMAL par axe × sens × type-jour
# Tableaux 8-11 — Temps MOYEN
# Tableaux 12-15 — Temps MAXIMAL
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TempsTraverseeStat:
    troncon_id: int
    troncon_nom: str
    type_jour: TypeJour
    nb_mesures: int
    temps_min_mn: int | None
    temps_moyen_mn: int | None
    temps_max_mn: int | None


def temps_traversee_par_troncon(
    db: Session,
    debut_utc: datetime,
    fin_utc: datetime,
) -> list[TempsTraverseeStat]:
    """Calcule min/moyen/max par tronçon × type_jour sur la fenêtre demandée.

    Reproduit la logique des Tableaux 3-15 :
      - Filtre les mesures Google avec `duree_trafic_s NOT NULL`
      - Convertit l'horodatage UTC en local Africa/Abidjan
      - Groupe par (troncon_id, type_jour)
      - Pour le temps moyen : moyenne des moyennes journalières
        (pas la moyenne brute, suivant l'énoncé § 4.5.4)
    """
    fuseau_local = ZoneInfo(get_settings().tz)

    troncons = list(
        db.execute(
            select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
        ).scalars()
    )

    mesures = list(
        db.execute(
            select(Mesure).where(
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.is_not(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_utc,
                Mesure.horodatage <= fin_utc,
            )
        ).scalars()
    )

    # Group key : (troncon_id, type_jour, date_locale) → list[duree_trafic_s]
    par_jour: dict[tuple[int, TypeJour, date], list[int]] = defaultdict(list)
    for m in mesures:
        d_local = m.horodatage.astimezone(fuseau_local).date()
        tj = _type_jour(d_local)
        par_jour[(m.troncon_id, tj, d_local)].append(m.duree_trafic_s)

    # Group key : (troncon_id, type_jour) → list[moyennes_journalières (mn)]
    moyennes_par_jour: dict[tuple[int, TypeJour], list[float]] = defaultdict(list)
    mins: dict[tuple[int, TypeJour], int] = {}
    maxs: dict[tuple[int, TypeJour], int] = {}
    nb_par_tj: dict[tuple[int, TypeJour], int] = defaultdict(int)

    for (tid, tj, _d), durees_s in par_jour.items():
        moyenne_jour_mn = statistics.fmean(durees_s) / 60.0
        moyennes_par_jour[(tid, tj)].append(moyenne_jour_mn)
        min_jour = min(durees_s)
        max_jour = max(durees_s)
        cle = (tid, tj)
        if cle not in mins or min_jour < mins[cle]:
            mins[cle] = min_jour
        if cle not in maxs or max_jour > maxs[cle]:
            maxs[cle] = max_jour
        nb_par_tj[cle] += len(durees_s)

    resultats: list[TempsTraverseeStat] = []
    for t in troncons:
        for tj in ("jour_ouvrable", "week_end"):
            cle = (t.id, tj)
            if cle not in nb_par_tj:
                resultats.append(TempsTraverseeStat(
                    troncon_id=t.id, troncon_nom=t.nom, type_jour=tj,
                    nb_mesures=0,
                    temps_min_mn=None, temps_moyen_mn=None, temps_max_mn=None,
                ))
                continue
            moyenne_des_moyennes = statistics.fmean(moyennes_par_jour[cle])
            resultats.append(TempsTraverseeStat(
                troncon_id=t.id,
                troncon_nom=t.nom,
                type_jour=tj,
                nb_mesures=nb_par_tj[cle],
                temps_min_mn=int(round(mins[cle] / 60)),
                temps_moyen_mn=int(round(moyenne_des_moyennes)),
                temps_max_mn=int(round(maxs[cle] / 60)),
            ))
    return resultats


# ---------------------------------------------------------------------------
# Tableau 16 — Tronçons congestionnés selon règles DEESP
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CongestionHoraire:
    troncon_id: int
    troncon_nom: str
    heure: int  # 7..18
    nb_jours_congestionnes_par_type: dict[str, int]  # weekday name → nb fois congestionné à cette heure
    nb_total_semaine: int  # toutes occurrences toutes journées confondues
    regle_jour_indicatif: bool  # ≥ 3 fois sur un jour-type donné
    regle_semaine: bool  # ≥ 4 fois la même heure n'importe quel jour


def troncons_congestionnes(
    db: Session,
    debut_utc: datetime,
    fin_utc: datetime,
) -> list[CongestionHoraire]:
    """Applique les règles § 4.5.3 pour identifier les tronçons congestionnés.

    Méthodologie DEESP :
      1. Pour chaque mesure : congestionné si duree_trafic > 1.5 × T_ref
      2. Pour chaque (troncon, jour-semaine, heure) : on cumule le nb
         d'occurrences congestionnées sur la fenêtre.
      3. Règle JOUR : congestionné si ≥ 3 fois sur les lundis (ou mardis…)
      4. Règle SEMAINE : congestionné si ≥ 4 fois à cette heure dans la
         semaine, peu importe le jour.
    """
    fuseau_local = ZoneInfo(get_settings().tz)

    troncons = {
        t.id: t for t in db.execute(
            select(Troncon).where(Troncon.actif.is_(True))
        ).scalars()
    }

    mesures = list(
        db.execute(
            select(Mesure).where(
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.is_not(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_utc,
                Mesure.horodatage <= fin_utc,
            )
        ).scalars()
    )

    # Clé : (troncon_id, weekday[0=lundi...6=dimanche], heure_locale)
    #        → nb occurrences congestionnées
    occurrences: dict[tuple[int, int, int], int] = defaultdict(int)
    for m in mesures:
        t = troncons.get(m.troncon_id)
        if t is None:
            continue
        t_ref = t.temps_reference_s()
        if t_ref <= 0:
            continue
        ratio = m.duree_trafic_s / t_ref
        if ratio < RATIO_CONGESTION_MIN:
            continue  # fluide ou orange court → ne compte pas
        local = m.horodatage.astimezone(fuseau_local)
        occurrences[(t.id, local.weekday(), local.hour)] += 1

    # Agrégation par (troncon, heure) — règle SEMAINE
    par_troncon_heure: dict[tuple[int, int], dict[int, int]] = defaultdict(dict)
    for (tid, wd, h), nb in occurrences.items():
        par_troncon_heure[(tid, h)][wd] = nb

    NOMS_JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    resultats: list[CongestionHoraire] = []
    for (tid, h), par_jour in par_troncon_heure.items():
        # Règle JOUR : un jour-indicatif a ≥ 3 occurrences sur la fenêtre
        regle_jour = any(nb >= 3 for nb in par_jour.values())
        # Règle SEMAINE : sur la semaine on a ≥ 4 occurrences toutes journées
        # confondues à cette heure
        nb_total = sum(par_jour.values())
        regle_sem = nb_total >= 4
        if not (regle_jour or regle_sem):
            continue
        t = troncons[tid]
        resultats.append(CongestionHoraire(
            troncon_id=tid,
            troncon_nom=t.nom,
            heure=h,
            nb_jours_congestionnes_par_type={
                NOMS_JOURS_FR[wd]: nb for wd, nb in par_jour.items()
            },
            nb_total_semaine=nb_total,
            regle_jour_indicatif=regle_jour,
            regle_semaine=regle_sem,
        ))
    # Trie : par troncon puis par heure
    resultats.sort(key=lambda r: (r.troncon_id, r.heure))
    return resultats


# ---------------------------------------------------------------------------
# Graphiques 1-12 — séries pour BarChart (min/max par jour x type-jour)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PointGraphique:
    date_locale: str   # "YYYY-MM-DD"
    libelle_jour: str  # "Lundi", "Mardi"... pour l'axe X
    temps_mn: int


def serie_graphique(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    agregat: Literal["min", "max"],
) -> list[PointGraphique]:
    """Construit la série pour les graphiques DEESP 1-12 (BarChart).

    Chaque barre = un jour de la campagne, hauteur = min ou max observé
    sur la journée, en minutes.
    """
    fuseau_local = ZoneInfo(get_settings().tz)
    NOMS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    mesures = list(
        db.execute(
            select(Mesure).where(
                Mesure.troncon_id == troncon_id,
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.is_not(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_utc,
                Mesure.horodatage <= fin_utc,
            )
        ).scalars()
    )

    par_jour: dict[date, list[int]] = defaultdict(list)
    for m in mesures:
        d = m.horodatage.astimezone(fuseau_local).date()
        par_jour[d].append(m.duree_trafic_s)

    resultats: list[PointGraphique] = []
    for d in sorted(par_jour):
        durees = par_jour[d]
        valeur_s = min(durees) if agregat == "min" else max(durees)
        resultats.append(PointGraphique(
            date_locale=d.isoformat(),
            libelle_jour=NOMS[d.weekday()],
            temps_mn=int(round(valeur_s / 60)),
        ))
    return resultats


# ---------------------------------------------------------------------------
# Tableau 19 — Comparaison pluriannuelle
# ---------------------------------------------------------------------------


def comparaison_campagnes(
    db: Session,
    campagne_a: tuple[date, date],
    campagne_b: tuple[date, date],
) -> list[dict]:
    """Compare 2 campagnes (Tableau 19 du rapport).

    Args:
        campagne_a, campagne_b : tuples (date_debut, date_fin) locaux
    """
    fuseau_local = ZoneInfo(get_settings().tz)

    def fenetre_utc(c: tuple[date, date]) -> tuple[datetime, datetime]:
        d, f = c
        return (
            datetime.combine(d, time.min, tzinfo=fuseau_local).astimezone(timezone.utc),
            datetime.combine(f, time.max, tzinfo=fuseau_local).astimezone(timezone.utc),
        )

    debut_a, fin_a = fenetre_utc(campagne_a)
    debut_b, fin_b = fenetre_utc(campagne_b)

    stats_a = {(s.troncon_id, s.type_jour): s for s in
               temps_traversee_par_troncon(db, debut_a, fin_a)}
    stats_b = {(s.troncon_id, s.type_jour): s for s in
               temps_traversee_par_troncon(db, debut_b, fin_b)}

    troncons = list(
        db.execute(
            select(Troncon).where(Troncon.actif.is_(True)).order_by(Troncon.id)
        ).scalars()
    )

    lignes = []
    for t in troncons:
        for tj in ("jour_ouvrable", "week_end"):
            a = stats_a.get((t.id, tj))
            b = stats_b.get((t.id, tj))
            lignes.append({
                "troncon_id": t.id,
                "troncon_nom": t.nom,
                "type_jour": tj,
                "campagne_a": {
                    "min_mn": a.temps_min_mn if a else None,
                    "moy_mn": a.temps_moyen_mn if a else None,
                    "max_mn": a.temps_max_mn if a else None,
                } if a else None,
                "campagne_b": {
                    "min_mn": b.temps_min_mn if b else None,
                    "moy_mn": b.temps_moyen_mn if b else None,
                    "max_mn": b.temps_max_mn if b else None,
                } if b else None,
                "delta_moyen_mn": (
                    (b.temps_moyen_mn - a.temps_moyen_mn)
                    if a and b and a.temps_moyen_mn is not None and b.temps_moyen_mn is not None
                    else None
                ),
            })
    return lignes


# ---------------------------------------------------------------------------
# Helpers pour les endpoints API
# ---------------------------------------------------------------------------


def fenetre_campagne(annee: int, mois: int) -> tuple[date, date]:
    """Retourne (1er du mois, dernier jour du mois) — une campagne DEESP."""
    debut = date(annee, mois, 1)
    if mois == 12:
        fin = date(annee + 1, 1, 1) - timedelta(days=1)
    else:
        fin = date(annee, mois + 1, 1) - timedelta(days=1)
    return debut, fin


def fenetre_jours_glissants(nb_jours: int) -> tuple[date, date]:
    """Retourne (aujourd'hui - N, aujourd'hui)."""
    fuseau_local = ZoneInfo(get_settings().tz)
    aujourd_hui = datetime.now(tz=fuseau_local).date()
    return (aujourd_hui - timedelta(days=nb_jours), aujourd_hui)
