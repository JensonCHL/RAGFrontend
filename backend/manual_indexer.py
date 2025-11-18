import os
import json
import time

# This file contains the core logic for the manual indexing process.

# --- LLM and Environment Configuration ---
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Initialize Deka AI client
DEKA_BASE = os.getenv("DEKA_BASE_URL")
DEKA_KEY = os.getenv("DEKA_KEY")
OCR_MODEL = "qwen/qwen3-coder"

deka_client = OpenAI(api_key=DEKA_KEY, base_url=DEKA_BASE) if DEKA_BASE and DEKA_KEY else None

def _call_llm_for_extraction(page_text: str, index_name: str) -> str | None:
    """
    Calls the DekaLLM API to extract a specific piece of information.
    Returns the found value as a string, or None if not found.
    """
    if not deka_client:
        print("      - ERROR: DekaLLM client not configured. Please check .env file.")
        return None

    print(f"      - LLM: Asking for '{index_name}' from page text...")

    system_prompt = f"""
        You are an expert data extraction assistant.

        Your only task is to extract the exact value for: '{index_name}' or word information from the given text.

        STRICT RULES:
        - You must return ONLY the exact text value as it appears.
        - Do NOT infer, guess, or assume any value.
        - If the requested information is missing, unclear, or not explicitly stated, return exactly: N/A
        - You must NOT generate or estimate any information.
        - Accept partial text only if it directly follows or clearly belongs to '{index_name}' but leave it if there is no context on its page ignore it.
        - Output the value ONLY — no labels, explanations, or punctuation.
        """

    try:
        response = deka_client.chat.completions.create(
            model=OCR_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": page_text}
            ],
            temperature=0,
            max_tokens=1000,
            timeout=60
        )
        
        result = response.choices[0].message.content.strip()

        if result.lower() == 'n/a':
            return None
        else:
            return result

    except Exception as e:
        print(f"      - ERROR: LLM API call failed. Error: {e}")
        return None

from db_utils import get_db_connection, create_table_if_not_exists, insert_extracted_data

def index_single_document(company_name: str, file_name: str, index_name: str, status_callback=None):
    """
    Processes a single document for a single index and saves the result to the database.
    """
    if status_callback:
        status_callback(f"  - Starting structured index '{index_name}' for {file_name}")

    try:
        # 1. Read the OCR cache for the specific document
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

        # 3. Prepare data and insert into the database
        from db_utils import get_db_connection, insert_extracted_data

        conn = get_db_connection()
        if conn:
            try:
                # Only insert if we found the index
                if extracted_value is not None:
                    result_data = {
                        "value": extracted_value,
                        "page": found_on_page,
                        "index_name": index_name
                    }

                    company_results_for_db = {
                        file_name: result_data
                    }

                    insert_extracted_data(conn, company_name, company_results_for_db)
            finally:
                conn.close()

    except Exception as e:
        error_message = f"  - ERROR: Failed during structured indexing for {file_name}. Error: {e}"
        if status_callback:
            status_callback(error_message)
        print(error_message)

def index_company_worker(company_name: str, index_name: str, output_file_path: str, lock, status_callback=None):
    """
    A thread-safe worker function that processes all documents for a single company
    and saves the results directly to the PostgreSQL database.
    """
    if status_callback:
        status_callback(f"START: Worker for company: {company_name}")

    try:
        company_results = {}
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        company_cache_dir = os.path.join(project_root, "backend", "ocr_cache", company_name)

        if not os.path.isdir(company_cache_dir):
            status_callback(f"ERROR: Cache directory not found for company '{company_name}'. Skipping.")
            return

        document_files = [f for f in os.listdir(company_cache_dir) if f.endswith('.json')]
        if not document_files:
            status_callback(f"INFO: No OCR cache files found for company '{company_name}'.")
            return

        status_callback(f"Processing {len(document_files)} documents for {company_name}...")

        # Track if any document had the index found
        any_index_found = False

        for doc_filename in document_files:
            cache_path = os.path.join(company_cache_dir, doc_filename)
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    ocr_pages = json.load(f)
            except Exception as e:
                status_callback(f"  - WARNING: Could not read or parse JSON file {doc_filename} for {company_name}. Skipping. Error: {e}")
                company_results[doc_filename] = None
                continue

            extracted_value = None
            found_on_page = None
            for page_data in ocr_pages:
                page_text = page_data.get("text", "")
                current_page = page_data.get("page")

                llm_response = _call_llm_for_extraction(page_text, index_name)

                if llm_response is not None:
                    status_callback(f"  - SUCCESS: Found '{index_name}' on page {current_page} of {doc_filename}.")
                    extracted_value = llm_response
                    found_on_page = current_page
                    any_index_found = True  # Mark that we found the index
                    break

            if extracted_value is None:
                status_callback(f"  - INFO: Index '{index_name}' not found in any page for {doc_filename}.")

            # Only store results for documents where index was found
            if extracted_value is not None:
                # We store the index_name in the result object itself for easier processing in the db_utils
                company_results[doc_filename] = {
                    "value": extracted_value,
                    "page": found_on_page,
                    "index_name": index_name
                }

        # --- Database Insertion Step ---
        conn = get_db_connection()
        if conn:
            try:
                # Ensure the table exists
                create_table_if_not_exists(conn)

                # Insert individual document results (only for found indexes)
                insert_extracted_data(conn, company_name, company_results)
            finally:
                conn.close()
                print(f"[DB_INFO] Database connection closed for {company_name}.")

    except Exception as e:
        if status_callback:
            status_callback(f"ERROR: Worker for company {company_name} failed. Error: {e}")
    finally:
        if status_callback:
            status_callback(f"FINISH: Worker for company: {company_name}")