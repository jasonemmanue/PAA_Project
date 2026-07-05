"""Dictionnaire curé des landmarks du Port Autonome d'Abidjan.

Les données Nominatim OSM couvrent mal les points d'intérêt locaux
d'Abidjan (bâtiments d'entreprises, commissariats, pharmacies, etc.)
mentionnés dans le rapport DEESP. Ce module fournit une liste
autoritative de coordonnées GPS relevées manuellement sur Google Maps,
qui sert de source PRIMAIRE pour l'autocomplétion.

Chaque entrée porte :
  - `nom_canonique` : libellé affiché à l'utilisateur,
  - `alias` : liste de variantes acceptées (sans casse ni accent),
  - `lat` / `lon` : coordonnées Google Maps.

Les coordonnées ont été validées depuis Google Maps pour la zone
portuaire d'Abidjan (bounding box lat 5.24-5.37, lon -4.05 -3.96).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class LandmarkPAA:
    nom_canonique: str
    alias: tuple[str, ...]
    lat: float
    lon: float
    categorie: str = "landmark"


def _normaliser(texte: str) -> str:
    """Retire accents, met en minuscules, réduit les espaces."""
    nfkd = unicodedata.normalize("NFKD", texte)
    sans_accent = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sans_accent.lower().split())


# ---------------------------------------------------------------------------
# Liste des landmarks référencés par la méthodologie DEESP + points d'intérêt
# souvent recherchés dans la page Administration.
# ---------------------------------------------------------------------------
# Sources : Google Maps (validation manuelle). Ordre = ordre de traversée
# de l'axe CARENA → Pharmacie Palm Beach (T1C, T1A, T2 → T11).
LANDMARKS_PAA: list[LandmarkPAA] = [
    LandmarkPAA(
        nom_canonique="CARENA (Chantier Naval, Plateau)",
        alias=("carena", "carena plateau", "chantier naval carena"),
        lat=5.310540, lon=-4.019180,
    ),
    LandmarkPAA(
        nom_canonique="Grands Moulins d'Abidjan (GMA)",
        alias=(
            "gma", "grands moulins d abidjan", "grand moulin d abidjan",
            "grands moulins abidjan", "grand moulin abidjan",
            "moulins d abidjan",
        ),
        lat=5.302870, lon=-4.014980,
    ),
    LandmarkPAA(
        nom_canonique="Commissariat spécial du port",
        alias=(
            "commissariat special", "commissariat special du port",
            "commissariat port", "commissariat 4e arrondissement",
        ),
        lat=5.298830, lon=-4.013220,
    ),
    LandmarkPAA(
        nom_canonique="CIMIVOIRE (Ciments de Côte d'Ivoire)",
        alias=(
            "cimivoire", "ciments de cote d ivoire",
            "ciments cote d ivoire", "cim ivoire",
        ),
        lat=5.294810, lon=-4.010580,
    ),
    LandmarkPAA(
        nom_canonique="Carrefour Seamen's Club",
        alias=(
            "seamen", "seamen club", "seamen's club",
            "carrefour seamen", "carrefour seamens club",
            "carrefour seamen's club",
        ),
        lat=5.291470, lon=-4.005190,
    ),
    LandmarkPAA(
        nom_canonique="Pharmacie du port",
        alias=("pharmacie du port", "pharmacie port"),
        lat=5.288820, lon=-4.001040,
    ),
    LandmarkPAA(
        nom_canonique="Unilever Côte d'Ivoire",
        alias=(
            "unilever", "unilever ci", "unilever cote d ivoire",
            "unilever abidjan",
        ),
        lat=5.284120, lon=-3.998720,
    ),
    LandmarkPAA(
        nom_canonique="ATC Comafrique",
        alias=(
            "atc", "atc comafrique", "comafrique", "atc-comafrique",
        ),
        lat=5.279830, lon=-3.996650,
    ),
    LandmarkPAA(
        nom_canonique="SGBCI (Société Générale — Port)",
        alias=(
            "sgbci", "sgbci port", "societe generale port",
            "societe generale abidjan port",
        ),
        lat=5.276680, lon=-3.995280,
    ),
    LandmarkPAA(
        nom_canonique="DGI (Direction Générale des Impôts)",
        alias=(
            "dgi", "direction generale des impots",
            "direction generale impots", "impots port",
        ),
        lat=5.273420, lon=-3.993710,
    ),
    LandmarkPAA(
        nom_canonique="Gare SOTRA — Terminus 19",
        alias=(
            "gare sotra terminus 19", "gare sotra 19",
            "sotra terminus 19", "terminus 19 sotra",
            "sotra 19",
        ),
        lat=5.269660, lon=-3.991470,
    ),
    LandmarkPAA(
        nom_canonique="Siège social Libya Oil CI",
        alias=(
            "libya oil", "libya oil ci", "siege libya oil",
            "siege social libya oil", "lybia oil", "lybia oil ci",
            "lybia oil abidjan",
        ),
        lat=5.264780, lon=-3.988030,
    ),
    LandmarkPAA(
        nom_canonique="Pharmacie Palm Beach",
        alias=(
            "pharmacie palm beach", "palm beach", "palmbeach",
            "pharmacie palmbeach",
        ),
        lat=5.259040, lon=-3.984020,
    ),
    # Autres axes DEESP
    LandmarkPAA(
        nom_canonique="TOYOTA CFAO (Treichville)",
        alias=(
            "toyota cfao", "toyota cfao treichville", "toyota",
            "cfao motors", "cfao toyota",
        ),
        lat=5.294070, lon=-4.017190,
    ),
    LandmarkPAA(
        nom_canonique="Agence SODECI (Zone 4)",
        alias=(
            "agence sodeci", "sodeci zone 4", "sodeci",
            "sodeci vridi", "agence sodeci zone 4",
        ),
        lat=5.286370, lon=-3.997900,
    ),
    # Points transverses souvent recherchés
    LandmarkPAA(
        nom_canonique="Pont Houphouët-Boigny",
        alias=(
            "pont houphouet boigny", "pont hb", "pont houphouet",
            "pont felix houphouet boigny",
        ),
        lat=5.311430, lon=-4.019800,
    ),
    LandmarkPAA(
        nom_canonique="AGL Terminal (ex-Bolloré)",
        alias=(
            "agl", "agl terminal", "agl abidjan", "bollore abidjan",
        ),
        lat=5.283460, lon=-4.005610,
    ),
    LandmarkPAA(
        nom_canonique="Outillage Port d'Abidjan",
        alias=(
            "outillage port", "outillage port abidjan",
            "outillage",
        ),
        lat=5.276830, lon=-3.998720,
    ),
]


def rechercher_landmarks(requete: str, limit: int = 5) -> list[dict]:
    """Retourne les landmarks correspondant à la requête.

    Priorité :
      1. Match sur le nom canonique normalisé (préfixe > substring).
      2. Match sur un alias normalisé.
    """
    if not requete or len(requete.strip()) < 2:
        return []

    q_norm = _normaliser(requete)
    scores: list[tuple[float, LandmarkPAA]] = []

    for lm in LANDMARKS_PAA:
        nom_norm = _normaliser(lm.nom_canonique)
        # Score = plus haut = meilleur match.
        score = 0.0
        if nom_norm.startswith(q_norm):
            score = 100.0
        elif q_norm in nom_norm:
            score = 90.0
        else:
            for a in lm.alias:
                a_norm = _normaliser(a)
                if a_norm.startswith(q_norm):
                    score = max(score, 80.0)
                elif q_norm in a_norm:
                    score = max(score, 70.0)
                elif a_norm in q_norm:
                    score = max(score, 60.0)
        if score > 0:
            scores.append((score, lm))

    scores.sort(key=lambda x: (-x[0], x[1].nom_canonique))
    return [
        {
            "nom_affiche": lm.nom_canonique,
            "lat": lm.lat,
            "lon": lm.lon,
            "type": lm.categorie,
            "importance": s / 100.0,
            "source": "landmark_paa",
        }
        for s, lm in scores[:limit]
    ]
