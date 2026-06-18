"""Clients des sources de mesure : Google Routes (externe) et OSRM (interne).

Conformément à CLAUDE.md § 2.5, l'ordre de dégradation gracieuse à 3 niveaux est :
    google → prédicteur interne (P6) → temps de référence 50 km/h (via OSRM).

TomTom a été retiré du projet après tests (cf. CLAUDE.md § 2.5).

Chaque client expose une fonction asynchrone retournant un dataclass
homogène pour faciliter la consommation par les endpoints /diag/* et le
robot de collecte (P2).
"""
