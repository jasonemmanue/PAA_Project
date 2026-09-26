"""Génération du Rapport DEESP officiel au format Word (.docx).

Ce package reproduit **à l'identique** le rapport
*« EVALUATION DU TEMPS DE TRAVERSEE DE LA ZONE PORTUAIRE »* publié par la
DEESP/DEEF du Port Autonome d'Abidjan : même page de garde, mêmes styles,
mêmes 19 tableaux, mêmes 12 graphiques, même table des matières.

Principe — le document de référence fourni par la DEESP est embarqué comme
**modèle** (`modele/rapport_modele.docx`). La génération ouvre ce modèle et
remplace uniquement les contenus variables :

  - les valeurs calculées par l'application (temps de traversée collectés via
    Google Routes sur la période et le créneau horaire choisis) ;
  - les valeurs saisies par le rédacteur dans un classeur Excel (chiffres
    macro-économiques, constats terrain, campagne de référence, annexes).

Tout le reste — images de couverture, logos, mise en forme, styles — provient
du modèle et reste donc rigoureusement identique à l'original.

Modules :
  - `parametres`  : contrat de données Excel (modèle, import, valeurs par défaut)
  - `donnees`     : extraction des données applicatives pour la période
  - `graphiques`  : réécriture des 12 graphiques natifs Word
  - `generateur`  : assemblage final du .docx
"""

from __future__ import annotations
