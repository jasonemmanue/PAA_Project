"""Assemblage du Rapport DEESP officiel au format Word.

Le document de référence de la DEESP est embarqué comme modèle
(`modele/rapport_modele.docx`). La génération l'ouvre et remplace uniquement
les contenus variables, ce qui garantit que la page de garde, les logos, les
styles, les bordures et la pagination restent rigoureusement identiques à
l'original.

Trois familles de remplacements :

1. **Textes** — paragraphes rédactionnels (introduction, conclusion,
   commentaires d'axe) et libellés datés. Repérés par des ancres textuelles
   stables plutôt que par un index de paragraphe, qui se décale dès qu'un
   tableau est inséré.

2. **Tableaux existants** — Tableaux 1, 4-7, 11-15, signatures. Seul le
   contenu des cellules est réécrit : la mise en forme du modèle est
   conservée.

3. **Images à remplacer** — dans le document d'origine, les Tableaux 2, 3,
   8, 9, 10, 16, 17 et 19, certains commentaires et toutes les lignes
   « Source : » situées sous les graphiques sont des images (captures Excel).
   Elles sont donc figées. La génération les remplace par de vrais tableaux
   et de vrais paragraphes Word, seuls capables de porter des valeurs à jour.

Les 12 graphiques natifs sont traités à part, au niveau du paquet OPC
(cf. `graphiques`).
"""

from __future__ import annotations

import copy
import io
import logging
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph
from sqlalchemy.orm import Session

from app.analyse import rapport_paa
from app.rapport_officiel import donnees as mod_donnees
from app.rapport_officiel import graphiques as mod_graphiques
from app.rapport_officiel import parametres as mod_parametres


logger = logging.getLogger("paa.rapport.generateur")

CHEMIN_MODELE = Path(__file__).parent / "modele" / "rapport_modele.docx"

# python-docx ne déclare pas ces préfixes, utilisés par Word pour encapsuler
# les formes, les zones de texte et leurs propriétés de rendu.
NS_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"

BALISE_ALTERNATE_CONTENT = f"{{{NS_MC}}}AlternateContent"
BALISE_BODY_PR_WPS = f"{{{NS_WPS}}}bodyPr"
BALISE_BODY_PR_A = f"{{{NS_A}}}bodyPr"
BALISE_NORM_AUTOFIT = f"{{{NS_A}}}normAutofit"
BALISE_TXBX_CONTENT = qn("w:txbxContent")

# Palette reprise du rapport de référence.
NAVY = "1F3864"          # en-têtes des tableaux de synthèse
BLEU_MOYEN = "4472C4"    # en-tête du Tableau 1
BLEU_CLAIR = "D9E2F3"    # lignes paires
GRIS_CLAIR = "D6DCE4"    # en-tête du Tableau 2
BLANC = RGBColor(0xFF, 0xFF, 0xFF)

# Bookmark référencé par la table des matières mais absent du modèle : sans
# lui, Word affiche « Erreur ! Signet non défini. » sur l'entrée concernée.
BOOKMARK_MANQUANT = "_Toc216781642"
ANCRE_BOOKMARK_MANQUANT = "Etat des zones congestionnées dans le sens « aller »"

# Écriture en toutes lettres des petits nombres, comme dans le rapport.
_EN_LETTRES = {
    1: "une", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six",
    7: "sept", 8: "huit", 9: "neuf", 10: "dix", 11: "onze", 12: "douze",
}


# ===========================================================================
# Outils bas niveau sur le document
# ===========================================================================


def tous_paragraphes(document: Document) -> list[Paragraph]:
    """Tous les paragraphes du corps, y compris ceux des zones de texte.

    `document.paragraphs` ne renvoie que les enfants directs du corps : la
    page de garde et le bloc qualité, qui vivent dans des zones de texte,
    en seraient absents.
    """
    return [Paragraph(el, document) for el in document.element.body.iter(qn("w:p"))]


def _runs_textuels(paragraphe: Paragraph) -> list:
    return paragraphe._p.findall(qn("w:r"))


def remplacer_texte(paragraphe: Paragraph, nouveau_texte: str) -> None:
    """Remplace le texte d'un paragraphe en conservant la mise en forme.

    Le premier `run` reçoit l'intégralité du nouveau texte — il porte la
    police, la taille et la couleur d'origine. Les suivants sont supprimés
    pour éviter de laisser traîner des fragments de l'ancien contenu.
    """
    runs = _runs_textuels(paragraphe)
    if not runs:
        paragraphe.add_run(nouveau_texte)
        return
    premier = runs[0]
    for noeud in premier.findall(qn("w:t")):
        premier.remove(noeud)
    noeud_texte = OxmlElement("w:t")
    noeud_texte.set(qn("xml:space"), "preserve")
    noeud_texte.text = nouveau_texte
    premier.append(noeud_texte)
    for run in runs[1:]:
        paragraphe._p.remove(run)


def remplacer_fragment(paragraphes: Iterable[Paragraph], ancien: str, nouveau: str) -> int:
    """Remplace une sous-chaîne dans tous les paragraphes qui la contiennent.

    Le texte d'un paragraphe Word est souvent éclaté sur plusieurs `run`
    (correcteur orthographique, changements de casse…). La substitution est
    donc faite sur le texte reconstitué, puis réécrite d'un bloc.
    """
    nombre = 0
    for paragraphe in paragraphes:
        texte = paragraphe.text
        if ancien and ancien in texte:
            remplacer_texte(paragraphe, texte.replace(ancien, nouveau))
            nombre += 1
    return nombre


def trouver(paragraphes: Iterable[Paragraph], marqueur: str) -> list[Paragraph]:
    """Paragraphes dont le texte contient le marqueur."""
    return [p for p in paragraphes if marqueur in p.text]


def premier(paragraphes: Iterable[Paragraph], marqueur: str) -> Paragraph | None:
    for paragraphe in paragraphes:
        if marqueur in paragraphe.text:
            return paragraphe
    return None


def _dessins(paragraphe: Paragraph) -> list:
    return list(paragraphe._p.iter(qn("w:drawing")))


def _dimensions_pouces(paragraphe: Paragraph) -> list[tuple[float, float]]:
    """Dimensions (largeur, hauteur) en pouces de chaque image du paragraphe."""
    resultats: list[tuple[float, float]] = []
    balise = (
        "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent"
    )
    for dessin in _dessins(paragraphe):
        for extent in dessin.iter(balise):
            try:
                resultats.append(
                    (int(extent.get("cx")) / 914400, int(extent.get("cy")) / 914400)
                )
            except (TypeError, ValueError):
                continue
    return resultats


def _supprimer_images(paragraphe: Paragraph) -> None:
    """Retire les images d'un paragraphe sans supprimer le paragraphe lui-même."""
    for run in list(paragraphe._p.findall(qn("w:r"))):
        if run.find(qn("w:drawing")) is not None or run.find(qn("w:object")) is not None:
            paragraphe._p.remove(run)
    for conteneur in list(paragraphe._p.iter(BALISE_ALTERNATE_CONTENT)):
        parent = conteneur.getparent()
        if parent is not None:
            parent.remove(conteneur)


def activer_autofit_zone_texte(paragraphe: Paragraph) -> None:
    """Autorise Word à réduire le texte d'une zone de texte pour qu'il y tienne.

    Les zones de texte de la page de garde ont une taille fixe, calibrée sur
    « Février 2026 ». Un libellé plus long (« Septembre 2026 ») passerait à la
    ligne et serait rogné. `normAutofit` demande à Word d'ajuster le corps du
    texte, ce qui préserve la mise en page quelle que soit la campagne.
    """
    forme = paragraphe._p
    while forme is not None and forme.tag != BALISE_TXBX_CONTENT:
        forme = forme.getparent()
    if forme is None:
        return
    # Remonte jusqu'à la forme porteuse, qui déclare les propriétés de corps.
    while forme is not None:
        for balise in (BALISE_BODY_PR_WPS, BALISE_BODY_PR_A):
            for body_pr in forme.iter(balise):
                _imposer_norm_autofit(body_pr)
                return
        forme = forme.getparent()


def dans_zone_texte(paragraphe: Paragraph) -> bool:
    """Indique si le paragraphe vit dans une zone de texte à largeur fixe."""
    element = paragraphe._p.getparent()
    while element is not None:
        if element.tag == BALISE_TXBX_CONTENT:
            return True
        element = element.getparent()
    return False


def reduire_pour_tenir(
    paragraphe: Paragraph,
    ancien: str,
    nouveau: str,
    *,
    taille_par_defaut: float | None = None,
) -> None:
    """Réduit la police quand le nouveau libellé est plus long que l'ancien.

    `normAutofit` laisse Word recalculer l'échelle, mais il ne le fait qu'à
    l'édition : une conversion directe en PDF rognerait encore le texte. On
    applique donc aussi la réduction sur les caractères, ce que tout moteur de
    rendu honore.
    """
    if not ancien or len(nouveau) <= len(ancien):
        return
    facteur = len(ancien) / len(nouveau)
    for run in paragraphe.runs:
        taille = run.font.size
        points = taille.pt if taille is not None else taille_par_defaut
        if points is None:
            continue
        run.font.size = Pt(max(7.0, round(points * facteur, 1)))


def _imposer_norm_autofit(body_pr) -> None:
    """Remplace le mode d'ajustement d'une zone de texte par `normAutofit`.

    Le schéma DrawingML n'autorise qu'un seul élément d'ajustement, à une
    position précise de la séquence : juste après `prstTxWarp` s'il existe,
    en tête sinon. Ajouter un second élément, ou le placer après `scene3d` ou
    `extLst`, rend le document illisible par Word.
    """
    for nom in ("noAutofit", "normAutofit", "spAutoFit"):
        for existant in body_pr.findall(f"{{{NS_A}}}{nom}"):
            body_pr.remove(existant)
    autofit = OxmlElement("a:normAutofit")
    warp = body_pr.find(f"{{{NS_A}}}prstTxWarp")
    if warp is not None:
        warp.addnext(autofit)
    else:
        body_pr.insert(0, autofit)


def ombrer(cellule, couleur_hex: str) -> None:
    proprietes = cellule._tc.get_or_add_tcPr()
    for ancien in proprietes.findall(qn("w:shd")):
        proprietes.remove(ancien)
    ombre = OxmlElement("w:shd")
    ombre.set(qn("w:val"), "clear")
    ombre.set(qn("w:color"), "auto")
    ombre.set(qn("w:fill"), couleur_hex)
    proprietes.append(ombre)


def ecrire_cellule(
    cellule,
    texte: str,
    *,
    gras: bool = False,
    italique: bool = False,
    taille: int = 9,
    couleur: RGBColor | None = None,
    centre: bool = True,
) -> None:
    """Écrit le contenu d'une cellule en repartant d'un paragraphe propre."""
    cellule.text = ""
    paragraphe = cellule.paragraphs[0]
    paragraphe.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER if centre else WD_ALIGN_PARAGRAPH.LEFT
    )
    run = paragraphe.add_run(texte)
    run.bold = gras
    run.italic = italique
    run.font.size = Pt(taille)
    if couleur is not None:
        run.font.color.rgb = couleur


def _mn(valeur: int | None) -> str:
    """Rend une durée en minutes, ou un tiret si la mesure est absente."""
    return "—" if valeur is None else str(valeur)


def _en_lettres(nombre: int) -> str:
    return _EN_LETTRES.get(nombre, str(nombre))


# ===========================================================================
# Insertion de tableaux à la place des images figées
# ===========================================================================


def inserer_tableau(
    document: Document,
    apres: Paragraph,
    nb_lignes: int,
    nb_colonnes: int,
) -> Table:
    """Crée un tableau bordé et le place juste avant le paragraphe indiqué."""
    tableau = document.add_table(rows=nb_lignes, cols=nb_colonnes)
    try:
        tableau.style = "Table Grid"
    except KeyError:
        # Le modèle peut ne pas déclarer ce style : les bordures explicites
        # ci-dessous suffisent alors à obtenir le même rendu.
        pass
    _bordures(tableau)
    apres._p.addprevious(tableau._tbl)
    return tableau


def _bordures(tableau: Table) -> None:
    proprietes = tableau._tbl.tblPr
    bordures = OxmlElement("w:tblBorders")
    for cote in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{cote}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), "808080")
        bordures.append(element)
    proprietes.append(bordures)


def _fixer_largeurs(tableau: Table, largeurs_cm: list[float]) -> None:
    """Impose une largeur à chaque colonne.

    Word ignore la largeur portée par la colonne seule : elle doit être répétée
    sur chaque cellule, et l'ajustement automatique désactivé.
    """
    tableau.autofit = False
    for index, largeur in enumerate(largeurs_cm):
        if index >= len(tableau.columns):
            break
        dimension = Cm(largeur)
        tableau.columns[index].width = dimension
        for cellule in tableau.columns[index].cells:
            cellule.width = dimension


def _fusionner(tableau: Table, ligne: int, col_debut: int, col_fin: int):
    cellule = tableau.cell(ligne, col_debut)
    if col_fin > col_debut:
        cellule = cellule.merge(tableau.cell(ligne, col_fin))
    return cellule


# ===========================================================================
# Génération — point d'entrée
# ===========================================================================


def generer_rapport(
    db: Session,
    campagne: str,
    debut_utc,
    fin_utc,
    heure_debut: int,
    heure_fin: int,
) -> bytes:
    """Produit le Rapport DEESP officiel (.docx) pour la période demandée."""
    contexte = mod_donnees.construire_contexte(
        db, campagne, debut_utc, fin_utc, heure_debut, heure_fin
    )
    params = mod_parametres.charger_parametres(db, campagne)
    _appliquer_donnees_directes(contexte, params)

    modele = CHEMIN_MODELE.read_bytes()
    modele = _reecrire_graphiques(modele, contexte)

    document = Document(io.BytesIO(modele))
    _appliquer_modifications(document, contexte, params)

    sortie = io.BytesIO()
    document.save(sortie)
    logger.info(
        "Rapport DEESP généré — campagne=%s, %d octets", campagne, sortie.tell()
    )
    return sortie.getvalue()


def _appliquer_donnees_directes(
    contexte: mod_donnees.ContexteRapport, params: dict[str, Any]
) -> None:
    """Fait primer les valeurs saisies dans le classeur sur les valeurs mesurées.

    Prévu pour les campagnes dont la collecte est incomplète : le rédacteur
    renseigne alors la valeur relevée manuellement, qui remplace celle
    calculée.
    """
    for cle, valeur in (params.get("donnees_directes") or {}).items():
        morceaux = cle.split("|")
        if len(morceaux) != 3:
            continue
        libelle, agregat, type_jour = morceaux
        contexte.temps[(libelle, agregat, type_jour)] = valeur


def _reecrire_graphiques(
    modele: bytes, contexte: mod_donnees.ContexteRapport
) -> bytes:
    """Réinjecte les données de la campagne dans les 12 graphiques natifs."""
    sens_par_axe: list[tuple[str, str | None, str | None]] = []
    for axe in contexte.axes:
        aller = next(
            (s.libelle for s in contexte.sens_circulation if s.axe == axe and s.sens == "aller"),
            None,
        )
        retour = next(
            (s.libelle for s in contexte.sens_circulation if s.axe == axe and s.sens == "retour"),
            None,
        )
        sens_par_axe.append((axe, aller, retour))

    plan = mod_graphiques.plan_des_graphiques(sens_par_axe)

    entree = zipfile.ZipFile(io.BytesIO(modele))
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as sortie:
        for info in entree.infolist():
            contenu = entree.read(info.filename)
            nom_court = info.filename.rsplit("/", 1)[-1]
            if info.filename.startswith("word/charts/") and nom_court in plan:
                libelle, agregat = plan[nom_court]
                serie = contexte.series_graphiques.get((libelle, agregat))
                if serie is not None:
                    libelles_semaines, matrice = serie
                    try:
                        contenu = mod_graphiques.reecrire_graphique(
                            contenu, libelles_semaines, matrice
                        )
                    except Exception:
                        logger.exception(
                            "Echec réécriture de %s — graphique du modèle conservé.",
                            nom_court,
                        )
            sortie.writestr(info, contenu)
    return tampon.getvalue()


# ===========================================================================
# Modifications au niveau du document
# ===========================================================================


def _appliquer_modifications(
    document: Document,
    contexte: mod_donnees.ContexteRapport,
    params: dict[str, Any],
) -> None:
    paragraphes = tous_paragraphes(document)

    _maj_couverture_et_entete(document, paragraphes, contexte, params)
    _maj_textes_rediges(paragraphes, params)
    _maj_methodologie(paragraphes, contexte)
    _maj_tableau_1(document, contexte)
    _remplacer_images_figees(document, paragraphes, contexte, params)
    _maj_tableaux_synthese(document, contexte)
    _maj_commentaires_axes(paragraphes, contexte)
    _maj_conclusion(paragraphes, contexte, params)
    _maj_signatures(document, params)
    _maj_libelles_sources(paragraphes, contexte)
    _neutraliser_liaisons_externes(document)
    _corriger_styles_de_titre(paragraphes)
    _reparer_table_des_matieres(document, paragraphes)


def _neutraliser_liaisons_externes(document: Document) -> None:
    """Retire les champs LINK hérités du modèle.

    Le document d'origine contient des objets liés à un classeur hébergé sur
    l'espace SharePoint de la direction. Comme la génération demande à Word de
    rafraîchir les champs, ces liens injoignables afficheraient
    « Erreur ! Liaison incorrecte. » en plein texte.
    """
    corps = document.element.body
    a_supprimer: list = []
    for instruction in corps.iter(qn("w:instrText")):
        if instruction.text and "LINK " in instruction.text:
            run = instruction.getparent()
            paragraphe = run.getparent() if run is not None else None
            if paragraphe is not None:
                a_supprimer.append(paragraphe)

    for paragraphe in a_supprimer:
        # Le champ s'étend sur plusieurs runs encadrés par des fldChar :
        # vider le paragraphe est la façon la plus sûre de le neutraliser.
        for run in list(paragraphe.findall(qn("w:r"))):
            paragraphe.remove(run)


def _corriger_styles_de_titre(paragraphes: list[Paragraph]) -> None:
    """Retire le style de titre des paragraphes qui n'en sont pas.

    Le modèle applique un style « Titre 2 » à quelques paragraphes de corps et
    à des paragraphes vides. Tant que la table des matières restait figée cela
    passait inaperçu ; une fois qu'elle est recalculée, ces paragraphes y
    apparaissent comme des sections fantômes.
    """
    for paragraphe in paragraphes:
        style = paragraphe.style
        nom = getattr(style, "name", "") or ""
        if not nom.lower().startswith(("heading", "titre")):
            continue
        texte = paragraphe.text.strip()
        # Un vrai titre de ce rapport est court et non vide.
        if texte and len(texte) <= 120:
            continue
        try:
            paragraphe.style = "Normal"
        except (KeyError, AttributeError):
            logger.debug("Style Normal indisponible — paragraphe laissé tel quel.")


# --- Couverture, bloc qualité ---------------------------------------------


def _maj_couverture_et_entete(
    document: Document,
    paragraphes: list[Paragraph],
    contexte: mod_donnees.ContexteRapport,
    params: dict[str, Any],
) -> None:
    meta = params["metadonnees"]
    mois = contexte.libelle_mois()

    # Le titre apparaît sur la couverture et sur la page 2, avec le mois entre
    # parenthèses. Les deux occurrences sont normalisées sur la campagne.
    for paragraphe in paragraphes:
        texte = paragraphe.text
        if "EVALUATION DU TEMPS DE TRAVERSEE DE LA ZONE PORTUAIRE" in texte and "(" in texte:
            nouveau = f"EVALUATION DU TEMPS DE TRAVERSEE DE LA ZONE PORTUAIRE ({mois})"
            remplacer_texte(paragraphe, nouveau)
            activer_autofit_zone_texte(paragraphe)
            reduire_pour_tenir(paragraphe, texte, nouveau)

    # La période du modèle est datée : elle doit être substituée AVANT le
    # libellé de campagne, dont elle contient le mois et l'année.
    remplacer_fragment(paragraphes, "01 au 28 Février 2026", contexte.libelle_periode())
    for paragraphe in paragraphes:
        if paragraphe.text.strip() == "Février 2026":
            remplacer_texte(paragraphe, contexte.libelle_campagne())
            activer_autofit_zone_texte(paragraphe)
            reduire_pour_tenir(paragraphe, "Février 2026", contexte.libelle_campagne())
    remplacer_fragment(paragraphes, "Février 2026", contexte.libelle_campagne())

    correspondances = {
        "Code : ": meta.get("code_document", ""),
        "Version : ": meta.get("version", ""),
        "PROCESSUS : ": meta.get("processus", ""),
        "DIRECTION : ": meta.get("direction", ""),
        "DEPARTEMENT : ": meta.get("departement", ""),
        "Date d’élaboration : ": meta.get("date_elaboration", ""),
    }
    for paragraphe in paragraphes:
        texte = paragraphe.text.strip()
        for prefixe, valeur in correspondances.items():
            # `startswith` évite de toucher un paragraphe qui ne ferait que
            # citer l'étiquette au fil du texte.
            if texte.startswith(prefixe) and valeur:
                remplacer_texte(paragraphe, f"{prefixe}{valeur}")
                break
        if texte.startswith("Page : "):
            remplacer_texte(paragraphe, f"Page : 2/{meta.get('nb_pages_total', '27')}")
        elif texte.startswith("Date : "):
            remplacer_texte(paragraphe, f"Date : {meta.get('date_document', '')}")


# --- Paragraphes rédigés (introduction, conclusion, recommandations) ------


def _maj_textes_rediges(paragraphes: list[Paragraph], params: dict[str, Any]) -> None:
    """Réinjecte les paragraphes saisis dans le classeur.

    Chaque texte du classeur est rapproché du paragraphe du modèle par ses
    premiers mots. La correspondance reste valable même après plusieurs
    campagnes, puisqu'elle s'appuie sur le modèle — jamais modifié — et non
    sur le document précédemment généré.
    """
    textes = params["textes"]
    defauts = mod_parametres.TEXTES_DEFAUT
    for cle, texte in textes.items():
        reference = defauts.get(cle)
        if not reference:
            continue
        ancre = reference[:60]
        cible = premier(paragraphes, ancre)
        if cible is None:
            logger.debug("Ancre introuvable pour le texte %s — ignoré.", cle)
            continue
        if texte != cible.text.strip():
            remplacer_texte(cible, texte)


def _maj_methodologie(
    paragraphes: list[Paragraph], contexte: mod_donnees.ContexteRapport
) -> None:
    """Réécrit le paragraphe de méthodologie avec la période et le créneau réels."""
    cible = premier(paragraphes, "Les informations enregistrées ont été prises")
    if cible is None:
        return
    base = premier(paragraphes, "Cette étude a été réalisée en utilisant")
    prefixe = (
        base.text.split("Les informations enregistrées")[0].strip()
        if base is cible
        else ""
    )
    phrase = (
        f"Les informations enregistrées ont été prises sur la période allant du "
        f"{contexte.libelle_periode()} de {contexte.libelle_creneau()}. En effet, les "
        f"données sur les zones congestionnées ont été relevées à chaque heure "
        f"pendant toute la période d’observation."
    )
    remplacer_texte(cible, f"{prefixe} {phrase}".strip())


# --- Tableau 1 -------------------------------------------------------------


def _maj_tableau_1(document: Document, contexte: mod_donnees.ContexteRapport) -> None:
    """Tableau 1 — distances et temps théoriques à 50 km/h."""
    tableau = _tableau_par_entete(document, "AXE", "DISTANCE")
    if tableau is None:
        return
    lignes_utiles = len(tableau.rows) - 1
    for index, theorique in enumerate(contexte.temps_theoriques):
        if index >= lignes_utiles:
            _cloner_derniere_ligne(tableau)
        ligne = index + 1
        ecrire_cellule(
            tableau.cell(ligne, 0), theorique.axe, gras=True, taille=10,
            couleur=BLANC, centre=False,
        )
        ecrire_cellule(
            tableau.cell(ligne, 1),
            f"{theorique.distance_km:.1f}".replace(".", ",") + " km",
            taille=10,
        )
        ecrire_cellule(
            tableau.cell(ligne, 2),
            _format_mn_s_rapport(theorique.temps_50kmh_s),
            taille=10,
        )
    # Les axes en trop par rapport au modèle sont retirés.
    for _ in range(lignes_utiles - len(contexte.temps_theoriques)):
        tableau._tbl.remove(tableau.rows[-1]._tr)


def _format_mn_s_rapport(secondes: int) -> str:
    """« 17 mn 53s » — notation exacte du Tableau 1 du rapport."""
    return f"{secondes // 60:02d} mn {secondes % 60:02d}s"


def _tableau_par_entete(document: Document, *entetes: str) -> Table | None:
    """Retrouve un tableau par le libellé de ses premières cellules d'en-tête."""
    for tableau in document.tables:
        if not tableau.rows:
            continue
        premiere_ligne = " | ".join(c.text.strip().upper() for c in tableau.rows[0].cells)
        if all(entete.upper() in premiere_ligne for entete in entetes):
            return tableau
    return None


def _cloner_derniere_ligne(tableau: Table):
    """Duplique la dernière ligne pour conserver sa mise en forme."""
    nouvelle = copy.deepcopy(tableau.rows[-1]._tr)
    tableau.rows[-1]._tr.addnext(nouvelle)
    return tableau.rows[-1]


# --- Tableaux de synthèse existants ---------------------------------------


# (titre du tableau, agrégat, libellé de la rubrique)
_TABLEAUX_SYNTHESE: tuple[tuple[str, str, str], ...] = (
    ("Tableau 4", "min", "TEMPS MINIMAL (en Mn)"),
    ("Tableau 5", "min", "TEMPS MINIMAL (en Mn)"),
    ("Tableau 6", "min", "TEMPS MINIMAL (en Mn)"),
    ("Tableau 7", "min", "TEMPS MINIMAL (en Mn)"),
    ("Tableau 11", "moyen", "TEMPS MOYEN (en Mn)"),
    ("Tableau 12", "max", "TEMPS MAXIMAL (en Mn)"),
    ("Tableau 13", "max", "TEMPS MAXIMAL (en Mn)"),
    ("Tableau 14", "max", "TEMPS MAXIMAL (en Mn)"),
    ("Tableau 15", "max", "TEMPS MAXIMAL (en Mn)"),
)


def _maj_tableaux_synthese(
    document: Document, contexte: mod_donnees.ContexteRapport
) -> None:
    """Réécrit les Tableaux 4-7, 11 et 12-15 (« RUBRIQUE / JOURS OUVRABLES »).

    Ces tableaux partagent la même structure : une ligne de libellé de sens
    suivie d'une ligne de valeurs, répétée pour chaque sens couvert. Les
    tableaux par axe en couvrent deux (aller et retour d'un même axe), les
    récapitulatifs les couvrent tous.
    """
    tableaux = [
        t for t in document.tables
        if t.rows and "RUBRIQUE" in t.rows[0].cells[0].text.upper()
    ]
    if not tableaux:
        logger.warning("Aucun tableau de synthèse trouvé dans le modèle.")
        return

    for tableau in tableaux:
        nb_sens_modele = (len(tableau.rows) - 1) // 2
        agregat = _agregat_du_tableau(tableau)
        if nb_sens_modele >= len(contexte.sens_circulation):
            sens_cibles = contexte.sens_circulation
        elif nb_sens_modele == 2:
            # Tableau par axe : on identifie l'axe grâce au libellé déjà
            # présent dans le modèle, qui nomme l'un des deux sens.
            sens_cibles = _sens_de_l_axe_du_tableau(tableau, contexte)
        else:
            sens_cibles = contexte.sens_circulation[: nb_sens_modele or 1]

        while (len(tableau.rows) - 1) // 2 < len(sens_cibles):
            _cloner_derniere_ligne(tableau)
            _cloner_derniere_ligne(tableau)

        for index, sens in enumerate(sens_cibles):
            ligne_libelle = 1 + index * 2
            ligne_valeurs = ligne_libelle + 1
            if ligne_valeurs >= len(tableau.rows):
                break
            cellule = _fusionner(tableau, ligne_libelle, 1, 2)
            ecrire_cellule(cellule, sens.libelle, italique=True, taille=11)
            ecrire_cellule(
                tableau.cell(ligne_valeurs, 1),
                _mn(contexte.valeur(sens.libelle, agregat, "jour_ouvrable")),
                gras=True, taille=11,
            )
            ecrire_cellule(
                tableau.cell(ligne_valeurs, 2),
                _mn(contexte.valeur(sens.libelle, agregat, "week_end")),
                gras=True, taille=11,
            )

        # Lignes excédentaires du modèle (axes retirés depuis l'original).
        lignes_utiles = 1 + len(sens_cibles) * 2
        while len(tableau.rows) > lignes_utiles:
            tableau._tbl.remove(tableau.rows[-1]._tr)


def _agregat_du_tableau(tableau: Table) -> str:
    """Déduit min / moyen / max du libellé de la colonne RUBRIQUE."""
    texte = " ".join(c.text.upper() for ligne in tableau.rows for c in ligne.cells)
    if "MINIMAL" in texte:
        return "min"
    if "MAXIMAL" in texte:
        return "max"
    return "moyen"


def _sens_de_l_axe_du_tableau(
    tableau: Table, contexte: mod_donnees.ContexteRapport
) -> list[mod_donnees.SensCirculation]:
    """Retrouve l'axe d'un tableau à deux sens d'après son contenu d'origine."""
    texte = " ".join(c.text for ligne in tableau.rows for c in ligne.cells)
    for axe in contexte.axes:
        origine = axe.split(" - ")[0].strip()
        if origine and origine.lower() in texte.lower():
            return [s for s in contexte.sens_circulation if s.axe == axe]
    return contexte.sens_circulation[:2]


# --- Commentaires d'axe ----------------------------------------------------


def _sens_axe(
    contexte: mod_donnees.ContexteRapport, axe: str
) -> tuple[mod_donnees.SensCirculation | None, mod_donnees.SensCirculation | None]:
    """Retourne le couple (aller, retour) d'un axe."""
    aller = next(
        (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "aller"), None
    )
    retour = next(
        (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "retour"), None
    )
    return aller, retour


def _origine_axe(axe: str) -> str:
    """Première extrémité d'un axe — sert d'ancre textuelle courte et stable."""
    return axe.split(" - ")[0].strip()


def _maj_commentaires_axes(
    paragraphes: list[Paragraph], contexte: mod_donnees.ContexteRapport
) -> None:
    """Réécrit les commentaires chiffrés qui suivent chaque tableau d'axe.

    L'ancre combine le qualificatif (« minimaux » / « maximaux ») et le nom de
    l'origine de l'axe : le libellé complet varie d'une occurrence à l'autre
    dans le modèle (tirets, espaces insécables), alors que l'origine est
    toujours écrite à l'identique.
    """
    deja_traites: list[Paragraph] = []
    for axe in contexte.axes:
        origine = _origine_axe(axe)
        for agregat, qualificatif in (("min", "minimaux"), ("max", "maximaux")):
            ancre = f"les temps {qualificatif} évalués"
            for paragraphe in paragraphes:
                texte = paragraphe.text
                if ancre not in texte or origine not in texte:
                    continue
                if any(p._p is paragraphe._p for p in deja_traites):
                    continue
                remplacer_texte(paragraphe, _phrase_commentaire(contexte, axe, agregat))
                deja_traites.append(paragraphe)
                break


def _phrase_commentaire(
    contexte: mod_donnees.ContexteRapport, axe: str, agregat: str
) -> str:
    """Commentaire chiffré d'un axe pour le temps minimal ou maximal."""
    qualificatif = "minimaux" if agregat == "min" else "maximaux"
    aller, retour = _sens_axe(contexte, axe)
    if aller is None or retour is None:
        return ""
    aller_jo = _mn(contexte.valeur(aller.libelle, agregat, "jour_ouvrable"))
    aller_we = _mn(contexte.valeur(aller.libelle, agregat, "week_end"))
    retour_jo = _mn(contexte.valeur(retour.libelle, agregat, "jour_ouvrable"))
    retour_we = _mn(contexte.valeur(retour.libelle, agregat, "week_end"))
    return (
        f"Après avoir observé sur la période concernée les différents temps de "
        f"traversée de l’axe « {axe} » dans les deux sens, il ressort que les temps "
        f"{qualificatif} évalués pour les jours ouvrables et les week-ends sont "
        f"respectivement de {aller_jo} Mn et de {aller_we} Mn dans le sens "
        f"« aller » ; dans le sens « retour », ces temps sont respectivement de "
        f"{retour_jo} Mn et de {retour_we} Mn."
    )


# --- Conclusion ------------------------------------------------------------


def _maj_conclusion(
    paragraphes: list[Paragraph],
    contexte: mod_donnees.ContexteRapport,
    params: dict[str, Any],
) -> None:
    """Met à jour les passages chiffrés de la conclusion."""
    campagne = contexte.libelle_campagne()
    congestion_aller = contexte.congestion_par_sens.get("aller", [])
    congestion_retour = contexte.congestion_par_sens.get("retour", [])

    # Commentaire qui suit le Tableau 3, en amont du document.
    _maj_commentaire_tableau_3(paragraphes, contexte, congestion_retour)

    # Phrase d'introduction du Tableau 16.
    cible = premier(paragraphes, "Dans le sens « aller », les tronçons")
    if cible is not None:
        remplacer_texte(cible, _phrase_synthese_congestion(
            contexte, congestion_aller, congestion_retour
        ))

    # Interprétation du Tableau 16 — construite sur le tronçon le plus touché.
    _maj_interpretation_tableau_16(paragraphes, congestion_retour + congestion_aller)

    # Observations sur le temps moyen, axe par axe.
    _maj_observations_temps_moyen(paragraphes, contexte, campagne)

    # Phrase de comparaison du Tableau 19.
    _maj_phrase_comparatif(paragraphes, contexte, params)

    # Titres datés des Tableaux 16, 17 et 19.
    libelle_majuscules = campagne.upper()
    for paragraphe in paragraphes:
        texte = paragraphe.text.strip()
        if texte.startswith("Tableau 16"):
            remplacer_texte(
                paragraphe,
                "Tableau 16 : Tableau récapitulatif des tronçons congestionnés "
                f"({libelle_majuscules})",
            )
        elif texte.startswith("Tableau 17"):
            remplacer_texte(
                paragraphe,
                "Tableau 17 : Tableau récapitulatif du temps de traversée en zone "
                f"portuaire ({campagne})",
            )
        elif texte.startswith("Tableau 19"):
            reference = params["comparatif"].get("libelle_reference", "campagne précédente")
            remplacer_texte(
                paragraphe,
                "Tableau 19 : Tableau comparatif du temps de traversée en zone "
                f"portuaire ({reference} - {campagne})",
            )


def _maj_commentaire_tableau_3(
    paragraphes: list[Paragraph],
    contexte: mod_donnees.ContexteRapport,
    congestion_retour: list[rapport_paa.CongestionHoraire],
) -> None:
    """Réécrit la phrase d'analyse et les puces qui suivent le Tableau 3.

    Le modèle comporte une phrase d'introduction puis une puce par tronçon
    congestionné. Le nombre de tronçons variant d'une campagne à l'autre, les
    puces excédentaires sont vidées et les manquantes regroupées sur la
    dernière disponible.
    """
    rang = None
    for index, paragraphe in enumerate(paragraphes):
        if paragraphe.text.strip().startswith("Au regard du tableau 3"):
            rang = index
            break
    if rang is None:
        return

    debut, fin = contexte.heure_debut, contexte.heure_fin
    if not congestion_retour:
        remplacer_texte(
            paragraphes[rang],
            f"Au regard du tableau 3, dans le sens retour, il ressort qu’aucun "
            f"tronçon n’a été congestionné de {debut:02d}h à {fin:02d}h.",
        )
    else:
        remplacer_texte(
            paragraphes[rang],
            f"Au regard du tableau 3, dans le sens retour, il ressort que "
            f"certains tronçons ont été congestionnés entre {debut:02d}h et "
            f"{fin:02d}h. Il s’agit du ou des tronçon(s) :",
        )

    # Puces disponibles dans le modèle : celles qui suivent immédiatement.
    puces = [
        paragraphe
        for paragraphe in paragraphes[rang + 1: rang + 6]
        if paragraphe.text.strip().startswith("-")
    ]
    groupes = list(_grouper_congestions(congestion_retour).items())
    for index, puce in enumerate(puces):
        if index < len(groupes):
            code, entrees = groupes[index]
            remplacer_texte(
                puce,
                f"-  {code} a été congestionné sur {_en_lettres(len(entrees))} "
                f"({len(entrees):02d}) tranches horaires "
                f"({_plages_horaires(entrees)}) ;",
            )
        else:
            remplacer_texte(puce, "")


def _phrase_synthese_congestion(
    contexte: mod_donnees.ContexteRapport,
    aller: list[rapport_paa.CongestionHoraire],
    retour: list[rapport_paa.CongestionHoraire],
) -> str:
    debut, fin = contexte.heure_debut, contexte.heure_fin

    def segment(sens: str, entrees: list[rapport_paa.CongestionHoraire]) -> str:
        if not entrees:
            return (
                f"dans le sens « {sens} », les tronçons ne sont pas congestionnés de "
                f"{debut:02d}h à {fin:02d}h"
            )
        heures = sorted({e.heure for e in entrees})
        return (
            f"dans le sens « {sens} » de {min(heures):02d}h à {max(heures) + 1:02d}h "
            f"certains tronçons sont congestionnés"
        )

    phrase = f"{segment('aller', aller).capitalize()} par contre {segment('retour', retour)}."
    if aller or retour:
        phrase += (
            f" En effet, la congestion s’est plus remarquée sur certains tronçons qui "
            f"étaient embouteillés à certaines heures et ce au moins sur "
            f"{_en_lettres(2)} (2) tranches horaires et au moins "
            f"{_en_lettres(rapport_paa.SEUIL_SEMAINE_DEESP)} "
            f"({rapport_paa.SEUIL_SEMAINE_DEESP}) jours dans la semaine ; Ce sont :"
        )
    return phrase


def _maj_interpretation_tableau_16(
    paragraphes: list[Paragraph], congestions: list[rapport_paa.CongestionHoraire]
) -> None:
    # La phrase de détail est cherchée APRÈS le titre : la même tournure est
    # utilisée dans le commentaire du Tableau 3, bien plus haut dans le
    # document, et serait sinon modifiée à sa place.
    rang_titre = None
    for index, paragraphe in enumerate(paragraphes):
        if "Interprétation du tableau 16" in paragraphe.text:
            rang_titre = index
            break
    if rang_titre is None:
        return
    titre = paragraphes[rang_titre]
    detail = premier(paragraphes[rang_titre + 1:], "a été congestionné sur")
    if detail is None:
        return
    if not congestions:
        remplacer_texte(
            titre,
            "Aucun tronçon ne remplit les critères de congestion du tableau 16 sur "
            "la période analysée.",
        )
        remplacer_texte(detail, "")
        return

    par_troncon = _grouper_congestions(congestions)
    code, entrees = max(par_troncon.items(), key=lambda kv: len(kv[1]))
    remplacer_texte(titre, f"Interprétation du tableau 16 à partir du tronçon « {code} » :")
    remplacer_texte(detail, _phrase_congestion_troncon(code, entrees, avec_jours=True))


def _grouper_congestions(
    congestions: list[rapport_paa.CongestionHoraire],
) -> dict[str, list[rapport_paa.CongestionHoraire]]:
    groupes: dict[str, list[rapport_paa.CongestionHoraire]] = {}
    for entree in congestions:
        code = entree.sous_troncon_code or entree.troncon_nom
        groupes.setdefault(code, []).append(entree)
    return groupes


def _plages_horaires(
    entrees: list[rapport_paa.CongestionHoraire], *, avec_prefixe: bool = True
) -> str:
    """Résume les heures en plages contiguës.

    Avec préfixe pour le fil du texte (« de 13h à 19h »), sans préfixe pour
    une cellule de tableau (« 13h à 19h »).
    """
    heures = sorted({e.heure for e in entrees})
    if not heures:
        return ""
    plages: list[tuple[int, int]] = []
    debut = precedent = heures[0]
    for heure in heures[1:]:
        if heure == precedent + 1:
            precedent = heure
            continue
        plages.append((debut, precedent))
        debut = precedent = heure
    plages.append((debut, precedent))
    morceaux = [f"{d:02d}h à {f + 1:02d}h" for d, f in plages]
    if not avec_prefixe:
        return " et ".join(morceaux)
    if len(morceaux) == 1:
        return f"de {morceaux[0]}"
    return "de " + " et de ".join(morceaux)


def _phrase_congestion_troncon(
    code: str,
    entrees: list[rapport_paa.CongestionHoraire],
    *,
    avec_jours: bool = False,
) -> str:
    nombre = len(entrees)
    phrase = (
        f"Dans le sens « retour », le tronçon « {code} » a été congestionné sur "
        f"{_en_lettres(nombre)} ({nombre:02d}) tranches horaires "
        f"({_plages_horaires(entrees)})"
    )
    if avec_jours:
        occurrences = [e.nb_total_semaine for e in entrees]
        if occurrences:
            mini, maxi = min(occurrences), max(occurrences)
            jours = (
                f"{_en_lettres(mini)} ({mini})"
                if mini == maxi
                else f"{_en_lettres(mini)} ({mini}) à {_en_lettres(maxi)} ({maxi})"
            )
            phrase += f" sur {jours} jours dans la semaine"
    return phrase + " ;"


def _maj_observations_temps_moyen(
    paragraphes: list[Paragraph],
    contexte: mod_donnees.ContexteRapport,
    campagne: str,
) -> None:
    """Réécrit les trois puces « l'axe … est de X minutes … ».

    Les puces sont cherchées après l'amorce « Au niveau du temps moyen… » :
    la méthodologie, en début de rapport, énumère elle aussi les axes avec la
    même tournure et serait sinon écrasée.
    """
    rang = None
    for index, paragraphe in enumerate(paragraphes):
        if paragraphe.text.strip().startswith("Au niveau du temps moyen de traversée"):
            rang = index
            break
    if rang is None:
        return
    puces = [
        p for p in paragraphes[rang + 1: rang + 12]
        if p.text.strip().startswith("l’axe ")
    ]
    for index, axe in enumerate(contexte.axes):
        if index >= len(puces):
            break
        aller = next(
            (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "aller"),
            None,
        )
        retour = next(
            (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "retour"),
            None,
        )
        if aller is None or retour is None:
            continue
        valeur_aller = _mn(contexte.valeur(aller.libelle, "moyen", "jour_ouvrable"))
        valeur_retour = _mn(contexte.valeur(retour.libelle, "moyen", "jour_ouvrable"))
        ponctuation = "." if index == len(contexte.axes) - 1 else " ;"
        remplacer_texte(
            puces[index],
            f"l’axe {axe} est de {valeur_aller} minutes dans le sens « aller » contre "
            f"{valeur_retour} minutes dans le sens « retour » en {campagne}{ponctuation}",
        )

    # Phrase sur les pics de congestion.
    cible = premier(paragraphes, "Notons qu’en période de congestion")
    if cible is None:
        return
    pires: dict[str, tuple[str, int]] = {}
    for sens in contexte.sens_circulation:
        valeur = contexte.valeur(sens.libelle, "max", "jour_ouvrable")
        if valeur is None:
            continue
        actuel = pires.get(sens.sens)
        if actuel is None or valeur > actuel[1]:
            pires[sens.sens] = (sens.axe, valeur)
    if "aller" not in pires:
        remplacer_texte(cible, "")
        return
    axe_aller, max_aller = pires["aller"]
    phrase = (
        f"Notons qu’en période de congestion, le temps de traversée le plus long, "
        f"dans le sens aller, est celui de l’axe {axe_aller} qui peut aller jusqu’à "
        f"{max_aller} minutes."
    )
    if "retour" in pires:
        phrase += f" Dans le sens retour, ce temps peut aller jusqu’à {pires['retour'][1]} minutes."
    remplacer_texte(cible, phrase)


def _maj_phrase_comparatif(
    paragraphes: list[Paragraph],
    contexte: mod_donnees.ContexteRapport,
    params: dict[str, Any],
) -> None:
    """Réécrit la phrase de comparaison du Tableau 19, sens de variation inclus."""
    cible = premier(paragraphes, "Une comparaison du temps moyen de traversée")
    if cible is None:
        return
    comparatif = params["comparatif"]
    reference = comparatif.get("libelle_reference", "la campagne précédente")
    valeurs_ref = comparatif.get("valeurs") or {}
    campagne = contexte.libelle_campagne()

    ecarts: list[int] = []
    for sens in contexte.sens_circulation:
        if sens.sens != "retour":
            continue
        courant = contexte.valeur(sens.libelle, "moyen", "jour_ouvrable")
        precedent = valeurs_ref.get(f"{sens.libelle}|moyen|jour_ouvrable")
        if courant is not None and precedent is not None:
            ecarts.append(courant - precedent)

    if not ecarts:
        tendance = "ne peut pas être comparé faute de campagne de référence renseignée"
    elif all(e < 0 for e in ecarts):
        tendance = "est en baisse principalement dans le sens « retour » les jours ouvrables peu importe l’axe"
    elif all(e > 0 for e in ecarts):
        tendance = "est en hausse principalement dans le sens « retour » les jours ouvrables peu importe l’axe"
    else:
        tendance = "évolue de façon contrastée selon les axes dans le sens « retour » les jours ouvrables"

    phrase = (
        f"Une comparaison du temps moyen de traversée de {reference} et de celui de "
        f"{campagne} montre que ce dernier {tendance}."
    )

    max_courant = max(
        (v for (_l, a, _t), v in contexte.temps.items() if a == "max" and v is not None),
        default=None,
    )
    max_reference = comparatif.get("temps_max_reference_mn")
    if max_courant is not None and max_reference:
        phrase += (
            f" Aussi le temps maximal a été de {max_reference} mn en {reference} "
            f"contre {max_courant} mn en {campagne}."
        )
    remplacer_texte(cible, phrase)


# --- Signatures ------------------------------------------------------------


def _maj_signatures(document: Document, params: dict[str, Any]) -> None:
    tableau = _tableau_par_entete(document, "REDACTEUR", "VERIFICATEUR")
    if tableau is None or len(tableau.rows) < 2:
        return
    signatures = params["signatures"]
    colonnes = (
        ("redacteur_nom", "redacteur_fonction"),
        ("verificateur_nom", "verificateur_fonction"),
        ("approbateur_nom", "approbateur_fonction"),
    )
    for index, (cle_nom, cle_fonction) in enumerate(colonnes, start=1):
        if index >= len(tableau.columns):
            break
        cellule = tableau.cell(1, index)
        cellule.text = ""
        for ligne_texte, gras in (
            (signatures.get(cle_nom, ""), False),
            ("", False),
            (signatures.get(cle_fonction, ""), False),
        ):
            paragraphe = cellule.paragraphs[-1] if not cellule.paragraphs[-1].text else cellule.add_paragraph()
            run = paragraphe.add_run(ligne_texte)
            run.bold = gras
            run.font.size = Pt(10)


# --- Lignes « Source : » ---------------------------------------------------


def _maj_libelles_sources(
    paragraphes: list[Paragraph], contexte: mod_donnees.ContexteRapport
) -> None:
    """Aligne toutes les mentions de source sur la campagne générée."""
    organisme = "DEESP/DEEF"
    campagne = contexte.libelle_campagne()
    precedent_etait_source = False

    for paragraphe in paragraphes:
        texte = paragraphe.text.strip()
        if not texte:
            continue
        if not texte.startswith("Source"):
            precedent_etait_source = False
            continue
        if precedent_etait_source:
            # Le modèle porte une mention par tableau d'origine. Les tableaux
            # régénérés étant fusionnés (annexes), la mention en double est
            # supprimée plutôt que répétée.
            remplacer_texte(paragraphe, "")
            continue
        variante = "/S=Semaine" if "S=Semaine" in texte else ""
        nouveau = f"Source : {organisme}{variante}, {campagne}"
        remplacer_texte(paragraphe, nouveau)
        _degager_marges(paragraphe)
        if dans_zone_texte(paragraphe):
            # Ces mentions sont posées dans des cadres calibrés sur le libellé
            # d'origine : un mois plus long y passerait à la ligne et serait
            # rogné.
            activer_autofit_zone_texte(paragraphe)
            reduire_pour_tenir(paragraphe, texte, nouveau, taille_par_defaut=9.0)
        precedent_etait_source = True


# --- Table des matières ----------------------------------------------------


def _reparer_table_des_matieres(document: Document, paragraphes: list[Paragraph]) -> None:
    """Rend la table des matières exacte à l'ouverture du document.

    Deux corrections :

    1. Le modèle référence un signet absent, ce qui fait afficher
       « Erreur ! Signet non défini. » sur l'entrée « Etat des zones
       congestionnées dans le sens "aller" ». Le signet est recréé sur le
       titre correspondant.
    2. `updateFields` demande à Word de recalculer tous les champs à
       l'ouverture : les numéros de page suivent donc la pagination réelle du
       document généré, quel que soit le nombre de lignes des tableaux.
    """
    corps = document.element.body.xml
    if f'w:name="{BOOKMARK_MANQUANT}"' not in corps:
        for paragraphe in paragraphes:
            if paragraphe.text.strip().startswith(ANCRE_BOOKMARK_MANQUANT[:40]):
                _poser_bookmark(paragraphe, BOOKMARK_MANQUANT)
                break

    parametres_doc = document.settings.element
    for ancien in parametres_doc.findall(qn("w:updateFields")):
        parametres_doc.remove(ancien)
    champ = OxmlElement("w:updateFields")
    champ.set(qn("w:val"), "true")
    parametres_doc.append(champ)


def _poser_bookmark(paragraphe: Paragraph, nom: str, identifiant: int = 9001) -> None:
    debut = OxmlElement("w:bookmarkStart")
    debut.set(qn("w:id"), str(identifiant))
    debut.set(qn("w:name"), nom)
    fin = OxmlElement("w:bookmarkEnd")
    fin.set(qn("w:id"), str(identifiant))
    paragraphe._p.insert(0, debut)
    paragraphe._p.append(fin)


# ===========================================================================
# Remplacement des images figées par de vrais tableaux
# ===========================================================================


def _remplacer_images_figees(
    document: Document,
    paragraphes: list[Paragraph],
    contexte: mod_donnees.ContexteRapport,
    params: dict[str, Any],
) -> None:
    """Substitue de vrais tableaux et paragraphes aux captures d'écran du modèle."""
    porteuses = [p for p in paragraphes if _dessins(p)]

    _remplacer_apres_titre(
        document, paragraphes, porteuses, "Tableau 2",
        lambda doc, ancre: _construire_tableau_2(doc, ancre, contexte),
    )
    _remplacer_apres_titre(
        document, paragraphes, porteuses, "Tableau 3",
        lambda doc, ancre: _construire_tableau_3(doc, ancre, contexte),
    )
    for numero, axe in zip(("Tableau 8", "Tableau 9", "Tableau 10"), contexte.axes):
        _remplacer_apres_titre(
            document, paragraphes, porteuses, numero,
            lambda doc, ancre, axe=axe: _construire_tableau_moyen(doc, ancre, contexte, axe),
        )
    _remplacer_apres_titre(
        document, paragraphes, porteuses, "Tableau 16",
        lambda doc, ancre: _construire_tableau_16(doc, ancre, contexte),
    )
    _remplacer_apres_titre(
        document, paragraphes, porteuses, "Tableau 17",
        lambda doc, ancre: _construire_tableau_17(doc, ancre, contexte),
    )
    _remplacer_apres_titre(
        document, paragraphes, porteuses, "Tableau 19",
        lambda doc, ancre: _construire_tableau_19(doc, ancre, contexte, params),
    )

    _remplacer_commentaires_images(paragraphes, contexte)
    _remplacer_sources_images(paragraphes)
    _remplacer_annexes(document, params)


def _remplacer_apres_titre(
    document: Document,
    paragraphes: list[Paragraph],
    porteuses: list[Paragraph],
    titre: str,
    constructeur,
) -> None:
    """Remplace l'image qui suit un titre de tableau par un tableau généré.

    Le titre (« Tableau 8 : Evaluation du temps moyen… ») est l'ancre : on
    prend la première image significative qui le suit dans le flux du
    document, on la supprime et on insère le tableau à sa place.
    """
    ancre = None
    for index, paragraphe in enumerate(paragraphes):
        if paragraphe.text.strip().startswith(titre):
            ancre = index
            break
    if ancre is None:
        logger.warning("Titre « %s » introuvable — tableau non régénéré.", titre)
        return

    for paragraphe in paragraphes[ancre + 1: ancre + 8]:
        dimensions = _dimensions_pouces(paragraphe)
        # On vise l'image du tableau : large et haute d'au moins 1,1 pouce.
        # En dessous se trouvent les commentaires (≤ 0,95 pouce) et les
        # vignettes « Source : » (≤ 0,45 pouce), traités séparément.
        if not any(largeur >= 4.0 and hauteur >= 1.1 for largeur, hauteur in dimensions):
            continue
        # Certaines images de tableau cohabitent avec la vignette de source
        # dans le même paragraphe : supprimer l'une efface l'autre, il faut
        # donc reposer la mention en texte.
        avait_source = any(
            2.0 <= largeur <= 4.5 and hauteur <= 0.45 for largeur, hauteur in dimensions
        )
        _supprimer_images(paragraphe)
        constructeur(document, paragraphe)
        if avait_source:
            remplacer_texte(paragraphe, "Source : DEESP/DEEF, ")
            _styliser_source(paragraphe)
        return
    logger.warning("Aucune image de tableau après « %s ».", titre)


def _entete(tableau: Table, ligne: int, libelles: list[str], couleur: str) -> None:
    for colonne, libelle in enumerate(libelles):
        if colonne >= len(tableau.columns):
            break
        ecrire_cellule(
            tableau.cell(ligne, colonne), libelle,
            gras=True, taille=9, couleur=BLANC,
        )
        ombrer(tableau.cell(ligne, colonne), couleur)


# --- Tableau 2 — légende des tronçons -------------------------------------


def _construire_tableau_2(
    document: Document, ancre: Paragraph, contexte: mod_donnees.ContexteRapport
) -> None:
    lignes = contexte.legende_troncons
    if not lignes:
        remplacer_texte(
            ancre,
            "Aucun tronçon codifié n’est défini pour les axes surveillés. "
            "Renseignez-les depuis la page Administration.",
        )
        return
    tableau = inserer_tableau(document, ancre, len(lignes) + 1, 3)
    _entete(tableau, 0, ["AXE", "TRONÇON", "CODE"], NAVY)
    axe_precedent = None
    for index, (axe, nom, code) in enumerate(lignes, start=1):
        libelle_axe = "" if axe == axe_precedent else axe
        axe_precedent = axe
        ecrire_cellule(tableau.cell(index, 0), libelle_axe, gras=True, taille=9, centre=False)
        ecrire_cellule(tableau.cell(index, 1), nom, taille=9, centre=False)
        ecrire_cellule(tableau.cell(index, 2), code, gras=True, taille=9)
        if index % 2 == 0:
            for colonne in range(3):
                ombrer(tableau.cell(index, colonne), BLEU_CLAIR)


# --- Tableau 3 — zones congestionnées sens retour -------------------------


def _construire_tableau_3(
    document: Document, ancre: Paragraph, contexte: mod_donnees.ContexteRapport
) -> None:
    entrees = contexte.congestion_par_sens.get("retour", [])
    if not entrees:
        remplacer_texte(
            ancre,
            "Aucun tronçon ne satisfait les critères de congestion dans le sens "
            f"« retour » sur la période du {contexte.libelle_periode()}.",
        )
        return
    tableau = inserer_tableau(document, ancre, len(entrees) + 1, 4)
    _entete(
        tableau, 0,
        [f"HEURE ({contexte.heure_debut:02d}H-{contexte.heure_fin:02d}H)",
         "CODE", "NBRE DE JOURS/SEMAINE", "JOURS"],
        NAVY,
    )
    for index, entree in enumerate(entrees, start=1):
        jours = ", ".join(
            jour[:3].capitalize()
            for jour, nombre in entree.nb_jours_congestionnes_par_type.items()
            if nombre > 0
        )
        ecrire_cellule(
            tableau.cell(index, 0),
            f"{entree.heure:02d}H-{entree.heure + 1:02d}H", gras=True, taille=9,
        )
        ecrire_cellule(
            tableau.cell(index, 1),
            entree.sous_troncon_code or entree.troncon_nom, gras=True, taille=9,
        )
        ecrire_cellule(tableau.cell(index, 2), str(entree.nb_total_semaine), taille=9)
        ecrire_cellule(tableau.cell(index, 3), jours or "—", taille=9)


# --- Tableaux 8, 9, 10 — temps moyen journalier ---------------------------


def _construire_tableau_moyen(
    document: Document,
    ancre: Paragraph,
    contexte: mod_donnees.ContexteRapport,
    axe: str,
) -> None:
    lignes = contexte.moyennes_journalieres.get(axe, [])
    aller = next(
        (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "aller"), None
    )
    retour = next(
        (s for s in contexte.sens_circulation if s.axe == axe and s.sens == "retour"), None
    )
    if not lignes or aller is None or retour is None:
        remplacer_texte(ancre, f"Aucune mesure disponible pour l’axe « {axe} ».")
        return

    tableau = inserer_tableau(document, ancre, len(lignes) + 4, 5)

    # Deux lignes d'en-tête : le sens, puis le type de jour.
    ecrire_cellule(tableau.cell(0, 0), "AXES / JOURS", gras=True, taille=9, couleur=BLANC)
    ombrer(tableau.cell(0, 0), NAVY)
    cellule_aller = _fusionner(tableau, 0, 1, 2)
    ecrire_cellule(cellule_aller, aller.libelle, gras=True, taille=9, couleur=BLANC)
    ombrer(cellule_aller, BLEU_MOYEN)
    cellule_retour = _fusionner(tableau, 0, 3, 4)
    ecrire_cellule(cellule_retour, retour.libelle, gras=True, taille=9, couleur=BLANC)
    ombrer(cellule_retour, BLEU_MOYEN)

    ecrire_cellule(tableau.cell(1, 0), "", taille=9)
    ombrer(tableau.cell(1, 0), NAVY)
    for colonne, libelle in ((1, "Jours ouvrables"), (2, "Week-ends"),
                             (3, "Jours ouvrables"), (4, "Week-ends")):
        ecrire_cellule(tableau.cell(1, colonne), libelle, gras=True, taille=8, couleur=BLANC)
        ombrer(tableau.cell(1, colonne), "808080")

    totaux = {"aller_jo": 0, "aller_we": 0, "retour_jo": 0, "retour_we": 0}
    compte = {"aller_jo": 0, "aller_we": 0, "retour_jo": 0, "retour_we": 0}

    for index, ligne in enumerate(lignes, start=2):
        ecrire_cellule(tableau.cell(index, 0), ligne.libelle, gras=True, taille=8)
        if ligne.est_week_end:
            ombrer(tableau.cell(index, 0), BLEU_MOYEN)
        # Les colonnes « week-end » ne reçoivent une valeur que les samedis et
        # dimanches, et inversement — comme dans le rapport de référence.
        cases = (
            (1, ligne.aller_mn, not ligne.est_week_end, "aller_jo"),
            (2, ligne.aller_mn, ligne.est_week_end, "aller_we"),
            (3, ligne.retour_mn, not ligne.est_week_end, "retour_jo"),
            (4, ligne.retour_mn, ligne.est_week_end, "retour_we"),
        )
        for colonne, valeur, applicable, cle in cases:
            texte = str(valeur) if (applicable and valeur is not None) else ""
            ecrire_cellule(tableau.cell(index, colonne), texte, taille=8)
            if applicable and valeur is not None:
                totaux[cle] += valeur
                compte[cle] += 1

    rang_total = len(lignes) + 2
    ecrire_cellule(
        tableau.cell(rang_total, 0),
        "Total du temps moyen journalier de traversée", gras=True, taille=8,
    )
    rang_moyenne = rang_total + 1
    ecrire_cellule(
        tableau.cell(rang_moyenne, 0),
        "Temps moyen de traversée", gras=True, taille=8, couleur=BLANC,
    )
    ombrer(tableau.cell(rang_moyenne, 0), NAVY)
    for colonne, cle in ((1, "aller_jo"), (2, "aller_we"), (3, "retour_jo"), (4, "retour_we")):
        ecrire_cellule(tableau.cell(rang_total, colonne), str(totaux[cle]) if compte[cle] else "", gras=True, taille=8)
        moyenne = round(totaux[cle] / compte[cle]) if compte[cle] else None
        ecrire_cellule(
            tableau.cell(rang_moyenne, colonne),
            "" if moyenne is None else str(moyenne),
            gras=True, taille=9, couleur=BLANC,
        )
        ombrer(tableau.cell(rang_moyenne, colonne), NAVY)


def _remplacer_commentaires_images(
    paragraphes: list[Paragraph], contexte: mod_donnees.ContexteRapport
) -> None:
    """Réécrit les commentaires que le modèle fige sous forme de capture d'écran.

    Quatre phrases sont concernées : le commentaire du temps minimal du
    deuxième axe (sous le Tableau 5) et les trois commentaires de temps moyen
    (sous les Tableaux 8, 9 et 10). Elles sont repérées par leur gabarit —
    image large et basse — dans les paragraphes qui suivent le titre du
    tableau correspondant.
    """
    # (titre du tableau servant d'ancre, agrégat commenté, rang de l'axe)
    cibles: tuple[tuple[str, str, int], ...] = (
        ("Tableau 5", "min", 1),
        ("Tableau 8", "moyen", 0),
        ("Tableau 9", "moyen", 1),
        ("Tableau 10", "moyen", 2),
    )
    for titre, agregat, rang_axe in cibles:
        if rang_axe >= len(contexte.axes):
            continue
        axe = contexte.axes[rang_axe]
        depart = None
        for index, paragraphe in enumerate(paragraphes):
            if paragraphe.text.strip().startswith(titre):
                depart = index
                break
        if depart is None:
            continue
        for paragraphe in paragraphes[depart + 1: depart + 14]:
            dimensions = _dimensions_pouces(paragraphe)
            if not any(
                largeur >= 6.0 and 0.5 <= hauteur <= 1.3 for largeur, hauteur in dimensions
            ):
                continue
            _supprimer_images(paragraphe)
            phrase = (
                _phrase_commentaire(contexte, axe, agregat)
                if agregat != "moyen"
                else _commentaire_temps_moyen(contexte, titre, axe)
            )
            remplacer_texte(paragraphe, phrase)
            # Le paragraphe portait une image : sa mise en forme de caractère
            # est celle d'une légende. On la ramène au corps de texte.
            for run in paragraphe.runs:
                run.italic = False
                run.bold = False
                run.font.size = Pt(12)
            break


def _commentaire_temps_moyen(
    contexte: mod_donnees.ContexteRapport, numero: str, axe: str
) -> str:
    aller, retour = _sens_axe(contexte, axe)
    if aller is None or retour is None:
        return ""
    aller_jo = _mn(contexte.valeur(aller.libelle, "moyen", "jour_ouvrable"))
    aller_we = _mn(contexte.valeur(aller.libelle, "moyen", "week_end"))
    retour_jo = _mn(contexte.valeur(retour.libelle, "moyen", "jour_ouvrable"))
    retour_we = _mn(contexte.valeur(retour.libelle, "moyen", "week_end"))
    return (
        f"Au regard du {numero.lower()}, il ressort que le temps moyen de traversée de "
        f"l’axe « {axe} » pour les jours ouvrables est de {aller_jo} Mn contre "
        f"{retour_jo} Mn dans le sens « retour ». Pour ce qui est des week-ends, ce "
        f"temps est de {aller_we} Mn en « aller » et de {retour_we} Mn « au retour »."
    )


# --- Tableau 16 — tronçons congestionnés ----------------------------------


def _construire_tableau_16(
    document: Document, ancre: Paragraph, contexte: mod_donnees.ContexteRapport
) -> None:
    lignes: list[tuple[str, str, list[rapport_paa.CongestionHoraire]]] = []
    for sens in ("aller", "retour"):
        for code, entrees in _grouper_congestions(
            contexte.congestion_par_sens.get(sens, [])
        ).items():
            lignes.append((code, sens.upper(), entrees))
    if not lignes:
        remplacer_texte(
            ancre,
            "Aucun tronçon ne satisfait les règles de congestion DEESP "
            f"(≥ {rapport_paa.SEUIL_JOUR_DEESP} occurrences sur un même jour "
            f"indicatif ou ≥ {rapport_paa.SEUIL_SEMAINE_DEESP} occurrences dans la "
            "semaine) sur la période analysée.",
        )
        return

    lignes.sort(key=lambda ligne: ligne[0])
    tableau = inserer_tableau(document, ancre, len(lignes) + 1, 5)
    _entete(
        tableau, 0,
        ["TRONCON", "SENS DE CIRCULATION", "NOMBRE DE TRANCHE HORAIRE",
         "TRANCHE HORAIRE", "NOMBRE DE JOURS DANS LA SEMAINE"],
        NAVY,
    )
    for index, (code, sens, entrees) in enumerate(lignes, start=1):
        occurrences = [e.nb_total_semaine for e in entrees]
        mini, maxi = min(occurrences), max(occurrences)
        jours = f"({mini}) jours" if mini == maxi else f"({mini}) à ({maxi}) jours"
        ecrire_cellule(tableau.cell(index, 0), code, gras=True, taille=9)
        ecrire_cellule(tableau.cell(index, 1), sens, taille=9)
        ecrire_cellule(tableau.cell(index, 2), str(len(entrees)), taille=9)
        ecrire_cellule(
            tableau.cell(index, 3),
            _plages_horaires(entrees, avec_prefixe=False),
            taille=9,
        )
        ecrire_cellule(tableau.cell(index, 4), jours, taille=9)


# --- Tableau 17 — récapitulatif du temps de traversée ---------------------


def _construire_tableau_17(
    document: Document, ancre: Paragraph, contexte: mod_donnees.ContexteRapport
) -> None:
    allers = contexte.sens_de("aller")
    retours = contexte.sens_de("retour")
    colonnes = 2 + len(allers) + len(retours)
    tableau = inserer_tableau(document, ancre, 8, colonnes)
    _fixer_largeurs(
        tableau, [2.2, 1.9] + [(16.0 - 4.1) / max(1, colonnes - 2)] * (colonnes - 2)
    )

    cellule_axes = _fusionner(tableau, 0, 0, 1)
    ecrire_cellule(cellule_axes, "Axes", gras=True, taille=9, couleur=BLANC)
    ombrer(cellule_axes, NAVY)
    if allers:
        cellule = _fusionner(tableau, 0, 2, 1 + len(allers))
        ecrire_cellule(cellule, "Sens « Aller »", gras=True, taille=9, couleur=BLANC)
        ombrer(cellule, BLEU_MOYEN)
    if retours:
        cellule = _fusionner(tableau, 0, 2 + len(allers), colonnes - 1)
        ecrire_cellule(cellule, "Sens « Retour »", gras=True, taille=9, couleur=BLANC)
        ombrer(cellule, BLEU_MOYEN)

    cellule_vide = _fusionner(tableau, 1, 0, 1)
    ecrire_cellule(cellule_vide, "", taille=9)
    ombrer(cellule_vide, GRIS_CLAIR)
    for decalage, sens in enumerate(allers + retours):
        colonne = 2 + decalage
        ecrire_cellule(tableau.cell(1, colonne), sens.libelle, gras=True, taille=8)
        ombrer(tableau.cell(1, colonne), GRIS_CLAIR)

    rubriques = (
        ("Temps minimal", "min"),
        ("Temps moyen", "moyen"),
        ("Temps maximal", "max"),
    )
    ligne = 2
    for libelle, agregat in rubriques:
        for type_jour, libelle_jour in (
            ("jour_ouvrable", "Jours ouvrables"),
            ("week_end", "Week-end"),
        ):
            ecrire_cellule(
                tableau.cell(ligne, 0),
                libelle if type_jour == "jour_ouvrable" else "",
                gras=True, taille=8,
            )
            ecrire_cellule(tableau.cell(ligne, 1), libelle_jour, taille=8)
            for decalage, sens in enumerate(allers + retours):
                ecrire_cellule(
                    tableau.cell(ligne, 2 + decalage),
                    _mn(contexte.valeur(sens.libelle, agregat, type_jour)),
                    gras=True, taille=9,
                )
            ligne += 1


# --- Tableau 19 — comparatif pluriannuel ----------------------------------


def _construire_tableau_19(
    document: Document,
    ancre: Paragraph,
    contexte: mod_donnees.ContexteRapport,
    params: dict[str, Any],
) -> None:
    comparatif = params["comparatif"]
    reference = comparatif.get("libelle_reference", "réf.")
    valeurs_ref = comparatif.get("valeurs") or {}
    courant = contexte.libelle_campagne()

    sens_liste = contexte.sens_de("aller") + contexte.sens_de("retour")
    colonnes = 2 + len(sens_liste) * 2
    # 2 lignes d'en-tête + 3 rubriques × 2 types de jour.
    tableau = inserer_tableau(document, ancre, 8, colonnes)
    # Douze colonnes de valeurs sur une page portrait : les libellés de
    # rubrique sont contraints pour laisser la place aux chiffres.
    _fixer_largeurs(
        tableau, [1.9, 1.3] + [(16.0 - 3.2) / max(1, colonnes - 2)] * (colonnes - 2)
    )

    cellule_axes = _fusionner(tableau, 0, 0, 1)
    ecrire_cellule(cellule_axes, "Axes", gras=True, taille=9, couleur=BLANC)
    ombrer(cellule_axes, NAVY)
    for index, sens in enumerate(sens_liste):
        gauche = 2 + index * 2
        cellule = _fusionner(tableau, 0, gauche, gauche + 1)
        ecrire_cellule(cellule, sens.libelle, gras=True, taille=7, couleur=BLANC)
        ombrer(cellule, BLEU_MOYEN)

    cellule_vide = _fusionner(tableau, 1, 0, 1)
    ecrire_cellule(cellule_vide, "", taille=7)
    ombrer(cellule_vide, GRIS_CLAIR)
    for index in range(len(sens_liste)):
        for decalage, libelle in enumerate((reference, courant)):
            colonne = 2 + index * 2 + decalage
            ecrire_cellule(tableau.cell(1, colonne), libelle, gras=True, taille=7)
            ombrer(tableau.cell(1, colonne), GRIS_CLAIR)

    ligne = 2
    for libelle, agregat in (
        ("Temps minimal", "min"), ("Temps moyen", "moyen"), ("Temps maximal", "max")
    ):
        for type_jour, libelle_jour in (
            ("jour_ouvrable", "Jours"), ("week_end", "Week-ends")
        ):
            ecrire_cellule(
                tableau.cell(ligne, 0),
                libelle if type_jour == "jour_ouvrable" else "",
                gras=True, taille=8,
            )
            ecrire_cellule(tableau.cell(ligne, 1), libelle_jour, taille=8)
            for index, sens in enumerate(sens_liste):
                cle = f"{sens.libelle}|{agregat}|{type_jour}"
                ecrire_cellule(
                    tableau.cell(ligne, 2 + index * 2),
                    _mn(valeurs_ref.get(cle)), taille=8,
                )
                ecrire_cellule(
                    tableau.cell(ligne, 3 + index * 2),
                    _mn(contexte.valeur(sens.libelle, agregat, type_jour)),
                    gras=True, taille=8,
                )
            ligne += 1


# --- Annexes ---------------------------------------------------------------


def _remplacer_annexes(document: Document, params: dict[str, Any]) -> None:
    """Réécrit le tableau des temps réels observés à partir du classeur.

    Ces relevés proviennent de sorties terrain : l'application ne les produit
    pas. Faute de saisie, le tableau du modèle — qui contient les relevés
    d'une campagne antérieure — est vidé plutôt que présenté comme courant.
    """
    tableaux = [
        t for t in document.tables
        if t.rows and "DATE DE SORTIE" in t.rows[0].cells[0].text.upper()
    ]
    if not tableaux:
        return

    # Le tableau du modèle porte une mise en forme calibrée sur le nombre de
    # sorties d'une campagne passée. Il est remplacé par un tableau construit
    # à la dimension des relevés saisis, inséré à la place du premier.
    ancre = tableaux[0]._tbl
    releves = params.get("annexes") or []
    nouveau = _construire_tableau_annexe(document, releves)
    ancre.addprevious(nouveau._tbl)
    for tableau in tableaux:
        tableau._tbl.getparent().remove(tableau._tbl)


def _construire_tableau_annexe(
    document: Document, releves: list[dict[str, Any]]
) -> Table:
    """Construit le tableau des temps réels : semaines, dates puis axes."""
    # Regroupement en préservant l'ordre de saisie du classeur.
    par_semaine: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for releve in releves:
        semaine = str(releve.get("semaine") or "—")
        jour = str(releve.get("date") or "—")
        par_semaine.setdefault(semaine, {}).setdefault(jour, []).append(releve)

    nb_lignes = 2 + sum(
        1 + sum(1 + len(entrees) for entrees in jours.values())
        for jours in par_semaine.values()
    )
    tableau = document.add_table(rows=max(nb_lignes, 3), cols=6)
    try:
        tableau.style = "Table Grid"
    except KeyError:
        pass
    _bordures(tableau)
    _fixer_largeurs(tableau, [4.6, 2.6, 2.2, 2.2, 2.2, 2.2])

    # Deux lignes d'en-tête, comme dans le rapport d'origine.
    ecrire_cellule(tableau.cell(0, 0), "DATE DE SORTIE", gras=True, taille=9)
    ecrire_cellule(tableau.cell(0, 1), "JOUR", gras=True, taille=9)
    cellule_aller = _fusionner(tableau, 0, 2, 3)
    ecrire_cellule(cellule_aller, "HEURES ALLER", gras=True, taille=9)
    cellule_retour = _fusionner(tableau, 0, 4, 5)
    ecrire_cellule(cellule_retour, "HEURES RETOUR", gras=True, taille=9)

    ecrire_cellule(tableau.cell(1, 0), "", taille=9)
    ecrire_cellule(tableau.cell(1, 1), "", taille=9)
    cellule = _fusionner(tableau, 1, 2, 3)
    ecrire_cellule(cellule, "TEMPS REEL MIS ALLER", gras=True, taille=8)
    cellule = _fusionner(tableau, 1, 4, 5)
    ecrire_cellule(cellule, "TEMPS REEL MIS RETOUR", gras=True, taille=8)

    if not releves:
        fusion = _fusionner(tableau, 2, 0, 5)
        ecrire_cellule(
            fusion,
            "Aucun relevé terrain saisi pour cette campagne — complétez la "
            "feuille « Annexes » du classeur Excel.",
            italique=True, taille=9,
        )
        return tableau

    index = 2
    for semaine, jours in par_semaine.items():
        fusion = _fusionner(tableau, index, 0, 5)
        ecrire_cellule(fusion, f"SEMAINE {semaine}", gras=True, taille=9, couleur=BLANC)
        ombrer(fusion, NAVY)
        index += 1

        for jour, entrees in jours.items():
            premiere = entrees[0]
            ecrire_cellule(tableau.cell(index, 0), jour, gras=True, taille=9)
            ecrire_cellule(
                tableau.cell(index, 1), str(premiere.get("jour") or ""),
                gras=True, taille=9,
            )
            for colonne, cle in enumerate(
                ("heure_aller_1", "heure_aller_2", "heure_retour_1", "heure_retour_2"),
                start=2,
            ):
                ecrire_cellule(
                    tableau.cell(index, colonne), str(premiere.get(cle) or ""),
                    gras=True, taille=9,
                )
            for colonne in range(6):
                ombrer(tableau.cell(index, colonne), GRIS_CLAIR)
            index += 1

            for entree in entrees:
                ecrire_cellule(
                    tableau.cell(index, 0), str(entree.get("axe") or ""),
                    taille=8, centre=False,
                )
                ecrire_cellule(tableau.cell(index, 1), "", taille=8)
                for colonne, cle in enumerate(
                    ("aller_1", "aller_2", "retour_1", "retour_2"), start=2
                ):
                    valeur = entree.get(cle)
                    ecrire_cellule(
                        tableau.cell(index, colonne),
                        "" if valeur is None else str(valeur),
                        gras=True, taille=9,
                    )
                index += 1

    return tableau


# --- Lignes « Source : » rendues en image ---------------------------------


def _remplacer_sources_images(paragraphes: list[Paragraph]) -> None:
    """Convertit les vignettes « Source : … » du modèle en vrai texte.

    Sous chaque graphique, le modèle place la mention de source sous forme
    d'image, ce qui y fige la campagne. Ces vignettes ont un gabarit très
    reconnaissable (environ 2 à 4,5 pouces de large pour moins d'un demi-pouce
    de haut) et n'apparaissent qu'après l'introduction.
    """
    debut = None
    for index, paragraphe in enumerate(paragraphes):
        if paragraphe.text.strip().upper().startswith("INTRODUCTION"):
            debut = index
            break
    if debut is None:
        return

    for index in range(debut + 1, len(paragraphes)):
        paragraphe = paragraphes[index]
        dimensions = _dimensions_pouces(paragraphe)
        if not dimensions:
            continue
        if not all(2.0 <= largeur <= 4.5 and hauteur <= 0.45 for largeur, hauteur in dimensions):
            continue
        # Seules les vignettes qui suivent un graphique sont des mentions de
        # source. Le modèle contient d'autres images de ce gabarit — filets
        # décoratifs sous les titres de section — qu'il ne faut pas toucher.
        # Les paragraphes intercalaires étant souvent vides, la recherche
        # remonte jusqu'au dernier paragraphe porteur de texte.
        contexte_amont = ""
        for precedent in reversed(paragraphes[max(0, index - 25): index]):
            if precedent.text.strip():
                contexte_amont = precedent.text
                break
        if "Graphique" not in contexte_amont:
            continue
        _supprimer_images(paragraphe)
        remplacer_texte(paragraphe, "Source : DEESP/DEEF/S=Semaine, ")
        _styliser_source(paragraphe)


def _styliser_source(paragraphe: Paragraph) -> None:
    for run in paragraphe.runs:
        run.italic = True
        run.font.size = Pt(9)
    _degager_marges(paragraphe)


def _degager_marges(paragraphe: Paragraph) -> None:
    """Annule les retraits hérités d'un paragraphe qui portait une image.

    Ces paragraphes sont calibrés sur la largeur de la vignette qu'ils
    contenaient — souvent moins de 7 cm. Le texte substitué y passerait à la
    ligne et serait tronqué.
    """
    format_p = paragraphe.paragraph_format
    format_p.left_indent = Cm(0)
    format_p.right_indent = Cm(0)
    format_p.first_line_indent = Cm(0)
    # Un cadre de positionnement figerait aussi la largeur.
    proprietes = paragraphe._p.find(qn("w:pPr"))
    if proprietes is not None:
        for cadre in proprietes.findall(qn("w:framePr")):
            proprietes.remove(cadre)
