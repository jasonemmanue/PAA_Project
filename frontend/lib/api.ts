/**
 * Client API typé pour PAA-Traverse.
 *
 * Lit l'URL de base depuis `NEXT_PUBLIC_API_BASE_URL`. Toutes les fonctions
 * retournent du JSON typé et propagent les erreurs HTTP via une exception
 * `ApiError` dédiée.
 *
 * Utilisable côté serveur (Server Components, Route Handlers) et côté client.
 */

import type {
  CarteEtat,
  CollecteStatus,
  IndicateursTroncon,
  Mesure,
  Troncon,
} from "./types";

export class ApiError extends Error {
  readonly statut: number;
  readonly corps: string;

  constructor(statut: number, corps: string, message?: string) {
    super(message ?? `HTTP ${statut}`);
    this.name = "ApiError";
    this.statut = statut;
    this.corps = corps;
  }
}

function baseUrl(): string {
  const url =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";
  return url.replace(/\/+$/, "");
}

async function appel<T>(
  chemin: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${baseUrl()}${chemin.startsWith("/") ? chemin : `/${chemin}`}`;
  let reponse: Response;
  try {
    reponse = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (cause) {
    throw new ApiError(
      0,
      "",
      `Réseau indisponible — impossible de joindre ${url}`,
    );
  }
  if (!reponse.ok) {
    const corps = await reponse.text().catch(() => "");
    throw new ApiError(reponse.status, corps);
  }
  return (await reponse.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpoints exposés
// ---------------------------------------------------------------------------

export function getHealth(): Promise<{ status: string }> {
  return appel("/health");
}

export function getTroncons(): Promise<Troncon[]> {
  return appel<Troncon[]>("/troncons");
}

export function getTroncon(id: number): Promise<Troncon> {
  return appel<Troncon>(`/troncons/${id}`);
}

export function getMesures(params?: {
  troncon_id?: number;
  limite?: number;
  date_debut?: string;
  date_fin?: string;
}): Promise<Mesure[]> {
  const query = new URLSearchParams();
  if (params?.troncon_id !== undefined)
    query.set("troncon_id", String(params.troncon_id));
  if (params?.limite !== undefined) query.set("limite", String(params.limite));
  if (params?.date_debut) query.set("date_debut", params.date_debut);
  if (params?.date_fin) query.set("date_fin", params.date_fin);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return appel<Mesure[]>(`/mesures${suffix}`);
}

export function getIndicateursTroncon(
  id: number,
  periode: "24h" | "7j" | "30j" = "7j",
): Promise<{ snapshot: IndicateursTroncon }> {
  return appel(`/troncons/${id}/indicateurs?periode=${periode}`);
}

export function getCarteEtat(): Promise<CarteEtat> {
  return appel<CarteEtat>("/carte/etat");
}

export function getCollecteStatus(): Promise<CollecteStatus> {
  return appel<CollecteStatus>("/collecte/status");
}

export const api = {
  baseUrl,
  health: getHealth,
  troncons: getTroncons,
  troncon: getTroncon,
  mesures: getMesures,
  indicateurs: getIndicateursTroncon,
  carteEtat: getCarteEtat,
  collecteStatus: getCollecteStatus,
};
