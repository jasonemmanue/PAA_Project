"""Chargement de la configuration applicative depuis les variables d'environnement.

Toute la configuration du backend transite par cette classe `Settings`.
Aucune valeur sensible (clé API, mot de passe, secret) n'est codée en dur :
elles proviennent toutes du fichier `backend/.env` ou de l'environnement Docker.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration applicative chargée via pydantic-settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Base de données PostgreSQL ===
    database_url: str = Field(..., alias="DATABASE_URL")

    # === Cache Redis ===
    redis_url: str = Field(..., alias="REDIS_URL")

    # === Moteur de routage interne OSRM ===
    # Optionnel au démarrage : si absent, les endpoints /diag/osrm et complete_troncons
    # ne fonctionneront pas, mais le reste de l'application tourne normalement.
    osrm_base_url: str | None = Field(default=None, alias="OSRM_BASE_URL")

    # === Clé Google Routes (optionnelle : dégradation gracieuse) ===
    # TomTom a été retiré du projet après tests — aucune couverture à Abidjan
    # (cf. CLAUDE.md § 2.5).
    google_routes_api_key: str | None = Field(default=None, alias="GOOGLE_ROUTES_API_KEY")

    # === Paramètres de collecte (APScheduler) ===
    # Méthodologie : 1 mesure par heure pleine, 24h/24.
    # Le rapport DEESP couvre 7h-19h mais notre collecte étend à 24h pour
    # offrir une couverture analytique complète (nuit / aube / pic matinal)
    # tout en restant largement sous le quota Google (144 ≪ 250 req/jour).
    # Voir CLAUDE.md § 4.5.1.
    collect_interval_minutes: int = Field(default=60, alias="COLLECT_INTERVAL_MINUTES")
    collect_start_hour: int = Field(default=0, alias="COLLECT_START_HOUR")
    collect_end_hour: int = Field(default=24, alias="COLLECT_END_HOUR")
    reference_speed_kmh: float = Field(default=50.0, alias="REFERENCE_SPEED_KMH")

    # === Fuseau horaire de référence du PAA ===
    tz: str = Field(default="Africa/Abidjan", alias="TZ")

    # === Seuils d'analyse (phase P3 — indicateurs de congestion FHWA) ===
    # Classification par TTI (Travel Time Index = temps_mesuré / temps_référence)
    #   fluide       : TTI < tti_seuil_dense
    #   dense        : tti_seuil_dense ≤ TTI ≤ tti_seuil_congestionne
    #   congestionné : TTI > tti_seuil_congestionne
    tti_seuil_dense: float = Field(default=1.3, alias="TTI_SEUIL_DENSE")
    tti_seuil_congestionne: float = Field(default=2.0, alias="TTI_SEUIL_CONGESTIONNE")
    # Détection d'une heure de pointe : moyenne(heure) / T_ref > seuil
    tti_seuil_heure_pointe: float = Field(default=1.5, alias="TTI_SEUIL_HEURE_POINTE")
    # Seuil par défaut pour la fréquence de dépassement (en secondes).
    # Si non précisé via query param, le code calcule un seuil = 1,5 × T_ref.
    seuil_depassement_s: int | None = Field(default=None, alias="SEUIL_DEPASSEMENT_S")

    # === Stockage des relevés terrain GPX (P5) ===
    # Dossier local où sont persistés les fichiers GPX importés. Le chemin est
    # créé au démarrage du backend s'il n'existe pas. En production Railway,
    # définir un volume persistant et pointer cette variable dessus.
    gpx_storage_dir: str = Field(default="./data/gpx", alias="GPX_STORAGE_DIR")

    # === Sécurité de l'API ===
    api_secret_key: str = Field(..., alias="API_SECRET_KEY")
    allowed_origins: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")

    @property
    def allowed_origins_list(self) -> list[str]:
        """Convertit la chaîne CSV ALLOWED_ORIGINS en liste exploitable par CORSMiddleware."""
        return [origine.strip() for origine in self.allowed_origins.split(",") if origine.strip()]


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique de la configuration (singleton via lru_cache)."""
    return Settings()
