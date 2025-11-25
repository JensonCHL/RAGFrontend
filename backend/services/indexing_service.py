# backend/services/indexing_service.py
"""
Indexing service for the FastAPI application.
Handles the complex workflow of indexing documents.
"""

import os
import json
import threading
import time
from typing import Callable, Optional
from pathlib import Path

from core.config import get_settings
from core.database import get_db_connection
from app.events import notify_processing_update

settings = get_settings()


def _call_llm_for_extraction(page_text: str, index_name: str) -> Optional[str]:
    """
    Calls the DekaLLM API to extract a specific piece of information.
    Returns the found value as a string, or None if not found.
    """
    # Get Deka AI client from config
    from core.config import get_deka_client
    deka_client = get_deka_client()
    OCR_MODEL = "meta/llama-4-maverick-instruct"

    if not deka_client:
        print("      - ERROR: DekaLLM client not configured. Please check .env file.")
        return None

    print(f"      - LLM: Asking for '{index_name}' from page text...")

    system_prompt = f"""
        You are an expert data extraction assistant.

        Your only task is to extract the exact value for: '{index_name}' from the given text.

        STRICT RULES:
        - You must return ONLY the exact text value as it appears.
        - Do NOT infer, guess, or assume any value.
        - If the requested information is missing, unclear, or not explicitly stated, return exactly: N/A
        - You must NOT generate or estimate any information.
        - Accept partial text only if it directly follows or clearly belongs to '{index_name}'.
        - Output the value ONLY — no labels, explanations, or punctuation.
        """

    try:
        response = deka_client.chat.completions.create(
            model=OCR_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract '{index_name}' from this text:\n\n{page_text}"}
            ],
            max_tokens=500,
            temperature=0
        )

        result = (response.choices[0].message.content or "").strip()
        return result if result else None
    except Exception as e:
        print(f"      - ERROR: LLM call failed: {e}")
        return None


def index_single_document(company_name: str, file_name: str, index_name: str, status_callback: Optional[Callable] = None):
    """
    Processes a single document for a single index and saves the result to the database.
    """
    if status_callback:
        status_callback(f"  - Starting structured index '{index_name}' for {file_name}")

    try:
        # 1. Read the OCR cache for the specific document
        project_root = settings.PROJECT_ROOT
        cache_path = os.path.join(project_root, "backend", "ocr_cache", company_name, f"{file_name}.json")

        ocr_pages = []
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                ocr_pages = json.load(f)
        else:
            if status_callback:
                status_callback(f"  - WARNING: OCR cache not found for {file_name}. Skipping structured index.")
            return

        # 2. Loop through pages and call LLM for extraction
        extracted_value = None
        found_on_page = None
        for page_data in ocr_pages:
            page_text = page_data.get("text", "")
            current_page = page_data.get("page")

            llm_response = _call_llm_for_extraction(page_text, index_name)

            if llm_response is not None:
                if status_callback:
                    status_callback(f"    - SUCCESS: Found '{index_name}' on page {current_page} of {file_name}.")
                extracted_value = llm_response
                found_on_page = current_page
                break # Early stopping

        if extracted_value is None and status_callback:
            status_callback(f"    - INFO: Index '{index_name}' not found in {file_name}.")

        # 3. Prepare data and insert into the database
        result_data = {
            "value": extracted_value,
            "page": found_on_page,
            "index_name": index_name
        }

        company_results_for_db = {
            file_name: result_data
        }

        conn = get_db_connection()
        if conn:
            try:
                # Import db_utils functions
                from core.database import insert_extracted_data
                insert_extracted_data(conn, company_name, company_results_for_db)
            finally:
                conn.close()

    except Exception as e:
        error_message = f"  - ERROR: Failed during structured indexing for {file_name}. Error: {e}"
        if status_callback:
            status_callback(error_message)
        print(error_message)


def index_company_worker(company_name: str, index_name: str, output_file_path: str, file_lock: threading.RLock, status_callback: Callable[[str], None]):
    """
    Worker function to index a company's documents.
    This is a placeholder implementation - in a real system, this would contain the actual indexing logic.
    """
    status_callback(f"Starting indexing for company: {company_name}")

    # Simulate some work
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