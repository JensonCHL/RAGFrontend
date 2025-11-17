# backend/services/indexing_service.py
"""
Indexing service for the FastAPI application.
Handles the complex workflow of indexing documents.
"""

import os
import json
import threading
from typing import Callable
from pathlib import Path

from core.config import get_settings
from app.events import notify_processing_update

settings = get_settings()


def index_company_worker(company_name: str, index_name: str, output_file_path: str, file_lock: threading.RLock, status_callback: Callable[[str], None]):
    """
    Worker function to index a company's documents.
    This is a placeholder implementation - in a real system, this would contain the actual indexing logic.
    """
    status_callback(f"Starting indexing for company: {company_name}")
    
    # Simulate some work
    import time
    time.sleep(2)
    
    status_callback(f"Completed indexing for company: {company_name}")


def job_orchestrator(index_name: str, project_root: str):
    """Discovers companies and launches a worker thread for each."""
    # Define the central output file
    output_file_path = os.path.join(project_root, "backend", "indexing_results.json")
    # Create a shared lock for file access
    file_lock = threading.RLock()

    # Clear the old results file at the start of a new job
    if os.path.exists(output_file_path):
        os.remove(output_file_path)

    def status_callback(message):
        # Add a timestamp to the message for clearer logging on the server
        print(f"[INDEXING_STATUS] {message}")
        notify_processing_update({"type": "indexing_status", "message": message})

    status_callback(f"Job started for index: '{index_name}'. Discovering companies...")

    try:
        ocr_cache_base_dir = os.path.join(project_root, "backend", "ocr_cache")
        if not os.path.isdir(ocr_cache_base_dir):
            status_callback("ERROR: OCR cache directory not found.")
            return

        company_dirs = [d for d in os.listdir(ocr_cache_base_dir) if os.path.isdir(os.path.join(ocr_cache_base_dir, d))]

        if not company_dirs:
            status_callback("INFO: No companies found in OCR cache. Job complete.")
            return

        status_callback(f"Found {len(company_dirs)} companies. Launching workers...")

        threads = []
        for company_name in company_dirs:
            thread = threading.Thread(
                target=index_company_worker,
                args=(company_name, index_name, output_file_path, file_lock, status_callback)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        status_callback("SUCCESS: All company workers have finished. Job complete.")
    except Exception as e:
        # Broad exception to catch any error during orchestration
        error_message = f"FATAL_ERROR: The indexing job failed during orchestration. Error: {str(e)}"
        status_callback(error_message)
        print(error_message) # Also print to server logs for debugging