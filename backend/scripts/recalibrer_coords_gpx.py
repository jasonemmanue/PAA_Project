"""Recalibrage des coordonnées des sous-tronçons et axes depuis les GPX terrain.

Coordonnées extraites des 26 fichiers GPX réels enregistrés le 2026-06-22
avec BasicAirData GPS Logger sur les 3 axes officiels DEESP.

Chaque point de jonction (landmark) est la MOYENNE des coordonnées de fin
du segment aller N et de début du segment aller N+1 (+ données retour
quand disponibles). Les points sont donc exactement SUR LA ROUTE.

Actions effectuées :
  1. Mise à jour des coordonnées lat/lon de chaque sous-tronçon actif
  2. Mise à jour des coordonnées lat/lon des 6 axes principaux
  3. Suppression des mesures existantes des sous-tronçons (données
     collectées avec les anciennes coordonnées, donc incohérentes)
  4. Régénération des polylines OSRM (si OSRM_BASE_URL est configurée)

Utilisation (Console Railway du service backend) :
    python -m scripts.recalibrer_coords_gpx
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import delete, text

from app.db.session import SessionLocal
from app.models.models import Mesure, SousTroncon, Troncon
from app.sources.coordonnees import PointGPS

# ---------------------------------------------------------------------------
# Coordonnées GPS terrain (moyenne aller/retour des fichiers GPX)
# ---------------------------------------------------------------------------

COORDS_SOUS_TRONCONS: dict[str, dict] = {
    "T1C": {
        "lat_debut": 5.317375, "lon_debut": -4.024489,
        "lat_fin":   5.306988, "lon_fin":   -4.021063,
    },
    "T1A": {
        "lat_debut": 5.306714, "lon_debut": -4.021347,
        "lat_fin":   5.303878, "lon_fin":   -4.023135,
    },
    "T2": {
        "lat_debut": 5.303789, "lon_debut": -4.022996,
        "lat_fin":   5.298873, "lon_fin":   -4.015610,
    },
    "T3": {
        "lat_debut": 5.298720, "lon_debut": -4.015441,
        "lat_fin":   5.293612, "lon_fin":   -4.008446,
    },
    "T4": {
        "lat_debut": 5.293532, "lon_debut": -4.008390,
        "lat_fin":   5.289217, "lon_fin":   -4.008357,
    },
    "T5": {
        "lat_debut": 5.288957, "lon_debut": -4.008391,
        "lat_fin":   5.282867, "lon_fin":   -4.008450,
    },
    "T6": {
        "lat_debut": 5.282770, "lon_debut": -4.008450,
        "lat_fin":   5.275927, "lon_fin":   -4.008550,
    },
    "T7": {
        "lat_debut": 5.275921, "lon_debut": -4.008554,
        "lat_fin":   5.268537, "lon_fin":   -4.004113,
    },
    "T8": {
        "lat_debut": 5.268501, "lon_debut": -4.004077,
        "lat_fin":   5.264857, "lon_fin":   -4.000071,
    },
    "T9": {
        "lat_debut": 5.264847, "lon_debut": -4.000058,
        "lat_fin":   5.256693, "lon_fin":   -3.997581,
    },
    "T10": {
        "lat_debut": 5.256601, "lon_debut": -3.997529,
        "lat_fin":   5.257501, "lon_fin":   -3.986028,
    },
    "T11": {
        "lat_debut": 5.257506, "lon_debut": -3.986017,
        "lat_fin":   5.258415, "lon_fin":   -3.981627,
    },
    "T1B": {
        "lat_debut": 5.293762, "lon_debut": -4.007786,
        "lat_fin":   5.293758, "lon_fin":   -4.008316,
    },
    "T1D": {
        "lat_debut": 5.293730, "lon_debut": -4.000654,
        "lat_fin":   5.275921, "lon_fin":   -4.008554,
    },
}

COORDS_AXES: dict[int, dict] = {
    1: {
        "lat_origine": 5.317375, "lon_origine": -4.024489,
        "lat_destination": 5.258348, "lon_destination": -3.981822,
    },
    2: {
        "lat_origine": 5.258348, "lon_origine": -3.981822,
        "lat_destination": 5.317375, "lon_destination": -4.024489,
    },
    3: {
        "lat_origine": 5.294394, "lon_origine": -4.006206,
        "lat_destination": 5.258348, "lon_destination": -3.981822,
    },
    4: {
        "lat_origine": 5.258348, "lon_origine": -3.981822,
        "lat_destination": 5.294394, "lon_destination": -4.006206,
    },
    5: {
        "lat_origine": 5.293730, "lon_origine": -4.000654,
        "lat_destination": 5.258348, "lon_destination": -3.981822,
    },
    6: {
        "lat_origine": 5.258348, "lon_origine": -3.981822,
        "lat_destination": 5.293730, "lon_destination": -4.000654,
    },
}


async def _regenerer_polylines(db):
    """Régénère les polylines OSRM pour tous les sous-tronçons et axes."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not settings.osrm_base_url:
            print("\n  OSRM_BASE_URL non configuree — polylines non regenerees.")
            print("  Lancer 'python -m app.complete_troncons' manuellement apres "
                  "avoir configure OSRM.")
            return
    except Exception:
        print("\n  Impossible de lire la config OSRM.")
        return

    from app.sources import osrm

    sous_troncons = (
        db.query(SousTroncon)
        .filter(SousTroncon.actif.is_(True))
        .order_by(SousTroncon.id)
        .all()
    )
    print(f"\n  Regeneration polylines OSRM pour {len(sous_troncons)} sous-troncons...")
    for s in sous_troncons:
        try:
            rep = await osrm.route(
                PointGPS(lat=s.lat_debut, lon=s.lon_debut),
                PointGPS(lat=s.lat_fin, lon=s.lon_fin),
            )
            ancien = s.distance_m
            s.polyline = rep.polyline_encodee
            s.distance_m = rep.distance_m
            print(f"    [OK] {s.code} {s.nom_court} : {ancien}m -> {rep.distance_m}m "
                  f"({len(rep.polyline_encodee)} car.)")
        except Exception as exc:
            print(f"    [ERREUR] {s.code} : {exc}")

    axes = (
        db.query(Troncon)
        .filter(Troncon.actif.is_(True), Troncon.id.in_(list(COORDS_AXES.keys())))
        .order_by(Troncon.id)
        .all()
    )
    print(f"\n  Regeneration polylines OSRM pour {len(axes)} axes...")
    for axe in axes:
        try:
            rep = await osrm.route(
                PointGPS(lat=axe.lat_origine, lon=axe.lon_origine),
                PointGPS(lat=axe.lat_destination, lon=axe.lon_destination),
            )
            ancien = axe.distance_m
            axe.polyline = rep.polyline_encodee
            axe.distance_m = rep.distance_m
            print(f"    [OK] id={axe.id} {axe.nom} : {ancien}m -> {rep.distance_m}m")
        except Exception as exc:
            print(f"    [ERREUR] id={axe.id} : {exc}")


def main():
    db = SessionLocal()
    try:
        # ===== ETAPE 1 : Mise a jour des sous-troncons =====
        print("=" * 70)
        print("ETAPE 1 : Mise a jour des coordonnees des sous-troncons")
        print("=" * 70)

        sous_troncons = (
            db.query(SousTroncon)
            .filter(SousTroncon.actif.is_(True))
            .order_by(SousTroncon.id)
            .all()
        )

        nb_maj = 0
        ids_sous_maj = []
        for s in sous_troncons:
            if s.code in COORDS_SOUS_TRONCONS:
                c = COORDS_SOUS_TRONCONS[s.code]
                print(f"  {s.code} (id={s.id}) {s.nom_court}")
                print(f"    AVANT: debut=({s.lat_debut:.6f}, {s.lon_debut:.6f}) "
                      f"fin=({s.lat_fin:.6f}, {s.lon_fin:.6f})")
                s.lat_debut = c["lat_debut"]
                s.lon_debut = c["lon_debut"]
                s.lat_fin = c["lat_fin"]
                s.lon_fin = c["lon_fin"]
                print(f"    APRES: debut=({s.lat_debut:.6f}, {s.lon_debut:.6f}) "
                      f"fin=({s.lat_fin:.6f}, {s.lon_fin:.6f})")
                nb_maj += 1
                ids_sous_maj.append(s.id)
            else:
                print(f"  {s.code} (id={s.id}) — code non reconnu, ignore")

        print(f"\n  -> {nb_maj} sous-troncons mis a jour\n")

        # ===== ETAPE 2 : Mise a jour des axes principaux =====
        print("=" * 70)
        print("ETAPE 2 : Mise a jour des coordonnees des axes principaux")
        print("=" * 70)

        nb_axes_maj = 0
        for axe_id, coords in COORDS_AXES.items():
            axe = db.get(Troncon, axe_id)
            if axe and axe.actif:
                print(f"  Axe {axe_id} : {axe.nom}")
                print(f"    AVANT: orig=({axe.lat_origine}, {axe.lon_origine}) "
                      f"dest=({axe.lat_destination}, {axe.lon_destination})")
                axe.lat_origine = coords["lat_origine"]
                axe.lon_origine = coords["lon_origine"]
                axe.lat_destination = coords["lat_destination"]
                axe.lon_destination = coords["lon_destination"]
                print(f"    APRES: orig=({axe.lat_origine}, {axe.lon_origine}) "
                      f"dest=({axe.lat_destination}, {axe.lon_destination})")
                nb_axes_maj += 1
            else:
                print(f"  Axe {axe_id} non trouve ou archive")

        print(f"\n  -> {nb_axes_maj} axes mis a jour\n")

        # ===== ETAPE 3 : Suppression des mesures des sous-troncons =====
        print("=" * 70)
        print("ETAPE 3 : Suppression des mesures des sous-troncons")
        print("=" * 70)

        if ids_sous_maj:
            nb_suppr = db.execute(
                delete(Mesure).where(Mesure.sous_troncon_id.in_(ids_sous_maj))
            ).rowcount
            print(f"  -> {nb_suppr} mesure(s) supprimee(s) pour les sous-troncons "
                  f"ids={ids_sous_maj}")
        else:
            print("  -> Aucun sous-troncon mis a jour, rien a supprimer")

        # ===== ETAPE 4 : Regeneration des polylines OSRM =====
        print("\n" + "=" * 70)
        print("ETAPE 4 : Regeneration des polylines OSRM")
        print("=" * 70)

        asyncio.run(_regenerer_polylines(db))

        # ===== COMMIT =====
        db.commit()
        print("\n" + "=" * 70)
        print("COMMIT OK — toutes les modifications ont ete persistees.")
        print("=" * 70)
        print(f"\nResume : {nb_maj} sous-troncons + {nb_axes_maj} axes recalibres")
        print("La collecte Google reprendra avec les nouvelles coordonnees")
        print("au prochain cycle du scheduler.")

    except Exception as exc:
        db.rollback()
        print(f"\nERREUR — rollback effectue : {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
