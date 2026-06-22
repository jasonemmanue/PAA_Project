/**
 * Helpers de formatage (durées, horodatages, vitesses) — utilisés à plusieurs
 * endroits de l'interface.
 */

import type { ClasseCongestion } from "./types";

/** Formate une durée en secondes en `Xmin YYs` (ou `Xh Ymin` au-delà de 1 h). */
export function formaterDuree(secondes: number | null | undefined): string {
  if (secondes === null || secondes === undefined || Number.isNaN(secondes)) {
    return "—";
  }
  const total = Math.round(secondes);
  if (total < 60) return `${total} s`;
  const min = Math.floor(total / 60);
  const sec = total % 60;
  if (min < 60) return sec ? `${min} min ${sec.toString().padStart(2, "0")} s` : `${min} min`;
  const heures = Math.floor(min / 60);
  const restantMin = min % 60;
  return `${heures} h ${restantMin.toString().padStart(2, "0")}`;
}

/** Formate un horodatage ISO en heure locale (Africa/Abidjan = UTC+0). */
export function formaterHeureAbidjan(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const date = new Date(iso);
    return date.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: "Africa/Abidjan",
    });
  } catch {
    return "—";
  }
}

/** Libellé court pour la classe de congestion DEESP (3 classes : fluide /
 *  congestionne / indetermine — cf. rapport DEESP oct. 2025 § METHODOLOGIE). */
export function libelleClasseCongestion(
  c: ClasseCongestion,
  langue: "fr" | "en" = "fr",
): string {
  const labels: Record<"fr" | "en", Record<ClasseCongestion, string>> = {
    fr: {
      fluide: "Fluide",
      congestionne: "Congestionné",
      indetermine: "Indéterminé",
    },
    en: {
      fluide: "Free flow",
      congestionne: "Congested",
      indetermine: "Unknown",
    },
  };
  return labels[langue][c] ?? c;
}

/** Couleur hex associée à une classe de congestion (cohérent avec backend
 *  `app/analyse/congestion.py` — palette DEESP). */
export function couleurClasseCongestion(c: ClasseCongestion): string {
  switch (c) {
    case "fluide":
      return "#2ECC71";
    case "congestionne":
      return "#E74C3C";
    default:
      return "#95A5A6";
  }
}

/** Libellé compact d'une source de mesure pour la légende. */
export function libelleSource(source: string | null | undefined): string {
  switch (source) {
    case "google":
      return "Google Routes";
    case "tomtom":
      return "TomTom";
    case "terrain":
      return "Relevé terrain GPX";
    case "interne":
      return "Prédicteur interne";
    case "historique_paa_2025":
      return "Historique Fév. 2025";
    default:
      return "Référence 50 km/h";
  }
}
