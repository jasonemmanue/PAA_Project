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

/**
 * Classification couleur DEESP (rapport oct. 2025 § METHODOLOGIE) :
 *   - "fluide"        → vert / orange court : circulation OK
 *   - "congestionne"  → rouge présent OU orange long (≥ 50 % du tronçon)
 *   - "indetermine"   → Google n'a pas qualifié le tracé pour ce cycle
 *
 * Plus de classe "dense" intermédiaire — le rapport ne la distingue pas.
 */
export type ClasseCongestion =
  | "fluide"
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
  /** True = axe officiel DEESP. False = tronçon supplémentaire ajouté via Administration. */
  est_axe?: boolean;
}

/**
 * Mesure publique exposée par l'API.
 *
 * `duree_sans_trafic_s` n'est plus exposé (cf. refonte DEESP : la
 * qualification fluide/congestionné ne dépend plus du ratio
 * trafic/freeflow mais des couleurs Google Maps).
 *
 * Les champs `pourcentage_*` et `est_congestionne` portent le verdict
 * couleur tel que stocké côté backend.
 */
export interface Mesure {
  id: number;
  troncon_id: number;
  horodatage?: string;
  horodatage_local?: string;
  horodatage_utc?: string;
  duree_trafic_s: number | null;
  source: SourceMesure;
  vitesse_moyenne_kmh: number | null;
  aberrante?: boolean;
  pourcentage_rouge: number | null;
  pourcentage_orange: number | null;
  pourcentage_vert: number | null;
  est_congestionne: boolean | null;
}

/** Pourcentages couleur Google Maps embarqués dans la dernière mesure d'un
 *  tronçon, prêts pour l'affichage (popups, panneau latéral). */
export interface CouleurGoogle {
  pourcentage_rouge: number | null;
  pourcentage_orange: number | null;
  pourcentage_vert: number | null;
}

export interface EtatSousTronconCarte {
  id: number;
  code: string;
  nom_court: string;
  ordre: number;
  distance_m?: number;
  distance_km?: number;
  polyline: string | null;
  geometrie?: {
    lat_debut: number | null;
    lon_debut: number | null;
    lat_fin: number | null;
    lon_fin: number | null;
  };
  temps_reference_50kmh_s?: number;
  couleur_etat: string;
  classe_congestion: ClasseCongestion;
  libelle_classe?: string;
  motif_congestion?: string;
  couleur_google?: CouleurGoogle;
  statut?: string;
  derniere_mesure: Mesure | null;
}

export interface EtatTronconCarte {
  id: number;
  nom: string;
  est_axe?: boolean;
  distance_m?: number;
  distance_km?: number;
  polyline: string | null;
  geometrie?: {
    lat_origine: number | null;
    lon_origine: number | null;
    lat_destination: number | null;
    lon_destination: number | null;
  };
  lat_origine?: number | null;
  lon_origine?: number | null;
  lat_destination?: number | null;
  lon_destination?: number | null;
  couleur_etat: string;
  classe_congestion: ClasseCongestion;
  libelle_classe?: string;
  motif_congestion?: string;
  couleur_google?: CouleurGoogle;
  statut?: string;
  derniere_mesure: Mesure | null;
  sous_troncons?: EtatSousTronconCarte[];
}

export interface IncidentCarte {
  id: number;
  lat: number;
  lon: number;
  titre: string;
  type_incident: string | null;
  severite: string | null;
  troncon_id: number | null;
  horodatage_publication: string;
}

export interface CarteEtat {
  horodatage_utc: string;
  fuseau_affichage: string;
  couleurs: Record<ClasseCongestion, string>;
  criteres?: {
    source: string;
    regle_congestion: string;
    seuil_orange_long_pct: number;
  };
  nb_troncons: number;
  troncons: EtatTronconCarte[];
  incidents_actifs?: IncidentCarte[];
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
// Série temporelle (courbe d'évolution journalière) — refonte DEESP
// ---------------------------------------------------------------------------
export interface PointSerie {
  instant_local: string;
  min_s: number | null;
  moyenne_s: number | null;
  max_s: number | null;
  taux_congestion: number | null;
  classe_congestion: ClasseCongestion;
  nb_mesures: number;
}

export interface SerieTemporelle {
  troncon_id: number;
  troncon_nom: string;
  granularite: "hour" | "day";
  temps_reference_50kmh_s: number;
  nb_points: number;
  points: PointSerie[];
}

// ---------------------------------------------------------------------------
// Snapshot d'indicateurs DEESP + détail par jour (KPI cards)
// ---------------------------------------------------------------------------
export interface SnapshotIndicateurs {
  nb_mesures: number;
  nb_mesures_congestionnees: number;
  nb_mesures_fluides: number;
  nb_mesures_couleur_indeterminee: number;
  min_s: number | null;
  moyenne_s: number | null;
  max_s: number | null;
  taux_congestion: number | null;
  classe_congestion: ClasseCongestion;
  pourcentage_rouge_moyen: number | null;
  pourcentage_orange_moyen: number | null;
  pourcentage_vert_moyen: number | null;
  temps_reference_50kmh_s: number;
}

export interface IndicateursPeriode {
  periode: string;
  fenetre_jours: number;
  fuseau: string;
  snapshot: SnapshotIndicateurs;
  evolution_par_jour: Array<{
    date_locale: string;
    min_s: number | null;
    moyenne_s: number | null;
    max_s: number | null;
    taux_congestion: number | null;
    classe_congestion: ClasseCongestion;
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

// ---------------------------------------------------------------------------
// Validation terrain (P5) — releves_terrain, calibration, import GPX
// ---------------------------------------------------------------------------

/** Une ligne issue d'un import GPX, telle que renvoyée par POST /terrain/import. */
export interface ReleveTerrainImport {
  id: number;
  troncon_id: number;
  troncon_nom: string;
  horodatage_passage_utc: string;
  duree_terrain_s: number;
  duree_api_s: number | null;
  ecart_relatif: number | null;
  confiance_matching: number | null;
  distance_trace_m: number;
  distance_officielle_m: number;
}

/** Réponse complète de POST /terrain/import. */
export interface ImportGpxResponse {
  date_session: string;
  fichier_gpx: string;
  nb_points_gpx: number;
  nb_troncons_detectes: number;
  releves: ReleveTerrainImport[];
}

/** Une ligne issue de GET /terrain/releves. */
export interface ReleveTerrainHistorique {
  id: number;
  troncon_id: number;
  date_session: string;
  horodatage_passage_utc: string | null;
  duree_mesuree_s: number | null;
  duree_api_s: number | null;
  ecart_relatif: number | null;
  confiance_matching: number | null;
  /** Nom court du fichier GPX (sans chemin) — utilisé pour le téléchargement. */
  nom_fichier_gpx: string | null;
}

export interface ReleveTerrainResponse {
  nb_lignes: number;
  lignes: ReleveTerrainHistorique[];
}

/** Facteur de calibration par tronçon (GET /terrain/calibration). */
export interface CalibrationTroncon {
  troncon_id: number;
  troncon_nom: string;
  nb_releves: number;
  ecart_moyen: number | null;
  ecart_courant: number | null;
}

export interface CalibrationResponse {
  fenetre_relevees: number;
  troncons: CalibrationTroncon[];
}

// ---------------------------------------------------------------------------
// Rapport DEESP — endpoints /rapport/*
// ---------------------------------------------------------------------------

export interface TempsTheorique {
  axe: string;
  distance_km: number;
  temps_50kmh_s: number;
  temps_50kmh: string; // ex. "17 mn 53 s"
}

export interface RapportTempsTheoriques {
  tableau: string;
  lignes: TempsTheorique[];
}

export interface LigneTempsTraversee {
  troncon_id: number;
  troncon_nom: string;
  type_jour: "jour_ouvrable" | "week_end";
  nb_mesures: number;
  temps_min_mn: number | null;
  temps_moyen_mn: number | null;
  temps_max_mn: number | null;
}

export interface RapportTempsTraversee {
  campagne: string;
  debut_utc: string;
  fin_utc: string;
  nb_lignes: number;
  lignes: LigneTempsTraversee[];
}

export interface EntreeCongestion {
  troncon_id: number;
  troncon_nom: string;
  sous_troncon_id: number | null;
  sous_troncon_code: string | null;
  sous_troncon_nom: string | null;
  heure: number;
  tranche: string;
  nb_par_jour_semaine: Record<string, number>;
  nb_total_semaine: number;
  regle_jour_indicatif: boolean;
  regle_semaine: boolean;
}

export interface RapportZonesCongestionnees {
  campagne: string;
  nb_jours_plage: number;
  nb_entrees: number;
  regles: {
    seuil_jour_effectif: number;
    seuil_semaine_effectif: number;
    regle_jour_indicatif: string;
    regle_semaine: string;
    adaptatif: boolean;
  };
  entrees: EntreeCongestion[];
}

export interface PointGraphiqueDEESP {
  date: string;
  libelle_jour: string;
  temps_mn: number;
}

export interface RapportGraphique {
  troncon_id: number;
  campagne: string;
  agregat: "min" | "max";
  axe_y_unite: string;
  nb_points: number;
  points: PointGraphiqueDEESP[];
}

// ---------------------------------------------------------------------------
// Prédicteur (P6.2)
// ---------------------------------------------------------------------------

export type SourcePrediction =
  | "google_routes"
  | "mesures_jour_type_7j"
  | "vitesse_ref_50kmh";

export interface StatsPeriode {
  min_mn: number;
  moyen_mn: number;
  max_mn: number;
  nb_mesures: number;
}

export interface ResumePrediction {
  troncon_id: number;
  troncon_nom: string;
  courante: {
    instant_local: string;
    type_jour: "jour_ouvrable" | "week_end";
    prediction: { min_mn: number | null; moyen_mn: number | null; max_mn: number | null };
    bornes_7j: { min_mn: number | null; moyen_mn: number | null; max_mn: number | null } | null;
    source: SourcePrediction;
    confiance: number;
    calibration_appliquee: number;
    avertissement: string | null;
  };
  semaine: {
    debut: string;
    fin: string;
    nb_mesures_total: number;
    jours_ouvrables: StatsPeriode | null;
    week_ends: StatsPeriode | null;
  };
  mois: {
    debut: string;
    fin: string;
    nb_mesures_total: number;
    jours_ouvrables: StatsPeriode | null;
    week_ends: StatsPeriode | null;
  };
}

// ---------------------------------------------------------------------------
// Heure optimale de départ (P6.3 rétabli)
// ---------------------------------------------------------------------------

export interface CreneauHoraire {
  heure: number;
  tranche: string;
  moyen_s: number;
  min_s: number;
  max_s: number;
  moyen_mn: number;
  min_mn: number;
  max_mn: number;
  nb_mesures: number;
  optimal: boolean;
}

export interface HeureOptimaleResponse {
  troncon_id: number;
  troncon_nom: string;
  type_jour: string;
  source: string;
  nb_creneaux: number;
  creneaux: CreneauHoraire[];
  temps_ref_50kmh_s: number | null;
  temps_ref_50kmh_mn: number | null;
  recommandation: CreneauHoraire[];
}

// ---------------------------------------------------------------------------
// Administration (P6.4) — CRUD tronçons + sous-tronçons codifiés
// ---------------------------------------------------------------------------

export interface TronconAdmin {
  id: number;
  nom: string;
  lat_origine: number | null;
  lon_origine: number | null;
  lat_destination: number | null;
  lon_destination: number | null;
  polyline: string | null;
  distance_m: number;
  distance_km: number;
  vitesse_ref_kmh: number;
  couleur: string;
  actif: boolean;
  /** True = axe officiel DEESP, False = tronçon supplémentaire (migration 0013). */
  est_axe?: boolean;
  /**
   * Résumé d'adoption renvoyé uniquement par POST /administration/troncons —
   * indique combien de tronçons sont surveillés après la création et si le
   * quota Google est encore tenable.
   */
  adoption_collecte?: AdoptionCollecte;
}

export interface AdoptionCollecte {
  nb_troncons_actifs: number;
  google_requetes_par_jour: number;
  plafond_google: number;
  scheduler_redemarrage_requis: boolean;
  inclusion_prochain_cycle: boolean;
  avertissement_quota: string | null;
}

export interface SousTroncon {
  id: number;
  troncon_id: number;
  code: string;
  nom_court: string;
  ordre: number;
  lat_debut: number;
  lon_debut: number;
  lat_fin: number;
  lon_fin: number;
  polyline: string | null;
  distance_m: number;
  actif: boolean;
}

export interface SousTronconsResponse {
  troncon_id: number;
  troncon_nom: string;
  nb_sous_troncons: number;
  sous_troncons: SousTroncon[];
}

export interface TronconCreer {
  nom: string;
  lat_origine: number;
  lon_origine: number;
  lat_destination: number;
  lon_destination: number;
  waypoints?: [number, number][];
  distance_m?: number;
  vitesse_ref_kmh?: number;
  couleur?: string;
  /** True = nouvel axe officiel, False (défaut) = tronçon supplémentaire. */
  est_axe?: boolean;
}

export interface SousTronconCreer {
  code: string;
  nom_court: string;
  lat_debut: number;
  lon_debut: number;
  lat_fin: number;
  lon_fin: number;
  ordre?: number;
}

// ---------------------------------------------------------------------------
// Segments terrain — accumulation progressive GPX libres (P6.9 / § 4.9)
// ---------------------------------------------------------------------------

/** Segment terrain importé (réponse de POST /terrain/segments/import). */
export interface SegmentImporte {
  id: number;
  nom_segment: string;
  troncon_id: number | null;
  direction: string | null;
  lat_debut: number;
  lon_debut: number;
  lat_fin: number;
  lon_fin: number;
  duree_s: number;
  duree_mn: number;
  distance_m: number | null;
  horodatage_debut: string;
  horodatage_fin: string;
  date_session: string;
  session_id: string | null;
}

/** Une session = somme de segments du même groupe (date_session, session_id). */
export interface EstimationSession {
  date_session: string;
  session_id: string | null;
  nb_segments: number;
  duree_totale_s: number;
  duree_totale_mn: number;
  distance_couverte_m: number;
  couverture_pct: number;
  source: "segments_directs" | "miroir_aller_retour";
}

/** Résumé consolidé par tronçon (GET /terrain/segments/resume/{id}). */
export interface ResumeSegments {
  troncon_id: number;
  troncon_nom: string;
  distance_m: number;
  nb_sessions: number;
  temps_moyen_s: number | null;
  temps_moyen_mn: number | null;
  temps_min_s: number | null;
  temps_max_s: number | null;
  couverture_moyenne_pct: number;
  confiance: number;
  sessions: EstimationSession[];
}

// ---------------------------------------------------------------------------
// Incidents de circulation — P8
// ---------------------------------------------------------------------------

export type TypeIncident =
  | "accident"
  | "embouteillage"
  | "route_barree"
  | "travaux"
  | "autre";

export type SeveriteIncident =
  | "mineur"
  | "moyen"
  | "grave"
  | "inconnu";

export interface Incident {
  id: number;
  titre: string;
  resume: string | null;
  source_url: string;
  source_nom: string;
  horodatage_publication: string; // ISO 8601 UTC
  horodatage_collecte: string;
  lat: number | null;
  lon: number | null;
  lieu_extrait: string | null;
  troncon_id: number | null;
  type_incident: TypeIncident | null;
  severite: SeveriteIncident | null;
  actif: boolean;
  verifie: boolean;
}

export interface IncidentsPage {
  total: number;
  items: Incident[];
}

export interface StatsIncidents {
  nb_total: number;
  nb_actifs: number;
  nb_par_type: Record<string, number>;
  nb_par_source: Record<string, number>;
  derniere_collecte: string | null;
}
