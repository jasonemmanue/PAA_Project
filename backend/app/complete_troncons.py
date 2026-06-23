"""Complète les tronçons à partir d'OSRM : coordonnées, polyline, distance réelle.

Pour chaque tronçon en base (actif=True), on :
  1. Déduit origine/destination depuis le nom (cf. `sources/coordonnees.py`).
  2. Appelle OSRM /route pour obtenir distance et polyline encodée.
  3. Met à jour les colonnes lat_*, lon_*, polyline et distance_m.

⚠️ La `distance_m` officielle du cahier des charges (14900 / 8000 / 8300 m)
   est volontairement remplacée par la distance OSRM, car c'est cette dernière
   qui correspond au tracé que TOUTES les sources de mesure suivent. Cohérence
   avant tout.

Utilisation :
    docker compose exec backend python -m app.complete_troncons
"""

import asyncio
import sys
from pathlib import Path

# Garantit que le dossier backend/ est dans le PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.models import SousTroncon, Troncon
from app.sources import osrm
from app.sources.coordonnees import PointGPS, origine_destination


async def completer_tous() -> None:
    """Met à jour les coordonnées/polyline/distance de tous les tronçons actifs."""
    db = SessionLocal()
    try:
        troncons = db.query(Troncon).filter(Troncon.actif.is_(True)).order_by(Troncon.id).all()
        if not troncons:
            print("Aucun tronçon actif en base — rien à compléter.")
            return

        print(f"Complétion via OSRM de {len(troncons)} tronçons…\n")
        echecs = 0

        for troncon in troncons:
            # Coords : d'abord celles en base (créées via Admin), sinon mapping par nom
            point_origine: PointGPS | None = None
            point_destination: PointGPS | None = None
            if (
                troncon.lat_origine is not None and troncon.lon_origine is not None
                and troncon.lat_destination is not None and troncon.lon_destination is not None
            ):
                point_origine = PointGPS(lat=troncon.lat_origine, lon=troncon.lon_origine)
                point_destination = PointGPS(
                    lat=troncon.lat_destination, lon=troncon.lon_destination,
                )
            else:
                try:
                    point_origine, point_destination = origine_destination(troncon.nom)
                except (KeyError, ValueError) as exc:
                    print(f"  [ignoré] id={troncon.id}  {troncon.nom!r} — {exc}")
                    echecs += 1
                    continue

            try:
                reponse = await osrm.route(point_origine, point_destination)
            except Exception as exc:
                print(f"  [erreur] id={troncon.id}  OSRM a échoué : {exc}")
                echecs += 1
                continue

            distance_avant = troncon.distance_m
            troncon.lat_origine = point_origine.lat
            troncon.lon_origine = point_origine.lon
            troncon.lat_destination = point_destination.lat
            troncon.lon_destination = point_destination.lon
            troncon.polyline = reponse.polyline_encodee
            troncon.distance_m = reponse.distance_m

            ecart_m = reponse.distance_m - distance_avant
            print(
                f"  [OK]      id={troncon.id}  {troncon.nom}\n"
                f"            distance : {distance_avant} m → {reponse.distance_m} m "
                f"({ecart_m:+d} m), polyline : {len(reponse.polyline_encodee)} caractères"
            )

        # Sous-tronçons : on a leurs coords explicites (lat_debut/fin) en base,
        # donc on peut systématiquement appeler OSRM pour la polyline.
        sous = db.query(SousTroncon).filter(SousTroncon.actif.is_(True)).order_by(SousTroncon.id).all()
        if sous:
            print(f"\nComplétion via OSRM de {len(sous)} sous-tronçons…\n")
            for s in sous:
                try:
                    reponse_s = await osrm.route(
                        PointGPS(lat=s.lat_debut, lon=s.lon_debut),
                        PointGPS(lat=s.lat_fin, lon=s.lon_fin),
                    )
                    distance_avant_s = s.distance_m
                    s.polyline = reponse_s.polyline_encodee
                    s.distance_m = reponse_s.distance_m
                    print(
                        f"  [OK]      id={s.id}  {s.code} — {s.nom_court}\n"
                        f"            distance : {distance_avant_s} m → {reponse_s.distance_m} m, "
                        f"polyline : {len(reponse_s.polyline_encodee)} car."
                    )
                except Exception as exc:
                    print(f"  [erreur] sous-tronçon id={s.id} {s.code} — {exc}")

        db.commit()
        print(
            f"\nComplétion terminée — {len(troncons) - echecs}/{len(troncons)} tronçons mis à jour."
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
    asyncio.run(completer_tous())
