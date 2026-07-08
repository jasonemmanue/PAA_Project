"""Script Railway Console — supprime TOUS les incidents existants.

Utilisé pour vider la base d'incidents obsolètes et forcer un
re-scraping propre après la correction du filtre de détection.

Utilisation (Console Railway, service backend) :
    python -m scripts.supprimer_incidents_demo

Idempotent : sans effet si la table est déjà vide.
"""

from app.db.session import SessionLocal
from app.models.models import Incident


def main() -> None:
    db = SessionLocal()
    try:
        n = db.query(Incident).delete(synchronize_session=False)
        db.commit()
        print(f"{n} incident(s) supprimé(s). Table vide — prêt pour un re-scraping propre.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
