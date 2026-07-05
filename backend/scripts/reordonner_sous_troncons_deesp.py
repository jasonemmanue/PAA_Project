"""Applique l'ordre officiel DEESP aux sous-tronçons des 6 axes principaux.

Usage (Console Railway ou local) :
    python -m scripts.reordonner_sous_troncons_deesp

Ce script lit les sous-tronçons rattachés à chaque axe officiel (id 1-6)
et met à jour la colonne `ordre` de la table `axe_sous_troncons` selon
la séquence DEESP officielle définie dans `_ORDRE_DEESP_PAR_AXE`.

Idempotent — peut être relancé sans effet secondaire.
"""

from app.api.administration import (
    _ORDRE_DEESP_PAR_AXE,
    _reordonner_sous_troncons_par_axe,
)
from app.db.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        for axe_id in sorted(_ORDRE_DEESP_PAR_AXE.keys()):
            _reordonner_sous_troncons_par_axe(db, axe_id)
            ordre = _ORDRE_DEESP_PAR_AXE[axe_id]
            print(f"[OK] Axe {axe_id} : {' → '.join(ordre)}")
        db.commit()
        print("\nOrdre DEESP appliqué avec succès sur les 6 axes.")
    except Exception as e:
        db.rollback()
        print(f"[ERREUR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
