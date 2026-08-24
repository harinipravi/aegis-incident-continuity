import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App config
    PROJECT_NAME: str = "aegis-incident-continuity"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # BigQuery config
    GOOGLE_CLOUD_PROJECT: str = "aegis-incident-continuity"
    BIGQUERY_DATASET: str = "aegis_ops"
    
    # Gemini config
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"
    
    # Database config
    DATABASE_URL: str = "sqlite:///./aegis.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
