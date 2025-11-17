# backend/core/database.py
"""
Database utilities for the FastAPI application.
"""

import psycopg2
from typing import Optional, Any
from .config import get_settings

settings = get_settings()


def get_db_connection() -> Optional[Any]:
    """
    Establishes and returns a connection to the PostgreSQL database.
    Returns None if connection fails.
    """
    try:
        conn = psycopg2.connect(
            dbname=settings.DB_NAME if hasattr(settings, 'DB_NAME') else "postgres",
            user=settings.DB_USER if hasattr(settings, 'DB_USER') else "postgres",
            password=settings.DB_PASSWORD if hasattr(settings, 'DB_PASSWORD') else "",
            host=settings.DB_HOST if hasattr(settings, 'DB_HOST') else "localhost",
            port=settings.DB_PORT if hasattr(settings, 'DB_PORT') else "5432"
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"[DB_ERROR] Could not connect to the database: {e}")
        return None