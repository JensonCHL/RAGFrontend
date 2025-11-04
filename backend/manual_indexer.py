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
                {"role": "user", "content": page_text}
            ],
            temperature=0,
            max_tokens=100,
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

def index_company_worker(company_name: str, index_name: str, output_file_path: str, lock, status_callback=None):
    """
    A thread-safe worker function that processes all documents for a single company
    and safely updates a central results file.
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

        for doc_filename in document_files:
            cache_path = os.path.join(company_cache_dir, doc_filename)
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    ocr_pages = json.load(f)
            except Exception as e:
                status_callback(f"  - WARNING: Could not read or parse JSON file {doc_filename} for {company_name}. Skipping. Error: {e}")
                company_results[doc_filename] = {"value": None, "page": None}
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
                    break
            
            if extracted_value is None:
                status_callback(f"  - INFO: Index '{index_name}' not found in any page for {doc_filename}.")

            company_results[doc_filename] = {
                "value": extracted_value,
                "page": found_on_page
            }

        # Thread-safe write to the central results file
        with lock:
            all_results = {}
            if os.path.exists(output_file_path):
                with open(output_file_path, 'r', encoding='utf-8') as f:
                    try:
                        all_results = json.load(f)
                    except json.JSONDecodeError:
                        pass
            
            if index_name not in all_results:
                all_results[index_name] = {}
            all_results[index_name][company_name] = company_results
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2)

    except Exception as e:
        if status_callback:
            status_callback(f"ERROR: Worker for company {company_name} failed. Error: {e}")
    finally:
        if status_callback:
            status_callback(f"FINISH: Worker for company: {company_name}")