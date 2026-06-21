"""Calcul de l'heure optimale de départ vers le port (P6.3).

Référence : CLAUDE.md § 4.5, mes_prompts_finaux.md § 6.3.

Principe — **propagation temporelle** :

  1. L'utilisateur fournit un point de départ X et un jour J
  2. On calcule la durée constante de l'approche libre [X → origine_du_tronçon]
     via OSRM (ou Haversine ÷ 30 km/h si OSRM indisponible)
  3. Pour chaque créneau de départ par pas de 30 min entre 7h et 19h :
       instant_arrivee_au_troncon = creneau_depart + approche_libre
       traversee_predite_mn = predire(troncon, instant_arrivee_au_troncon)
       temps_total_mn = approche_libre_mn + traversee_predite_mn
  4. On identifie le créneau optimal (min temps_total_mn) et le pire
  5. Distinction jour_ouvrable / week_end dans la réponse

L'idée clé est que **le profil horaire utilisé pour la traversée est celui
de l'heure d'arrivée au tronçon**, pas celle de l'heure de départ. Sans
cette propagation, on traite à tort 6h30 comme un départ 6h30 alors que
le véhicule arrive au tronçon à ~6h45.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import Troncon
from app.predicteur.profils import _type_jour, predire
from app.sources import osrm
from app.sources.coordonnees import PointGPS


TypeJour = Literal["jour_ouvrable", "week_end"]

# Vitesse moyenne urbaine pour le repli quand OSRM indisponible
VITESSE_URBAINE_KMH = 30.0

# Plage horaire des créneaux proposés (cohérente avec DEESP 7h-19h)
HEURE_DEBUT = 7
HEURE_FIN = 19  # exclusive : dernier créneau = 18h30
PAS_MINUTES = 30


@dataclass(frozen=True)
class Creneau:
    """Un créneau de départ candidat."""
    depart_local: str          # "HH:MM"
    arrivee_troncon_local: str  # "HH:MM"
    approche_mn: int
    traversee_mn: int
    total_mn: int


@dataclass(frozen=True)
class CalculHeureOptimale:
    """Résultat complet du calcul."""
    depart: PointGPS
    depart_libelle: str
    troncon_id: int
    troncon_nom: str
    date_cible: date
    type_jour: TypeJour
    approche_libre_mn: int
    methode_approche: Literal["osrm", "haversine_30kmh"]
    creneaux: list[Creneau]
    creneau_optimal: Creneau
    creneau_pire: Creneau
    gain_vs_pire_mn: int
    recommandation: str


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _haversine_m(a: PointGPS, b: PointGPS) -> float:
    R = 6_371_000.0
    lat1, lat2 = radians(a.lat), radians(b.lat)
    dlat = lat2 - lat1
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(h))


async def _approche_libre_mn(
    depart: PointGPS,
    origine_troncon: PointGPS,
) -> tuple[int, Literal["osrm", "haversine_30kmh"]]:
    """Estime la durée [depart → origine_du_tronçon] en minutes.

    Essaie d'abord OSRM /route (réaliste, suit le réseau routier).
    Si OSRM indisponible : repli Haversine ÷ vitesse urbaine.
    """
    try:
        reponse = await osrm.route(depart, origine_troncon, timeout_s=8.0)
        return max(1, int(round(reponse.duree_sans_trafic_s / 60))), "osrm"
    except Exception:
        # Repli déterministe
        distance_m = _haversine_m(depart, origine_troncon)
        duree_s = (distance_m / 1000.0) / VITESSE_URBAINE_KMH * 3600.0
        return max(1, int(round(duree_s / 60))), "haversine_30kmh"


def _trouver_troncon_le_plus_proche(
    db: Session,
    depart: PointGPS,
) -> Troncon | None:
    """Trouve le tronçon dont l'origine est la plus proche du départ.

    Filtre sur les tronçons ACTIFS dont les coords origine sont renseignées.
    """
    troncons = list(
        db.execute(
            select(Troncon).where(
                Troncon.actif.is_(True),
                Troncon.lat_origine.is_not(None),
                Troncon.lon_origine.is_not(None),
            )
        ).scalars()
    )
    if not troncons:
        return None
    meilleur = None
    distance_min = float("inf")
    for t in troncons:
        origine = PointGPS(lat=t.lat_origine, lon=t.lon_origine)
        d = _haversine_m(depart, origine)
        if d < distance_min:
            distance_min = d
            meilleur = t
    return meilleur


def _construire_recommandation(
    creneau_optimal: Creneau,
    creneau_pire: Creneau,
    type_jour: TypeJour,
) -> str:
    """Phrase d'interprétation en langage clair pour l'utilisateur."""
    gain_mn = creneau_pire.total_mn - creneau_optimal.total_mn
    libelle_jour = "ce jour ouvrable" if type_jour == "jour_ouvrable" else "ce week-end"
    if gain_mn < 2:
        return (
            f"Le temps total est quasi-constant {libelle_jour} ({creneau_optimal.total_mn} min) — "
            f"vous pouvez partir à n'importe quelle heure entre {HEURE_DEBUT}h et "
            f"{HEURE_FIN}h sans pénalité notable."
        )
    return (
        f"Partez vers {creneau_optimal.depart_local} {libelle_jour} : "
        f"vous gagnez ≈ {gain_mn} min par rapport à {creneau_pire.depart_local} "
        f"({creneau_optimal.total_mn} min vs {creneau_pire.total_mn} min)."
    )


# ---------------------------------------------------------------------------
# Calcul principal
# ---------------------------------------------------------------------------


async def calculer_heure_optimale(
    db: Session,
    depart: PointGPS,
    depart_libelle: str,
    date_cible: date,
    troncon_id: int | None = None,
) -> CalculHeureOptimale:
    """Calcule pour chaque créneau de 30 min entre 7h et 19h le temps total
    de trajet, et identifie l'optimum."""

    # 1. Trouver le tronçon d'arrivée
    if troncon_id is not None:
        troncon = db.get(Troncon, troncon_id)
        if troncon is None:
            raise LookupError(f"Tronçon id={troncon_id} introuvable.")
    else:
        troncon = _trouver_troncon_le_plus_proche(db, depart)
        if troncon is None:
            raise LookupError(
                "Aucun tronçon actif avec coordonnées résolues n'a été trouvé."
            )

    if troncon.lat_origine is None or troncon.lon_origine is None:
        raise LookupError(
            f"Le tronçon id={troncon.id} n'a pas de coordonnées d'origine."
        )

    origine_troncon = PointGPS(lat=troncon.lat_origine, lon=troncon.lon_origine)

    # 2. Approche libre constante sur la journée
    approche_mn, methode = await _approche_libre_mn(depart, origine_troncon)

    # 3. Construction des créneaux
    fuseau = ZoneInfo(get_settings().tz)
    creneaux: list[Creneau] = []

    minutes_total = (HEURE_FIN - HEURE_DEBUT) * 60  # 720
    nb_creneaux = minutes_total // PAS_MINUTES       # 24

    for i in range(nb_creneaux):
        depart_minutes_apres_7h = i * PAS_MINUTES
        heure_dep = HEURE_DEBUT + depart_minutes_apres_7h // 60
        minute_dep = depart_minutes_apres_7h % 60
        instant_depart = datetime.combine(
            date_cible, time(heure_dep, minute_dep), tzinfo=fuseau,
        )
        instant_arrivee = instant_depart + timedelta(minutes=approche_mn)

        # 4. Propagation temporelle : prédire à l'instant d'ARRIVÉE au tronçon
        pred = predire(db, troncon.id, instant_arrivee)
        traversee_mn = pred.moyen_mn if pred.moyen_mn is not None else 0

        creneaux.append(Creneau(
            depart_local=instant_depart.strftime("%H:%M"),
            arrivee_troncon_local=instant_arrivee.strftime("%H:%M"),
            approche_mn=approche_mn,
            traversee_mn=traversee_mn,
            total_mn=approche_mn + traversee_mn,
        ))

    # 5. Identifier optimal / pire
    creneau_optimal = min(creneaux, key=lambda c: c.total_mn)
    creneau_pire = max(creneaux, key=lambda c: c.total_mn)
    gain_mn = creneau_pire.total_mn - creneau_optimal.total_mn

    type_jour = _type_jour(date_cible)
    recommandation = _construire_recommandation(
        creneau_optimal, creneau_pire, type_jour,
    )

    return CalculHeureOptimale(
        depart=depart,
        depart_libelle=depart_libelle,
        troncon_id=troncon.id,
        troncon_nom=troncon.nom,
        date_cible=date_cible,
        type_jour=type_jour,
        approche_libre_mn=approche_mn,
        methode_approche=methode,
        creneaux=creneaux,
        creneau_optimal=creneau_optimal,
        creneau_pire=creneau_pire,
        gain_vs_pire_mn=gain_mn,
        recommandation=recommandation,
    )
