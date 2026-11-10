import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

KNOWN_INSECURE_JWT_SECRET = "veridex_secret_key_phase_95h_jwt_auth_key"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Default values ensure backend can start cleanly even without a .env file.
    """
    PROJECT_NAME: str = "VERIDEX-AI"
    PORT: int = 8000
    DATABASE_URL: Optional[str] = "postgresql+psycopg2://veridex:veridex_pass@localhost:5432/veridex_db"
    FRONTEND_ORIGIN: Optional[str] = None
    LLM_PROVIDER: str = "gemini"  # "gemini" or "mock"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = "gemini-2.5-flash"
    ENVIRONMENT: str = "development"
    JWT_SECRET: Optional[str] = None
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins(self) -> List[str]:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ]
        if self.FRONTEND_ORIGIN:
            for item in self.FRONTEND_ORIGIN.split(","):
                clean = item.strip()
                if clean and clean not in origins:
                    origins.append(clean)
        return origins


settings = Settings()


def validate_jwt_secret_configuration(
    environment: Optional[str] = None,
    secret: Optional[str] = None
) -> None:
    """
    Validates JWT secret configuration against production security rules.
    Fails fast with RuntimeError if running in production and secret is missing or insecure default.
    Never logs, prints, or exposes the actual secret value.
    """
    env = (environment or os.environ.get("ENVIRONMENT") or getattr(settings, "ENVIRONMENT", "development")).strip().lower()
    jwt_sec = secret if secret is not None else (os.environ.get("JWT_SECRET") or getattr(settings, "JWT_SECRET", None))

    if env == "production":
        if not jwt_sec or not str(jwt_sec).strip():
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: JWT_SECRET environment variable is missing. "
                "Production startup aborted. A strong, random signing secret must be configured."
            )
        if str(jwt_sec).strip() == KNOWN_INSECURE_JWT_SECRET:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Known insecure default JWT_SECRET detected. "
                "Production startup aborted. A unique, random signing secret must be configured for production."
            )
