"""Construction de l'état temps réel des tronçons pour la carte.

Cette logique est appelée :
  - par l'endpoint HTTP `GET /carte/etat` (réponse synchrone immédiate),
  - par le WebSocket `/ws/etat` à chaque nouvelle mesure (push).

Le résultat est un dictionnaire prêt à sérialiser, structuré pour qu'un
frontend Leaflet puisse l'afficher sans transformation.

Critère de classification — désormais **purement couleur Google Maps**,
conformément à la méthodologie DEESP (cf. CLAUDE.md § 4.5.2 et le rapport
*Évaluation du temps de traversée octobre 2025*) :

  - 🔴 Rouge présent OU 🟠 Orange ≥ 50 % du tronçon → **congestionné**
  - 🟢 Vert + 🟠 Orange court                       → **fluide**
  - Aucune couleur retournée par Google             → **indéterminé**

Le ratio TTI (`duree_trafic / T_ref`) **n'entre PLUS** dans la qualification.
Il restait précédemment utilisé comme dégradé "fluide → dense → congestionné",
mais le rapport ne distingue pas "dense" et utilise exclusivement la lecture
visuelle des couleurs. Les durées (`duree_trafic_s`) sont conservées dans la
réponse uniquement pour l'affichage informatif (« Temps actuel ») — elles
restent essentielles pour les **agrégats** par jour/semaine/mois (Tableaux
3-15 du rapport).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyse.congestion import (
    COULEURS_DEESP,
    LIBELLES_DEESP_FR,
    classer_congestion,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.models import Mesure, Troncon


def construire_etat_carte(session: Session | None = None) -> dict[str, Any]:
    """Construit le snapshot complet : un objet par tronçon actif.

    Retourne :
      {
        "horodatage_utc": "...",
        "fuseau_affichage": "Africa/Abidjan",
        "couleurs": { fluide / congestionne / indetermine },
        "criteres": { description littérale de la règle DEESP },
        "nb_troncons": N,
        "troncons": [ { ... } x N ]
      }
    """
    settings = get_settings()
    fuseau_local = ZoneInfo(settings.tz)
    instant_utc = datetime.now(tz=timezone.utc)

    fermer_apres = session is None
    if fermer_apres:
        session = SessionLocal()

    try:
        # 1. Tronçons actifs (ordre stable)
        troncons: list[Troncon] = list(
            session.execute(
                select(Troncon)
                .where(Troncon.actif.is_(True))
                .order_by(Troncon.id)
            ).scalars()
        )

        # 2. Dernière mesure par tronçon (1 requête grâce à DISTINCT ON Postgres).
        dernieres = list(
            session.execute(
                select(Mesure)
                .where(Mesure.troncon_id.in_([t.id for t in troncons]))
                .distinct(Mesure.troncon_id)
                .order_by(Mesure.troncon_id, Mesure.horodatage.desc())
            ).scalars()
        )
        dernieres_par_troncon: dict[int, Mesure] = {m.troncon_id: m for m in dernieres}

        # 3. Construction des cartes de tronçons (critère couleur DEESP)
        etat_troncons: list[dict[str, Any]] = []
        for troncon in troncons:
            derniere = dernieres_par_troncon.get(troncon.id)

            duree_mesuree: int | None = None
            horodatage_iso: str | None = None
            horodatage_local_iso: str | None = None
            vitesse_kmh: float | None = None
            source_mesure: str | None = None
            statut: str = "sans_mesure"
            pct_rouge: float | None = None
            pct_orange: float | None = None
            pct_vert: float | None = None

            if derniere is not None:
                horodatage_iso = derniere.horodatage.isoformat()
                horodatage_local_iso = derniere.horodatage.astimezone(
                    fuseau_local
                ).isoformat()
                source_mesure = derniere.source.value
                pct_rouge = derniere.pourcentage_rouge
                pct_orange = derniere.pourcentage_orange
                pct_vert = derniere.pourcentage_vert
                if derniere.duree_trafic_s is not None:
                    duree_mesuree = derniere.duree_trafic_s
                    vitesse_kmh = derniere.vitesse_moyenne_kmh
                    statut = "mesure_disponible"
                else:
                    statut = "trou_de_mesure"

            verdict = classer_congestion(pct_rouge, pct_orange, pct_vert)
            couleur_etat = COULEURS_DEESP[verdict.classe]

            etat_troncons.append({
                "id": troncon.id,
                "nom": troncon.nom,
                "distance_m": troncon.distance_m,
                "distance_km": round(troncon.distance_m / 1000.0, 2),
                "vitesse_ref_kmh": troncon.vitesse_ref_kmh,
                "couleur_base": troncon.couleur,
                "couleur_etat": couleur_etat,
                "polyline": troncon.polyline,
                "geometrie": {
                    "lat_origine": troncon.lat_origine,
                    "lon_origine": troncon.lon_origine,
                    "lat_destination": troncon.lat_destination,
                    "lon_destination": troncon.lon_destination,
                },
                "temps_reference_50kmh_s": round(troncon.temps_reference_s(), 1),
                "statut": statut,
                "derniere_mesure": (
                    {
                        "horodatage_utc": horodatage_iso,
                        "horodatage_local": horodatage_local_iso,
                        # Temps observé — informatif uniquement, ne sert pas
                        # à la qualification congestionné/fluide.
                        "duree_trafic_s": duree_mesuree,
                        "vitesse_moyenne_kmh": vitesse_kmh,
                        "source": source_mesure,
                    }
                    if derniere is not None
                    else None
                ),
                # Critère DEESP — la qualification
                "classe_congestion": verdict.classe,
                "libelle_classe": LIBELLES_DEESP_FR[verdict.classe],
                "motif_congestion": verdict.motif,
                "couleur_google": {
                    "pourcentage_rouge": pct_rouge,
                    "pourcentage_orange": pct_orange,
                    "pourcentage_vert": pct_vert,
                },
            })

        return {
            "horodatage_utc": instant_utc.isoformat(),
            "fuseau_affichage": settings.tz,
            "couleurs": COULEURS_DEESP,
            "criteres": {
                "source": "Couleurs Google Maps (speedReadingIntervals)",
                "regle_congestion": (
                    "Congestionné si présence de ROUGE OU si ORANGE couvre "
                    "≥ 50 % du tronçon. Source : rapport DEESP/DEEF "
                    "« Évaluation du temps de traversée — octobre 2025 », "
                    "section METHODOLOGIE."
                ),
                "seuil_orange_long_pct": 50.0,
            },
            "nb_troncons": len(etat_troncons),
            "troncons": etat_troncons,
        }
    finally:
        if fermer_apres:
            session.close()
