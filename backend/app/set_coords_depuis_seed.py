"""Réaligne les coordonnées des tronçons depuis la table canonique `coordonnees.py`.

À utiliser quand la DB (locale ou Railway) a des `lat_origine`/`lon_origine`/
`lat_destination`/`lon_destination` qui ne correspondent plus aux constantes
définies dans `app/sources/coordonnees.py`. Le cas typique : Railway a été
seedé tôt dans le projet avec d'anciennes valeurs et n'a jamais fait tourner
`complete_troncons.py` (qui aurait écrasé les coords depuis le même fichier).

Différence avec `complete_troncons.py` :
  - Ce script **ne touche pas** à OSRM — donc utilisable même quand OSRM n'est
    pas exposé (sur Railway en particulier).
  - Il ne modifie ni la polyline ni la distance_m — uniquement les coords.

Utilisation :

    # Local (via Docker Compose)
    docker compose exec backend python -m app.set_coords_depuis_seed

    # Sur Railway → service backend → Console
    python -m app.set_coords_depuis_seed
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garantit que le dossier backend/ est dans le PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.models import Troncon
from app.sources.coordonnees import origine_destination


def synchroniser() -> None:
    """Réécrit lat/lon de chaque tronçon depuis `coordonnees.py`."""
    db = SessionLocal()
    try:
        troncons = (
            db.query(Troncon).filter(Troncon.actif.is_(True)).order_by(Troncon.id).all()
        )
        if not troncons:
            print("Aucun tronçon actif en base — rien à synchroniser.")
            return

        print(f"Synchronisation des coordonnées de {len(troncons)} tronçons…\n")
        modifies = 0
        inchanges = 0

        for troncon in troncons:
            try:
                origine, destination = origine_destination(troncon.nom)
            except (KeyError, ValueError) as exc:
                print(f"  [ignoré]  id={troncon.id}  {troncon.nom!r} — {exc}")
                continue

            avant = (
                troncon.lat_origine, troncon.lon_origine,
                troncon.lat_destination, troncon.lon_destination,
            )
            apres = (origine.lat, origine.lon, destination.lat, destination.lon)

            if avant == apres:
                print(f"  [inchangé] id={troncon.id}  {troncon.nom}")
                inchanges += 1
                continue

            troncon.lat_origine = origine.lat
            troncon.lon_origine = origine.lon
            troncon.lat_destination = destination.lat
            troncon.lon_destination = destination.lon

            print(
                f"  [MAJ]      id={troncon.id}  {troncon.nom}\n"
                f"             origine      : ({avant[0]}, {avant[1]}) → "
                f"({apres[0]}, {apres[1]})\n"
                f"             destination  : ({avant[2]}, {avant[3]}) → "
                f"({apres[2]}, {apres[3]})"
            )
            modifies += 1

        db.commit()
        print(
            f"\nSync terminée — {modifies} tronçon(s) modifié(s), "
            f"{inchanges} déjà à jour."
        )
        print(
            "\nNote : polyline et distance_m **NE SONT PAS** modifiées par ce script. "
            "Pour les recalculer, lancer `python -m app.complete_troncons` "
            "(nécessite OSRM exposé)."
        )
    except Exception as exc:
        db.rollback()
        print(f"\nErreur, rollback effectué : {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    synchroniser()
