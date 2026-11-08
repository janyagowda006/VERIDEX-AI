from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


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
