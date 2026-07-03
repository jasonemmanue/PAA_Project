"""Script de seed des 6 tronçons officiels FLUIDIS.

Insère les 3 axes du cahier des charges en aller ET retour (6 lignes).
Les coordonnées et les polylines sont laissées à NULL : elles seront
renseignées automatiquement par OSRM lors du prompt suivant.

Utilisation (depuis le conteneur backend ou un venv local) :
    python -m app.seed_troncons

Le script est idempotent : si un tronçon portant le même nom existe déjà,
il est ignoré (pas de doublon).
"""

import os
import sys
from pathlib import Path

# Garantit que le dossier backend/ est dans le PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.models import Troncon

# ---------------------------------------------------------------------------
# Données des 6 tronçons officiels (source : cahier des charges PAA)
#
# Couleurs :
#   Axe 1 (CARENA ↔ Palm Beach)     — nuances de bleu
#   Axe 2 (Toyota CFAO ↔ Palm Beach) — nuances de rouge
#   Axe 3 (SODECI ↔ Palm Beach)     — nuances de vert
#
# Distance identique dans les deux sens (distance physique de l'axe).
# Coordonnées à NULL → à résoudre via OSRM au prompt suivant.
# ---------------------------------------------------------------------------

TRONCONS_INITIAUX: list[dict] = [
    # -----------------------------------------------------------------------
    # Axe 1 : CARENA (Plateau) ↔ Pharmacie Palm Beach — 14,9 km
    # Temps de référence à 50 km/h ≈ 17 min 53 s (1073 s)
    # -----------------------------------------------------------------------
    {
        "nom": "CARENA (Plateau) → Pharmacie Palm Beach",
        "distance_m": 14900,
        "vitesse_ref_kmh": 50.0,
        "couleur": "#1565C8",   # Bleu marine
        "actif": True,
    },
    {
        "nom": "Pharmacie Palm Beach → CARENA (Plateau)",
        "distance_m": 14900,
        "vitesse_ref_kmh": 50.0,
        "couleur": "#64B5F6",   # Bleu ciel
        "actif": True,
    },
    # -----------------------------------------------------------------------
    # Axe 2 : Toyota CFAO (Treichville) ↔ Pharmacie Palm Beach — 8,0 km
    # Temps de référence à 50 km/h ≈ 9 min 36 s (576 s)
    # -----------------------------------------------------------------------
    {
        "nom": "Toyota CFAO (Treichville) → Pharmacie Palm Beach",
        "distance_m": 8000,
        "vitesse_ref_kmh": 50.0,
        "couleur": "#C62828",   # Rouge foncé
        "actif": True,
    },
    {
        "nom": "Pharmacie Palm Beach → Toyota CFAO (Treichville)",
        "distance_m": 8000,
        "vitesse_ref_kmh": 50.0,
        "couleur": "#EF9A9A",   # Rouge pâle
        "actif": True,
    },
    # -----------------------------------------------------------------------
    # Axe 3 : Agence SODECI (Zone 4) ↔ Pharmacie Palm Beach — 8,3 km
    # Temps de référence à 50 km/h ≈ 9 min 58 s (598 s)
    # -----------------------------------------------------------------------
    {
        "nom": "Agence SODECI (Zone 4) → Pharmacie Palm Beach",
        "distance_m": 8300,
        "vitesse_ref_kmh": 50.0,
        "couleur": "#2E7D32",   # Vert foncé
        "actif": True,
    },
    {
        "nom": "Pharmacie Palm Beach → Agence SODECI (Zone 4)",
        "distance_m": 8300,
        "vitesse_ref_kmh": 50.0,
        "couleur": "#A5D6A7",   # Vert pâle
        "actif": True,
    },
]


def seed() -> None:
    """Insère les tronçons manquants (idempotent)."""
    db = SessionLocal()
    try:
        inseres = 0
        ignores = 0
        for donnees in TRONCONS_INITIAUX:
            existant = (
                db.query(Troncon).filter(Troncon.nom == donnees["nom"]).first()
            )
            if existant:
                print(f"  [ignoré]  {donnees['nom']!r} — déjà présent (id={existant.id})")
                ignores += 1
            else:
                troncon = Troncon(**donnees)
                db.add(troncon)
                print(f"  [inséré]  {donnees['nom']!r}")
                inseres += 1

        db.commit()
        print(
            f"\nSeed terminé — {inseres} tronçon(s) inséré(s), "
            f"{ignores} ignoré(s) (déjà existants)."
        )
        print(
            "\nNote : les coordonnées et polylines sont NULL. "
            "Elles seront renseignées par le script de résolution OSRM."
        )
    except Exception as exc:
        db.rollback()
        print(f"\nErreur lors du seed : {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
