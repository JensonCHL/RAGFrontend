# backend/core/utils.py
"""
Utility functions for the FastAPI application.
"""

import os
import re
import hashlib
from pathlib import Path
from .config import get_settings

settings = get_settings()


def get_ocr_cache_path(company_id: str, source_name: str) -> str:
    """Constructs the path for an OCR cache file, creating subdirs as needed."""
    safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_id)
    company_cache_dir = os.path.join(settings.OCR_CACHE_DIR, safe_company_id)
    os.makedirs(company_cache_dir, exist_ok=True)
    return os.path.join(company_cache_dir, f"{source_name}.json")


def get_log_file_path(company_id: str) -> str:
    """Constructs the path for a company's log file."""
    safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_id)
    return os.path.join(settings.PROCESSING_LOGS_DIR, f"{safe_company_id}_processing.log")


def get_file_hash(file_path: str) -> str:
    """Generate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()