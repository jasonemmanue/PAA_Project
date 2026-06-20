"""Réaligne les colonnes lat_*/lon_* des troncons sur app/sources/coordonnees.py.

Contexte : la DB Railway a été initialisée avec des coordonnées différentes des
valeurs canoniques actuelles de `coordonnees.py`. Ce script remet tous les
tronçons en cohérence avec le code source, **sans toucher** à `polyline` ou
`distance_m` (donc pas besoin d'OSRM exposé sur Railway).

Idempotent : à chaque run, les tronçons sont remis à la valeur canonique. Si
elles sont déjà correctes, aucune ligne n'est modifiée.

Utilisation :

    # Local
    docker compose exec backend python -m app.realigner_coordonnees

    # Sur Railway — depuis la Console du service backend
    python -m app.realigner_coordonnees

Sortie : compte-rendu par tronçon avec l'écart Haversine entre l'ancienne et la
nouvelle position d'origine, pour confirmer visuellement la correction.
"""

from __future__ import annotations

import sys
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

# Garantit que le dossier backend/ est dans le PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.models.models import Troncon  # noqa: E402
from app.sources.coordonnees import origine_destination  # noqa: E402


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en mètres entre deux points GPS."""
    R = 6_371_000.0
    lat1r, lat2r = radians(lat1), radians(lat2)
    dlat = lat2r - lat1r
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def realigner() -> None:
    db = SessionLocal()
    try:
        troncons = (
            db.query(Troncon)
            .filter(Troncon.actif.is_(True))
            .order_by(Troncon.id)
            .all()
        )
        if not troncons:
            print("Aucun tronçon actif en base — rien à réaligner.")
            return

        print(f"Réalignement de {len(troncons)} tronçons sur coordonnees.py\n")
        nb_modifies = 0

        for troncon in troncons:
            try:
                point_origine, point_destination = origine_destination(troncon.nom)
            except (KeyError, ValueError) as exc:
                print(f"  [ignoré] id={troncon.id}  {troncon.nom!r} — {exc}")
                continue

            ancienne_orig = (troncon.lat_origine, troncon.lon_origine)
            ancienne_dest = (troncon.lat_destination, troncon.lon_destination)
            nouvelle_orig = (point_origine.lat, point_origine.lon)
            nouvelle_dest = (point_destination.lat, point_destination.lon)

            if ancienne_orig == nouvelle_orig and ancienne_dest == nouvelle_dest:
                print(f"  [inchangé] id={troncon.id}  {troncon.nom}")
                continue

            ecart_orig = (
                haversine_m(*ancienne_orig, *nouvelle_orig)
                if all(v is not None for v in ancienne_orig)
                else None
            )
            ecart_dest = (
                haversine_m(*ancienne_dest, *nouvelle_dest)
                if all(v is not None for v in ancienne_dest)
                else None
            )

            troncon.lat_origine = point_origine.lat
            troncon.lon_origine = point_origine.lon
            troncon.lat_destination = point_destination.lat
            troncon.lon_destination = point_destination.lon
            nb_modifies += 1

            print(
                f"  [OK]      id={troncon.id}  {troncon.nom}\n"
                f"            origine     : déplacée de {ecart_orig:>7.0f} m"
                if ecart_orig is not None
                else f"            origine     : initialisée (avant : NULL)"
            )
            print(
                f"            destination : déplacée de {ecart_dest:>7.0f} m"
                if ecart_dest is not None
                else f"            destination : initialisée (avant : NULL)"
            )

        db.commit()
        print(
            f"\nRéalignement terminé — {nb_modifies}/{len(troncons)} tronçons modifiés."
        )
        if nb_modifies > 0:
            print(
                "\nNote : `polyline` et `distance_m` n'ont PAS été touchés. Si la "
                "carte du frontend affiche un tracé incohérent, relance "
                "`complete_troncons` (nécessite OSRM exposé)."
            )
    except Exception as exc:
        db.rollback()
        print(f"\nErreur globale, rollback effectué : {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    realigner()
