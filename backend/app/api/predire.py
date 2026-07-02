"""Routeur `/predire` — temps de traversée par période.

Endpoint unique :
  - GET /predire/resume?troncon_id= → 3 blocs temporels (courante / semaine / mois)

La précision de l'estimation courante est améliorée par les relevés GPX terrain
importés via POST /terrain/import (page Fiabilité). Le facteur de calibration
issu des `releves_terrain.ecart_relatif` est appliqué uniquement si des relevés
réels (source_reelle=True) sont disponibles.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Mesure, ProfilHoraire, SourceMesure, Troncon
from app.predicteur.profils import (
    predire,
    _stats_mesures_periode,
    _prediction_jour_type,
)


router = APIRouter(prefix="/predire", tags=["temps de traversée par période"])

# Plage horaire par défaut : 24h/24 (anciennement 7h-19h DEESP)
_H_DEBUT, _H_FIN = 0, 24


@router.get(
    "/resume",
    summary="Temps de traversée sur 3 périodes — courante, semaine, mois",
    description=(
        "Retourne en un seul appel les 3 blocs temporels affichés sur la page "
        "Temps de traversée :\n\n"
        "- **courante** : estimation pour l'instant présent (cascade Google → "
        "profils horaires 60 j → référence 50 km/h). Calibrée par les relevés "
        "GPX terrain si des relevés réels sont disponibles.\n"
        "- **semaine** : stats observées (min/moyen/max) depuis le lundi de la "
        "semaine en cours, séparées jours-ouvrables/week-ends.\n"
        "- **mois** : stats observées depuis le 1er du mois courant, "
        "séparées jours-ouvrables/week-ends.\n\n"
        "Les blocs `semaine` et `mois` s'appuient sur les mesures Google réelles "
        "déjà collectées — pas sur le prédicteur."
    ),
)
async def get_resume(
    troncon_id: int = Query(..., description="ID du tronçon"),
    heure_debut: int = Query(0, ge=0, le=23, description="Heure locale de début (0-23)"),
    heure_fin: int = Query(24, ge=1, le=24, description="Heure locale de fin (1-24)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fuseau = ZoneInfo(get_settings().tz)
    maintenant_local = datetime.now(tz=fuseau)
    maintenant_utc = maintenant_local.astimezone(timezone.utc)

    # Estimation courante — cascade complète
    try:
        pred = predire(db, troncon_id, maintenant_local)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    # Fenêtre semaine — lundi local à 00:00 → maintenant
    debut_semaine_date = maintenant_local.date() - timedelta(days=maintenant_local.weekday())
    debut_semaine_utc = (
        datetime.combine(debut_semaine_date, time(0, 0), tzinfo=fuseau)
        .astimezone(timezone.utc)
    )

    # Fenêtre mois — 1er du mois local à 00:00 → maintenant
    debut_mois_date = maintenant_local.date().replace(day=1)
    debut_mois_utc = (
        datetime.combine(debut_mois_date, time(0, 0), tzinfo=fuseau)
        .astimezone(timezone.utc)
    )

    stats_semaine = _stats_mesures_periode(db, troncon_id, debut_semaine_utc, maintenant_utc, heure_debut, heure_fin)
    stats_mois = _stats_mesures_periode(db, troncon_id, debut_mois_utc, maintenant_utc, heure_debut, heure_fin)

    # Bornes 7 j même type de jour — toujours calculées pour informer l'UI
    # (min/max stables même quand le moyen vient de la mesure Google instantanée)
    troncon = db.get(Troncon, troncon_id)
    bornes_7j = None
    if troncon is not None:
        pred_n2 = _prediction_jour_type(db, troncon, maintenant_utc)
        if pred_n2 is not None:
            bornes_7j = {
                "min_mn": pred_n2.min_mn,
                "moyen_mn": pred_n2.moyen_mn,
                "max_mn": pred_n2.max_mn,
            }

    return {
        "troncon_id": pred.troncon_id,
        "troncon_nom": pred.troncon_nom,
        "courante": {
            "instant_local": pred.instant_local,
            "type_jour": pred.type_jour,
            "prediction": {
                "min_mn": pred.min_mn,
                "moyen_mn": pred.moyen_mn,
                "max_mn": pred.max_mn,
            },
            "bornes_7j": bornes_7j,
            "source": pred.source,
            "confiance": round(pred.confiance, 3),
            "calibration_appliquee": pred.calibration_appliquee,
            "avertissement": pred.avertissement,
        },
        "semaine": {
            "debut": debut_semaine_date.isoformat(),
            "fin": maintenant_local.date().isoformat(),
            "nb_mesures_total": stats_semaine["nb_mesures_total"],
            "jours_ouvrables": stats_semaine["jour_ouvrable"],
            "week_ends": stats_semaine["week_end"],
        },
        "mois": {
            "debut": debut_mois_date.isoformat(),
            "fin": maintenant_local.date().isoformat(),
            "nb_mesures_total": stats_mois["nb_mesures_total"],
            "jours_ouvrables": stats_mois["jour_ouvrable"],
            "week_ends": stats_mois["week_end"],
        },
    }


# ---------------------------------------------------------------------------
# GET /predire/heure-optimale
# ---------------------------------------------------------------------------


@router.get(
    "/heure-optimale",
    summary="Fenêtre optimale de départ — créneaux DEESP classés par durée",
    description=(
        "Retourne les créneaux 7h-18h classés du plus rapide au plus lent "
        "pour le tronçon demandé, et identifie le top-3 recommandé. "
        "Source prioritaire : table `profils_horaires` (agrégats nocternes). "
        "Repli si vide : mesures Google des 30 derniers jours."
    ),
)
async def get_heure_optimale(
    troncon_id: int = Query(..., description="ID du tronçon"),
    type_jour: str = Query(
        "jour_ouvrable",
        description="'jour_ouvrable', 'week_end' ou 'tous'",
    ),
    heure_debut: int = Query(0, ge=0, le=23, description="Heure de début de la plage (incluse). Défaut 0 = 24h/24."),
    heure_fin: int = Query(24, ge=1, le=24, description="Heure de fin de la plage (exclue). Défaut 24 = 24h/24."),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    troncon = db.get(Troncon, troncon_id)
    if not troncon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tronçon introuvable.")

    fuseau = ZoneInfo(get_settings().tz)

    # Jours de semaine selon type_jour (0=lundi…6=dimanche)
    if type_jour == "jour_ouvrable":
        jours_filtre = list(range(5))
    elif type_jour == "week_end":
        jours_filtre = [5, 6]
    else:
        jours_filtre = list(range(7))

    creneaux: list[dict] = []

    # --- Source 1 : profils horaires (agrégats nocternes) ---
    # Fenêtre 30 j uniquement — évite de mélanger les 3 fenêtres (30/60/90)
    # qui produiraient un triple-comptage et feraient converger min/max vers la moyenne.
    # min() et max() agrégés sur les jours filtrés pour obtenir les vraies bornes.
    rows_profils = (
        db.execute(
            select(
                ProfilHoraire.heure,
                func.avg(ProfilHoraire.moyenne).label("moyenne"),
                func.min(ProfilHoraire.min).label("p_min"),
                func.max(ProfilHoraire.max).label("p_max"),
                func.sum(ProfilHoraire.nb_mesures).label("nb"),
            )
            .where(
                ProfilHoraire.troncon_id == troncon_id,
                ProfilHoraire.fenetre_jours == 30,
                ProfilHoraire.jour_semaine.in_(jours_filtre),
                ProfilHoraire.heure >= heure_debut,
                ProfilHoraire.heure < heure_fin,
                ProfilHoraire.nb_mesures > 0,
            )
            .group_by(ProfilHoraire.heure)
            .order_by(ProfilHoraire.heure)
        ).all()
    )

    source = "profils_horaires"

    if rows_profils:
        for p in rows_profils:
            moy = float(p.moyenne or 0)
            creneaux.append({
                "heure": p.heure,
                "tranche": f"{p.heure:02d}h-{p.heure + 1:02d}h",
                "moyen_s": round(moy),
                "min_s": round(float(p.p_min or 0)),
                "max_s": round(float(p.p_max or 0)),
                "moyen_mn": round(moy / 60, 1),
                "min_mn": round(float(p.p_min or 0) / 60, 1),
                "max_mn": round(float(p.p_max or 0) / 60, 1),
                "nb_mesures": int(p.nb or 0),
                "optimal": False,
            })
    else:
        # --- Source 2 : mesures Google 30 derniers jours (repli) ---
        source = "mesures_recentes_30j"
        debut_utc = datetime.now(tz=timezone.utc) - timedelta(days=30)

        mesures_db = db.execute(
            select(Mesure.horodatage, Mesure.duree_trafic_s)
            .where(
                Mesure.troncon_id == troncon_id,
                Mesure.source == SourceMesure.google,
                Mesure.duree_trafic_s.isnot(None),
                Mesure.aberrante.is_(False),
                Mesure.horodatage >= debut_utc,
            )
        ).all()

        buckets: dict[int, list[int]] = defaultdict(list)
        for m in mesures_db:
            h_local = m.horodatage.astimezone(fuseau).hour
            weekday = m.horodatage.astimezone(fuseau).weekday()
            if heure_debut <= h_local < heure_fin and weekday in jours_filtre:
                buckets[h_local].append(m.duree_trafic_s)

        for h in sorted(buckets.keys()):
            vals = buckets[h]
            if not vals:
                continue
            moy = statistics.fmean(vals)
            creneaux.append({
                "heure": h,
                "tranche": f"{h:02d}h-{h + 1:02d}h",
                "moyen_s": round(moy),
                "min_s": min(vals),
                "max_s": max(vals),
                "moyen_mn": round(moy / 60, 1),
                "min_mn": round(min(vals) / 60, 1),
                "max_mn": round(max(vals) / 60, 1),
                "nb_mesures": len(vals),
                "optimal": False,
            })

    # Marquer le top-3 (heures les plus rapides)
    top3 = sorted(creneaux, key=lambda c: c["moyen_s"])[:3]
    top3_heures = {c["heure"] for c in top3}
    for c in creneaux:
        c["optimal"] = c["heure"] in top3_heures

    # Temps de référence 50 km/h
    ref_s = int((troncon.distance_m or 0) / 1000 / 50 * 3600) if troncon.distance_m else None

    return {
        "troncon_id": troncon_id,
        "troncon_nom": troncon.nom,
        "type_jour": type_jour,
        "source": source,
        "nb_creneaux": len(creneaux),
        "creneaux": creneaux,
        "temps_ref_50kmh_s": ref_s,
        "temps_ref_50kmh_mn": round(ref_s / 60, 1) if ref_s else None,
        "recommandation": sorted(creneaux, key=lambda c: c["moyen_s"])[:3],
    }
