/**
 * Modèles métier typés — mirroir des schémas Pydantic exposés par
 * l'API FastAPI (cf. backend/app/api/*).
 *
 * Convention : tous les noms suivent le vocabulaire du cahier des charges
 * et restent en français (« troncon », « duree_trafic_s », etc.).
 */

export type SourceMesure =
  | "google"
  | "tomtom"
  | "terrain"
  | "interne"
  | "historique_paa_2025";

export type ClasseCongestion =
  | "fluide"
  | "dense"
  | "congestionne"
  | "indetermine";

export interface Troncon {
  id: number;
  nom: string;
  lat_origine: number | null;
  lon_origine: number | null;
  lat_destination: number | null;
  lon_destination: number | null;
  polyline: string | null;
  distance_m: number;
  vitesse_ref_kmh: number;
  couleur: string;
  actif: boolean;
}

export interface Mesure {
  id: number;
  troncon_id: number;
  horodatage: string;
  duree_trafic_s: number | null;
  duree_sans_trafic_s: number;
  source: SourceMesure;
  vitesse_moyenne_kmh: number | null;
  aberrante?: boolean;
}

export interface IndicateursTroncon {
  tti: number | null;
  pti: number | null;
  bti: number | null;
  classe_congestion: ClasseCongestion;
  temps_reference_s: number;
  source_temps_reference: string;
  nb_mesures: number;
}

export interface EtatTronconCarte {
  id: number;
  nom: string;
  polyline: string | null;
  lat_origine: number;
  lon_origine: number;
  lat_destination: number;
  lon_destination: number;
  couleur_etat: string;
  classe_congestion: ClasseCongestion;
  tti: number | null;
  derniere_mesure: Mesure | null;
}

export interface CarteEtat {
  horodatage_utc: string;
  fuseau_affichage: string;
  seuils: {
    tti_dense: number;
    tti_congestionne: number;
  };
  couleurs: Record<ClasseCongestion, string>;
  nb_troncons: number;
  troncons: EtatTronconCarte[];
}

export interface CollecteStatus {
  actif: boolean;
  prochaine_execution: string | null;
  prochaine_agregation: string | null;
  fuseau: string;
  config: {
    intervalle_min: number;
    plage_horaire: string;
    estimation_requetes_google_par_jour: number;
    plafond_google_par_jour: number;
  };
  compteurs_jour: {
    nb_mesures_total: number;
    nb_succes: number;
    nb_trous: number;
    nb_troncons_actifs: number;
  };
}

// ---------------------------------------------------------------------------
// Profil horaire (24 points par jour de la semaine)
// ---------------------------------------------------------------------------
export type JourSemaine =
  | "lundi"
  | "mardi"
  | "mercredi"
  | "jeudi"
  | "vendredi"
  | "samedi"
  | "dimanche";

export interface PointProfilHoraire {
  heure: number;
  moyenne_s: number | null;
  mediane_s: number | null;
  min_s: number | null;
  max_s: number | null;
  p95_s: number | null;
  nb_mesures: number;
}

export interface ProfilHoraire {
  troncon: {
    id: number;
    nom: string;
    distance_m: number;
    vitesse_ref_kmh: number;
    temps_reference_s: number;
  };
  jour: JourSemaine;
  jour_index: number;
  fenetre_jours: number;
  points: PointProfilHoraire[];
}

// ---------------------------------------------------------------------------
// Série temporelle (courbe d'évolution journalière)
// ---------------------------------------------------------------------------
export interface PointSerie {
  instant_local: string;
  moyenne_s: number | null;
  p95_s: number | null;
  tti: number | null;
  classe_congestion: ClasseCongestion;
  nb_mesures: number;
}

export interface SerieTemporelle {
  troncon_id: number;
  troncon_nom: string;
  granularite: "hour" | "day";
  temps_reference_s: number;
  nb_points: number;
  points: PointSerie[];
}

// ---------------------------------------------------------------------------
// Snapshot d'indicateurs + détail par jour (pour les KPI cards)
// ---------------------------------------------------------------------------
export interface SnapshotIndicateurs {
  nb_mesures: number;
  moyenne_s: number | null;
  mediane_s: number | null;
  min_s: number | null;
  max_s: number | null;
  p95_s: number | null;
  tti: number | null;
  pti: number | null;
  bti: number | null;
  classe_congestion: ClasseCongestion;
  temps_reference_s: number;
  source_temps_reference: string;
  frequence_depassement: number | null;
}

export interface IndicateursPeriode {
  periode: string;
  fenetre_jours: number;
  fuseau: string;
  snapshot: SnapshotIndicateurs;
  evolution_par_jour: Array<{
    date_locale: string;
    moyenne_s: number | null;
    p95_s: number | null;
    tti: number | null;
    nb_mesures: number;
  }>;
}

// ---------------------------------------------------------------------------
// Evolution pluriannuelle (table evolution_indicateur)
// ---------------------------------------------------------------------------
export interface LigneEvolution {
  id: number;
  axe: string;
  sens: string;
  periode: string;
  type_jour: string;
  temps_min_s: number | null;
  temps_moyen_s: number | null;
  temps_max_s: number | null;
}

export interface EvolutionResponse {
  nb_lignes: number;
  lignes: LigneEvolution[];
}
