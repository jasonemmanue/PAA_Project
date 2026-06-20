"""Génère 6 GPX synthétiques (Option A — cf. discussion P5).

Pour chaque tronçon actif et résolu :

  1. Appelle OSRM `/route` pour récupérer la polyline et la durée fluide.
  2. Décode la polyline → liste de (lat, lon).
  3. Sur-échantillonne le tracé pour avoir un point à peu près chaque seconde
     (sinon le GPX final est trop court pour être réaliste).
  4. Calcule un horodatage pour chaque point en supposant une vitesse moyenne
     proche du temps fluide OSRM (par défaut). On peut multiplier ce temps
     par un coefficient `--congestion` pour simuler du trafic.
  5. Écrit un fichier GPX 1.1 standard dans le dossier choisi.

Usage (depuis le conteneur backend ou un venv local avec OSRM_BASE_URL défini) :
    python -m app.generer_gpx_synthetiques --sortie /data/gpx_synth --congestion 1.4

Le GPX produit est directement importable via POST /terrain/import.
Si plusieurs tronçons sont rassemblés en UN seul GPX (option `--combiner`),
la trace est concaténée chronologiquement et l'endpoint terrain redécoupera
automatiquement aux bornes des tronçons.

⚠️  C'est un OUTIL DE DÉVELOPPEMENT, pas une source de données terrain. Les
    GPX produits sont par construction quasi-identiques au tracé OSRM officiel,
    donc l'écart relatif Google ↔ GPX sera proche de 0 — c'est attendu et
    sert uniquement à valider la boucle d'import.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Permet de lancer le script via `python backend/app/generer_gpx_synthetiques.py`
# en plus de `python -m app.generer_gpx_synthetiques`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.models.models import Troncon  # noqa: E402
from app.sources import osrm  # noqa: E402
from app.sources.coordonnees import PointGPS  # noqa: E402

logger = logging.getLogger("paa.gpx-synth")


# ---------------------------------------------------------------------------
# Décodage Google Polyline (precision 5) — pas de dépendance externe
# ---------------------------------------------------------------------------


def decoder_polyline(polyline: str) -> list[tuple[float, float]]:
    """Décode une polyline encodée (precision 5) en liste de (lat, lon)."""
    coords: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    while index < len(polyline):
        shift = 0
        result = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat
        shift = 0
        result = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if result & 1 else result >> 1
        lon += dlon
        coords.append((lat * 1e-5, lon * 1e-5))
    return coords


# ---------------------------------------------------------------------------
# Interpolation linéaire — pour atteindre ~1 point par seconde
# ---------------------------------------------------------------------------


def interpoler_points(
    points: list[tuple[float, float]],
    nb_total_cible: int,
) -> list[tuple[float, float]]:
    """Interpole linéairement pour atteindre `nb_total_cible` points.

    Conserve les extrémités exactes.
    """
    if nb_total_cible <= len(points):
        return points
    if len(points) < 2:
        return points

    # Calcul des distances cumulées (proxy : segments euclidiens en degrés)
    cumul = [0.0]
    for i in range(1, len(points)):
        dx = points[i][1] - points[i - 1][1]
        dy = points[i][0] - points[i - 1][0]
        cumul.append(cumul[-1] + (dx * dx + dy * dy) ** 0.5)
    longueur_totale = cumul[-1] or 1.0

    sortie: list[tuple[float, float]] = []
    for k in range(nb_total_cible):
        ratio = k / (nb_total_cible - 1)
        cible = ratio * longueur_totale
        # Cherche l'intervalle qui contient `cible`
        j = 1
        while j < len(cumul) and cumul[j] < cible:
            j += 1
        if j >= len(cumul):
            sortie.append(points[-1])
            continue
        # Interpolation linéaire entre points[j-1] et points[j]
        d0, d1 = cumul[j - 1], cumul[j]
        if d1 == d0:
            sortie.append(points[j - 1])
            continue
        t = (cible - d0) / (d1 - d0)
        lat = points[j - 1][0] + t * (points[j][0] - points[j - 1][0])
        lon = points[j - 1][1] + t * (points[j][1] - points[j - 1][1])
        sortie.append((lat, lon))
    return sortie


# ---------------------------------------------------------------------------
# Construction du GPX 1.1
# ---------------------------------------------------------------------------


def construire_gpx(
    nom_trace: str,
    points: list[tuple[float, float]],
    horodatage_debut: datetime,
    duree_totale_s: float,
) -> bytes:
    """Construit un document GPX 1.1 avec un seul track, un seul segment.

    Les horodatages sont répartis uniformément sur `duree_totale_s`.
    """
    if len(points) < 2:
        raise ValueError("Au moins 2 points sont nécessaires pour un GPX valide.")

    ns_gpx = "http://www.topografix.com/GPX/1/1"
    ET.register_namespace("", ns_gpx)
    gpx = ET.Element(f"{{{ns_gpx}}}gpx", attrib={
        "version": "1.1",
        "creator": "PAA-Traverse generer_gpx_synthetiques",
    })
    metadata = ET.SubElement(gpx, f"{{{ns_gpx}}}metadata")
    ET.SubElement(metadata, f"{{{ns_gpx}}}name").text = nom_trace
    ET.SubElement(metadata, f"{{{ns_gpx}}}time").text = horodatage_debut.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    trk = ET.SubElement(gpx, f"{{{ns_gpx}}}trk")
    ET.SubElement(trk, f"{{{ns_gpx}}}name").text = nom_trace
    trkseg = ET.SubElement(trk, f"{{{ns_gpx}}}trkseg")

    pas_s = duree_totale_s / max(1, len(points) - 1)
    for i, (lat, lon) in enumerate(points):
        instant = horodatage_debut + timedelta(seconds=pas_s * i)
        trkpt = ET.SubElement(trkseg, f"{{{ns_gpx}}}trkpt", attrib={
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
        })
        ET.SubElement(trkpt, f"{{{ns_gpx}}}time").text = instant.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    arbre = ET.ElementTree(gpx)
    # Encodage XML standard avec déclaration
    from io import BytesIO

    flux = BytesIO()
    arbre.write(flux, encoding="utf-8", xml_declaration=True)
    return flux.getvalue()


# ---------------------------------------------------------------------------
# Orchestration : un GPX par tronçon
# ---------------------------------------------------------------------------


@dataclass
class GpxGenere:
    troncon_id: int
    chemin: Path
    nb_points: int
    duree_simulee_s: float


async def generer_pour_troncon(
    troncon: Troncon,
    dossier_sortie: Path,
    *,
    horodatage_depart: datetime,
    facteur_congestion: float,
) -> GpxGenere:
    """Génère un GPX pour un tronçon, basé sur la polyline OSRM /route."""
    origine = PointGPS(lat=troncon.lat_origine, lon=troncon.lon_origine)
    destination = PointGPS(lat=troncon.lat_destination, lon=troncon.lon_destination)
    reponse = await osrm.route(origine, destination)

    points_bruts = decoder_polyline(reponse.polyline_encodee)
    duree_simulee_s = max(1.0, reponse.duree_sans_trafic_s * facteur_congestion)
    # Cible : 1 point par seconde, plafonné à 1500 pour éviter des GPX énormes.
    nb_cible = min(1500, max(int(duree_simulee_s), len(points_bruts)))
    points_lisses = interpoler_points(points_bruts, nb_cible)

    contenu = construire_gpx(
        nom_trace=troncon.nom,
        points=points_lisses,
        horodatage_debut=horodatage_depart,
        duree_totale_s=duree_simulee_s,
    )

    dossier_sortie.mkdir(parents=True, exist_ok=True)
    nom_fichier = f"troncon_{troncon.id:02d}_{_slug(troncon.nom)}.gpx"
    chemin = dossier_sortie / nom_fichier
    chemin.write_bytes(contenu)

    return GpxGenere(
        troncon_id=troncon.id,
        chemin=chemin,
        nb_points=len(points_lisses),
        duree_simulee_s=duree_simulee_s,
    )


def _slug(texte: str) -> str:
    import re
    import unicodedata
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Za-z0-9._-]+", "_", sans_accents).strip("_")


async def main_async(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    dossier_sortie = Path(args.sortie).resolve()

    session = SessionLocal()
    try:
        from sqlalchemy import select
        troncons = list(
            session.execute(
                select(Troncon).where(
                    Troncon.actif.is_(True),
                    Troncon.lat_origine.is_not(None),
                    Troncon.lon_origine.is_not(None),
                    Troncon.lat_destination.is_not(None),
                    Troncon.lon_destination.is_not(None),
                ).order_by(Troncon.id)
            ).scalars()
        )
    finally:
        session.close()

    if not troncons:
        logger.error(
            "Aucun tronçon actif et résolu trouvé. Lancer d'abord :\n"
            "  python -m app.seed_troncons\n"
            "  python -m app.complete_troncons"
        )
        sys.exit(1)

    if args.horodatage_debut:
        try:
            horodatage_depart = datetime.fromisoformat(args.horodatage_debut)
        except ValueError as exc:
            logger.error(
                "Format ISO invalide pour --horodatage-debut : %s "
                "(ex. attendu : '2026-06-19T14:00:00').", exc,
            )
            sys.exit(1)
        if horodatage_depart.tzinfo is None:
            horodatage_depart = horodatage_depart.replace(tzinfo=timezone.utc)
    else:
        horodatage_depart = datetime.now(tz=timezone.utc).replace(
            hour=8, minute=0, second=0, microsecond=0,
        )
    logger.info(
        "Premier tronçon démarre à %s (UTC). Les suivants s'enchaînent "
        "10 min après la fin du précédent.",
        horodatage_depart.isoformat(),
    )

    resultats: list[GpxGenere] = []
    for troncon in troncons:
        logger.info("Génération du GPX pour le tronçon %d (%s)…", troncon.id, troncon.nom)
        try:
            res = await generer_pour_troncon(
                troncon,
                dossier_sortie,
                horodatage_depart=horodatage_depart,
                facteur_congestion=args.congestion,
            )
        except Exception:
            logger.exception("Échec pour le tronçon %d", troncon.id)
            continue
        resultats.append(res)
        # Le tronçon suivant démarre 10 min après la fin du précédent
        horodatage_depart = horodatage_depart + timedelta(seconds=res.duree_simulee_s + 600)

    logger.info("Terminé — %d GPX générés dans %s :", len(resultats), dossier_sortie)
    for r in resultats:
        logger.info(
            "  - tronçon %d → %s (%d points, %.0fs)",
            r.troncon_id, r.chemin.name, r.nb_points, r.duree_simulee_s,
        )


def parser_arguments() -> argparse.Namespace:
    parseur = argparse.ArgumentParser(
        description="Génère des GPX synthétiques pour tester l'import terrain (P5)."
    )
    parseur.add_argument(
        "--sortie",
        default="./data/gpx_synth",
        help="Dossier où écrire les GPX (défaut : ./data/gpx_synth).",
    )
    parseur.add_argument(
        "--congestion",
        type=float,
        default=1.4,
        help=(
            "Facteur multiplicateur du temps fluide OSRM (défaut 1.4 — simule "
            "un trafic moyen). 1.0 = pas de congestion, 2.0 = très fort trafic."
        ),
    )
    parseur.add_argument(
        "--horodatage-debut",
        default=None,
        help=(
            "Horodatage ISO 8601 du premier point du premier tronçon "
            "(ex. '2026-06-19T14:00:00'). UTC si pas de fuseau. Si omis, "
            "utilise aujourd'hui à 08:00 UTC. Utile pour caller les GPX sur "
            "une fenêtre où des mesures Google existent déjà en base "
            "(validation P5)."
        ),
    )
    return parseur.parse_args()


def main() -> None:
    args = parser_arguments()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
