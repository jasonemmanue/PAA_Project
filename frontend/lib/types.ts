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
