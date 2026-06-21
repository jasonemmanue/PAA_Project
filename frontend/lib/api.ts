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
  CalibrationResponse,
  CarteEtat,
  CollecteStatus,
  EvolutionResponse,
  ImportGpxResponse,
  IndicateursPeriode,
  JourSemaine,
  Mesure,
  HeureOptimaleResponse,
  PredictionResponse,
  ProfilHoraire,
  QualiteResponse,
  SousTroncon,
  SousTronconCreer,
  SousTronconsResponse,
  TronconAdmin,
  TronconCreer,
  RapportGraphique,
  RapportTempsTheoriques,
  RapportTempsTraversee,
  RapportZonesCongestionnees,
  ReleveTerrainResponse,
  SerieTemporelle,
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

// Le backend expose `/troncons` sous deux formes possibles selon la version :
//   - tableau direct  : Troncon[]
//   - wrapper enrichi : { troncons: Troncon[], horodatage_utc, seuils, ... }
// On accepte les deux pour rester robuste.
export async function getTroncons(): Promise<Troncon[]> {
  const res = await appel<unknown>("/troncons");
  if (Array.isArray(res)) return res as Troncon[];
  if (
    res &&
    typeof res === "object" &&
    Array.isArray((res as { troncons?: unknown }).troncons)
  ) {
    return (res as { troncons: Troncon[] }).troncons;
  }
  return [];
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
  periode: "24h" | "7j" | "30j" | "90j" = "7j",
): Promise<IndicateursPeriode> {
  // Le backend attend un format `Nj` (1j, 7j, 30j, 90j). L'UI garde l'étiquette
  // « 24 h » pour la lisibilité — on traduit ici en `1j`.
  const periodeApi = periode === "24h" ? "1j" : periode;
  return appel<IndicateursPeriode>(
    `/troncons/${id}/indicateurs?periode=${periodeApi}`,
  );
}

export function getCarteEtat(): Promise<CarteEtat> {
  return appel<CarteEtat>("/carte/etat");
}

export function getCollecteStatus(): Promise<CollecteStatus> {
  return appel<CollecteStatus>("/collecte/status");
}

export function postCollecteStart(): Promise<CollecteStatus> {
  return appel<CollecteStatus>("/collecte/start", { method: "POST" });
}

export function postCollecteStop(): Promise<CollecteStatus> {
  return appel<CollecteStatus>("/collecte/stop", { method: "POST" });
}

// --- Profils horaires (24 points / jour-semaine)
export function getProfilHoraire(
  id: number,
  jour: JourSemaine,
  fenetre_jours: 30 | 60 | 90 = 30,
): Promise<ProfilHoraire> {
  return appel<ProfilHoraire>(
    `/profils/troncons/${id}?jour=${jour}&fenetre_jours=${fenetre_jours}`,
  );
}

// --- Série temporelle (courbe d'évolution)
export function getSerieTemporelle(
  id: number,
  params?: {
    debut?: string; // YYYY-MM-DD
    fin?: string;
    granularite?: "hour" | "day";
    inclure_aberrantes?: boolean;
  },
): Promise<SerieTemporelle> {
  const query = new URLSearchParams();
  if (params?.debut) query.set("debut", params.debut);
  if (params?.fin) query.set("fin", params.fin);
  if (params?.granularite) query.set("granularite", params.granularite);
  if (params?.inclure_aberrantes !== undefined) {
    query.set("inclure_aberrantes", String(params.inclure_aberrantes));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return appel<SerieTemporelle>(
    `/indicateurs/troncons/${id}/serie${suffix}`,
  );
}

// --- Evolution pluriannuelle (table evolution_indicateur, P6.1)
// L'endpoint GET /evolution peut ne pas encore être exposé côté backend ;
// dans ce cas on retourne silencieusement un résultat vide pour que le
// composant affiche un message neutre plutôt que de crasher la page.
export async function getEvolution(params?: {
  axe?: string;
  sens?: string;
  type_jour?: string;
}): Promise<EvolutionResponse> {
  const query = new URLSearchParams();
  if (params?.axe) query.set("axe", params.axe);
  if (params?.sens) query.set("sens", params.sens);
  if (params?.type_jour) query.set("type_jour", params.type_jour);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  try {
    const res = await appel<EvolutionResponse>(`/evolution${suffix}`);
    return {
      nb_lignes: res?.nb_lignes ?? 0,
      lignes: Array.isArray(res?.lignes) ? res.lignes : [],
    };
  } catch (e) {
    if (e instanceof ApiError && e.statut === 404) {
      return { nb_lignes: 0, lignes: [] };
    }
    throw e;
  }
}

// --- URLs d'export (renvoyées telles quelles, pour <a href> direct)
export function urlExportMesures(params: {
  troncon_id?: number;
  debut?: string;
  fin?: string;
  format: "csv" | "xlsx";
}): string {
  const query = new URLSearchParams({ format: params.format });
  if (params.troncon_id !== undefined)
    query.set("troncon_id", String(params.troncon_id));
  if (params.debut) query.set("debut", params.debut);
  if (params.fin) query.set("fin", params.fin);
  return `${baseUrl()}/export/mesures?${query.toString()}`;
}

export function urlExportProfils(format: "xlsx" = "xlsx"): string {
  return `${baseUrl()}/export/profils?format=${format}`;
}

// ---------------------------------------------------------------------------
// Validation terrain (P5) — POST /terrain/import + lecture des relevés
// ---------------------------------------------------------------------------

export async function postTerrainImport(
  fichier: File,
  dateSession?: string,
): Promise<ImportGpxResponse> {
  const formData = new FormData();
  formData.append("fichier", fichier);
  if (dateSession) formData.append("date_session", dateSession);

  const url = `${baseUrl()}/terrain/import`;
  let reponse: Response;
  try {
    reponse = await fetch(url, { method: "POST", body: formData });
  } catch (cause) {
    throw new ApiError(0, "", `Réseau indisponible — impossible de joindre ${url}`);
  }
  if (!reponse.ok) {
    const corps = await reponse.text().catch(() => "");
    // FastAPI renvoie typiquement `{"detail": "message"}` — on l'extrait pour
    // l'afficher tel quel à l'utilisateur, sinon on retombe sur "HTTP <code>".
    let message = `HTTP ${reponse.status}`;
    try {
      const json = JSON.parse(corps);
      if (typeof json?.detail === "string") {
        message = `HTTP ${reponse.status} — ${json.detail}`;
      } else if (Array.isArray(json?.detail)) {
        message = `HTTP ${reponse.status} — ${json.detail
          .map((d: { msg?: string }) => d?.msg ?? JSON.stringify(d))
          .join(" ; ")}`;
      }
    } catch {
      // corps non-JSON — on garde "HTTP <code>"
    }
    throw new ApiError(reponse.status, corps, message);
  }
  return (await reponse.json()) as ImportGpxResponse;
}

export function getTerrainReleves(params?: {
  troncon_id?: number;
  limite?: number;
}): Promise<ReleveTerrainResponse> {
  const query = new URLSearchParams();
  if (params?.troncon_id !== undefined)
    query.set("troncon_id", String(params.troncon_id));
  if (params?.limite !== undefined) query.set("limite", String(params.limite));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return appel<ReleveTerrainResponse>(`/terrain/releves${suffix}`);
}

export function getTerrainCalibration(fenetre = 4): Promise<CalibrationResponse> {
  return appel<CalibrationResponse>(`/terrain/calibration?fenetre=${fenetre}`);
}

/**
 * Télécharge le fichier GPX brut d'un relevé (le contenu, pas une URL).
 * Retourne un File pour pouvoir le reparser côté client comme un upload.
 */
export async function getTerrainGpx(releveId: number): Promise<File> {
  const url = `${baseUrl()}/terrain/releves/${releveId}/gpx`;
  const reponse = await fetch(url);
  if (!reponse.ok) {
    const corps = await reponse.text().catch(() => "");
    throw new ApiError(reponse.status, corps);
  }
  const blob = await reponse.blob();
  // On fabrique un File à partir du Blob — préserve le content-type GPX.
  return new File([blob], `releve_${releveId}.gpx`, {
    type: "application/gpx+xml",
  });
}

// ---------------------------------------------------------------------------
// Rapport DEESP — endpoints /rapport/*
// ---------------------------------------------------------------------------

export function getRapportTempsTheoriques(): Promise<RapportTempsTheoriques> {
  return appel<RapportTempsTheoriques>("/rapport/temps-theoriques");
}

export function getRapportTempsTraversee(
  campagne: string,
): Promise<RapportTempsTraversee> {
  return appel<RapportTempsTraversee>(
    `/rapport/temps-traversee?campagne=${encodeURIComponent(campagne)}`,
  );
}

export function getRapportZonesCongestionnees(
  campagne: string,
): Promise<RapportZonesCongestionnees> {
  return appel<RapportZonesCongestionnees>(
    `/rapport/zones-congestionnees?campagne=${encodeURIComponent(campagne)}`,
  );
}

export function getRapportGraphique(
  tronconId: number,
  campagne: string,
  agregat: "min" | "max",
): Promise<RapportGraphique> {
  return appel<RapportGraphique>(
    `/rapport/graphique/${tronconId}?campagne=${encodeURIComponent(campagne)}&agregat=${agregat}`,
  );
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
  collecteStart: postCollecteStart,
  collecteStop: postCollecteStop,
  profilHoraire: getProfilHoraire,
  serieTemporelle: getSerieTemporelle,
  evolution: getEvolution,
  terrainImport: postTerrainImport,
  terrainReleves: getTerrainReleves,
  terrainCalibration: getTerrainCalibration,
  terrainGpx: getTerrainGpx,
  rapportTempsTheoriques: getRapportTempsTheoriques,
  rapportTempsTraversee: getRapportTempsTraversee,
  rapportZonesCongestionnees: getRapportZonesCongestionnees,
  rapportGraphique: getRapportGraphique,
  predire: getPredire,
  qualitePrediction: getQualitePrediction,
  heureOptimale: getHeureOptimale,
  creerTroncon: postCreerTroncon,
  supprimerTroncon: deleteTroncon,
  sousTroncons: getSousTroncons,
  creerSousTroncon: postCreerSousTroncon,
  supprimerSousTroncon: deleteSousTroncon,
  urlExportMesures,
  urlExportProfils,
};

// ---------------------------------------------------------------------------
// Prédicteur (P6.2)
// ---------------------------------------------------------------------------

export function getPredire(
  tronconId: number,
  dateCible?: string,
  heure?: number,
): Promise<PredictionResponse> {
  const params = new URLSearchParams({ troncon_id: String(tronconId) });
  if (dateCible) params.set("date", dateCible);
  if (heure !== undefined) params.set("heure", String(heure));
  return appel<PredictionResponse>(`/predire?${params.toString()}`);
}

export function getQualitePrediction(fenetreJours = 7): Promise<QualiteResponse> {
  return appel<QualiteResponse>(
    `/predire/qualite?fenetre_jours=${fenetreJours}`,
  );
}

export function getHeureOptimale(
  depart: string,
  dateCible?: string,
  tronconId?: number,
): Promise<HeureOptimaleResponse> {
  const params = new URLSearchParams({ depart });
  if (dateCible) params.set("date", dateCible);
  if (tronconId !== undefined) params.set("troncon_id", String(tronconId));
  return appel<HeureOptimaleResponse>(`/heure-optimale?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Administration (P6.4)
// ---------------------------------------------------------------------------

export function postCreerTroncon(payload: TronconCreer): Promise<TronconAdmin> {
  return appel<TronconAdmin>("/administration/troncons", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteTroncon(id: number): Promise<unknown> {
  return appel<unknown>(`/administration/troncons/${id}`, { method: "DELETE" });
}

export function getSousTroncons(tronconId: number): Promise<SousTronconsResponse> {
  return appel<SousTronconsResponse>(
    `/administration/troncons/${tronconId}/sous-troncons`,
  );
}

export function postCreerSousTroncon(
  tronconId: number,
  payload: SousTronconCreer,
): Promise<SousTroncon> {
  return appel<SousTroncon>(
    `/administration/troncons/${tronconId}/sous-troncons`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function deleteSousTroncon(id: number): Promise<unknown> {
  return appel<unknown>(`/administration/sous-troncons/${id}`, {
    method: "DELETE",
  });
}
