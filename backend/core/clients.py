"""
Core Clients Module
Initializes and manages Qdrant and Deka AI clients
"""

from qdrant_client import QdrantClient
from openai import OpenAI
from .config import QDRANT_URL, QDRANT_API_KEY, DEKA_BASE, DEKA_KEY

# ============================================================================
# QDRANT CLIENT
# ============================================================================

qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)

# ============================================================================
# DEKA AI CLIENT
# ============================================================================

deka_client = OpenAI(
    api_key=DEKA_KEY, 
    base_url=DEKA_BASE
) if DEKA_BASE and DEKA_KEY else None

print("✅ Clients initialized successfully")
print(f"   - Qdrant: {'Connected' if QDRANT_URL else 'Not configured'}")
print(f"   - Deka AI: {'Connected' if deka_client else 'Not configured'}")
