"""Agrégation axe ← sous-tronçons.

Quand un axe possède des sous-tronçons actifs, le scheduler ne mesure que
les sous-tronçons. Ce module fournit des helpers pour reconstruire les
indicateurs au niveau axe en sommant les durées des sous-tronçons par
créneau horaire et en agrégeant les verdicts de congestion.

Règles :
  - Temps axe = SOMME des durées des sous-tronçons pour chaque créneau
  - Congestionné si AU MOINS UN sous est congestionné
  - Fluide seulement si TOUS les sous sont fluides
  - Couleurs : moyenne pondérée par distance des sous-tronçons
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import (
    Mesure,
    SousTroncon,
    SourceMesure,
    axe_sous_troncons,
)


logger = logging.getLogger("paa.aggregation")


# ---------------------------------------------------------------------------
# Recherche des sous-tronçons actifs d'un axe
# ---------------------------------------------------------------------------


def get_sous_ids_pour_axe(db: Session, axe_id: int) -> list[int]:
    """Retourne les IDs des sous-tronçons actifs rattachés à cet axe via M2M."""
    ids_m2m = list(
        db.execute(
            select(axe_sous_troncons.c.sous_troncon_id)
            .join(
                SousTroncon,
                SousTroncon.id == axe_sous_troncons.c.sous_troncon_id,
            )
            .where(
                axe_sous_troncons.c.axe_id == axe_id,
                SousTroncon.actif.is_(True),
            )
        ).scalars()
    )
    if ids_m2m:
        return ids_m2m
    return list(
        db.execute(
            select(SousTroncon.id).where(
                SousTroncon.troncon_id == axe_id,
                SousTroncon.actif.is_(True),
            )
        ).scalars()
    )


def axe_a_sous_troncons(db: Session, axe_id: int) -> bool:
    """True si l'axe possède au moins un sous-tronçon actif."""
    return bool(get_sous_ids_pour_axe(db, axe_id))


def distance_ref_sous_troncons(db: Session, axe_id: int) -> int:
    """Somme des distances (m) des sous-tronçons actifs rattachés à l'axe."""
    sous_ids = get_sous_ids_pour_axe(db, axe_id)
    if not sous_ids:
        return 0
    rows = list(
        db.execute(
            select(SousTroncon.distance_m).where(SousTroncon.id.in_(sous_ids))
        ).scalars()
    )
    return sum(rows)


# ---------------------------------------------------------------------------
# Mesure agrégée — dataclass compatible avec les attributs de Mesure
# ---------------------------------------------------------------------------


@dataclass
class MesureAgregee:
    """Mesure virtuelle représentant la somme des sous-tronçons sur un créneau."""
    horodatage: datetime
    duree_trafic_s: int
    est_congestionne: bool | None
    pourcentage_rouge: float | None
    pourcentage_orange: float | None
    pourcentage_vert: float | None
    aberrante: bool = False
    source: SourceMesure = SourceMesure.google
    nb_sous_presents: int = 0
    nb_sous_attendus: int = 0


# ---------------------------------------------------------------------------
# Agrégation principale
# ---------------------------------------------------------------------------


def agreger_mesures_axe(
    db: Session,
    axe_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    source_google_only: bool = False,
    exclure_aberrantes: bool = True,
) -> list[MesureAgregee]:
    """Agrège les mesures des sous-tronçons d'un axe par créneau (date, heure).

    Retourne une liste de ``MesureAgregee`` triée par horodatage.
    """
    sous_ids = get_sous_ids_pour_axe(db, axe_id)
    if not sous_ids:
        return []

    sous_list = list(
        db.execute(
            select(SousTroncon).where(SousTroncon.id.in_(sous_ids))
        ).scalars()
    )
    distances = {s.id: s.distance_m for s in sous_list}
    nb_sous = len(sous_ids)

    conds = [
        Mesure.troncon_id == axe_id,
        Mesure.sous_troncon_id.in_(sous_ids),
        Mesure.duree_trafic_s.is_not(None),
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
    ]
    if source_google_only:
        conds.append(Mesure.source == SourceMesure.google)
    if exclure_aberrantes:
        conds.append(Mesure.aberrante.is_(False))

    mesures = list(db.execute(select(Mesure).where(*conds)).scalars())

    if not mesures:
        return []

    fuseau = ZoneInfo(get_settings().tz)

    # Grouper par créneau (date, heure) — un cycle scheduler = un créneau
    par_creneau: dict[tuple[str, int], dict[int, Mesure]] = defaultdict(dict)
    for m in mesures:
        h_local = (
            m.horodatage.astimezone(fuseau)
            if m.horodatage.tzinfo
            else m.horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
        )
        cle = (h_local.date().isoformat(), h_local.hour)
        sid = m.sous_troncon_id
        if (
            sid not in par_creneau[cle]
            or m.horodatage > par_creneau[cle][sid].horodatage
        ):
            par_creneau[cle][sid] = m

    resultats: list[MesureAgregee] = []
    for (date_str, heure), mesures_par_sous in sorted(par_creneau.items()):
        duree_totale = sum(
            m.duree_trafic_s for m in mesures_par_sous.values()
        )

        verdicts = [m.est_congestionne for m in mesures_par_sous.values()]
        if any(v is True for v in verdicts):
            est_cong: bool | None = True
        elif all(v is False for v in verdicts):
            est_cong = False
        else:
            est_cong = None

        pct_r = _moyenne_ponderee(
            [
                (m.pourcentage_rouge, distances.get(m.sous_troncon_id, 1))
                for m in mesures_par_sous.values()
            ]
        )
        pct_o = _moyenne_ponderee(
            [
                (m.pourcentage_orange, distances.get(m.sous_troncon_id, 1))
                for m in mesures_par_sous.values()
            ]
        )
        pct_v = _moyenne_ponderee(
            [
                (m.pourcentage_vert, distances.get(m.sous_troncon_id, 1))
                for m in mesures_par_sous.values()
            ]
        )

        aberrante = any(m.aberrante for m in mesures_par_sous.values())
        horodatage = max(m.horodatage for m in mesures_par_sous.values())
        source_val = next(iter(mesures_par_sous.values())).source

        resultats.append(
            MesureAgregee(
                horodatage=horodatage,
                duree_trafic_s=duree_totale,
                est_congestionne=est_cong,
                pourcentage_rouge=pct_r,
                pourcentage_orange=pct_o,
                pourcentage_vert=pct_v,
                aberrante=aberrante,
                source=source_val,
                nb_sous_presents=len(mesures_par_sous),
                nb_sous_attendus=nb_sous,
            )
        )

    return resultats


def agreger_durees_par_creneau(
    db: Session,
    axe_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    source_google_only: bool = False,
) -> list[tuple[datetime, int, str]]:
    """Retourne (horodatage, duree_totale_s, source) par créneau — version légère.

    Utilisée par les fonctions de stats qui n'ont besoin que des durées.
    """
    sous_ids = get_sous_ids_pour_axe(db, axe_id)
    if not sous_ids:
        return []

    conds = [
        Mesure.troncon_id == axe_id,
        Mesure.sous_troncon_id.in_(sous_ids),
        Mesure.duree_trafic_s.is_not(None),
        Mesure.aberrante.is_(False),
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
    ]
    if source_google_only:
        conds.append(Mesure.source == SourceMesure.google)

    rows = list(
        db.execute(
            select(
                Mesure.horodatage,
                Mesure.duree_trafic_s,
                Mesure.sous_troncon_id,
                Mesure.source,
            ).where(*conds)
        ).all()
    )
    if not rows:
        return []

    fuseau = ZoneInfo(get_settings().tz)

    par_creneau: dict[tuple[str, int], dict[int, tuple]] = defaultdict(dict)
    for horodatage, duree_s, sid, source in rows:
        h_local = (
            horodatage.astimezone(fuseau)
            if horodatage.tzinfo
            else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
        )
        cle = (h_local.date().isoformat(), h_local.hour)
        if sid not in par_creneau[cle] or horodatage > par_creneau[cle][sid][0]:
            par_creneau[cle][sid] = (horodatage, duree_s, source)

    resultats = []
    for (date_str, heure), subs in sorted(par_creneau.items()):
        duree_totale = sum(t[1] for t in subs.values())
        horodatage = max(t[0] for t in subs.values())
        source_val = next(iter(subs.values()))[2]
        src_str = source_val.value if hasattr(source_val, "value") else str(source_val)
        resultats.append((horodatage, duree_totale, src_str))

    return resultats


# ---------------------------------------------------------------------------
# Utilitaire interne
# ---------------------------------------------------------------------------


def compter_mesures_brutes_axe(
    db: Session,
    axe_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
) -> int:
    """Compte les mesures brutes des sous-tronçons d'un axe sur une fenêtre."""
    from sqlalchemy import func as sqlfunc
    sous_ids = get_sous_ids_pour_axe(db, axe_id)
    if not sous_ids:
        return 0
    result = db.execute(
        select(sqlfunc.count()).select_from(Mesure).where(
            Mesure.troncon_id == axe_id,
            Mesure.sous_troncon_id.in_(sous_ids),
            Mesure.source == SourceMesure.google,
            Mesure.duree_trafic_s.is_not(None),
            Mesure.aberrante.is_(False),
            Mesure.horodatage >= debut_utc,
            Mesure.horodatage <= fin_utc,
        )
    ).scalar_one()
    return result or 0


def _moyenne_ponderee(
    valeurs_poids: list[tuple[float | None, int]],
) -> float | None:
    """Moyenne pondérée par distance. Ignore les None."""
    valides = [(v, p) for v, p in valeurs_poids if v is not None]
    if not valides:
        return None
    total_poids = sum(p for _, p in valides)
    if total_poids == 0:
        return None
    return sum(v * p for v, p in valides) / total_poids
