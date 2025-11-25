# backend/core/config.py
"""
Configuration module for the FastAPI application.
Loads environment variables and defines application settings.
"""

import os
from functools import lru_cache
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)


class Settings:
    """Application settings loaded from environment variables."""

    # Project paths
    PROJECT_ROOT: str = str(project_root)
    OCR_CACHE_DIR: str = os.path.join(str(project_root), "backend", "ocr_cache")
    PROCESSING_LOGS_DIR: str = os.path.join(str(project_root), "backend", "processing_logs")

    # Database Configuration
    DB_NAME: str = os.getenv("DB_NAME", "postgres")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")

    # Qdrant Configuration
    QDRANT_URL: str = os.getenv('QDRANT_URL', '')
    QDRANT_API_KEY: str = os.getenv('QDRANT_API_KEY', '')
    QDRANT_COLLECTION: str = os.getenv('QDRANT_COLLECTION', 'BadResult')

    # Deka AI Configuration
    DEKA_BASE_URL: str = os.getenv("DEKA_BASE_URL", "")
    DEKA_KEY: str = os.getenv("DEKA_KEY", "")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "baai/bge-multilingual-gemma2")

    # API Keys
    N8N_API_KEY: str = os.getenv("API_BEARER_TOKEN", "")

    # Processing settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "64"))

    # OCR Model
    OCR_MODEL: str = "meta/llama-4-maverick-instruct"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_deka_client():
    """Initialize and return the Deka AI client."""
    settings = get_settings()

    if not settings.DEKA_BASE_URL or not settings.DEKA_KEY:
        return None

    try:
        from openai import OpenAI
        return OpenAI(api_key=settings.DEKA_KEY, base_url=settings.DEKA_BASE_URL)
    except ImportError:
        print("WARNING: openai package not installed. Deka AI client not available.")
        return None


# Create directories if they don't exist
settings = get_settings()
os.makedirs(settings.OCR_CACHE_DIR, exist_ok=True)
os.makedirs(settings.PROCESSING_LOGS_DIR, exist_ok=True)