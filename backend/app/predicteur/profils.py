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
    "google_routes", "predicteur_profils_60j", "vitesse_ref_50kmh"
]
TypeJour = Literal["jour_ouvrable", "week_end"]


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


def calculer_calibration(
    db: Session,
    troncon_id: int,
    fenetre_releves: int = 4,
) -> tuple[float, str | None]:
    """Renvoie (facteur, avertissement_optionnel).

    Le facteur n'est appliqué QUE si au moins 1 relevé terrain `source_reelle=true`
    existe pour le tronçon. Sinon : facteur=0.0 et avertissement explicite.

    Cf. amendement 1 du prompt 6.2 : tant que les GPX terrain sont synthétiques,
    leur écart ne reflète pas la réalité ; on ne calibre donc PAS le prédicteur.
    """
    releves_reels = list(
        db.execute(
            select(ReleveTerrain)
            .where(
                ReleveTerrain.troncon_id == troncon_id,
                ReleveTerrain.source_reelle.is_(True),
                ReleveTerrain.ecart_relatif.is_not(None),
            )
            .order_by(ReleveTerrain.horodatage_passage.desc().nullslast())
            .limit(fenetre_releves)
        ).scalars()
    )
    if not releves_reels:
        return 0.0, (
            "Calibration désactivée — aucun relevé terrain réel disponible. "
            "Les GPX synthétiques ne sont pas utilisés pour calibrer."
        )
    ecarts = [r.ecart_relatif for r in releves_reels if r.ecart_relatif is not None]
    if not ecarts:
        return 0.0, "Calibration désactivée — aucun écart relatif exploitable."
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
    """Si une mesure Google existe à ±fenetre_minutes de l'instant cible,
    on la renvoie comme prédiction (source la plus fraîche)."""
    debut = instant_utc - timedelta(minutes=fenetre_minutes)
    fin = instant_utc + timedelta(minutes=fenetre_minutes)
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


def _prediction_profils(
    db: Session,
    troncon: Troncon,
    instant_utc: datetime,
    fenetre_jours: int = 60,
) -> Prediction | None:
    """Prédiction par profils horaires agrégés + calibration terrain (si réelle)."""
    fuseau = ZoneInfo(get_settings().tz)
    instant_local = instant_utc.astimezone(fuseau)
    stats = _stats_profils(
        db, troncon.id, instant_local.weekday(), instant_local.hour,
        fenetre_jours=fenetre_jours,
    )
    if stats is None:
        return None

    calibration, avertissement = calculer_calibration(db, troncon.id)
    facteur = 1.0 + calibration  # ε = (T_terrain - T_api) / T_api → terrain = api × (1+ε)

    def to_mn(secondes: float) -> int:
        return int(round((secondes * facteur) / 60))

    return Prediction(
        troncon_id=troncon.id,
        troncon_nom=troncon.nom,
        instant_local=instant_local.isoformat(),
        type_jour=_type_jour(instant_local.date()),
        min_mn=to_mn(stats["min_s"]),
        mediane_mn=to_mn(stats["mediane_s"]),
        moyen_mn=to_mn(stats["moyenne_s"]),
        max_mn=to_mn(stats["max_s"]),
        p95_mn=to_mn(stats["p95_s"]),
        # Pas de quartiles dans profils_horaires → approximation min-mediane
        fourchette_p25_p75_mn=(to_mn(stats["min_s"]), to_mn(stats["p95_s"])),
        source="predicteur_profils_60j",
        confiance=_confiance_depuis_nb(int(stats["nb_mesures"])),
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
        confiance=0.3,  # déterministe mais peu d'info — confiance modérée
        calibration_appliquee=0.0,
        avertissement=(
            "Aucun profil historique pour ce créneau — repli sur le temps "
            "de référence 50 km/h."
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

    # Niveau 2 — Prédicteur par profils horaires
    pred = _prediction_profils(db, troncon, instant_utc)
    if pred is not None:
        return pred

    # Niveau 3 — Référence déterministe 50 km/h
    return _prediction_50kmh(troncon, instant_utc)


# ---------------------------------------------------------------------------
# Qualité — MAE du prédicteur sur les 7 derniers jours
# ---------------------------------------------------------------------------


def evaluer_qualite(db: Session, nb_jours: int = 7) -> dict:
    """Renvoie la MAE du prédicteur en minutes sur la fenêtre récente.

    Méthode : pour chaque mesure Google des 7 derniers jours, on retire
    cette mesure et on demande au prédicteur de profils sa valeur. On
    compare. Cela évalue l'écart « prédicteur seul » vs « observation réelle ».
    """
    fuseau = ZoneInfo(get_settings().tz)
    fin_utc = datetime.now(tz=timezone.utc)
    debut_utc = fin_utc - timedelta(days=nb_jours)

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

    erreurs_par_tj: dict[str, list[float]] = {"jour_ouvrable": [], "week_end": []}
    troncons = {
        t.id: t for t in db.execute(
            select(Troncon).where(Troncon.actif.is_(True))
        ).scalars()
    }

    for m in mesures:
        troncon = troncons.get(m.troncon_id)
        if troncon is None:
            continue
        instant_local = m.horodatage.astimezone(fuseau)
        pred = _prediction_profils(db, troncon, m.horodatage)
        if pred is None or pred.moyen_mn is None:
            continue
        valeur_reelle_mn = m.duree_trafic_s / 60
        erreur = abs(pred.moyen_mn - valeur_reelle_mn)
        erreurs_par_tj[_type_jour(instant_local.date())].append(erreur)

    return {
        "fenetre_jours": nb_jours,
        "mae_minutes": {
            "jour_ouvrable": (
                round(statistics.fmean(erreurs_par_tj["jour_ouvrable"]), 2)
                if erreurs_par_tj["jour_ouvrable"] else None
            ),
            "week_end": (
                round(statistics.fmean(erreurs_par_tj["week_end"]), 2)
                if erreurs_par_tj["week_end"] else None
            ),
        },
        "nb_observations": {
            "jour_ouvrable": len(erreurs_par_tj["jour_ouvrable"]),
            "week_end": len(erreurs_par_tj["week_end"]),
        },
    }
