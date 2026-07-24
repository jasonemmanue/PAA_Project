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
  - Carry-forward : si un sous-tronçon n'a pas de mesure pour un créneau
    donné, on réutilise sa dernière mesure valide connue. Cela évite que
    l'absence ponctuelle d'un seul sous (échec API) produise un créneau
    vide ou une somme tronquée au niveau axe.

Extension 2026-07-24 — remplissage complet (cf. CLAUDE.md § 36) :
  - CROSS-AXE : les mesures sont lues depuis TOUS les axes qui partagent
    un même sous-tronçon dans le MÊME sens (calculer_sens_par_axe).
    Un sous partagé cloné vers plusieurs axes voit ainsi sa donnée
    disponible sur chaque axe, même si un cycle passé n'a pas cloné.
  - SEED HISTORIQUE : la dernière mesure connue AVANT debut_utc est
    injectée en amorçage → les premiers créneaux de la fenêtre reçoivent
    un carry-forward même si aucune mesure directe ne les couvre.
  - CRÉNEAUX ATTENDUS : tous les créneaux (date, heure) de la fenêtre
    [debut_utc, min(fin_utc, now())] sont matérialisés → les heures sans
    mesure directe reçoivent le carry-forward au lieu de disparaître.
  - BACKWARD-FILL : deuxième passe qui comble les rares créneaux encore
    vides en début de fenêtre à partir de la première mesure future.

Résultat : aucune cellule vide dans les matrices Rapport DEESP dès qu'au
moins une mesure existe pour un sous-tronçon (quel que soit son axe et
son créneau).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import (
    Mesure,
    SousTroncon,
    SourceMesure,
    Troncon,
    axe_sous_troncons,
)
from app.sources.polyline import calculer_sens_par_axe


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
# Cross-axe : axes équivalents dans le même sens
# ---------------------------------------------------------------------------


def _resoudre_axes_equivalents(
    db: Session, axe_cible_id: int, sous_ids: list[int]
) -> set[int]:
    """Ensemble des axe_id qui traversent CES sous dans le MÊME sens que axe_cible.

    Inclut toujours ``axe_cible_id``. Permet de puiser dans les mesures d'un
    axe frère (M2M) quand un sous est partagé et parcouru dans la même
    direction : la mesure faite pour l'axe A vaut aussi pour l'axe B si le
    trafic les traverse dans le même sens.

    Pour les axes de sens opposé, on ne partage PAS — le trafic peut être
    très asymétrique (retour d'école, exports vs imports du port…).
    """
    axe_cible = db.get(Troncon, axe_cible_id)
    if axe_cible is None or axe_cible.lat_origine is None:
        return {axe_cible_id}

    liens = list(
        db.execute(
            select(
                axe_sous_troncons.c.axe_id,
                axe_sous_troncons.c.sous_troncon_id,
            ).where(axe_sous_troncons.c.sous_troncon_id.in_(sous_ids))
        ).all()
    )
    if not liens:
        return {axe_cible_id}

    sous_map = {
        s.id: s
        for s in db.execute(
            select(SousTroncon).where(SousTroncon.id.in_(sous_ids))
        ).scalars()
    }

    axe_ids_candidats = {axe_id for axe_id, _sid in liens} | {axe_cible_id}
    axes_map = {
        t.id: t
        for t in db.execute(
            select(Troncon).where(Troncon.id.in_(axe_ids_candidats))
        ).scalars()
    }

    equivalents: set[int] = {axe_cible_id}
    for sid, sous in sous_map.items():
        try:
            sens_cible = calculer_sens_par_axe(
                axe_cible.lat_origine, axe_cible.lon_origine,
                sous.lat_debut, sous.lon_debut,
                sous.lat_fin, sous.lon_fin,
            )
        except Exception:
            continue
        for axe_id, sid_row in liens:
            if sid_row != sid or axe_id == axe_cible_id:
                continue
            axe_autre = axes_map.get(axe_id)
            if axe_autre is None or axe_autre.lat_origine is None:
                continue
            try:
                sens_autre = calculer_sens_par_axe(
                    axe_autre.lat_origine, axe_autre.lon_origine,
                    sous.lat_debut, sous.lon_debut,
                    sous.lat_fin, sous.lon_fin,
                )
            except Exception:
                continue
            if sens_autre == sens_cible:
                equivalents.add(axe_id)

    return equivalents


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
# Chargement des mesures (cross-axe)
# ---------------------------------------------------------------------------


def _charger_mesures_sous_troncons(
    db: Session,
    axe_id: int,
    sous_ids: list[int],
    debut_utc: datetime,
    fin_utc: datetime,
    *,
    source_google_only: bool = False,
    exclure_aberrantes: bool = True,
) -> list:
    """Charge les mesures des sous-tronçons d'un axe sur la fenêtre.

    CROSS-AXE : lit aussi les mesures des axes qui partagent ces sous dans le
    même sens. Un sous partagé bénéficie ainsi de la donnée de tout axe frère.
    """
    axes_equivalents = _resoudre_axes_equivalents(db, axe_id, sous_ids)
    conds = [
        Mesure.troncon_id.in_(axes_equivalents),
        Mesure.sous_troncon_id.in_(sous_ids),
        Mesure.duree_trafic_s.is_not(None),
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
    ]
    if source_google_only:
        conds.append(Mesure.source == SourceMesure.google)
    if exclure_aberrantes:
        conds.append(Mesure.aberrante.is_(False))
    return list(db.execute(select(Mesure).where(*conds)).scalars())


def _charger_seed_historique(
    db: Session,
    axe_id: int,
    sous_ids: list[int],
    debut_utc: datetime,
    *,
    source_google_only: bool = False,
    exclure_aberrantes: bool = True,
    fenetre_historique_jours: int = 30,
) -> dict[int, "Mesure"]:
    """Pour chaque sous_id, retourne la DERNIÈRE mesure AVANT debut_utc.

    Sert d'amorce pour le carry-forward : sans ça, un sous qui n'a aucune
    mesure directe dans les 1ers créneaux de la fenêtre laisse des cellules
    vides. Avec ça, il repart de sa dernière valeur connue avant la fenêtre.

    On limite la recherche à ``fenetre_historique_jours`` en arrière pour
    éviter d'utiliser une donnée obsolète (ex. mesure de 2 mois).
    """
    if not sous_ids:
        return {}
    axes_equivalents = _resoudre_axes_equivalents(db, axe_id, sous_ids)
    borne_min = debut_utc - timedelta(days=fenetre_historique_jours)
    conds = [
        Mesure.troncon_id.in_(axes_equivalents),
        Mesure.sous_troncon_id.in_(sous_ids),
        Mesure.duree_trafic_s.is_not(None),
        Mesure.horodatage >= borne_min,
        Mesure.horodatage < debut_utc,
    ]
    if source_google_only:
        conds.append(Mesure.source == SourceMesure.google)
    if exclure_aberrantes:
        conds.append(Mesure.aberrante.is_(False))
    mesures = list(
        db.execute(
            select(Mesure).where(*conds).order_by(Mesure.horodatage)
        ).scalars()
    )
    dernieres: dict[int, "Mesure"] = {}
    for m in mesures:
        dernieres[m.sous_troncon_id] = m  # ordre croissant → écrase par la plus récente
    return dernieres


# ---------------------------------------------------------------------------
# Complétion des créneaux attendus + carry-forward bidirectionnel
# ---------------------------------------------------------------------------


def _generer_creneaux_attendus(
    debut_utc: datetime, fin_utc: datetime, fuseau: ZoneInfo,
) -> list[tuple[str, int]]:
    """Liste tous les créneaux (date_iso, heure_locale) dans la fenêtre.

    Borne haute cappée à ``now()`` pour ne pas générer de créneaux futurs.
    """
    now_utc = datetime.now(tz=timezone.utc)
    fin_effective = min(fin_utc, now_utc)
    if fin_effective < debut_utc:
        return []

    debut_local = debut_utc.astimezone(fuseau)
    fin_local = fin_effective.astimezone(fuseau)
    # On aligne debut sur l'heure pleine.
    cur = debut_local.replace(minute=0, second=0, microsecond=0)
    if cur < debut_local:
        cur = cur + timedelta(hours=1)

    creneaux: list[tuple[str, int]] = []
    while cur <= fin_local:
        creneaux.append((cur.date().isoformat(), cur.hour))
        cur = cur + timedelta(hours=1)
    return creneaux


def _grouper_par_creneau(
    mesures: list,
    fuseau,
) -> dict[tuple[str, int], dict[int, "Mesure"]]:
    """Groupe les mesures par créneau (date_iso, heure) → {sous_id: Mesure}."""
    par_creneau: dict[tuple[str, int], dict[int, "Mesure"]] = defaultdict(dict)
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
    return par_creneau


def _completer_avec_carry_forward(
    par_creneau: dict[tuple[str, int], dict[int, "Mesure"]],
    sous_ids: list[int],
    creneaux_attendus: list[tuple[str, int]],
    seed_historique: dict[int, "Mesure"],
) -> dict[tuple[str, int], dict[int, "Mesure"]]:
    """Comble les sous-tronçons manquants par carry-forward bidirectionnel.

    3 passes :
      1. Injection des créneaux attendus manquants (dict vide) — garantit
         qu'aucun créneau de la fenêtre n'est absent.
      2. Passe forward avec seed historique : pour chaque créneau (ordre
         chronologique), tout sous manquant reçoit la dernière mesure
         valide connue (mesures antérieures dans la fenêtre OU seed).
      3. Passe backward : comble les créneaux du DÉBUT où le forward n'a
         rien pu injecter (aucun historique disponible), en piochant la
         PREMIÈRE mesure future du sous.

    Résultat : chaque créneau attendu contient l'ensemble complet des sous
    dès qu'au moins une mesure existe pour chaque sous (ancienne ou future).
    """
    sous_set = set(sous_ids)

    # Passe 1 — injection des créneaux attendus manquants
    for cle in creneaux_attendus:
        par_creneau.setdefault(cle, {})

    if not par_creneau:
        return par_creneau

    # Passe 2 — forward carry-forward avec seed historique
    derniere_par_sous: dict[int, "Mesure"] = dict(seed_historique)
    creneaux_tries = sorted(par_creneau.keys())
    for cle in creneaux_tries:
        mesures_du_creneau = par_creneau[cle]
        for sid, m in mesures_du_creneau.items():
            derniere_par_sous[sid] = m
        for sid in sous_set:
            if sid not in mesures_du_creneau and sid in derniere_par_sous:
                mesures_du_creneau[sid] = derniere_par_sous[sid]

    # Passe 3 — backward-fill pour combler les premiers créneaux
    prochaine_par_sous: dict[int, "Mesure"] = {}
    for cle in reversed(creneaux_tries):
        mesures_du_creneau = par_creneau[cle]
        for sid, m in mesures_du_creneau.items():
            prochaine_par_sous[sid] = m
        for sid in sous_set:
            if sid not in mesures_du_creneau and sid in prochaine_par_sous:
                mesures_du_creneau[sid] = prochaine_par_sous[sid]

    return par_creneau


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

    Voir docstring du module : cross-axe + seed historique + créneaux
    attendus + backward-fill garantissent l'absence de cellule vide.

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

    mesures = _charger_mesures_sous_troncons(
        db, axe_id, sous_ids, debut_utc, fin_utc,
        source_google_only=source_google_only,
        exclure_aberrantes=exclure_aberrantes,
    )

    seed = _charger_seed_historique(
        db, axe_id, sous_ids, debut_utc,
        source_google_only=source_google_only,
        exclure_aberrantes=exclure_aberrantes,
    )

    if not mesures and not seed:
        return []

    fuseau = ZoneInfo(get_settings().tz)
    par_creneau = _grouper_par_creneau(mesures, fuseau)
    creneaux_attendus = _generer_creneaux_attendus(debut_utc, fin_utc, fuseau)
    _completer_avec_carry_forward(par_creneau, sous_ids, creneaux_attendus, seed)

    resultats: list[MesureAgregee] = []
    for (date_str, heure), mesures_par_sous in sorted(par_creneau.items()):
        if not mesures_par_sous:
            continue  # créneau attendu mais aucune donnée disponible (jamais collectée)

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
    Bénéficie du même mécanisme complet (cross-axe + seed + créneaux
    attendus + backward-fill) que ``agreger_mesures_axe``.
    """
    sous_ids = get_sous_ids_pour_axe(db, axe_id)
    if not sous_ids:
        return []

    axes_equivalents = _resoudre_axes_equivalents(db, axe_id, sous_ids)

    conds = [
        Mesure.troncon_id.in_(axes_equivalents),
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

    # Seed historique (dernière mesure de chaque sous AVANT debut_utc).
    borne_min = debut_utc - timedelta(days=30)
    conds_seed = [
        Mesure.troncon_id.in_(axes_equivalents),
        Mesure.sous_troncon_id.in_(sous_ids),
        Mesure.duree_trafic_s.is_not(None),
        Mesure.aberrante.is_(False),
        Mesure.horodatage >= borne_min,
        Mesure.horodatage < debut_utc,
    ]
    if source_google_only:
        conds_seed.append(Mesure.source == SourceMesure.google)
    rows_seed = list(
        db.execute(
            select(
                Mesure.horodatage,
                Mesure.duree_trafic_s,
                Mesure.sous_troncon_id,
                Mesure.source,
            ).where(*conds_seed).order_by(Mesure.horodatage)
        ).all()
    )
    seed_par_sous: dict[int, tuple] = {}
    for horodatage, duree_s, sid, source in rows_seed:
        seed_par_sous[sid] = (horodatage, duree_s, source)

    if not rows and not seed_par_sous:
        return []

    fuseau = ZoneInfo(get_settings().tz)
    sous_set = set(sous_ids)

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

    # Injection des créneaux attendus manquants
    for cle in _generer_creneaux_attendus(debut_utc, fin_utc, fuseau):
        par_creneau.setdefault(cle, {})

    # Passe forward carry-forward avec seed
    derniere_par_sous: dict[int, tuple] = dict(seed_par_sous)
    creneaux_tries = sorted(par_creneau.keys())
    for cle in creneaux_tries:
        subs = par_creneau[cle]
        for sid, val in subs.items():
            derniere_par_sous[sid] = val
        for sid in sous_set:
            if sid not in subs and sid in derniere_par_sous:
                subs[sid] = derniere_par_sous[sid]

    # Passe backward pour combler les premiers créneaux
    prochaine_par_sous: dict[int, tuple] = {}
    for cle in reversed(creneaux_tries):
        subs = par_creneau[cle]
        for sid, val in subs.items():
            prochaine_par_sous[sid] = val
        for sid in sous_set:
            if sid not in subs and sid in prochaine_par_sous:
                subs[sid] = prochaine_par_sous[sid]

    resultats = []
    for (_date_str, _heure), subs in sorted(par_creneau.items()):
        if not subs:
            continue
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
    """Compte les mesures brutes des sous-tronçons d'un axe sur une fenêtre.

    Prend en compte le cross-axe (mesures des axes frères même sens).
    """
    from sqlalchemy import func as sqlfunc
    sous_ids = get_sous_ids_pour_axe(db, axe_id)
    if not sous_ids:
        return 0
    axes_equivalents = _resoudre_axes_equivalents(db, axe_id, sous_ids)
    result = db.execute(
        select(sqlfunc.count()).select_from(Mesure).where(
            Mesure.troncon_id.in_(axes_equivalents),
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
