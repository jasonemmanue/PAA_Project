"""Import des données historiques PAA — campagne terrain Février 2025.

Feuille source : '1. Donnees nettoyees' du fichier Base_Nettoyee_PAA_Fev2025.xlsx
Source cible   : source='historique_paa_2025' dans la table mesures

Utilisation directe :
    python -m app.import_base_nettoyee chemin/vers/Base_Nettoyee_PAA_Fev2025.xlsx

Appelé aussi via POST /import/base-nettoyee (upload multipart).

Mapping (axe Excel, sens) → troncon.nom (DB) :
    ('CARENA',  'Aller')  → 'CARENA (Plateau) → Pharmacie Palm Beach'
    ('CARENA',  'Retour') → 'Pharmacie Palm Beach → CARENA (Plateau)'
    ('Toyota',  'Aller')  → 'Toyota CFAO (Treichville) → Pharmacie Palm Beach'
    ('Toyota',  'Retour') → 'Pharmacie Palm Beach → Toyota CFAO (Treichville)'
    ('SODECI',  'Aller')  → 'Agence SODECI (Zone 4) → Pharmacie Palm Beach'
    ('SODECI',  'Retour') → 'Pharmacie Palm Beach → Agence SODECI (Zone 4)'

IMPORTANT : ne jamais écraser les mesures du robot (source='google').
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.models import Mesure, SourceMesure, Troncon

logger = logging.getLogger("paa.import.base_nettoyee")

FEUILLE = "1. Donnees nettoyees"
SOURCE = SourceMesure.historique_paa_2025
TZ_ABIDJAN = ZoneInfo("Africa/Abidjan")

# Mots-clés permettant de retrouver chaque tronçon dans la table troncons
_MOTS_CLES: list[tuple[list[str], str, str]] = [
    # (mots_cles_axe, sens_excel, cle_mapping)
    (["carena"],        "Aller",  "CARENA_ALLER"),
    (["carena"],        "Retour", "CARENA_RETOUR"),
    (["toyota", "cfao"], "Aller",  "TOYOTA_ALLER"),
    (["toyota", "cfao"], "Retour", "TOYOTA_RETOUR"),
    (["sodeci"],        "Aller",  "SODECI_ALLER"),
    (["sodeci"],        "Retour", "SODECI_RETOUR"),
]


def _construire_mapping(session) -> dict[str, int]:
    """Construit le mapping cle_interne → troncon_id depuis la base de données."""
    troncons = session.query(Troncon).filter(Troncon.actif.is_(True)).all()
    mapping: dict[str, int] = {}

    for troncon in troncons:
        nom_lower = troncon.nom.lower()
        est_retour = nom_lower.startswith("pharmacie")

        if "carena" in nom_lower:
            cle = "CARENA_RETOUR" if est_retour else "CARENA_ALLER"
        elif "toyota" in nom_lower or "cfao" in nom_lower:
            cle = "TOYOTA_RETOUR" if est_retour else "TOYOTA_ALLER"
        elif "sodeci" in nom_lower:
            cle = "SODECI_RETOUR" if est_retour else "SODECI_ALLER"
        else:
            continue
        mapping[cle] = troncon.id

    return mapping


def _cle_depuis_excel(axe: str, sens: str) -> str | None:
    """Traduit (axe Excel, sens) en clé interne de mapping."""
    axe_lower = axe.lower()
    if "carena" in axe_lower:
        prefixe = "CARENA"
    elif "toyota" in axe_lower or "cfao" in axe_lower:
        prefixe = "TOYOTA"
    elif "sodeci" in axe_lower:
        prefixe = "SODECI"
    else:
        return None

    suffixe = "ALLER" if sens.strip().lower() == "aller" else "RETOUR"
    return f"{prefixe}_{suffixe}"


def importer(chemin_fichier: str | Path) -> dict:
    """Importe la feuille '1. Donnees nettoyees' dans la table mesures.

    Retourne un dict résumant les résultats :
    {
        'nb_lignes_lues': int,
        'nb_inseres': int,
        'nb_ignores_doublon': int,
        'nb_ignores_troncon_inconnu': int,
        'nb_erreurs': int,
        'par_troncon': {troncon_id: nb_inseres}
    }
    """
    chemin = Path(chemin_fichier)
    logger.info("Lecture de %s (feuille '%s')…", chemin.name, FEUILLE)

    df = pd.read_excel(chemin, sheet_name=FEUILLE, engine="openpyxl")
    logger.info("%d lignes lues.", len(df))

    session = SessionLocal()
    try:
        mapping_troncon = _construire_mapping(session)
        if not mapping_troncon:
            raise RuntimeError(
                "Aucun tronçon actif trouvé en base. "
                "Lancer d'abord app.seed_troncons."
            )
        logger.info("Mapping tronçons : %s", mapping_troncon)

        # Récupère les (troncon_id, horodatage) déjà présents avec cette source
        # pour l'idempotence — évite de recharger toute la table.
        existants: set[tuple[int, object]] = set(
            session.query(Mesure.troncon_id, Mesure.horodatage)
            .filter(Mesure.source == SOURCE)
            .all()
        )
        logger.info("%d mesures '%s' déjà en base.", len(existants), SOURCE.value)

        nb_inseres = 0
        nb_ignores_doublon = 0
        nb_ignores_troncon = 0
        nb_erreurs = 0
        par_troncon: dict[int, int] = {}

        for _, row in df.iterrows():
            try:
                axe = str(row["axe"])
                sens = str(row["sens"])
                cle = _cle_depuis_excel(axe, sens)
                if cle is None or cle not in mapping_troncon:
                    logger.warning(
                        "Tronçon inconnu : axe=%r sens=%r — ligne ignorée.", axe, sens
                    )
                    nb_ignores_troncon += 1
                    continue

                troncon_id = mapping_troncon[cle]

                # Horodatage : déjà un datetime dans le fichier, on force UTC+0
                # (Africa/Abidjan = UTC+0 toute l'année, pas de DST)
                horodatage = pd.Timestamp(row["horodatage"]).to_pydatetime()
                if horodatage.tzinfo is None:
                    horodatage = horodatage.replace(tzinfo=TZ_ABIDJAN)

                if (troncon_id, horodatage) in existants:
                    nb_ignores_doublon += 1
                    continue

                duree_min = float(row["duree_min"])
                t_ref_min = float(row["T_ref_min"])
                duree_trafic_s = round(duree_min * 60)
                duree_sans_trafic_s = round(t_ref_min * 60)

                # distance_m depuis le tronçon pour calculer la vitesse
                troncon = session.get(Troncon, troncon_id)
                distance_m = troncon.distance_m if troncon else None
                if distance_m and duree_trafic_s > 0:
                    vitesse_kmh = (distance_m / duree_trafic_s) * 3.6
                else:
                    vitesse_kmh = None

                mesure = Mesure(
                    troncon_id=troncon_id,
                    horodatage=horodatage,
                    duree_trafic_s=duree_trafic_s,
                    duree_sans_trafic_s=duree_sans_trafic_s,
                    source=SOURCE,
                    vitesse_moyenne_kmh=vitesse_kmh,
                    aberrante=False,
                )
                session.add(mesure)
                existants.add((troncon_id, horodatage))
                nb_inseres += 1
                par_troncon[troncon_id] = par_troncon.get(troncon_id, 0) + 1

                # Commit par lots de 200 pour limiter la mémoire
                if nb_inseres % 200 == 0:
                    session.commit()
                    logger.info("  … %d insérées.", nb_inseres)

            except Exception as exc:
                logger.warning("Erreur ligne %s : %s", row.get("horodatage"), exc)
                nb_erreurs += 1

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    resultat = {
        "nb_lignes_lues": len(df),
        "nb_inseres": nb_inseres,
        "nb_ignores_doublon": nb_ignores_doublon,
        "nb_ignores_troncon_inconnu": nb_ignores_troncon,
        "nb_erreurs": nb_erreurs,
        "par_troncon": par_troncon,
    }
    logger.info("Import terminé : %s", resultat)
    _afficher_resume(resultat)
    return resultat


def _afficher_resume(r: dict) -> None:
    print(f"\n{'=' * 55}")
    print(f"  Import Base_Nettoyee_PAA_Fev2025 — résumé")
    print(f"{'=' * 55}")
    print(f"  Lignes lues          : {r['nb_lignes_lues']}")
    print(f"  Insérées             : {r['nb_inseres']}")
    print(f"  Ignorées (doublon)   : {r['nb_ignores_doublon']}")
    print(f"  Ignorées (tronçon ?) : {r['nb_ignores_troncon_inconnu']}")
    print(f"  Erreurs              : {r['nb_erreurs']}")
    if r["par_troncon"]:
        print("  Détail par tronçon :")
        for tid, n in sorted(r["par_troncon"].items()):
            print(f"    troncon_id={tid} → {n} mesures")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("Usage : python -m app.import_base_nettoyee <chemin_fichier.xlsx>")
        sys.exit(1)
    importer(sys.argv[1])
