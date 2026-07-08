"""Script Railway Console — supprime les 3 incidents démo de la base.

Les incidents démo utilisaient le domaine fictif `demo.fluidis.paa` ;
ils ne correspondent à aucun article réel et ne doivent pas figurer
en production.

Utilisation (Console Railway, service backend) :
    python -m scripts.supprimer_incidents_demo

Idempotent : sans effet si les incidents ont déjà été supprimés.
"""

from app.db.session import SessionLocal
from app.models.models import Incident


def main() -> None:
    db = SessionLocal()
    try:
        n = (
            db.query(Incident)
            .filter(Incident.source_url.like("https://demo.fluidis.paa/%"))
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"{n} incident(s) démo supprimé(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
