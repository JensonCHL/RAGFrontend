"""
Core Configuration Module
Handles all environment variables and configuration settings
"""

import os
from dotenv import load_dotenv

# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# ============================================================================
# DIRECTORY CONFIGURATION
# ============================================================================

# OCR Cache Directory
OCR_CACHE_DIR = os.path.join(project_root, "backend", "ocr_cache")
os.makedirs(OCR_CACHE_DIR, exist_ok=True)

# ============================================================================
# QDRANT CONFIGURATION
# ============================================================================

QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION')

# ============================================================================
# DEKA AI CONFIGURATION
# ============================================================================

DEKA_BASE = os.getenv("DEKA_BASE_URL")
DEKA_KEY = os.getenv("DEKA_KEY")
OCR_MODEL = "meta/llama-4-maverick-instruct"
EMBED_MODEL = os.getenv("EMBED_MODEL", "baai/bge-multilingual-gemma2")

# ============================================================================
# PROCESSING CONFIGURATION
# ============================================================================

MAX_CONCURRENT_JOBS = 30
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ocr_cache_path(company_id: str, source_name: str) -> str:
    """
    Constructs the path for an OCR cache file, creating subdirs as needed.
    
    Args:
        company_id: Company identifier
        source_name: Source document name
        
    Returns:
        Full path to the OCR cache file
    """
    import re
    safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_id)
    
    company_cache_dir = os.path.join(OCR_CACHE_DIR, safe_company_id)
    os.makedirs(company_cache_dir, exist_ok=True)
    
    return os.path.join(company_cache_dir, f"{source_name}.json")

def get_project_root() -> str:
    """Get the project root directory"""
    return project_root

print("✅ Configuration loaded successfully")
