from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Default values ensure backend can start cleanly even without a .env file.
    """
    PROJECT_NAME: str = "VERIDEX-AI"
    PORT: int = 8000
    DATABASE_URL: Optional[str] = "sqlite:///./veridex.db"
    LLM_PROVIDER: str = "gemini"  # "gemini" or "mock"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
