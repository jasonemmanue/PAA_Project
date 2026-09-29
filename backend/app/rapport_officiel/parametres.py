"""Contrat de données Excel du Rapport DEESP — modèle, import, valeurs par défaut.

Le rapport officiel contient des contenus que l'application ne peut pas
connaître : campagne de référence du tableau comparatif, relevés manuels des
annexes, signataires.

Ces contenus sont saisis par le rédacteur dans un classeur Excel :

  1. il télécharge le modèle (`construire_modele_excel`), pré-rempli avec les
     valeurs de la campagne courante ou, à défaut, celles du rapport de
     référence ;
  2. il le complète ;
  3. il le ré-importe (`lire_classeur`), ce qui persiste le contenu normalisé
     dans la table `rapport_parametres`.

Refonte 2026-09-29 — rapport épuré, sans commentaires textuels :

Le classeur ne comporte plus que **cinq feuilles** (la feuille « Textes » a
été retirée puisque les paragraphes rédactionnels ne sont plus injectés
dans le rapport, cf. `generateur.py`) :

  - « Metadonnees »       : code document, version, dates, pagination
  - « Comparatif »        : campagne de référence du Tableau 19
  - « Donnees directes »  : surcharge manuelle des temps calculés
  - « Annexes »           : relevés terrain du tableau des temps réels
  - « Signatures »        : rédacteur / vérificateur / approbateur

Un classeur d'ancienne version qui contient encore une feuille « Textes »
reste lisible : elle est ignorée silencieusement. `TEXTES_DEFAUT` est
conservé pour la rétro-compat des documents `rapport_parametres` déjà
stockés en base — le générateur n'y touche plus.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import RapportParametres


logger = logging.getLogger("paa.rapport.parametres")


# ---------------------------------------------------------------------------
# Nomenclature partagée
# ---------------------------------------------------------------------------

# Noms exacts des feuilles du classeur — servent aussi bien à l'écriture du
# modèle qu'à la lecture d'un fichier importé.
FEUILLE_METADONNEES = "Metadonnees"
FEUILLE_TEXTES = "Textes"
FEUILLE_COMPARATIF = "Comparatif"
FEUILLE_DIRECTES = "Donnees directes"
FEUILLE_ANNEXES = "Annexes"
FEUILLE_SIGNATURES = "Signatures"

# Agrégats et types de jour utilisés comme clés dans les feuilles tabulaires.
AGREGATS = ("min", "moyen", "max")
TYPES_JOUR = ("jour_ouvrable", "week_end")


# ---------------------------------------------------------------------------
# Valeurs par défaut — reprises du rapport de référence (octobre 2025)
# ---------------------------------------------------------------------------

METADONNEES_DEFAUT: dict[str, str] = {
    "code_document": "DEESP-RF-01",
    "version": "03",
    "processus": "PILOTER LE SMI",
    "direction": "DEESP",
    "departement": "ETUDES ECONOMIQUES ET FINANCIERES",
    "date_elaboration": "03/02/2025",
    "date_document": "26/05/2025",
    "nb_pages_total": "27",
    "libelle_organisme": "DEESP/DEEF",
}

# Paragraphes rédactionnels. Les clés sont stables — le générateur les
# retrouve dans le modèle Word par le marqueur associé (cf. `generateur`).
# Les valeurs sont celles du rapport de référence : le rédacteur les ajuste
# dans le classeur sans avoir à les retaper intégralement.
TEXTES_DEFAUT: dict[str, str] = {
    "intro_p1": (
        "Dans un contexte d’intensification des échanges internationaux, la fluidité "
        "des chaînes logistiques constitue un levier essentiel de la compétitivité "
        "portuaire. Au-delà des volumes traités, la performance d’un port se mesure "
        "désormais à la rapidité et à l’efficacité du transit des marchandises, le "
        "temps de traversée de la zone portuaire s’imposant comme un indicateur clé "
        "de l’état des infrastructures, de l’organisation des flux et du niveau de "
        "coordination entre les acteurs."
    ),
    "intro_p2": (
        "Au Port Autonome d’Abidjan, hub maritime majeur de la sous-région et pilier "
        "de l’économie ivoirienne, la forte dynamique du trafic a longtemps engendré "
        "des congestions routières récurrentes au sein et aux abords de la zone "
        "portuaire, affectant les coûts logistiques, les délais de livraison et la "
        "compétitivité globale du port. En 2025, avec plus de 40,1 millions de tonnes "
        "de marchandises traitées, le port a assuré près des trois quarts du commerce "
        "extérieur de la Côte d’Ivoire et généré 78,08 % des recettes douanières "
        "nationales."
    ),
    "intro_p3": (
        "Toutefois, les travaux d’infrastructures routières réalisés dans la zone "
        "portuaire par le Ministère en charge de la Construction ont contribué de "
        "manière significative à la réduction de ces congestions. Ces aménagements ont "
        "permis une amélioration notable de la fluidité du trafic, se traduisant par "
        "des temps de traversée désormais globalement raisonnables. Malgré l’afflux "
        "important de poids lourds, la circulation demeure globalement fluide. "
        "Néanmoins, l’insuffisance d’aires de stationnement et les lenteurs "
        "administratives constituent encore des facteurs de contrainte qui appellent "
        "une attention particulière afin de consolider durablement la fluidité "
        "portuaire."
    ),
    "intro_p4": (
        "Dans ce contexte, le suivi régulier du temps moyen de traversée de la zone "
        "portuaire demeure indispensable pour évaluer l’efficacité des aménagements "
        "réalisés, identifier les éventuels points de congestion résiduels et orienter "
        "les décisions futures en matière d’organisation des flux et "
        "d’investissements, dans une perspective de performance logistique durable."
    ),
    "intro_p5": (
        "Cette problématique trouve une résonance particulière au Port d’Abidjan, "
        "moteur de l’économie ivoirienne et principal hub maritime de la sous-région. "
        "Avec plus de 40,1 millions de tonnes de marchandises traitées en 2024, il "
        "assure près des trois quarts du commerce extérieur de la Côte d’Ivoire et "
        "génère 78,08 % des recettes douanières du pays."
    ),
    "intro_p6": (
        "Cependant, cette bonne dynamique s’accompagne d’une pression croissante sur "
        "les infrastructures, particulièrement visible dans les congestions routières "
        "récurrentes observées aux abords et à l’intérieur de la zone portuaire."
    ),
    "intro_p7": (
        "Dans ce contexte, analyser le temps moyen nécessaire pour traverser la zone "
        "portuaire et identifier les tronçons congestionnés deviennent indispensables "
        "pour orienter les décisions d’aménagement, améliorer la coordination des "
        "acteurs et renforcer l’attractivité du port."
    ),
    "intro_p8": (
        "C’est pourquoi la Direction des Études Économiques, de la Stratégie et de la "
        "Planification (DEESP) a entrepris une étude régulière, conduite deux fois par "
        "an (pendant la période de forte activité et la période creuse), afin de "
        "mesurer le temps de traversée de la zone portuaire et d’évaluer objectivement "
        "le niveau de congestion routière."
    ),
    "intro_p9": (
        "Cette initiative s’inscrit dans une volonté d’éclairer les stratégies "
        "logistiques, dans un souci constant d’efficacité, de compétitivité et de "
        "durabilité."
    ),
    "conclusion_p1": (
        "Au terme de l’étude, les résultats de l’analyse montrent que la zone "
        "portuaire ne connaît pas une congestion permanente. En effet, certaines "
        "plages horaires présentent une fluidité de circulation satisfaisante, comme "
        "l’attestent les temps de traversée enregistrés durant la période "
        "d’observation."
    ),
    "conclusion_p2": (
        "Par ailleurs, il convient de souligner que la mise en service du boulevard du "
        "Port a contribué de manière significative à l’amélioration de la fluidité du "
        "trafic sur l’axe Grand Moulin – Carrefour Seamen’s Club. De même, la "
        "réouverture du boulevard de Vridi (axe ATC COMAFRIQUE – DGI) a permis de "
        "rétablir la continuité de la circulation dans ce secteur stratégique, "
        "réduisant ainsi les points de rupture du trafic."
    ),
    "conclusion_p3": (
        "Cependant, l’analyse révèle la présence d’un nombre élevé de nouveaux feux "
        "tricolores le long du boulevard du Port et du boulevard de Vridi, avec "
        "environ quinze (15) dispositifs recensés. Il est toutefois constaté que la "
        "majorité de ces feux, notamment au niveau de CIMIVOIRE, UNILEVER, ATC "
        "Comafrique ainsi qu’au carrefour Tripostal – SIR, ne sont pas fonctionnels. "
        "Ce dysfonctionnement, bien que non conforme aux normes de régulation du "
        "trafic, s’avère momentanément avantageux pour les usagers et les opérateurs "
        "portuaires, en ce qu’il permet une réduction notable des temps de traversée."
    ),
    "conclusion_p4": (
        "À l’inverse, certains feux en service sur le boulevard du Port présentent des "
        "temps d’attente relativement long. En particulier, au niveau de GLOBAL "
        "MANUTENTION, le cycle de feux, estimé à environ 80 secondes, pourrait "
        "constituer un facteur défavorable à la performance du temps de traversée."
    ),
    "conclusion_p5": (
        "Ces différents constats mettent en évidence un paradoxe : les "
        "dysfonctionnements observés sur plusieurs feux tricolores contribuent, dans "
        "les conditions actuelles, à une fluidité relative du trafic dans la zone "
        "portuaire. En effet, un fonctionnement simultané et pleinement opérationnel "
        "de l’ensemble des feux tricolores, sans adaptation préalable des plans de "
        "circulation et de signalisation, serait susceptible d’engendrer une "
        "congestion plus marquée au sein de ce périmètre."
    ),
    "methodologie_p1": (
        "Cette étude a été réalisée en utilisant l’application « GOOGLE MAPS » "
        "complétée par la traversée réelle sur les trois axes identifiés à des heures "
        "bien précises. Cette application a servi, pendant une durée bien précise, à "
        "relever les différentes zones congestionnées et à évaluer le temps mis pour "
        "les parcourir."
    ),
    "recommandation_1": "la mise en place d’un système de programmation et d’appel des camions ;",
    "recommandation_2": (
        "la relocalisation des habitants des deux cités du port (cités des cadres et "
        "du personnel) ;"
    ),
    "recommandation_3": (
        "la délocalisation de la SICTA (visite et immatriculation) et de tous ses "
        "services de la zone portuaire ;"
    ),
    "recommandation_4": (
        "remédier au plus vite les écarts constatés suite à la réalisation du projet "
        "(eau stagnante, les aspérités sur la route, etc.) ;"
    ),
    "recommandation_5": (
        "mettre en place un système d’alerte en temps réel sur les conditions de "
        "circulation (radio, applications mobiles)."
    ),
}

SIGNATURES_DEFAUT: dict[str, str] = {
    "redacteur_nom": "AHOKE Edwige",
    "redacteur_fonction": "CHEF DE SERVICE",
    "verificateur_nom": "KOFFI BONI Eli",
    "verificateur_fonction": "CHEF DE DEPARTEMENT",
    "approbateur_nom": "KOUADIO KOUASSI Jules",
    "approbateur_fonction": "DIRECTEUR",
}

# Campagne de référence du Tableau 19 (comparatif pluriannuel).
COMPARATIF_DEFAUT: dict[str, Any] = {
    "libelle_reference": "févr-25",
    "temps_max_reference_mn": 111,
    # Clé : "<sens>|<agregat>|<type_jour>" → minutes
    "valeurs": {},
}


# ---------------------------------------------------------------------------
# Aide contextuelle affichée dans le classeur
# ---------------------------------------------------------------------------

AIDE_FEUILLES: dict[str, str] = {
    FEUILLE_METADONNEES: (
        "Identification du document (bloc qualité en tête de page 2). "
        "Ne renseigner que la colonne VALEUR."
    ),
    FEUILLE_COMPARATIF: (
        "Tableau 19 — campagne de référence à laquelle la campagne courante est "
        "comparée. La colonne VALEUR (Mn) attend un entier. Le sens de variation "
        "(hausse / baisse) est calculé automatiquement."
    ),
    FEUILLE_DIRECTES: (
        "Surcharge facultative. Une valeur saisie ici REMPLACE celle calculée par "
        "l'application pour ce sens / agrégat / type de jour. Laissez vide pour "
        "utiliser la mesure collectée."
    ),
    FEUILLE_ANNEXES: (
        "Tableau des temps réels de traversée observés (sorties terrain). Une "
        "ligne par relevé. Les durées sont en minutes."
    ),
    FEUILLE_SIGNATURES: "Bloc de validation en fin de rapport.",
}


# ---------------------------------------------------------------------------
# Lecture / écriture en base
# ---------------------------------------------------------------------------


def charger_parametres(db: Session, campagne: str) -> dict[str, Any]:
    """Retourne les paramètres persistés pour une campagne, complétés des défauts.

    Une campagne jamais importée renvoie donc un dictionnaire entièrement
    rempli avec les valeurs du rapport de référence — le document reste
    générable sans import préalable.
    """
    ligne = db.execute(
        select(RapportParametres).where(RapportParametres.campagne == campagne)
    ).scalar_one_or_none()
    stockees: dict[str, Any] = dict(ligne.donnees) if ligne and ligne.donnees else {}
    return fusionner_avec_defauts(stockees)


def fusionner_avec_defauts(stockees: dict[str, Any]) -> dict[str, Any]:
    """Complète un document partiel avec les valeurs de référence manquantes."""
    metadonnees = {**METADONNEES_DEFAUT, **(stockees.get("metadonnees") or {})}
    signatures = {**SIGNATURES_DEFAUT, **(stockees.get("signatures") or {})}

    # Un texte vide signifie « conserver la référence », pas « paragraphe vide ».
    textes = dict(TEXTES_DEFAUT)
    for cle, valeur in (stockees.get("textes") or {}).items():
        if isinstance(valeur, str) and valeur.strip():
            textes[cle] = valeur.strip()

    comparatif = {**COMPARATIF_DEFAUT, **(stockees.get("comparatif") or {})}
    comparatif["valeurs"] = dict(comparatif.get("valeurs") or {})

    return {
        "metadonnees": metadonnees,
        "textes": textes,
        "comparatif": comparatif,
        "donnees_directes": dict(stockees.get("donnees_directes") or {}),
        "annexes": list(stockees.get("annexes") or []),
        "signatures": signatures,
        "_importe": bool(stockees),
    }


def enregistrer_parametres(
    db: Session,
    campagne: str,
    donnees: dict[str, Any],
    nom_fichier: str | None = None,
) -> RapportParametres:
    """Insère ou met à jour les paramètres d'une campagne (UPSERT sur `campagne`)."""
    ligne = db.execute(
        select(RapportParametres).where(RapportParametres.campagne == campagne)
    ).scalar_one_or_none()
    if ligne is None:
        ligne = RapportParametres(campagne=campagne, donnees=donnees, nom_fichier=nom_fichier)
        db.add(ligne)
    else:
        ligne.donnees = donnees
        ligne.nom_fichier = nom_fichier
    db.commit()
    db.refresh(ligne)
    return ligne


# ---------------------------------------------------------------------------
# Construction du modèle Excel
# ---------------------------------------------------------------------------


def construire_modele_excel(
    campagne: str,
    parametres: dict[str, Any],
    sens_disponibles: list[str],
) -> bytes:
    """Produit le classeur Excel à remplir par le rédacteur.

    Args:
        campagne: libellé 'AAAA-MM' de la campagne concernée.
        parametres: document déjà fusionné avec les défauts — pré-remplit
            les cellules pour que le rédacteur n'ait qu'à ajuster.
        sens_disponibles: libellés des sens de circulation actifs (ex.
            « CARENA - Pharmacie Palm Beach »), utilisés pour générer les
            lignes des feuilles tabulaires.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    classeur = Workbook()
    classeur.remove(classeur.active)

    entete_fond = PatternFill("solid", fgColor="1A365D")
    entete_police = Font(bold=True, color="FFFFFF", size=10)
    aide_police = Font(italic=True, size=9, color="555555")

    def nouvelle_feuille(nom: str, colonnes: list[tuple[str, int]]):
        feuille = classeur.create_sheet(nom)
        feuille["A1"] = AIDE_FEUILLES.get(nom, "")
        feuille["A1"].font = aide_police
        feuille.merge_cells(
            start_row=1, start_column=1, end_row=1, end_column=max(2, len(colonnes))
        )
        feuille.row_dimensions[1].height = 30
        feuille["A1"].alignment = Alignment(wrap_text=True, vertical="center")
        for idx, (titre, largeur) in enumerate(colonnes, start=1):
            cellule = feuille.cell(row=2, column=idx, value=titre)
            cellule.fill = entete_fond
            cellule.font = entete_police
            cellule.alignment = Alignment(horizontal="center", vertical="center")
            feuille.column_dimensions[get_column_letter(idx)].width = largeur
        feuille.freeze_panes = "A3"
        return feuille

    # --- Métadonnées -------------------------------------------------------
    feuille = nouvelle_feuille(FEUILLE_METADONNEES, [("CLE", 26), ("VALEUR", 46)])
    for ligne_idx, (cle, valeur) in enumerate(parametres["metadonnees"].items(), start=3):
        feuille.cell(row=ligne_idx, column=1, value=cle)
        feuille.cell(row=ligne_idx, column=2, value=valeur)

    # --- (Refonte 2026-09-29) feuille « Textes » retirée du modèle Excel :
    # les paragraphes rédactionnels ne sont plus injectés dans le rapport.

    # --- Comparatif (Tableau 19) ------------------------------------------
    feuille = nouvelle_feuille(
        FEUILLE_COMPARATIF,
        [("SENS", 42), ("AGREGAT", 14), ("TYPE JOUR", 18), ("VALEUR (Mn)", 14)],
    )
    feuille["F2"] = "LIBELLE CAMPAGNE DE REFERENCE"
    feuille["F2"].font = entete_police
    feuille["F2"].fill = entete_fond
    feuille["F3"] = parametres["comparatif"].get("libelle_reference", "")
    feuille["G2"] = "TEMPS MAX REFERENCE (Mn)"
    feuille["G2"].font = entete_police
    feuille["G2"].fill = entete_fond
    feuille["G3"] = parametres["comparatif"].get("temps_max_reference_mn")
    feuille.column_dimensions["F"].width = 32
    feuille.column_dimensions["G"].width = 26

    valeurs_ref = parametres["comparatif"].get("valeurs") or {}
    ligne_idx = 3
    for sens in sens_disponibles:
        for agregat in AGREGATS:
            for type_jour in TYPES_JOUR:
                feuille.cell(row=ligne_idx, column=1, value=sens)
                feuille.cell(row=ligne_idx, column=2, value=agregat)
                feuille.cell(row=ligne_idx, column=3, value=type_jour)
                feuille.cell(
                    row=ligne_idx,
                    column=4,
                    value=valeurs_ref.get(f"{sens}|{agregat}|{type_jour}"),
                )
                ligne_idx += 1

    # --- Données directes --------------------------------------------------
    feuille = nouvelle_feuille(
        FEUILLE_DIRECTES,
        [("SENS", 42), ("AGREGAT", 14), ("TYPE JOUR", 18), ("VALEUR (Mn)", 14)],
    )
    directes = parametres.get("donnees_directes") or {}
    ligne_idx = 3
    for sens in sens_disponibles:
        for agregat in AGREGATS:
            for type_jour in TYPES_JOUR:
                feuille.cell(row=ligne_idx, column=1, value=sens)
                feuille.cell(row=ligne_idx, column=2, value=agregat)
                feuille.cell(row=ligne_idx, column=3, value=type_jour)
                feuille.cell(
                    row=ligne_idx,
                    column=4,
                    value=directes.get(f"{sens}|{agregat}|{type_jour}"),
                )
                ligne_idx += 1

    # --- Annexes -----------------------------------------------------------
    colonnes_annexes = [
        ("DATE", 14),
        ("JOUR", 14),
        ("SEMAINE", 12),
        ("HEURE ALLER 1", 15),
        ("HEURE ALLER 2", 15),
        ("HEURE RETOUR 1", 16),
        ("HEURE RETOUR 2", 16),
        ("AXE", 40),
        ("ALLER 1 (Mn)", 14),
        ("ALLER 2 (Mn)", 14),
        ("RETOUR 1 (Mn)", 15),
        ("RETOUR 2 (Mn)", 15),
    ]
    feuille = nouvelle_feuille(FEUILLE_ANNEXES, colonnes_annexes)
    cles_annexes = [
        "date", "jour", "semaine",
        "heure_aller_1", "heure_aller_2", "heure_retour_1", "heure_retour_2",
        "axe", "aller_1", "aller_2", "retour_1", "retour_2",
    ]
    for ligne_idx, releve in enumerate(parametres.get("annexes") or [], start=3):
        for col_idx, cle in enumerate(cles_annexes, start=1):
            feuille.cell(row=ligne_idx, column=col_idx, value=releve.get(cle))

    # --- Signatures --------------------------------------------------------
    feuille = nouvelle_feuille(FEUILLE_SIGNATURES, [("CLE", 28), ("VALEUR", 40)])
    for ligne_idx, (cle, valeur) in enumerate(parametres["signatures"].items(), start=3):
        feuille.cell(row=ligne_idx, column=1, value=cle)
        feuille.cell(row=ligne_idx, column=2, value=valeur)

    # Une feuille de garde rappelant la campagne visée, pour éviter qu'un
    # classeur soit ré-importé sur la mauvaise période.
    garde = classeur.create_sheet("Lisez-moi", 0)
    garde["A1"] = f"Rapport DEESP — campagne {campagne}"
    garde["A1"].font = Font(bold=True, size=14, color="1A365D")
    garde["A3"] = (
        "Ce classeur ne contient QUE les données que l'application ne collecte pas. "
        "Les temps de traversée, les tronçons congestionnés et les 12 graphiques "
        "sont recalculés automatiquement depuis les mesures Google Routes de la "
        "période et du créneau horaire sélectionnés sur la page Rapport.\n"
        "\n"
        "Note (refonte 2026-09-29) : le rapport généré n'affiche plus de "
        "paragraphes rédactionnels — uniquement les tableaux, les 12 graphiques, "
        "les mentions de source et les signatures. La feuille « Textes » des "
        "versions précédentes est donc retirée du modèle."
    )
    garde["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    garde.merge_cells("A3:H8")
    garde["A10"] = "Complétez les feuilles puis ré-importez ce fichier sur la page Rapport."
    garde["A10"].font = Font(italic=True, size=10)
    garde.column_dimensions["A"].width = 18
    for lettre in "BCDEFGH":
        garde.column_dimensions[lettre].width = 14

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


# ---------------------------------------------------------------------------
# Lecture d'un classeur importé
# ---------------------------------------------------------------------------


def _texte(valeur: Any) -> str | None:
    """Normalise une cellule en chaîne non vide, ou None."""
    if valeur is None:
        return None
    texte = str(valeur).strip()
    return texte or None


def _entier(valeur: Any) -> int | None:
    """Normalise une cellule en entier, ou None si vide / illisible."""
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return None
    try:
        return int(round(float(str(valeur).replace(",", ".").strip())))
    except (TypeError, ValueError):
        return None


def lire_classeur(contenu: bytes) -> tuple[dict[str, Any], list[str]]:
    """Parse un classeur rempli et retourne (document normalisé, avertissements).

    La lecture est tolérante : une feuille absente ou une ligne incomplète est
    ignorée avec un avertissement plutôt que de faire échouer l'import. Seules
    les valeurs effectivement saisies sont conservées — le reste retombe sur
    les valeurs de référence au moment de la génération.
    """
    from openpyxl import load_workbook

    avertissements: list[str] = []
    classeur = load_workbook(io.BytesIO(contenu), data_only=True)

    def lignes(nom_feuille: str) -> list[tuple]:
        if nom_feuille not in classeur.sheetnames:
            avertissements.append(f"Feuille « {nom_feuille} » absente — ignorée.")
            return []
        # Ligne 1 = aide, ligne 2 = en-têtes, données à partir de la ligne 3.
        return list(classeur[nom_feuille].iter_rows(min_row=3, values_only=True))

    # --- Métadonnées -------------------------------------------------------
    metadonnees: dict[str, str] = {}
    for ligne in lignes(FEUILLE_METADONNEES):
        cle, valeur = _texte(ligne[0] if ligne else None), _texte(
            ligne[1] if len(ligne) > 1 else None
        )
        if cle and valeur:
            metadonnees[cle] = valeur

    # --- Textes ------------------------------------------------------------
    # Refonte 2026-09-29 — feuille retirée du modèle. La lecture reste
    # tolérante pour les classeurs d'ancienne version : les textes trouvés
    # sont persistés en base pour rétro-compat mais ne sont plus rendus dans
    # le rapport généré. La feuille absente n'émet pas d'avertissement (ce
    # n'est plus une anomalie).
    textes: dict[str, str] = {}
    if FEUILLE_TEXTES in classeur.sheetnames:
        for ligne in classeur[FEUILLE_TEXTES].iter_rows(min_row=3, values_only=True):
            if not ligne:
                continue
            cle = _texte(ligne[0])
            texte = _texte(ligne[2] if len(ligne) > 2 else None)
            if cle and texte:
                textes[cle] = texte

    # --- Comparatif --------------------------------------------------------
    comparatif: dict[str, Any] = {"valeurs": {}}
    if FEUILLE_COMPARATIF in classeur.sheetnames:
        feuille = classeur[FEUILLE_COMPARATIF]
        libelle = _texte(feuille["F3"].value)
        if libelle:
            comparatif["libelle_reference"] = libelle
        temps_max = _entier(feuille["G3"].value)
        if temps_max is not None:
            comparatif["temps_max_reference_mn"] = temps_max
    for ligne in lignes(FEUILLE_COMPARATIF):
        if not ligne or len(ligne) < 4:
            continue
        sens, agregat, type_jour = (_texte(ligne[0]), _texte(ligne[1]), _texte(ligne[2]))
        valeur = _entier(ligne[3])
        if sens and agregat and type_jour and valeur is not None:
            comparatif["valeurs"][f"{sens}|{agregat}|{type_jour}"] = valeur

    # --- Données directes --------------------------------------------------
    directes: dict[str, int] = {}
    for ligne in lignes(FEUILLE_DIRECTES):
        if not ligne or len(ligne) < 4:
            continue
        sens, agregat, type_jour = (_texte(ligne[0]), _texte(ligne[1]), _texte(ligne[2]))
        valeur = _entier(ligne[3])
        if sens and agregat and type_jour and valeur is not None:
            directes[f"{sens}|{agregat}|{type_jour}"] = valeur

    # --- Annexes -----------------------------------------------------------
    annexes: list[dict[str, Any]] = []
    cles_annexes = [
        "date", "jour", "semaine",
        "heure_aller_1", "heure_aller_2", "heure_retour_1", "heure_retour_2",
        "axe", "aller_1", "aller_2", "retour_1", "retour_2",
    ]
    for ligne in lignes(FEUILLE_ANNEXES):
        if not ligne or not any(ligne):
            continue
        releve: dict[str, Any] = {}
        for idx, cle in enumerate(cles_annexes):
            brut = ligne[idx] if idx < len(ligne) else None
            if cle in ("aller_1", "aller_2", "retour_1", "retour_2"):
                releve[cle] = _entier(brut)
            elif cle == "date":
                # openpyxl rend une date Excel en datetime — on la fige au
                # format JJ/MM/AAAA attendu par le rapport.
                if hasattr(brut, "strftime"):
                    releve[cle] = brut.strftime("%d/%m/%Y")
                else:
                    releve[cle] = _texte(brut)
            else:
                releve[cle] = _texte(brut)
        if releve.get("axe") or releve.get("date"):
            annexes.append(releve)

    # --- Signatures --------------------------------------------------------
    signatures: dict[str, str] = {}
    for ligne in lignes(FEUILLE_SIGNATURES):
        cle, valeur = _texte(ligne[0] if ligne else None), _texte(
            ligne[1] if len(ligne) > 1 else None
        )
        if cle and valeur:
            signatures[cle] = valeur

    document = {
        "metadonnees": metadonnees,
        "textes": textes,
        "comparatif": comparatif,
        "donnees_directes": directes,
        "annexes": annexes,
        "signatures": signatures,
    }
    logger.info(
        "Classeur lu — %d metadonnees, %d textes, %d comparatifs, %d directes, "
        "%d annexes, %d signatures",
        len(metadonnees), len(textes), len(comparatif["valeurs"]),
        len(directes), len(annexes), len(signatures),
    )
    return document, avertissements
