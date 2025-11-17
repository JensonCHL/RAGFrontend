# backend/core/qdrant_client.py
"""
Qdrant client wrapper for the FastAPI application.
"""

from qdrant_client import QdrantClient
from .config import get_settings

settings = get_settings()

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
) if settings.QDRANT_URL and settings.QDRANT_API_KEY else None


def get_qdrant_client():
    """Get the Qdrant client instance."""
    return qdrant_client