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
    osrm_base_url: str = Field(..., alias="OSRM_BASE_URL")

    # === Clés des sources externes (optionnelles : dégradation gracieuse) ===
    google_routes_api_key: str | None = Field(default=None, alias="GOOGLE_ROUTES_API_KEY")
    tomtom_api_key: str | None = Field(default=None, alias="TOMTOM_API_KEY")

    # === Paramètres de collecte (APScheduler) ===
    collect_interval_minutes: int = Field(default=15, alias="COLLECT_INTERVAL_MINUTES")
    collect_start_hour: int = Field(default=7, alias="COLLECT_START_HOUR")
    collect_end_hour: int = Field(default=19, alias="COLLECT_END_HOUR")
    reference_speed_kmh: float = Field(default=50.0, alias="REFERENCE_SPEED_KMH")

    # === Fuseau horaire de référence du PAA ===
    tz: str = Field(default="Africa/Abidjan", alias="TZ")

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
