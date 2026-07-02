"""Script de gestion : insère 3 incidents réalistes pour la démo.

Usage depuis la Console Railway :
    python -m app.scripts.insert_demo_incidents
"""
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.models import Incident


def main() -> None:
    db = SessionLocal()
    now = datetime.now(tz=timezone.utc)

    # Nettoyage des éventuels doublons
    urls_demo = [
        "https://www.fraternitematin.ci/2026/07/02/accident-pont-houphouet-boigny-poids-lourd-minibus/",
        "https://news.abidjan.net/articles/2026/07/02/travaux-boulevard-marseille-plateau-port-abidjan",
        "https://koaci.com/cote-divoire-conteneur-tombe-zone4-route-barree-2026-07-02.html",
    ]
    n = db.query(Incident).filter(
        Incident.source_url.in_(urls_demo)
    ).delete(synchronize_session=False)
    db.commit()
    if n:
        print(f"Nettoyage : {n} incident(s) demo precedent(s) supprime(s)")

    incidents = [
        Incident(
            titre="Accident entre un poids lourd et un minibus sur le pont Houphouet-Boigny",
            resume=(
                "Un accident de la circulation impliquant un camion de transport "
                "de marchandises et un minibus gbaka est survenu ce matin sur le "
                "pont Houphouet-Boigny, provoquant un ralentissement majeur de la "
                "circulation en direction de Treichville. Les sapeurs-pompiers ont "
                "ete depeches sur les lieux. Deux blesses legers ont ete evacues "
                "vers le CHU de Treichville."
            ),
            source_url=urls_demo[0],
            source_nom="fraternite_matin",
            horodatage_publication=now - timedelta(minutes=45),
            horodatage_collecte=now,
            lat=5.3081,
            lon=-4.0155,
            lieu_extrait="Pont Houphouet-Boigny",
            troncon_id=1,
            type_incident="accident",
            severite="grave",
            verifie=False,
            fiabilite_source=0.90,
        ),
        Incident(
            titre="Travaux de refection de la chaussee sur le boulevard de Marseille perturbent le trafic",
            resume=(
                "Des travaux de rehabilitation de la voirie ont debute sur le "
                "boulevard de Marseille a hauteur de la zone portuaire du Plateau. "
                "La circulation est deviee sur une seule voie, occasionnant des "
                "files de vehicules aux heures de pointe. Les travaux sont prevus "
                "pour une duree de deux semaines selon la mairie du Plateau."
            ),
            source_url=urls_demo[1],
            source_nom="abidjan_net",
            horodatage_publication=now - timedelta(hours=2, minutes=15),
            horodatage_collecte=now - timedelta(hours=1),
            lat=5.3220,
            lon=-4.0240,
            lieu_extrait="Boulevard de Marseille, Plateau",
            troncon_id=1,
            type_incident="travaux",
            severite="moyen",
            verifie=False,
            fiabilite_source=0.80,
        ),
        Incident(
            titre="Route barree a Zone 4 apres la chute d un conteneur sur la chaussee",
            resume=(
                "Un conteneur est tombe d un camion-remorque a hauteur de "
                "l agence SODECI en Zone 4, bloquant completement la voie en "
                "direction de la Pharmacie Palm Beach. Les agents de la police "
                "municipale ont mis en place une deviation par les rues adjacentes. "
                "Le degagement du conteneur est en cours."
            ),
            source_url=urls_demo[2],
            source_nom="koaci",
            horodatage_publication=now - timedelta(hours=1, minutes=30),
            horodatage_collecte=now - timedelta(minutes=30),
            lat=5.2920,
            lon=-3.9985,
            lieu_extrait="Zone 4, agence SODECI",
            troncon_id=5,
            type_incident="route_barree",
            severite="grave",
            verifie=False,
            fiabilite_source=0.75,
        ),
    ]

    db.add_all(incidents)
    db.commit()
    print("3 incidents demo crees avec succes :")
    for inc in incidents:
        print(
            f"  id={inc.id} | {inc.type_incident:15s} | "
            f"lat={inc.lat}, lon={inc.lon} | {inc.titre[:55]}"
        )
    db.close()


if __name__ == "__main__":
    main()
