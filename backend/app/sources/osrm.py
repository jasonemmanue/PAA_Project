"""Client du moteur de routage interne OSRM (auto-hébergé, profil voiture).

OSRM est utilisé pour deux usages distincts :
  1. **Calcul de la polyline de référence** d'un tronçon (endpoint /route).
  2. **Map-matching** d'une trace GPX terrain sur le réseau routier
     (endpoint /match — utilisé en P5 pour les relevés terrain).

OSRM ne fournit pas d'info trafic — il sert de **repli déterministe** et de
**source de polyline officielle** dans le projet FLUIDIS.
"""

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.sources.coordonnees import PointGPS


@dataclass
class ReponseOSRMRoute:
    """Résultat d'un appel /route — distance et tracé entre deux points."""
    distance_m: int
    duree_sans_trafic_s: int
    polyline_encodee: str


@dataclass
class ReponseOSRMMatch:
    """Résultat d'un appel /match — trace GPX recalée sur le réseau routier."""
    confiance_moyenne: float
    distance_m: int
    duree_s: int
    polyline_encodee: str | None


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _base_url() -> str:
    """URL de base d'OSRM (lue à chaque appel — facilite les tests)."""
    url = get_settings().osrm_base_url
    if not url:
        raise RuntimeError("OSRM_BASE_URL non configurée — service OSRM indisponible.")
    return url.rstrip("/")


def _coords_str(points: list[PointGPS]) -> str:
    """Sérialise une liste de points au format OSRM `lon,lat;lon,lat;...`.

    ⚠️ OSRM attend l'ordre **longitude,latitude** — l'inverse de la convention
    courante. Erreur classique à ne pas commettre.
    """
    return ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in points)


# ---------------------------------------------------------------------------
# Appels publics
# ---------------------------------------------------------------------------


async def route(
    origine: PointGPS,
    destination: PointGPS,
    *,
    timeout_s: float = 10.0,
) -> ReponseOSRMRoute:
    """Calcule l'itinéraire voiture entre deux points via OSRM.

    Retourne distance, durée fluide théorique et polyline encodée (precision 5).
    """
    url = f"{_base_url()}/route/v1/driving/{_coords_str([origine, destination])}"
    parametres = {
        "overview": "full",          # polyline complète (pas simplifiée)
        "geometries": "polyline",    # encodage Google polyline precision 5
        "steps": "false",            # pas besoin des instructions de navigation
        "alternatives": "false",
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        reponse = await client.get(url, params=parametres)
        reponse.raise_for_status()
        donnees = reponse.json()

    if donnees.get("code") != "Ok" or not donnees.get("routes"):
        raise RuntimeError(
            f"OSRM /route a échoué — code={donnees.get('code')!r}, "
            f"message={donnees.get('message')!r}"
        )

    premiere_route = donnees["routes"][0]
    return ReponseOSRMRoute(
        distance_m=int(round(premiere_route["distance"])),
        duree_sans_trafic_s=int(round(premiere_route["duration"])),
        polyline_encodee=premiere_route["geometry"],
    )


async def match(
    trace: list[PointGPS],
    *,
    timestamps: list[int] | None = None,
    timeout_s: float = 15.0,
) -> ReponseOSRMMatch:
    """Recale une trace GPS sur le réseau routier OSRM (utilisé en P5).

    Args:
        trace: liste de points GPS bruts (issus d'un fichier GPX terrain).
        timestamps: timestamps Unix associés à chaque point — facultatif mais
            recommandé pour améliorer la confiance du matching.

    Returns:
        ReponseOSRMMatch avec la confiance moyenne (0–1), la distance totale,
        la durée et la polyline recalée (None si OSRM n'a trouvé aucun matching).
    """
    if len(trace) < 2:
        raise ValueError("Le map-matching nécessite au moins 2 points GPS.")

    url = f"{_base_url()}/match/v1/driving/{_coords_str(trace)}"
    parametres = {
        "overview": "full",
        "geometries": "polyline",
        "steps": "false",
    }
    if timestamps is not None:
        if len(timestamps) != len(trace):
            raise ValueError("Le nombre de timestamps doit égaler le nombre de points.")
        parametres["timestamps"] = ";".join(str(t) for t in timestamps)

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        reponse = await client.get(url, params=parametres)
        reponse.raise_for_status()
        donnees = reponse.json()

    if donnees.get("code") != "Ok" or not donnees.get("matchings"):
        return ReponseOSRMMatch(
            confiance_moyenne=0.0,
            distance_m=0,
            duree_s=0,
            polyline_encodee=None,
        )

    matchings = donnees["matchings"]
    confiance_moyenne = sum(m.get("confidence", 0.0) for m in matchings) / len(matchings)
    distance_totale = sum(m["distance"] for m in matchings)
    duree_totale = sum(m["duration"] for m in matchings)
    # On concatène les polylines des sous-matchings dans l'ordre.
    polyline = matchings[0]["geometry"] if len(matchings) == 1 else None

    return ReponseOSRMMatch(
        confiance_moyenne=confiance_moyenne,
        distance_m=int(round(distance_totale)),
        duree_s=int(round(duree_totale)),
        polyline_encodee=polyline,
    )
