from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file with pydantic-settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./data/librislog.db"
    google_books_api_key: str = ""
    cors_origins: List[str] = ["http://localhost", "http://localhost:5173", "http://localhost:4173"]
    log_level: str = "INFO"
    covers_dir: str = "./data/covers"
    api_key_encryption_key: str
    auth_cookie_name: str = "librislog_session"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: str = ""
    oidc_enabled: bool = False
    oidc_provider_id: str = "oidc"
    oidc_provider_name: str = "Single Sign-On"
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_well_known_url: str = ""
    oidc_scope: str = "openid email profile"
    dashboard_quote_enabled: bool = True
    dashboard_quote_url: str = (
        "https://motivational-spark-api.vercel.app/api/quotes/random"
    )
    dashboard_quote_cache_ttl: int = 86400
    max_import_file_size_mb: int = 100
    max_import_row_count: int = 10000
    import_temp_dir: str = "./data/import_temp"
    backup_temp_dir: str = "./data/backup_temp"
    data_dir: str = "./data"
    cover_candidate_timeout_seconds: int = 5
    cover_candidate_min_size_bytes: int = 1000
    cover_import_timeout_seconds: int = 15
    hardcover_app_api_token: str = ""
    thalia_cover_search_enabled: bool = False
    embed_enabled: bool = True
    forwarded_allow_ips: str = "*"

    @field_validator("api_key_encryption_key")
    @classmethod
    def validate_api_key_encryption_key(cls, value: str) -> str:
        """Ensure the API key encryption key is set and not the default placeholder."""
        if not value.strip():
            raise ValueError("API_KEY_ENCRYPTION_KEY must be set")
        if value == "CHANGE_ME_TO_32PLUS_CHARS":
            raise ValueError("API_KEY_ENCRYPTION_KEY must be set to a real secret")
        return value


settings: Settings = Settings()
