"""Script d'import des 26 fichiers GPX terrain du 2026-06-22.

Usage (depuis le dossier backend/) :
    python -m scripts.importer_segments_gpx [--api-url URL] [--dossier DOSSIER]

Arguments :
    --api-url    URL du backend PAA (défaut : http://localhost:8000)
    --dossier    Dossier contenant les fichiers .gpx (défaut : détecté auto)
    --dry-run    Affiche l'analyse sans envoyer de requêtes

Principes :
  1. Lit chaque fichier GPX, extrait le premier/dernier point GPS et la durée.
  2. Assigne chaque segment à un tronçon et une direction (aller/retour)
     selon la table de correspondance codée ci-dessous.
  3. Appelle POST /terrain/segments/import pour chaque fichier.
  4. Affiche un résumé des temps de traversée par tronçon.

Affectation des sessions (déterminée par analyse géographique) :
  Session A (08:45–09:45) : CARENA->Palm Beach aller       -> troncon_id=1
  Session B (09:45–10:19) : Palm Beach->CARENA retour (partial)  -> troncon_id=2
  Session C (10:20–10:31) : Toyota↔Carrefour Seamen's     -> troncon_id=3 / 4
  Session D (10:36)        : SODECI->Gendarmerie du port aller  -> troncon_id=5
  Session E (11:03–11:09) : Carrefour->GMA retour partial  -> troncon_id=2

Cf. CLAUDE.md § 4.9.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import gpxpy


# ---------------------------------------------------------------------------
# Table de correspondance fichier -> métadonnées
# ---------------------------------------------------------------------------

@dataclass
class MetaSegment:
    nom: str
    troncon_id: int | None
    direction: str         # 'aller' | 'retour'
    session_id: str


# Clé = sous-chaîne unique du nom de fichier (après le timestamp)
# Ordre = chronologique (session A -> B -> C -> D -> E)
SEGMENTS_CONFIG: list[tuple[str, MetaSegment]] = [
    # -----------------------------------------------------------------------
    # Session A — CARENA -> Palm Beach  (aller, troncon_id=1)
    # Durées observées le lundi 2026-06-22 matin (~09h, heure de pointe)
    # -----------------------------------------------------------------------
    ("CARENA-GMA", MetaSegment(
        "CARENA -> GMA", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("GMA-COMMISSARIAT", MetaSegment(
        "GMA -> Commissariat Spécial", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Commissariat-Sim Ivoire", MetaSegment(
        "Commissariat Spécial -> Sim Ivoire", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Sim Ivoire-Carrefour", MetaSegment(
        "Sim Ivoire -> Carrefour Seamen's", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Carrefour Seamen's -pharmacie du port", MetaSegment(
        "Carrefour Seamen's -> Pharmacie du port", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Pharmacie du port-Unilever", MetaSegment(
        "Pharmacie du port -> Unilever", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Unilever-Atc comafrique", MetaSegment(
        "Unilever -> ATC Comafrique", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("ATC COMAFRIQUE-Sgb Ci", MetaSegment(
        "ATC Comafrique -> SGBCI", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Sgbci -Dgi", MetaSegment(
        "SGBCI -> DGI", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("DGI-TERMINUS19", MetaSegment(
        "DGI -> Terminus 19", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Terminus19-siège olibia", MetaSegment(
        "Terminus 19 -> Siège Olibia", troncon_id=1, direction="aller", session_id="20260622_A"
    )),
    ("Siège Olivia-Pharmacie palmbeach", MetaSegment(
        "Siège Olibia -> Pharmacie Palm Beach", troncon_id=1, direction="aller", session_id="20260622_A"
    )),

    # -----------------------------------------------------------------------
    # Session B — Palm Beach -> CARENA  (retour, troncon_id=2, partiel)
    # Couvre Palm Beach -> Carrefour Seamen's (~54 % du retour)
    # -----------------------------------------------------------------------
    ("Pharmacie palmbeach-siège olibia", MetaSegment(
        "Pharmacie Palm Beach -> Siège Olibia", troncon_id=2, direction="retour", session_id="20260622_B"
    )),
    ("Station Olibia-Terminus 19", MetaSegment(
        "Station Olibia -> Terminus 19", troncon_id=2, direction="retour", session_id="20260622_B"
    )),
    ("Terminus 19-Dgi", MetaSegment(
        "Terminus 19 -> DGI", troncon_id=2, direction="retour", session_id="20260622_B"
    )),
    ("Dgi - Sgb Ci", MetaSegment(
        "DGI -> SGBCI", troncon_id=2, direction="retour", session_id="20260622_B"
    )),
    ("Sgbci-atc com afrique", MetaSegment(
        "SGBCI -> ATC Comafrique", troncon_id=2, direction="retour", session_id="20260622_B"
    )),
    ("Atci com Afrique-unilever", MetaSegment(
        "ATC Comafrique -> Unilever", troncon_id=2, direction="retour", session_id="20260622_B"
    )),
    ("UNILEVER-Pharmacie du port", MetaSegment(
        "Unilever -> Pharmacie du port", troncon_id=2, direction="retour", session_id="20260622_B"
    )),
    ("Pharmacie du port -Carrefour seamen's", MetaSegment(
        "Pharmacie du port -> Carrefour Seamen's", troncon_id=2, direction="retour", session_id="20260622_B"
    )),

    # -----------------------------------------------------------------------
    # Session C — Toyota CFAO ↔ Carrefour Seamen's
    # -----------------------------------------------------------------------
    ("Toyota Cfao- Carrefour seamen's", MetaSegment(
        "Toyota CFAO -> Carrefour Seamen's", troncon_id=3, direction="aller", session_id="20260622_C"
    )),
    ("Carrefour seamen's-Toyota Cfao", MetaSegment(
        "Carrefour Seamen's -> Toyota CFAO", troncon_id=4, direction="retour", session_id="20260622_C"
    )),

    # -----------------------------------------------------------------------
    # Session D — SODECI -> Gendarmerie du port  (aller, troncon_id=5, partiel)
    # -----------------------------------------------------------------------
    ("Agence Sodeci-Gendarmerie du port", MetaSegment(
        "SODECI -> Gendarmerie du port", troncon_id=5, direction="aller", session_id="20260622_D"
    )),

    # -----------------------------------------------------------------------
    # Session E — Carrefour Seamen's -> GMA  (retour Axe 1, troncon_id=2, partiel)
    # Complète la portion nord manquante de la Session B
    # -----------------------------------------------------------------------
    ("Carrefour seamen's-Sim ivoire", MetaSegment(
        "Carrefour Seamen's -> Sim Ivoire", troncon_id=2, direction="retour", session_id="20260622_E"
    )),
    ("Sim Ivoire-Commissariat Spécial", MetaSegment(
        "Sim Ivoire -> Commissariat Spécial", troncon_id=2, direction="retour", session_id="20260622_E"
    )),
    ("Clmmissariat spécial-Gma", MetaSegment(
        "Commissariat Spécial -> GMA", troncon_id=2, direction="retour", session_id="20260622_E"
    )),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trouver_meta(nom_fichier: str) -> MetaSegment | None:
    """Recherche la configuration d'un fichier par sous-chaîne dans son nom."""
    for cle, meta in SEGMENTS_CONFIG:
        if cle in nom_fichier:
            return meta
    return None


def _analyser_gpx(chemin: Path) -> dict | None:
    """Extrait premier/dernier point GPS + durée d'un fichier GPX."""
    try:
        contenu = chemin.read_bytes()
        doc = gpxpy.parse(contenu.decode("utf-8", errors="replace"))
    except Exception as exc:
        print(f"  ✗ Erreur parsing GPX : {exc}")
        return None

    points = []
    for track in doc.tracks:
        for segment in track.segments:
            for pt in segment.points:
                if pt.time and pt.latitude and pt.longitude:
                    points.append(pt)

    if len(points) < 2:
        print(f"  ✗ Moins de 2 points horodatés")
        return None

    points.sort(key=lambda p: p.time)
    debut = points[0]
    fin = points[-1]
    duree_s = int((fin.time - debut.time).total_seconds())

    return {
        "lat_debut": debut.latitude,
        "lon_debut": debut.longitude,
        "lat_fin": fin.latitude,
        "lon_fin": fin.longitude,
        "duree_s": duree_s,
        "horodatage_debut": debut.time.isoformat(),
        "horodatage_fin": fin.time.isoformat(),
        "nb_points": len(points),
    }


# ---------------------------------------------------------------------------
# Import principal
# ---------------------------------------------------------------------------


def importer_segments(
    dossier: Path,
    api_url: str,
    dry_run: bool = False,
) -> None:
    import httpx

    gpx_fichiers = sorted(dossier.glob("*.gpx"))
    if not gpx_fichiers:
        print(f"Aucun fichier .gpx trouvé dans {dossier}")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print(f"  Import des segments terrain GPX -> {api_url}")
    print(f"  Dossier  : {dossier}")
    print(f"  Fichiers : {len(gpx_fichiers)} .gpx trouves")
    if dry_run:
        print("  MODE DRY-RUN -- aucune requete envoyee")
    print(f"{'=' * 70}\n")

    stats: dict[int | None, list[int]] = {}  # troncon_id -> liste de durees (s)
    ok = 0
    erreurs = 0

    for chemin in gpx_fichiers:
        nom = chemin.name
        meta = _trouver_meta(nom)
        if meta is None:
            print(f"[?] {nom}")
            print("    Non reconnu dans la table de correspondance -- ignore\n")
            continue

        print(f"[+] {nom}")
        print(f"    Nom       : {meta.nom}")
        print(f"    Troncon   : {meta.troncon_id}  Direction : {meta.direction}  Session : {meta.session_id}")

        infos = _analyser_gpx(chemin)
        if infos is None:
            erreurs += 1
            print()
            continue

        d_mn = infos["duree_s"] // 60
        d_s = infos["duree_s"] % 60
        print(f"    Duree     : {d_mn}:{d_s:02d} min  ({infos['duree_s']}s)")
        print(f"    GPS debut : lat={infos['lat_debut']:.6f} lon={infos['lon_debut']:.6f}")
        print(f"    GPS fin   : lat={infos['lat_fin']:.6f} lon={infos['lon_fin']:.6f}")
        print(f"    Points    : {infos['nb_points']}")

        if not dry_run:
            try:
                contenu = chemin.read_bytes()
                r = httpx.post(
                    f"{api_url}/terrain/segments/import",
                    files={"fichier": (nom, contenu, "application/gpx+xml")},
                    data={
                        "nom_segment": meta.nom,
                        "troncon_id": str(meta.troncon_id) if meta.troncon_id else "",
                        "direction": meta.direction,
                        "session_id": meta.session_id,
                        "source_reelle": "true",
                    },
                    timeout=30.0,
                )
                if r.status_code == 201:
                    print(f"    OK importe (id={r.json()['id']})")
                    ok += 1
                    stats.setdefault(meta.troncon_id, []).append(infos["duree_s"])
                else:
                    print(f"    ERREUR HTTP {r.status_code} : {r.text[:200]}")
                    erreurs += 1
            except Exception as exc:
                print(f"    ERREUR reseau : {exc}")
                erreurs += 1
        else:
            ok += 1
            stats.setdefault(meta.troncon_id, []).append(infos["duree_s"])

        print()

    # --- Resume par troncon ---
    print(f"\n{'=' * 70}")
    print("  RESUME DES TEMPS DE TRAVERSEE PAR TRONCON")
    print(f"{'=' * 70}")

    noms_troncons = {
        1: "CARENA -> Palm Beach",
        2: "Palm Beach -> CARENA",
        3: "Toyota CFAO -> Palm Beach",
        4: "Palm Beach -> Toyota CFAO",
        5: "SODECI -> Palm Beach",
        6: "Palm Beach -> SODECI",
    }

    for tid, durees in sorted(stats.items(), key=lambda x: x[0] or 99):
        total_s = sum(durees)
        total_mn = total_s // 60
        total_reste_s = total_s % 60
        nom = noms_troncons.get(tid, f"Troncon {tid}")
        print(f"  Troncon {tid} -- {nom}")
        print(f"    Segments       : {len(durees)}")
        print(f"    Duree cumulee  : {total_mn}:{total_reste_s:02d} min ({total_s}s)")
        print()

    print(f"  Importes : {ok}  |  Erreurs : {erreurs}")
    print(f"{'=' * 70}\n")

    if not dry_run:
        print("Resume consolide par troncon (avec miroir aller/retour) :")
        print(f"  GET {api_url}/terrain/segments/resume\n")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def _detecter_dossier() -> Path:
    """Recherche le dossier des GPX dans les emplacements courants."""
    candidats = [
        Path.home() / "Downloads" / "Telegram Desktop",
        Path.home() / "Downloads",
        Path.cwd(),
    ]
    for c in candidats:
        if c.exists() and list(c.glob("*.gpx")):
            return c
    # Dernier recours : dossier courant
    return Path.cwd()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import des 26 segments GPX terrain PAA du 2026-06-22",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="URL du backend FLUIDIS (défaut: http://localhost:8000)",
    )
    parser.add_argument(
        "--dossier",
        type=Path,
        default=None,
        help="Dossier contenant les fichiers .gpx",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse les fichiers sans envoyer de requêtes",
    )
    args = parser.parse_args()

    dossier = args.dossier or _detecter_dossier()
    importer_segments(dossier, args.api_url, dry_run=args.dry_run)
