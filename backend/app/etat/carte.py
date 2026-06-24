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

from datetime import datetime, timedelta, timezone
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
from app.models.models import Incident, Mesure, SousTroncon, Troncon


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

        # 2a. Dernière mesure par tronçon parent (mesures sans sous-tronçon).
        dernieres = list(
            session.execute(
                select(Mesure)
                .where(
                    Mesure.troncon_id.in_([t.id for t in troncons]),
                    Mesure.sous_troncon_id.is_(None),
                )
                .distinct(Mesure.troncon_id)
                .order_by(Mesure.troncon_id, Mesure.horodatage.desc())
            ).scalars()
        )
        dernieres_par_troncon: dict[int, Mesure] = {m.troncon_id: m for m in dernieres}

        # 2b. Sous-tronçons actifs des tronçons listés, avec leur dernière mesure
        sous_troncons: list[SousTroncon] = list(
            session.execute(
                select(SousTroncon).where(
                    SousTroncon.actif.is_(True),
                    SousTroncon.troncon_id.in_([t.id for t in troncons]),
                ).order_by(SousTroncon.troncon_id, SousTroncon.ordre)
            ).scalars()
        )
        dernieres_par_sous: dict[int, Mesure] = {}
        if sous_troncons:
            ms_sous = list(
                session.execute(
                    select(Mesure)
                    .where(Mesure.sous_troncon_id.in_([s.id for s in sous_troncons]))
                    .distinct(Mesure.sous_troncon_id)
                    .order_by(Mesure.sous_troncon_id, Mesure.horodatage.desc())
                ).scalars()
            )
            dernieres_par_sous = {m.sous_troncon_id: m for m in ms_sous if m.sous_troncon_id is not None}

        # Index des sous-tronçons par parent pour insertion dans la réponse
        sous_par_parent: dict[int, list[SousTroncon]] = {}
        for s in sous_troncons:
            sous_par_parent.setdefault(s.troncon_id, []).append(s)

        def _serialiser_mesure(m: Mesure | None) -> dict[str, Any] | None:
            if m is None:
                return None
            return {
                "horodatage_utc": m.horodatage.isoformat(),
                "horodatage_local": m.horodatage.astimezone(fuseau_local).isoformat(),
                "duree_trafic_s": m.duree_trafic_s,
                "vitesse_moyenne_kmh": m.vitesse_moyenne_kmh,
                "source": m.source.value,
            }

        def _carte_sous_troncon(s: SousTroncon) -> dict[str, Any]:
            m = dernieres_par_sous.get(s.id)
            pct_rouge = m.pourcentage_rouge if m is not None else None
            pct_orange = m.pourcentage_orange if m is not None else None
            pct_vert = m.pourcentage_vert if m is not None else None
            verdict_s = classer_congestion(pct_rouge, pct_orange, pct_vert)
            statut_s = "sans_mesure"
            if m is not None:
                statut_s = "mesure_disponible" if m.duree_trafic_s is not None else "trou_de_mesure"
            return {
                "id": s.id,
                "code": s.code,
                "nom_court": s.nom_court,
                "ordre": s.ordre,
                "distance_m": s.distance_m,
                "distance_km": round(s.distance_m / 1000.0, 2),
                "polyline": s.polyline,
                "geometrie": {
                    "lat_debut": s.lat_debut, "lon_debut": s.lon_debut,
                    "lat_fin": s.lat_fin, "lon_fin": s.lon_fin,
                },
                "temps_reference_50kmh_s": round(s.temps_reference_s(), 1),
                "statut": statut_s,
                "derniere_mesure": _serialiser_mesure(m),
                "classe_congestion": verdict_s.classe,
                "libelle_classe": LIBELLES_DEESP_FR[verdict_s.classe],
                "couleur_etat": COULEURS_DEESP[verdict_s.classe],
                "motif_congestion": verdict_s.motif,
                "couleur_google": {
                    "pourcentage_rouge": pct_rouge,
                    "pourcentage_orange": pct_orange,
                    "pourcentage_vert": pct_vert,
                },
            }

        # 3. Construction des cartes de tronçons (critère couleur DEESP)
        etat_troncons: list[dict[str, Any]] = []
        for troncon in troncons:
            sous_du_parent = sous_par_parent.get(troncon.id, [])
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

            sous_serialises = [_carte_sous_troncon(s) for s in sous_du_parent]

            # Si le parent n'a pas de mesure directe mais a des sous-tronçons,
            # on agrège leur classe DEESP : congestionné si AU MOINS UN sous
            # est congestionné, sinon fluide si AU MOINS UN est fluide, sinon
            # indéterminé. Pas d'invention de pourcentages couleur.
            if derniere is None and sous_serialises:
                classes_sous = [s["classe_congestion"] for s in sous_serialises]
                if "congestionne" in classes_sous:
                    verdict = classer_congestion(1.0, 0.0, 99.0)  # force congestionne
                elif "fluide" in classes_sous:
                    verdict = classer_congestion(0.0, 0.0, 100.0)  # force fluide
                else:
                    verdict = classer_congestion(None, None, None)
            else:
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
                "sous_troncons": sous_serialises,
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

        # 4. Incidents actifs géolocalisés (< 6 h) — max 20 les plus récents
        seuil_actif = instant_utc - timedelta(hours=6)
        incidents_actifs_db: list[Incident] = list(
            session.execute(
                select(Incident)
                .where(
                    Incident.lat.is_not(None),
                    Incident.lon.is_not(None),
                    Incident.horodatage_publication >= seuil_actif,
                )
                .order_by(Incident.horodatage_publication.desc())
                .limit(20)
            ).scalars()
        )
        incidents_serialises = [
            {
                "id": inc.id,
                "lat": inc.lat,
                "lon": inc.lon,
                "titre": inc.titre,
                "type_incident": inc.type_incident.value if inc.type_incident else None,
                "severite": inc.severite.value if inc.severite else None,
                "troncon_id": inc.troncon_id,
                "horodatage_publication": inc.horodatage_publication.isoformat(),
            }
            for inc in incidents_actifs_db
        ]

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
            "incidents_actifs": incidents_serialises,
        }
    finally:
        if fermer_apres:
            session.close()
