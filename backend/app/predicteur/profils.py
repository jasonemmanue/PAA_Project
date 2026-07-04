"""Prédicteur DEESP par profils horaires + cascade de dégradation gracieuse.

Référence : CLAUDE.md § 4.5 + mes_prompts_finaux.md § 6.2.

Pour un tronçon et un horodatage cible (ex. mardi 8h00), retourne la
prédiction du temps de traversée au format DEESP :

  - min_mn, mediane_mn, moyen_mn, max_mn, p95_mn (minutes entières)
  - type_jour (jour_ouvrable / week_end)
  - source utilisée dans la cascade (google_routes / predicteur_profils_60j /
    vitesse_ref_50kmh)
  - confiance (0..1)
  - calibration_appliquee (multiplicateur appliqué — 0 si aucun relevé
    terrain RÉEL n'est disponible, cf. amendement 1 du prompt 6.2)

Cascade de dégradation gracieuse :
  1. **Google Routes** si la clé est disponible ET l'instant cible est
     proche du présent (±15 min)
  2. **Prédicteur profils horaires** (agrégats `profils_horaires` table)
     pondéré par ancienneté et calibration
  3. **Référence 50 km/h** dérivée de la distance officielle du tronçon
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import (
    Mesure,
    ProfilHoraire,
    ReleveTerrain,
    SourceMesure,
    Troncon,
)


SourcePrediction = Literal[
    "google_routes", "mesures_jour_type_7j", "vitesse_ref_50kmh"
]
TypeJour = Literal["jour_ouvrable", "week_end"]


# Fenêtre du niveau 2 (mesures Google récentes par type de jour).
# 7 jours glissants = 5 occurrences de jours ouvrables + 2 week-ends en moyenne,
# ce qui suffit pour stabiliser min/moyen/max sans trainer d'historique stale.
FENETRE_JOUR_TYPE_JOURS = 7


@dataclass(frozen=True)
class Prediction:
    """Résultat de prédiction au format DEESP (cf. CLAUDE.md § 4.5)."""
    troncon_id: int
    troncon_nom: str
    instant_local: str
    type_jour: TypeJour
    min_mn: int | None
    mediane_mn: int | None
    moyen_mn: int | None
    max_mn: int | None
    p95_mn: int | None
    fourchette_p25_p75_mn: tuple[int, int] | None
    source: SourcePrediction
    confiance: float
    calibration_appliquee: float
    avertissement: str | None  # texte si calibration désactivée


def _type_jour(d: date) -> TypeJour:
    return "jour_ouvrable" if d.weekday() < 5 else "week_end"


# ---------------------------------------------------------------------------
# Facteur de calibration — moyenne mobile des écarts terrain RÉELS
# ---------------------------------------------------------------------------


# Fenêtre par défaut (8) — compromis entre stabilité statistique (≥ 5 échantillons)
# et fraîcheur (assez récents pour rester représentatifs des conditions actuelles).
FENETRE_CALIBRATION_DEFAUT = 8

# Seuil minimal pour qu'une calibration soit appliquée — sous ce seuil, le bruit
# d'échantillonnage rend le facteur peu fiable.
MIN_RELEVES_CALIBRATION = 4


def calculer_calibration(
    db: Session,
    troncon_id: int,
    fenetre_releves: int = FENETRE_CALIBRATION_DEFAUT,
    type_jour_cible: TypeJour | None = None,
) -> tuple[float, str | None]:
    """Renvoie (facteur, avertissement_optionnel).

    Le facteur n'est appliqué QUE si au moins MIN_RELEVES_CALIBRATION relevés
    terrain `source_reelle=true` existent pour le tronçon. Sinon : facteur=0.0
    et avertissement explicite.

    Si `type_jour_cible` est précisé, on ne moyenne que les ε des relevés du
    même type de jour (jour_ouvrable ou week_end). C'est l'alignement DEESP :
    le rapport sépare systématiquement les statistiques par type de jour
    (cf. CLAUDE.md § 4.5.5). En cas d'échantillon insuffisant pour le type
    cible, on retombe sur l'ensemble des relevés.
    """
    requete = (
        select(ReleveTerrain)
        .where(
            ReleveTerrain.troncon_id == troncon_id,
            ReleveTerrain.source_reelle.is_(True),
            ReleveTerrain.ecart_relatif.is_not(None),
        )
        .order_by(ReleveTerrain.horodatage_passage.desc().nullslast())
        .limit(fenetre_releves * 2)  # surcouche pour filtrage type_jour ensuite
    )
    releves_reels = list(db.execute(requete).scalars())

    if not releves_reels:
        return 0.0, (
            "Calibration désactivée — aucun relevé terrain réel disponible. "
            "Importez au moins 4 vrais GPX (page Fiabilité, paramètre "
            "synthetique=false) pour activer la calibration."
        )

    # Filtrage optionnel par type_jour, avec repli si échantillon trop petit
    if type_jour_cible is not None:
        memes_type = [
            r for r in releves_reels
            if r.horodatage_passage is not None
            and _type_jour(r.horodatage_passage.date()) == type_jour_cible
        ]
        if len(memes_type) >= MIN_RELEVES_CALIBRATION:
            releves_reels = memes_type[:fenetre_releves]
        else:
            releves_reels = releves_reels[:fenetre_releves]
    else:
        releves_reels = releves_reels[:fenetre_releves]

    ecarts = [r.ecart_relatif for r in releves_reels if r.ecart_relatif is not None]

    if len(ecarts) < MIN_RELEVES_CALIBRATION:
        return 0.0, (
            f"Calibration désactivée — seulement {len(ecarts)} relevé(s) "
            f"réel(s) disponible(s) ; il en faut au moins {MIN_RELEVES_CALIBRATION}."
        )

    return statistics.fmean(ecarts), None


# ---------------------------------------------------------------------------
# Lecture des profils horaires + pondération exponentielle
# ---------------------------------------------------------------------------


def _stats_profils(
    db: Session,
    troncon_id: int,
    jour_semaine: int,
    heure: int,
    fenetre_jours: int = 60,
) -> dict[str, float] | None:
    """Récupère les stats agrégées (min, médiane, p95, moyenne, max, nb) pour
    le créneau (tronçon, jour_semaine, heure) sur la fenêtre demandée.

    Renvoie None si aucun profil n'existe.
    """
    profil = db.execute(
        select(ProfilHoraire).where(
            ProfilHoraire.troncon_id == troncon_id,
            ProfilHoraire.jour_semaine == jour_semaine,
            ProfilHoraire.heure == heure,
            ProfilHoraire.fenetre_jours == fenetre_jours,
        )
    ).scalar_one_or_none()
    if profil is None or profil.nb_mesures == 0:
        return None
    return {
        "min_s": profil.min or 0.0,
        "mediane_s": profil.mediane or 0.0,
        "moyenne_s": profil.moyenne or 0.0,
        "max_s": profil.max or 0.0,
        "p95_s": profil.p95 or 0.0,
        "nb_mesures": profil.nb_mesures,
    }


def _confiance_depuis_nb(nb_mesures: int) -> float:
    """Confiance ∈ [0, 1] croissante en log avec le nombre d'observations."""
    if nb_mesures <= 0:
        return 0.0
    # 5 mesures → 0.5 ; 20 → ~0.8 ; 50+ → ~0.93
    import math
    return min(1.0, math.log(nb_mesures + 1) / math.log(50))


# ---------------------------------------------------------------------------
# Cascade : Google → prédicteur → 50 km/h
# ---------------------------------------------------------------------------


def _prediction_google(
    db: Session,
    troncon: Troncon,
    instant_utc: datetime,
    fenetre_minutes: int = 15,
) -> Prediction | None:
    """Si une mesure Google existe dans les `fenetre_minutes` dernières minutes
    de l'instant cible, on la renvoie comme prédiction (source la plus fraîche).

    La fenêtre est `[instant - fenetre, instant]` — pas symétrique, car le
    futur n'existe pas en base (le scheduler n'a pas encore tourné après
    `instant_utc`).
    """
    debut = instant_utc - timedelta(minutes=fenetre_minutes)
    fin = instant_utc
    mesure = db.execute(
        select(Mesure)
        .where(
            Mesure.troncon_id == troncon.id,
            Mesure.source == SourceMesure.google,
            Mesure.duree_trafic_s.is_not(None),
            Mesure.horodatage >= debut,
            Mesure.horodatage <= fin,
        )
        .order_by(func.abs(
            func.extract("epoch", Mesure.horodatage)
            - func.extract("epoch", instant_utc)
        ))
        .limit(1)
    ).scalar_one_or_none()
    if mesure is None or not mesure.duree_trafic_s:
        return None
    duree_mn = int(round(mesure.duree_trafic_s / 60))
    fuseau = ZoneInfo(get_settings().tz)
    instant_local = instant_utc.astimezone(fuseau)
    return Prediction(
        troncon_id=troncon.id,
        troncon_nom=troncon.nom,
        instant_local=instant_local.isoformat(),
        type_jour=_type_jour(instant_local.date()),
        min_mn=duree_mn,
        mediane_mn=duree_mn,
        moyen_mn=duree_mn,
        max_mn=duree_mn,
        p95_mn=duree_mn,
        fourchette_p25_p75_mn=(duree_mn, duree_mn),
        source="google_routes",
        confiance=1.0,
        calibration_appliquee=0.0,
        avertissement=None,
    )


def _prediction_jour_type(
    db: Session,
    troncon: Troncon,
    instant_utc: datetime,
    fenetre_jours: int = FENETRE_JOUR_TYPE_JOURS,
) -> Prediction | None:
    """Niveau 2 — mesures Google récentes du même type de jour.

    Approche **temps réel** : on n'utilise plus les profils horaires
    historiques (60 j × créneau heure × jour-semaine). On agrège
    directement les mesures Google des `fenetre_jours` derniers jours
    en filtrant uniquement par `type_jour` (jour_ouvrable / week_end).
    Pas de filtre par heure : le bloc « Temps actuel » donne la fourchette
    min/moyen/max observée sur le type de jour courant, peu importe le
    créneau horaire.

    Retourne None s'il n'y a aucune mesure exploitable.
    Calibration terrain (GPX réels) appliquée si disponible — cf.
    `calculer_calibration()`.
    """
    fuseau = ZoneInfo(get_settings().tz)
    instant_local = instant_utc.astimezone(fuseau)
    type_jour_cible = _type_jour(instant_local.date())

    # Fenêtre récente — utilise les mesures temps réel des derniers jours
    fin_utc = instant_utc
    debut_utc = fin_utc - timedelta(days=fenetre_jours)

    rows = list(
        db.execute(
            select(Mesure.duree_trafic_s, Mesure.horodatage).where(
                Mesure.troncon_id == troncon.id,
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.is_not(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_utc,
                Mesure.horodatage <= fin_utc,
            )
        ).all()
    )

    # Filtrage par type de jour de chaque mesure (en heure locale)
    durees_s: list[float] = []
    for duree_s, horodatage in rows:
        if duree_s is None:
            continue
        h_local = (
            horodatage.astimezone(fuseau)
            if horodatage.tzinfo
            else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
        )
        if _type_jour(h_local.date()) == type_jour_cible:
            durees_s.append(float(duree_s))

    if not durees_s:
        return None

    calibration, avertissement = calculer_calibration(
        db, troncon.id, type_jour_cible=type_jour_cible,
    )
    facteur = 1.0 + calibration  # ε = (T_terrain − T_api) / T_api → terrain = api × (1+ε)

    def to_mn(secondes: float) -> int:
        return int(round((secondes * facteur) / 60))

    min_s = min(durees_s)
    max_s = max(durees_s)
    moyenne_s = statistics.fmean(durees_s)
    mediane_s = statistics.median(durees_s)
    p95_s = (
        statistics.quantiles(durees_s, n=20)[18]
        if len(durees_s) >= 20 else max_s
    )

    return Prediction(
        troncon_id=troncon.id,
        troncon_nom=troncon.nom,
        instant_local=instant_local.isoformat(),
        type_jour=type_jour_cible,
        min_mn=to_mn(min_s),
        mediane_mn=to_mn(mediane_s),
        moyen_mn=to_mn(moyenne_s),
        max_mn=to_mn(max_s),
        p95_mn=to_mn(p95_s),
        fourchette_p25_p75_mn=(to_mn(min_s), to_mn(p95_s)),
        source="mesures_jour_type_7j",
        confiance=_confiance_depuis_nb(len(durees_s)),
        calibration_appliquee=round(calibration, 4),
        avertissement=avertissement,
    )


def _prediction_50kmh(troncon: Troncon, instant_utc: datetime) -> Prediction:
    """Repli déterministe : temps théorique 50 km/h depuis la distance officielle."""
    t_ref_s = troncon.temps_reference_s()
    t_ref_mn = int(round(t_ref_s / 60))
    fuseau = ZoneInfo(get_settings().tz)
    instant_local = instant_utc.astimezone(fuseau)
    return Prediction(
        troncon_id=troncon.id,
        troncon_nom=troncon.nom,
        instant_local=instant_local.isoformat(),
        type_jour=_type_jour(instant_local.date()),
        min_mn=t_ref_mn,
        mediane_mn=t_ref_mn,
        moyen_mn=t_ref_mn,
        max_mn=t_ref_mn,
        p95_mn=t_ref_mn,
        fourchette_p25_p75_mn=(t_ref_mn, t_ref_mn),
        source="vitesse_ref_50kmh",
        confiance=0.3,
        calibration_appliquee=0.0,
        avertissement=(
            "Aucune mesure Google pour ce type de jour sur les 7 derniers "
            "jours — repli sur le temps de référence 50 km/h."
        ),
    )


# ---------------------------------------------------------------------------
# Entrée publique du prédicteur — cascade complète
# ---------------------------------------------------------------------------


def predire(
    db: Session,
    troncon_id: int,
    instant_local: datetime,
) -> Prediction:
    """Prédiction DEESP avec cascade Google → profils → 50 km/h.

    `instant_local` est un datetime en heure locale Africa/Abidjan (sans
    forcément le tzinfo). Le code le normalise en UTC.
    """
    troncon = db.get(Troncon, troncon_id)
    if troncon is None:
        raise LookupError(f"Tronçon id={troncon_id} introuvable.")

    fuseau = ZoneInfo(get_settings().tz)
    if instant_local.tzinfo is None:
        instant_local = instant_local.replace(tzinfo=fuseau)
    instant_utc = instant_local.astimezone(timezone.utc)

    # Niveau 1 — Google si proche du présent
    maintenant = datetime.now(tz=timezone.utc)
    if abs((instant_utc - maintenant).total_seconds()) <= 15 * 60:
        pred = _prediction_google(db, troncon, instant_utc)
        if pred is not None:
            return pred

    # Niveau 2 — Mesures Google récentes du même type de jour (7 j glissants)
    pred = _prediction_jour_type(db, troncon, instant_utc)
    if pred is not None:
        return pred

    # Niveau 3 — Référence déterministe 50 km/h
    return _prediction_50kmh(troncon, instant_utc)


# ---------------------------------------------------------------------------
# Qualité — MAE du prédicteur sur les 7 derniers jours
# ---------------------------------------------------------------------------


def _stats_mesures_periode(
    db: Session,
    troncon_id: int,
    debut_utc: datetime,
    fin_utc: datetime,
    heure_debut: int = 0,
    heure_fin: int = 24,
    sous_troncon_id: int | None = None,
) -> dict:
    """Stats min/moyen/max des mesures Google réelles sur une période, par type_jour.

    Retourne un dict avec :
      - ``jour_ouvrable`` / ``week_end`` : dict { min_mn, moyen_mn, max_mn, nb_mesures } ou None
      - ``nb_mesures_total``

    ``heure_debut`` / ``heure_fin`` filtrent sur l'heure locale (Africa/Abidjan).
    Par défaut 0-24 = pas de filtre.
    """
    from sqlalchemy.sql.expression import and_

    fuseau = ZoneInfo(get_settings().tz)

    conditions = [
        Mesure.troncon_id == troncon_id,
        Mesure.source == SourceMesure.google,
        Mesure.duree_trafic_s.is_not(None),
        Mesure.aberrante.is_(False),
        Mesure.horodatage >= debut_utc,
        Mesure.horodatage <= fin_utc,
    ]
    if sous_troncon_id is not None:
        conditions.append(Mesure.sous_troncon_id == sous_troncon_id)

    rows = list(
        db.execute(
            select(Mesure.duree_trafic_s, Mesure.horodatage)
            .where(and_(*conditions))
        ).all()
    )

    filtrer_heure = not (heure_debut == 0 and heure_fin == 24)
    par_type: dict[str, list[float]] = {"jour_ouvrable": [], "week_end": []}
    for duree_s, horodatage in rows:
        if duree_s is None:
            continue
        horodatage_local = horodatage.astimezone(fuseau) if horodatage.tzinfo else horodatage.replace(tzinfo=timezone.utc).astimezone(fuseau)
        if filtrer_heure and not (heure_debut <= horodatage_local.hour < heure_fin):
            continue
        tj = _type_jour(horodatage_local.date())
        par_type[tj].append(duree_s / 60.0)

    def _calc(valeurs: list[float]) -> dict | None:
        if not valeurs:
            return None
        return {
            "min_mn": int(round(min(valeurs))),
            "moyen_mn": int(round(statistics.fmean(valeurs))),
            "max_mn": int(round(max(valeurs))),
            "nb_mesures": len(valeurs),
        }

    return {
        "jour_ouvrable": _calc(par_type["jour_ouvrable"]),
        "week_end": _calc(par_type["week_end"]),
        "nb_mesures_total": len(rows),
    }
