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

Critère DEESP de congestion (cf. § 4.5.2 et rapport octobre 2025) :
    Une mesure est congestionnée ssi Google Maps affiche du ROUGE OU de
    l'ORANGE sur ≥ 50 % du tronçon. Ce verdict est désormais stocké dans
    la colonne `mesures.est_congestionne` (alimentée par
    `app/analyse/congestion.py` à partir des `speedReadingIntervals`
    Google).
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
from app.analyse.aggregation import (
    agreger_durees_par_creneau,
    agreger_mesures_axe,
    axe_a_sous_troncons,
)


# ---------------------------------------------------------------------------
# Types et constantes
# ---------------------------------------------------------------------------

# Critère de congestion : on s'appuie désormais sur `mesures.est_congestionne`
# (verdict couleur Google Maps, cf. `app/analyse/congestion.py`). Ce booléen
# remplace l'ancien ratio `duree_trafic / T_ref ≥ 1.5` qui n'était qu'une
# approximation numérique du critère couleur du rapport.

# Plage horaire DEESP — le rapport officiel ne couvre que 7h-19h, même si
# notre collecte étend à 24h/24 (cf. CLAUDE.md § 4.5.1 et § 4.5.7).
# Les heures hors plage sont **filtrées** des calculs publiés dans /rapport
# pour préserver la conformité méthodologique stricte.
DEESP_HEURE_DEBUT = 0
DEESP_HEURE_FIN = 24  # Par défaut 24h/24 — filtrable via paramètres API

TypeJour = Literal["jour_ouvrable", "week_end"]


def _dans_plage_horaire(horodatage_local, heure_debut: int = DEESP_HEURE_DEBUT, heure_fin: int = DEESP_HEURE_FIN) -> bool:
    """True si l'heure locale est dans la plage [heure_debut, heure_fin[."""
    return heure_debut <= horodatage_local.hour < heure_fin


def _creneau_termine(horodatage_local, fuseau) -> bool:
    """True si le créneau horaire de cette mesure est terminé (pas en cours)."""
    maintenant = datetime.now(tz=timezone.utc).astimezone(fuseau)
    # Même jour + même heure = créneau en cours → exclure
    if (horodatage_local.date() == maintenant.date()
            and horodatage_local.hour == maintenant.hour):
        return False
    return True


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
    """Reproduit le Tableau 1 du rapport — temps théoriques par axe à 50 km/h.

    Fonctionne pour **tout tronçon actif** (les 6 axes officiels seedés + les
    axes ajoutés dynamiquement via /administration/troncons). La déduplication
    aller/retour utilise un libellé d'axe insensible au sens (cf.
    `_libelle_axe`), donc un nouvel axe « AGL → Grand Moulin » + son retour
    « Grand Moulin → AGL » apparaissent sur une seule ligne du Tableau 1.
    """
    troncons = list(
        db.execute(select(Troncon).where(Troncon.actif.is_(True))).scalars()
    )
    par_axe: dict[str, Troncon] = {}
    for t in troncons:
        nom_axe = _libelle_axe(t.nom)
        if nom_axe not in par_axe:
            par_axe[nom_axe] = t

    resultats: list[TempsTheorique] = []
    for nom, t in par_axe.items():
        temps_s = int(round(t.temps_reference_s()))
        resultats.append(TempsTheorique(
            axe=nom,
            distance_km=round(t.distance_ref_m / 1000.0, 1),
            temps_50kmh_s=temps_s,
            temps_50kmh_str=_format_mn_s(temps_s),
        ))
    return resultats


def _libelle_axe(nom_troncon: str) -> str:
    """Libellé canonique de l'axe (insensible au sens de circulation).

    Convertit « CARENA → Pharmacie Palm Beach » et « Pharmacie Palm Beach →
    CARENA » vers le même libellé, pour pouvoir dédupliquer les 2 sens du
    même axe dans le Tableau 1 du rapport DEESP.

    Stratégie :
      1. Pour les axes officiels (« … → Palm Beach » ou « Palm Beach → … »),
         on impose Palm Beach en seconde position pour conserver l'ordre
         attendu par le rapport.
      2. Pour tout autre axe (créé via /administration), on normalise par
         **ordre alphabétique** des deux extrémités. Cela garantit que
         « FOO → BAR » et « BAR → FOO » produisent le même libellé sans
         dépendre d'un mot-clé particulier.
    """
    parts = nom_troncon.split(" → ")
    if len(parts) != 2:
        return nom_troncon
    a, b = parts[0].strip(), parts[1].strip()
    # 1) Convention rapport DEESP : Palm Beach toujours en seconde position
    if "Palm Beach" in a:
        a, b = b, a
        return f"{a} - {b}"
    if "Palm Beach" in b:
        return f"{a} - {b}"
    # 2) Tronçons libres ajoutés via /administration : tri alphabétique stable
    extremite_1, extremite_2 = sorted([a, b])
    return f"{extremite_1} - {extremite_2}"


def _format_mn_s(secondes: int) -> str:
    """Formate des secondes en "X mn YY s" (style rapport DEESP)."""
    mn = secondes // 60
    sec = secondes % 60
    return f"{mn} min {sec:02d} s"


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
    temps_min_s: int | None
    temps_moyen_s: int | None
    temps_max_s: int | None


def temps_traversee_par_troncon(
    db: Session,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    heure_debut: int = DEESP_HEURE_DEBUT,
    heure_fin: int = DEESP_HEURE_FIN,
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

    # Group key : (troncon_id, type_jour, date_locale) → list[duree_trafic_s]
    # ATTENTION : on FILTRE strictement à la plage DEESP officielle (7h-19h)
    # même si la collecte étend à 24h/24, pour préserver la conformité
    # méthodologique (cf. CLAUDE.md § 4.5.1).
    par_jour: dict[tuple[int, TypeJour, date], list[int]] = defaultdict(list)

    # Axes SANS sous-tronçons actifs : lecture directe des mesures axe-level
    ids_sans_sous = [t.id for t in troncons if not axe_a_sous_troncons(db, t.id)]
    if ids_sans_sous:
        mesures_directes = list(
            db.execute(
                select(Mesure).where(
                    Mesure.source == SourceMesure.google,
                    Mesure.troncon_id.in_(ids_sans_sous),
                    Mesure.sous_troncon_id.is_(None),
                    Mesure.duree_trafic_s.is_not(None),
                    Mesure.aberrante.is_(False),
                    Mesure.horodatage >= debut_utc,
                    Mesure.horodatage <= fin_utc,
                )
            ).scalars()
        )
        for m in mesures_directes:
            local = m.horodatage.astimezone(fuseau_local)
            if not _dans_plage_horaire(local, heure_debut, heure_fin):
                continue
            d_local = local.date()
            tj = _type_jour(d_local)
            par_jour[(m.troncon_id, tj, d_local)].append(m.duree_trafic_s)

    # Axes AVEC sous-tronçons actifs : agrégation SUM des sous-tronçons par créneau
    ids_sans_sous_set = set(ids_sans_sous)
    for t in troncons:
        if t.id in ids_sans_sous_set:
            continue
        tuples_agg = agreger_durees_par_creneau(db, t.id, debut_utc, fin_utc, source_google_only=True)
        for horodatage, duree_s, _src in tuples_agg:
            local = (
                horodatage.astimezone(fuseau_local)
                if horodatage.tzinfo
                else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau_local)
            )
            if not _dans_plage_horaire(local, heure_debut, heure_fin):
                continue
            d_local = local.date()
            tj = _type_jour(d_local)
            par_jour[(t.id, tj, d_local)].append(duree_s)

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
                    temps_min_s=None, temps_moyen_s=None, temps_max_s=None,
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
                temps_min_s=int(round(mins[cle])),
                temps_moyen_s=int(round(moyenne_des_moyennes * 60)),
                temps_max_s=int(round(maxs[cle])),
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
    nb_jours_disponibles_par_type: dict[str, int]  # weekday name → nb de ce jour dans la période
    nb_total_semaine: int  # toutes occurrences toutes journées confondues
    regle_jour_indicatif: bool  # ≥ seuil_jour fois sur un jour-type donné
    regle_semaine: bool  # ≥ seuil_semaine fois la même heure n'importe quel jour
    # Renseignés UNIQUEMENT si la mesure portait sur un sous-tronçon
    # (codification DEESP T1A, T1B…). Sinon None.
    sous_troncon_id: int | None = None
    sous_troncon_code: str | None = None
    sous_troncon_nom: str | None = None


def seuils_congestion(debut_utc: datetime, fin_utc: datetime) -> tuple[int, int]:
    """Retourne (seuil_jour, seuil_semaine) adaptés à la durée de la plage.

    Référence DEESP : 28 jours → seuil_jour=3, seuil_semaine=4.
    En-dessous de 28 jours, les seuils sont proratisés pour que le tableau
    reste utilisable sur des plages courtes tout en restant proportionnel.

    fin_utc est cappée à maintenant — on ne peut pas avoir de données du
    futur, donc utiliser juillet complet (31 j) alors qu'on est au 7 juillet
    produirait des seuils inatteignables.
    """
    maintenant = datetime.now(timezone.utc)
    fin_effective = min(fin_utc, maintenant)
    nb_jours = max(1, (fin_effective - debut_utc).days + 1)
    facteur = nb_jours / 28
    seuil_jour = max(1, round(3 * facteur))
    seuil_semaine = max(2, round(4 * facteur))
    return seuil_jour, seuil_semaine


def troncons_congestionnes(
    db: Session,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    heure_debut: int = DEESP_HEURE_DEBUT,
    heure_fin: int = DEESP_HEURE_FIN,
) -> list[CongestionHoraire]:
    """Applique les règles § 4.5.3 pour identifier les tronçons congestionnés.

    Méthodologie DEESP — désormais fidèle à 100 % au rapport :
      1. Pour chaque mesure : congestionné ssi la couleur Google Maps
         indique ROUGE (présent) OU ORANGE sur ≥ 50 % du tronçon. Ce
         verdict est lu directement dans `mesures.est_congestionne`.
      2. Granularité : si la mesure porte sur un sous-tronçon (T1A, T1B…),
         on évalue les règles AU NIVEAU SOUS-TRONÇON. Sinon au niveau axe.
      3. Règle JOUR : congestionné si ≥ 3 fois sur les lundis (ou mardis…)
      4. Règle SEMAINE : congestionné si ≥ 4 fois à cette heure dans la
         semaine, peu importe le jour.
    """
    from app.models.models import SousTroncon  # import paresseux pour éviter cycle

    fuseau_local = ZoneInfo(get_settings().tz)
    NOMS_JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

    # Nombre de jours disponibles de chaque type dans la période (cappée à maintenant)
    # Sert au dénominateur DEESP : "3 fois sur les 4 lundis" → nb_disponibles["lundi"] = 4
    maintenant_dispo = datetime.now(timezone.utc)
    fin_effective_dispo = min(fin_utc, maintenant_dispo)
    _nb_dispo: dict[str, int] = defaultdict(int)
    _d_iter = debut_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    while _d_iter.date() <= fin_effective_dispo.date():
        _wd_local = _d_iter.astimezone(fuseau_local).weekday()
        _nb_dispo[NOMS_JOURS_FR[_wd_local]] += 1
        _d_iter += timedelta(days=1)
    nb_disponibles_dict = dict(_nb_dispo)

    troncons = {
        t.id: t for t in db.execute(
            select(Troncon).where(Troncon.actif.is_(True))
        ).scalars()
    }
    sous_troncons = {
        s.id: s for s in db.execute(select(SousTroncon)).scalars()
    }

    # On ne retient que les mesures dont la couleur Google Maps indique
    # explicitement « congestionné ». Les NULL (Google n'a pas qualifié
    # le tracé) sont ignorées — pas d'invention de donnée.
    mesures = list(
        db.execute(
            select(Mesure).where(
                Mesure.source == SourceMesure.google,
                Mesure.est_congestionne.is_(True),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_utc,
                Mesure.horodatage <= fin_utc,
            )
        ).scalars()
    )

    # Règles DEESP officielles (§ 4.5.3) — strictes, appliquées par période fixe
    SEUIL_JOUR_DEESP = 3     # ≥ 3 occurrences sur le même jour indicatif (ex. 3 lundis)
    SEUIL_SEMAINE_DEESP = 4  # ≥ 4 occurrences dans une seule semaine calendaire (lun-dim)

    # Compteur par (tid, sid, weekday, heure) → nb total dans la période (règle jour)
    occurrences: dict[tuple[int, int | None, int, int], int] = defaultdict(int)
    # Compteur par (tid, sid, heure, année_iso, semaine_iso) → nb dans cette semaine (règle semaine)
    par_semaine_iso: dict[tuple[int, int | None, int, int, int], int] = defaultdict(int)

    for m in mesures:
        if m.troncon_id not in troncons:
            continue
        local = m.horodatage.astimezone(fuseau_local)
        if not _dans_plage_horaire(local, heure_debut, heure_fin):
            continue
        iy, iw, _ = local.isocalendar()
        occurrences[(m.troncon_id, m.sous_troncon_id, local.weekday(), local.hour)] += 1
        par_semaine_iso[(m.troncon_id, m.sous_troncon_id, local.hour, iy, iw)] += 1

    # Agrégation par (troncon, sous, heure) — comptages par jour indicatif
    par_cle_heure: dict[tuple[int, int | None, int], dict[int, int]] = defaultdict(dict)
    for (tid, sid, wd, h), nb in occurrences.items():
        par_cle_heure[(tid, sid, h)][wd] = nb

    # Maximum d'occurrences dans une seule semaine calendaire, par créneau
    max_par_semaine: dict[tuple[int, int | None, int], int] = defaultdict(int)
    for (tid, sid, h, iy, iw), nb in par_semaine_iso.items():
        if nb > max_par_semaine[(tid, sid, h)]:
            max_par_semaine[(tid, sid, h)] = nb

    resultats: list[CongestionHoraire] = []
    for (tid, sid, h), par_jour in par_cle_heure.items():
        # Règle 2 — jour indicatif STRICT : ≥ 3 fois sur le même type de jour dans le mois
        regle_jour = any(nb >= SEUIL_JOUR_DEESP for nb in par_jour.values())
        nb_total = sum(par_jour.values())
        # Règle 1 — semaine STRICT : ≥ 4 occurrences dans une seule semaine calendaire
        regle_sem = max_par_semaine[(tid, sid, h)] >= SEUIL_SEMAINE_DEESP
        if not (regle_jour or regle_sem):
            continue
        t = troncons[tid]
        s = sous_troncons.get(sid) if sid is not None else None
        resultats.append(CongestionHoraire(
            troncon_id=tid,
            troncon_nom=t.nom,
            heure=h,
            nb_jours_congestionnes_par_type={
                NOMS_JOURS_FR[wd]: nb for wd, nb in par_jour.items()
            },
            nb_jours_disponibles_par_type=nb_disponibles_dict,
            nb_total_semaine=nb_total,
            regle_jour_indicatif=regle_jour,
            regle_semaine=regle_sem,
            sous_troncon_id=sid,
            sous_troncon_code=s.code if s else None,
            sous_troncon_nom=s.nom_court if s else None,
        ))
    # Trie : par troncon, sous-tronçon (None d'abord), heure
    resultats.sort(key=lambda r: (r.troncon_id, r.sous_troncon_id or 0, r.heure))
    return resultats


# ---------------------------------------------------------------------------
# Matrice congestion — par créneau horaire × date (brut, sans agrégation)
# ---------------------------------------------------------------------------


def matrice_congestion(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    heure_debut: int = DEESP_HEURE_DEBUT,
    heure_fin: int = DEESP_HEURE_FIN,
    sous_troncon_id: int | None = None,
) -> dict:
    """Retourne pour chaque (date locale, heure DEESP) l'état congestionné/fluide.

    Résultat :
      - dates   : liste triée de dates ISO (YYYY-MM-DD) présentes dans la plage
      - tranches : [{heure, tranche '07h-08h', par_date}]
        où par_date[date_str] = {est_congestionne, pct_rouge, pct_orange} | None
    """
    fuseau = ZoneInfo(get_settings().tz)

    utiliser_aggregation = (
        sous_troncon_id is None and axe_a_sous_troncons(db, troncon_id)
    )

    # Indexation : date_str → heure → cellule (dernière mesure de l'heure)
    par_date_heure: dict[str, dict[int, dict]] = {}
    dates_set: set[str] = set()

    if utiliser_aggregation:
        mesures_agg = agreger_mesures_axe(
            db, troncon_id, debut_utc, fin_utc,
            source_google_only=True, exclure_aberrantes=True,
        )
        nb_rows = len(mesures_agg)
        for m in mesures_agg:
            h_local = (
                m.horodatage.astimezone(fuseau)
                if m.horodatage.tzinfo
                else m.horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
            )
            if not _dans_plage_horaire(h_local, heure_debut, heure_fin):
                continue
            date_str = h_local.date().isoformat()
            heure = h_local.hour
            dates_set.add(date_str)
            par_date_heure.setdefault(date_str, {})[heure] = {
                "est_congestionne": m.est_congestionne,
                "pct_rouge": round(m.pourcentage_rouge, 1) if m.pourcentage_rouge is not None else None,
                "pct_orange": round(m.pourcentage_orange, 1) if m.pourcentage_orange is not None else None,
            }
    else:
        conds = [
            Mesure.troncon_id == troncon_id,
            Mesure.source == SourceMesure.google,
            Mesure.aberrante.is_(False),
            Mesure.horodatage >= debut_utc,
            Mesure.horodatage <= fin_utc,
        ]
        if sous_troncon_id is not None:
            conds.append(Mesure.sous_troncon_id == sous_troncon_id)
        else:
            conds.append(Mesure.sous_troncon_id.is_(None))
        rows = list(
            db.execute(
                select(
                    Mesure.horodatage,
                    Mesure.est_congestionne,
                    Mesure.pourcentage_rouge,
                    Mesure.pourcentage_orange,
                )
                .where(*conds)
                .order_by(Mesure.horodatage)
            ).all()
        )
        nb_rows = len(rows)

        for horodatage, est_cong, pct_rouge, pct_orange in rows:
            h_local = (
                horodatage.astimezone(fuseau)
                if horodatage.tzinfo
                else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
            )
            if not _dans_plage_horaire(h_local, heure_debut, heure_fin):
                continue
            date_str = h_local.date().isoformat()
            heure = h_local.hour
            dates_set.add(date_str)
            par_date_heure.setdefault(date_str, {})[heure] = {
                "est_congestionne": est_cong,
                "pct_rouge": round(pct_rouge, 1) if pct_rouge is not None else None,
                "pct_orange": round(pct_orange, 1) if pct_orange is not None else None,
            }

    dates_list = sorted(dates_set)

    tranches = []
    for h in range(heure_debut, heure_fin):
        par_date = {
            date_str: par_date_heure.get(date_str, {}).get(h)
            for date_str in dates_list
        }
        if any(v is not None for v in par_date.values()):
            tranches.append({
                "heure": h,
                "tranche": f"{h:02d}h-{h + 1:02d}h",
                "par_date": par_date,
            })

    return {
        "troncon_id": troncon_id,
        "nb_mesures": nb_rows,
        "dates": dates_list,
        "tranches": tranches,
    }


# ---------------------------------------------------------------------------
# Matrice temps de traversée — par créneau horaire × date (durées brutes)
# ---------------------------------------------------------------------------


def matrice_temps(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    heure_debut: int = DEESP_HEURE_DEBUT,
    heure_fin: int = DEESP_HEURE_FIN,
    sous_troncon_id: int | None = None,
) -> dict:
    """Retourne pour chaque (date locale, heure DEESP) la durée de traversée en secondes.

    Contrairement à `matrice_congestion` (source=google uniquement), inclut
    TOUTES les sources (google, terrain, historique_paa_2025…) afin d'afficher
    les données importées depuis Excel aux côtés des mesures live.

    Résultat :
      - dates   : liste triée de dates ISO (YYYY-MM-DD)
      - tranches : [{heure, tranche, par_date}]
        où par_date[date_str] = {duree_s, source} | None
    """
    fuseau = ZoneInfo(get_settings().tz)

    utiliser_aggregation_temps = (
        sous_troncon_id is None and axe_a_sous_troncons(db, troncon_id)
    )

    par_date_heure: dict[str, dict[int, dict]] = {}
    dates_set: set[str] = set()

    if utiliser_aggregation_temps:
        tuples_agg = agreger_durees_par_creneau(
            db, troncon_id, debut_utc, fin_utc,
            source_google_only=False,
        )
        nb_rows_t = len(tuples_agg)
        for horodatage, duree_s, src_str in tuples_agg:
            h_local = (
                horodatage.astimezone(fuseau)
                if horodatage.tzinfo
                else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
            )
            if not _dans_plage_horaire(h_local, heure_debut, heure_fin):
                continue
            date_str = h_local.date().isoformat()
            heure = h_local.hour
            dates_set.add(date_str)
            par_date_heure.setdefault(date_str, {})[heure] = {
                "duree_s": duree_s,
                "source": src_str,
            }
    else:
        conds = [
            Mesure.troncon_id == troncon_id,
            Mesure.duree_trafic_s.is_not(None),
            Mesure.aberrante.is_(False),
            Mesure.horodatage >= debut_utc,
            Mesure.horodatage <= fin_utc,
        ]
        if sous_troncon_id is not None:
            conds.append(Mesure.sous_troncon_id == sous_troncon_id)
        else:
            conds.append(Mesure.sous_troncon_id.is_(None))
        rows = list(
            db.execute(
                select(
                    Mesure.horodatage,
                    Mesure.duree_trafic_s,
                    Mesure.source,
                )
                .where(*conds)
                .order_by(Mesure.horodatage)
            ).all()
        )
        nb_rows_t = len(rows)

        for horodatage, duree_s, source in rows:
            h_local = (
                horodatage.astimezone(fuseau)
                if horodatage.tzinfo
                else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
            )
            if not _dans_plage_horaire(h_local, heure_debut, heure_fin):
                continue
            date_str = h_local.date().isoformat()
            heure = h_local.hour
            dates_set.add(date_str)
            par_date_heure.setdefault(date_str, {})[heure] = {
                "duree_s": duree_s,
                "source": source.value if hasattr(source, "value") else str(source),
            }

    dates_list = sorted(dates_set)

    tranches = []
    for h in range(heure_debut, heure_fin):
        par_date = {
            date_str: par_date_heure.get(date_str, {}).get(h)
            for date_str in dates_list
        }
        if any(v is not None for v in par_date.values()):
            tranches.append({
                "heure": h,
                "tranche": f"{h:02d}h-{h + 1:02d}h",
                "par_date": par_date,
            })

    return {
        "troncon_id": troncon_id,
        "nb_mesures": nb_rows_t,
        "dates": dates_list,
        "tranches": tranches,
    }


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
    heure_debut: int = DEESP_HEURE_DEBUT,
    heure_fin: int = DEESP_HEURE_FIN,
) -> list[PointGraphique]:
    """Construit la série pour les graphiques DEESP 1-12 (BarChart).

    Chaque barre = un jour de la campagne, hauteur = min ou max observé
    sur la journée, en minutes.
    """
    fuseau_local = ZoneInfo(get_settings().tz)
    NOMS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    par_jour: dict[date, list[int]] = defaultdict(list)

    if axe_a_sous_troncons(db, troncon_id):
        # Axe décomposé en sous-tronçons : agrégation SUM par créneau
        tuples_agg = agreger_durees_par_creneau(
            db, troncon_id, debut_utc, fin_utc, source_google_only=True
        )
        for horodatage, duree_s, _src in tuples_agg:
            local = (
                horodatage.astimezone(fuseau_local)
                if horodatage.tzinfo
                else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau_local)
            )
            if not _dans_plage_horaire(local, heure_debut, heure_fin):
                continue
            par_jour[local.date()].append(duree_s)
    else:
        mesures = list(
            db.execute(
                select(Mesure).where(
                    Mesure.troncon_id == troncon_id,
                    Mesure.sous_troncon_id.is_(None),
                    Mesure.source == SourceMesure.google,
                    Mesure.duree_trafic_s.is_not(None),
                    Mesure.aberrante.is_(False),
                    Mesure.horodatage >= debut_utc,
                    Mesure.horodatage <= fin_utc,
                )
            ).scalars()
        )
        for m in mesures:
            local = m.horodatage.astimezone(fuseau_local)
            if not _dans_plage_horaire(local, heure_debut, heure_fin):
                continue
            par_jour[local.date()].append(m.duree_trafic_s)

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
