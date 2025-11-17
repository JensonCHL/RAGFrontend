# backend/services/processing_service.py
"""
Document processing service for the FastAPI application.
Handles the complex workflow of OCR -> Embedding -> Ingestion.
"""

import os
import json
import time
import urllib.parse
import hashlib
from typing import List, Dict, Any, Generator
import threading
from pathlib import Path

from core.config import get_settings
from core.utils import get_log_file_path
from core.database import get_db_connection

settings = get_settings()

# Global lock for thread-safe operations on the processing state
processing_lock = threading.RLock()


def generate_document_id(company_id: str, file_name: str) -> str:
    """Generate a unique document ID based on company and file name."""
    combined = f"{company_id}:{file_name}"
    return hashlib.md5(combined.encode()).hexdigest()


def load_processing_states(company_id: str) -> Dict[str, Any]:
    """Load processing states from file for a company."""
    log_file_path = get_log_file_path(company_id)
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_processing_states(company_id: str, states: Dict[str, Any]) -> None:
    """Save processing states to file for a company."""
    log_file_path = get_log_file_path(company_id)
    try:
        with open(log_file_path, 'w') as f:
            json.dump(states, f, indent=2)
    except IOError as e:
        print(f"ERROR: Failed to save processing states: {e}")


def get_pdf_path(project_root: str, company_id: str, file_name: str) -> str:
    """Get the path to a PDF file, trying both encoded and original paths."""
    encoded_company_id = urllib.parse.quote(company_id)
    encoded_file_name = urllib.parse.quote(file_name)
    potential_pdf_path_encoded = os.path.join(project_root, "knowledge", encoded_company_id, encoded_file_name)
    potential_pdf_path_original = os.path.join(project_root, "knowledge", company_id, file_name)
    
    if os.path.exists(potential_pdf_path_encoded):
        return potential_pdf_path_encoded
    elif os.path.exists(potential_pdf_path_original):
        return potential_pdf_path_original
    
    return None