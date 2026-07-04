"""Insère 3 incidents démo dans la zone portuaire d'Abidjan.

À lancer depuis la Console Railway du service `backend` :

    python -m scripts.inserer_incidents_demo

Idempotent : les insertions sont protégées par `ON CONFLICT (source_url)`
via la contrainte UNIQUE — relancer n'ajoute pas de doublon.

Les 3 incidents utilisent :
  - des URLs source uniques et reconnaissables (`demo-fluidis-*`) pour
    pouvoir les identifier/supprimer facilement plus tard
  - des coordonnées GPS dans la zone portuaire (bbox 5.24-5.37 / -4.05 à -3.96)
  - un `horodatage_publication` récent (24h glissantes) pour que la
    propriété `actif` renvoie True (seuil INCIDENT_ACTIF_HEURES = 720h)
  - un `troncon_id` rattaché quand le lieu est proche d'une extrémité d'axe
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.models import Incident, SeveriteIncident


INCIDENTS_DEMO = [
    {
        "titre": "Accident de la circulation sur le boulevard de Marseille près du Port",
        "resume": (
            "Un accrochage entre un poids lourd et un véhicule particulier "
            "a été signalé ce matin sur le boulevard de Marseille, à hauteur "
            "du carrefour d'accès au Port d'Abidjan. La circulation est "
            "ralentie dans les deux sens. Aucun blessé grave rapporté."
        ),
        "source_url": "https://demo.fluidis.paa/incidents/demo-fluidis-01",
        "source_nom": "fraternite_matin",
        "lat": 5.2843,
        "lon": -4.0058,
        "lieu_extrait": "Boulevard de Marseille",
        "troncon_id": 1,  # CARENA → Palm Beach
        "type_incident": "accident",
        "severite": SeveriteIncident.moyen,
        "fiabilite_source": 0.90,
    },
    {
        "titre": "Travaux d'asphaltage en cours à Treichville — voie réduite",
        "resume": (
            "Des travaux de réfection de la chaussée sont en cours sur "
            "l'avenue Christiani à Treichville, aux abords de Toyota CFAO. "
            "La circulation se fait sur une seule voie, ralentissements "
            "attendus aux heures de pointe. Fin prévue dans 3 jours."
        ),
        "source_url": "https://demo.fluidis.paa/incidents/demo-fluidis-02",
        "source_nom": "abidjan_net",
        "lat": 5.3010,
        "lon": -4.0115,
        "lieu_extrait": "Avenue Christiani, Treichville",
        "troncon_id": 3,  # Toyota CFAO → Palm Beach
        "type_incident": "travaux",
        "severite": SeveriteIncident.mineur,
        "fiabilite_source": 0.80,
    },
    {
        "titre": "Route barrée temporairement à Zone 4 — convoi exceptionnel",
        "resume": (
            "Le passage d'un convoi exceptionnel entre la Zone 4 et Palm "
            "Beach nécessite la fermeture temporaire de la voie principale "
            "aux abords de l'agence SODECI. Prévoir un itinéraire alternatif "
            "via le boulevard de Marseille. Réouverture prévue dans 2 heures."
        ),
        "source_url": "https://demo.fluidis.paa/incidents/demo-fluidis-03",
        "source_nom": "koaci",
        "lat": 5.2678,
        "lon": -3.9985,
        "lieu_extrait": "Zone 4 — Agence SODECI",
        "troncon_id": 5,  # SODECI → Palm Beach
        "type_incident": "route_barree",
        "severite": SeveriteIncident.grave,
        "fiabilite_source": 0.75,
    },
]


def main() -> None:
    maintenant = datetime.now(tz=timezone.utc)
    # Répartir les horodatages sur les 24 dernières heures pour que
    # les 3 incidents apparaissent avec des âges différents.
    decalages = [timedelta(hours=2), timedelta(hours=8), timedelta(hours=18)]

    with SessionLocal() as db:
        inseres = 0
        deja = 0
        for demo, decalage in zip(INCIDENTS_DEMO, decalages):
            existant = (
                db.query(Incident)
                .filter(Incident.source_url == demo["source_url"])
                .one_or_none()
            )
            if existant is not None:
                # Réactualise l'horodatage pour qu'il reste "actif" (< 30 j)
                existant.horodatage_publication = maintenant - decalage
                deja += 1
                continue

            inc = Incident(
                titre=demo["titre"],
                resume=demo["resume"],
                source_url=demo["source_url"],
                source_nom=demo["source_nom"],
                horodatage_publication=maintenant - decalage,
                lat=demo["lat"],
                lon=demo["lon"],
                lieu_extrait=demo["lieu_extrait"],
                troncon_id=demo["troncon_id"],
                type_incident=demo["type_incident"],
                severite=demo["severite"],
                fiabilite_source=demo["fiabilite_source"],
                verifie=False,
            )
            db.add(inc)
            inseres += 1

        db.commit()
        print(f"[OK] {inseres} incident(s) démo inséré(s), "
              f"{deja} déjà présent(s) (horodatage rafraîchi).")


if __name__ == "__main__":
    main()
