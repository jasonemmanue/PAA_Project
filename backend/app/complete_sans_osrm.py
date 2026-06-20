"""Complète les tronçons SANS appel à OSRM — usage Railway (où OSRM n'est pas exposé).

Pose les coordonnées canoniques depuis `app/sources/coordonnees.py` et fabrique
une **polyline rudimentaire** à 2 points (origine → destination, segment droit).
La distance_m est recalculée par Haversine sur le segment droit.

⚠️ La polyline obtenue est un **trait droit** entre les 4 POI — utile pour que
la carte affiche quelque chose mais beaucoup moins précis qu'un tracé OSRM
suivant le réseau routier. Dès qu'OSRM est exposé (cf. CLAUDE.md § 8.3),
relancer `python -m app.complete_troncons` pour avoir les vraies polylines.

Différence avec les scripts voisins :

  - `seed_troncons.py`        → insère les 6 lignes (noms, distance officielle), coords NULL.
  - `complete_troncons.py`    → coords + polyline + distance via OSRM (besoin OSRM exposé).
  - **`complete_sans_osrm.py`** → coords + polyline droite + distance Haversine, sans OSRM.
  - `set_coords_depuis_seed.py` → uniquement coords (laisse polyline et distance inchangées).

Utilisation :

    # Local (Docker Compose)
    docker compose exec backend python -m app.complete_sans_osrm

    # Sur Railway → service backend → Console
    python -m app.complete_sans_osrm
"""

from __future__ import annotations

import sys
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

# Garantit que le dossier backend/ est dans le PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.models import Troncon
from app.sources.coordonnees import PointGPS, origine_destination


def _haversine_m(a: PointGPS, b: PointGPS) -> int:
    """Distance entre deux points GPS en mètres (Haversine, formule standard)."""
    R = 6_371_000.0  # rayon terrestre moyen
    lat1, lat2 = radians(a.lat), radians(b.lat)
    dlat = lat2 - lat1
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return int(round(2 * R * asin(sqrt(h))))


def _encoder_signe(n: int) -> str:
    """Encode un entier signé selon l'algo Google Polyline."""
    n = n << 1
    if n < 0:
        n = ~n
    chunks: list[str] = []
    while n >= 0x20:
        chunks.append(chr((0x20 | (n & 0x1F)) + 63))
        n >>= 5
    chunks.append(chr(n + 63))
    return "".join(chunks)


def encoder_polyline(points: list[tuple[float, float]]) -> str:
    """Encode une liste de (lat, lon) en chaîne Google polyline precision 5.

    Algorithme : https://developers.google.com/maps/documentation/utilities/polylinealgorithm
    """
    result: list[str] = []
    prev_lat = 0
    prev_lon = 0
    for lat, lon in points:
        lat_int = round(lat * 1e5)
        lon_int = round(lon * 1e5)
        result.append(_encoder_signe(lat_int - prev_lat))
        result.append(_encoder_signe(lon_int - prev_lon))
        prev_lat = lat_int
        prev_lon = lon_int
    return "".join(result)


def completer_tous_sans_osrm() -> None:
    """Met à jour les coordonnées + polyline (2 points) + distance Haversine.

    Idempotent : rejouable autant de fois qu'on veut, écrase les valeurs
    précédentes par le calcul à partir de `coordonnees.py`.
    """
    db = SessionLocal()
    try:
        troncons = (
            db.query(Troncon).filter(Troncon.actif.is_(True)).order_by(Troncon.id).all()
        )
        if not troncons:
            print("Aucun tronçon actif en base — rien à compléter.")
            return

        print(f"Complétion sans OSRM de {len(troncons)} tronçons…\n")
        echecs = 0

        for troncon in troncons:
            try:
                origine, destination = origine_destination(troncon.nom)
            except (KeyError, ValueError) as exc:
                print(f"  [ignoré]  id={troncon.id}  {troncon.nom!r} — {exc}")
                echecs += 1
                continue

            distance_avant = troncon.distance_m
            distance_haversine = _haversine_m(origine, destination)
            polyline = encoder_polyline([
                (origine.lat, origine.lon),
                (destination.lat, destination.lon),
            ])

            troncon.lat_origine = origine.lat
            troncon.lon_origine = origine.lon
            troncon.lat_destination = destination.lat
            troncon.lon_destination = destination.lon
            troncon.polyline = polyline
            # On NE remplace PAS `distance_m` officielle par Haversine — la
            # distance du cahier des charges (14,9 km, 8 km, 8,3 km) reste
            # la référence pour le temps de référence 50 km/h. Haversine est
            # juste loggée pour info (souvent ~50-70% de la distance routière).
            ratio = distance_haversine / distance_avant if distance_avant else 0
            print(
                f"  [OK]      id={troncon.id}  {troncon.nom}\n"
                f"            coords    : ({origine.lat:.6f}, {origine.lon:.6f}) → "
                f"({destination.lat:.6f}, {destination.lon:.6f})\n"
                f"            distance  : officielle {distance_avant} m, "
                f"haversine {distance_haversine} m (ratio {ratio:.2f})\n"
                f"            polyline  : {len(polyline)} caractères (segment droit)"
            )

        db.commit()
        print(
            f"\nComplétion sans OSRM terminée — {len(troncons) - echecs}/{len(troncons)} "
            f"tronçons mis à jour."
        )
        print(
            "\n⚠️  Polyline = trait droit. Pour de vraies polylines routières, "
            "exposer OSRM puis lancer `python -m app.complete_troncons`."
        )
        if echecs > 0:
            print(f"⚠️  {echecs} tronçon(s) en échec — voir messages ci-dessus.")
    except Exception as exc:
        db.rollback()
        print(f"\nErreur globale, rollback effectué : {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    completer_tous_sans_osrm()
