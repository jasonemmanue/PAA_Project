"""Réécriture des 12 graphiques natifs du modèle Word.

Le rapport de référence embarque douze graphiques Word (et non des images) :
des barres horizontales empilées, une série par semaine (S1, S2…), une
catégorie par jour de la semaine.

Plutôt que de les remplacer par des images — ce qui ferait perdre la mise en
forme d'origine (couleurs, bordures arrondies, étiquettes de données) — on
réécrit directement le cache de valeurs de chaque graphique dans son XML.
Word affiche ce cache tel quel : le rendu reste donc rigoureusement identique
à l'original, seules les valeurs changent.

Structure ciblée dans `word/charts/chartN.xml` :

    <c:ser>
      <c:tx><c:v>S1</c:v></c:tx>              ← nom de la série (semaine)
      <c:cat>…<c:strCache>…</c:strCache></c:cat>   ← jours de la semaine
      <c:val>…<c:numCache>…</c:numCache></c:val>   ← valeurs en minutes
    </c:ser>
"""

from __future__ import annotations

import copy
import logging

from lxml import etree

from app.rapport_officiel.donnees import JOURS_SEMAINE


logger = logging.getLogger("paa.rapport.graphiques")


NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NSMAP = {"c": NS_C}


def _q(balise: str) -> str:
    return f"{{{NS_C}}}{balise}"


def _vider(element: etree._Element) -> None:
    for enfant in list(element):
        element.remove(enfant)


def _ecrire_cache_categories(serie: etree._Element, categories: list[str]) -> None:
    """Remplace la liste des catégories (jours) du cache de la série."""
    cache = serie.find(f"{_q('cat')}/{_q('strRef')}/{_q('strCache')}", NSMAP)
    if cache is None:
        return
    _vider(cache)
    compte = etree.SubElement(cache, _q("ptCount"))
    compte.set("val", str(len(categories)))
    for index, libelle in enumerate(categories):
        point = etree.SubElement(cache, _q("pt"))
        point.set("idx", str(index))
        etree.SubElement(point, _q("v")).text = libelle


def _ecrire_cache_valeurs(serie: etree._Element, valeurs: list[int | None]) -> None:
    """Remplace les valeurs numériques du cache de la série.

    Un jour sans mesure est simplement omis du cache : Word n'affiche alors
    aucune barre, ce qui correspond au comportement du rapport de référence
    (cf. la première semaine de février, partiellement couverte).
    """
    cache = serie.find(f"{_q('val')}/{_q('numRef')}/{_q('numCache')}", NSMAP)
    if cache is None:
        return
    format_code = cache.find(_q("formatCode"), NSMAP)
    texte_format = format_code.text if format_code is not None else "General"
    _vider(cache)
    etree.SubElement(cache, _q("formatCode")).text = texte_format
    compte = etree.SubElement(cache, _q("ptCount"))
    compte.set("val", str(len(valeurs)))
    for index, valeur in enumerate(valeurs):
        if valeur is None:
            continue
        point = etree.SubElement(cache, _q("pt"))
        point.set("idx", str(index))
        etree.SubElement(point, _q("v")).text = str(valeur)


def _ecrire_nom_serie(serie: etree._Element, nom: str) -> None:
    noeud = serie.find(f"{_q('tx')}/{_q('v')}", NSMAP)
    if noeud is not None:
        noeud.text = nom
        return
    reference = serie.find(f"{_q('tx')}/{_q('strRef')}/{_q('strCache')}", NSMAP)
    if reference is not None:
        _vider(reference)
        compte = etree.SubElement(reference, _q("ptCount"))
        compte.set("val", "1")
        point = etree.SubElement(reference, _q("pt"))
        point.set("idx", "0")
        etree.SubElement(point, _q("v")).text = nom


def reecrire_graphique(
    xml_source: bytes,
    libelles_semaines: list[str],
    matrice: list[list[int | None]],
) -> bytes:
    """Retourne le XML du graphique avec les nouvelles données.

    Args:
        xml_source: contenu de `word/charts/chartN.xml` du modèle.
        libelles_semaines: noms des séries, un par semaine (« S1 », « S2 »…).
        matrice: valeurs en minutes, `matrice[semaine][jour]`, `None` si le
            jour n'a pas été mesuré.
    """
    racine = etree.fromstring(xml_source)
    graphe = racine.find(f".//{_q('barChart')}", NSMAP)
    if graphe is None:
        logger.warning("Graphique sans barChart — laissé inchangé.")
        return xml_source

    series_modele = graphe.findall(_q("ser"), NSMAP)
    if not series_modele:
        logger.warning("Graphique sans série — laissé inchangé.")
        return xml_source

    # On conserve la position d'insertion : les séries précèdent les éléments
    # de configuration (gapWidth, overlap, axId…) dans l'ordre du schéma.
    position = list(graphe).index(series_modele[0])
    for serie in series_modele:
        graphe.remove(serie)

    for index, libelle in enumerate(libelles_semaines):
        # Réutilisation cyclique des séries d'origine : chacune porte sa
        # propre couleur, ce qui préserve la palette du rapport même si la
        # période analysée compte plus de semaines que le modèle.
        serie = copy.deepcopy(series_modele[index % len(series_modele)])
        for balise, valeur in (("idx", index), ("order", index)):
            noeud = serie.find(_q(balise), NSMAP)
            if noeud is not None:
                noeud.set("val", str(valeur))
        _ecrire_nom_serie(serie, libelle)
        _ecrire_cache_categories(serie, list(JOURS_SEMAINE))
        valeurs = matrice[index] if index < len(matrice) else [None] * len(JOURS_SEMAINE)
        _ecrire_cache_valeurs(serie, valeurs)
        graphe.insert(position + index, serie)

    return etree.tostring(
        racine, xml_declaration=True, encoding="UTF-8", standalone=True
    )


def plan_des_graphiques(
    sens_par_axe: list[tuple[str, str | None, str | None]],
) -> dict[str, tuple[str, str]]:
    """Associe chaque fichier `chartN.xml` à un couple (libellé de sens, agrégat).

    Le rapport ordonne ses graphiques par agrégat puis par axe puis par sens :
    Graphiques 1 à 6 pour le temps minimal (axe 1 aller, axe 1 retour, axe 2
    aller, …), Graphiques 7 à 12 pour le temps maximal, dans le même ordre.

    Args:
        sens_par_axe: pour chaque axe, le couple (libellé aller, libellé
            retour) — `None` si le sens n'existe pas.

    Returns:
        Dictionnaire `{"chart1.xml": (libellé, "min"), …}` limité aux
        graphiques réellement alimentables.
    """
    plan: dict[str, tuple[str, str]] = {}
    for rang_agregat, agregat in enumerate(("min", "max")):
        numero = rang_agregat * 6 + 1
        for _axe, aller, retour in sens_par_axe[:3]:
            for libelle in (aller, retour):
                if numero > (rang_agregat + 1) * 6:
                    break
                if libelle:
                    plan[f"chart{numero}.xml"] = (libelle, agregat)
                numero += 1
    return plan
