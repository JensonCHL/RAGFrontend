
import os
import json
import time

# --- Placeholder for actual LLM client ---
# In a real implementation, this would be initialized properly.
deka_client = None # OpenAI(...)

def _call_llm_for_extraction(page_text: str, index_name: str) -> str | None:
    """
    Placeholder: Calls the DekaLLM API to extract a specific piece of information.
    Returns the found value as a string, or None if not found.
    """
    print(f"    - LLM: Asking for '{index_name}' from page text...")
    
    # --- MOCK LLM LOGIC FOR DEMONSTRATION ---
    # This simulates the LLM finding a value on a specific page.
    # In a real scenario, this would be a network API call.
    if index_name.lower() == "end date" and "31 Desember 2024" in page_text:
        # Simulate the LLM extracting and standardizing the date.
        return "2024-12-31"
    if index_name.lower() == "start date" and "01 Januari 2023" in page_text:
        return "2023-01-01"
    # --- END MOCK LLM LOGIC ---
    
    # If the LLM doesn't find the value, it should return a consistent "not found" indicator.
    return None

def create_index_for_company(company_name: str, index_name: str):
    """
    Worker function to find and index a new piece of information for all
    documents belonging to a single company by reading the OCR cache.

    Args:
        company_name (str): The name of the company to process.
        index_name (str): The name of the data to extract (e.g., "End Date").

    Returns:
        dict: A dictionary where keys are document names and values are the
              extracted information (or None if not found).
    """
    print(f"--- Starting index creation job for Company: '{company_name}', Index: '{index_name}' ---")
    
    # This dictionary will hold the results.
    results = {}

    # 1. Construct path to the company's OCR cache directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    company_cache_dir = os.path.join(project_root, "backend", "ocr_cache", company_name)

    if not os.path.isdir(company_cache_dir):
        print(f"ERROR: Cache directory not found for company '{company_name}'. Aborting.")
        return {}

    # 2. Get a list of all JSON cache files in the directory
    try:
        document_files = [f for f in os.listdir(company_cache_dir) if f.endswith('.json')]
        if not document_files:
            print(f"INFO: No OCR cache files found for company '{company_name}'. Job complete.")
            return {}
    except Exception as e:
        print(f"ERROR: Could not read cache directory {company_cache_dir}: {e}")
        return {}

    # 3. Main loop: Iterate through each document cache file
    for doc_filename in document_files:
        print(f"\n-> Processing document: {doc_filename}")
        
        # 4. Load the OCR page data from the JSON file
        cache_path = os.path.join(company_cache_dir, doc_filename)
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                ocr_pages = json.load(f)
        except Exception as e:
            print(f"  - WARNING: Could not read or parse JSON file {doc_filename}. Skipping. Error: {e}")
            results[doc_filename] = None
            continue

        # 5. Inner loop: Iterate through pages with early stopping
        extracted_value = None
        for i, page_data in enumerate(ocr_pages):
            page_text = page_data.get("text", "")
            print(f"  - Analyzing page {i + 1}/{len(ocr_pages)}...")

            # 6. Dynamic prompt and LLM call
            llm_response = _call_llm_for_extraction(page_text, index_name)

            # 7. Validate response and implement early stopping
            if llm_response is not None:
                print(f"  - SUCCESS: Found value '{llm_response}' on page {i + 1}.")
                extracted_value = llm_response
                break # <-- This is the early stopping optimization
        
        # If after checking all pages, no value was found, extracted_value remains None
        if extracted_value is None:
            print(f"  - INFO: Index '{index_name}' not found in any page for {doc_filename}.")

        # Store the result for this document (either the value or None)
        results[doc_filename] = extracted_value

    print(f"\n--- Finished index creation job for Company: '{company_name}' ---")
    return results

# Example of how this worker function would be called
if __name__ == "__main__":
    # This simulates a worker process picking up a job for a specific company.
    target_company = "3D TECH"
    target_index = "End Date"
    
    # To make this example runnable, let's create a dummy cache file.
    print("--- Setting up dummy OCR cache for demonstration ---")
    dummy_cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_cache", target_company)
    os.makedirs(dummy_cache_dir, exist_ok=True)
    dummy_file_path = os.path.join(dummy_cache_dir, "SC100016317.pdf.json")
    dummy_data = [
        {"page": 1, "text": "This is page 1. It contains the start date: 01 Januari 2023.", "words": 12},
        {"page": 2, "text": "This is page 2. Nothing important here.", "words": 7},
        {"page": 3, "text": "This is page 3. The contract End Date is 31 Desember 2024.", "words": 13}
    ]
    with open(dummy_file_path, 'w', encoding='utf-8') as f:
        json.dump(dummy_data, f)
    print(f"Dummy cache created at: {dummy_file_path}\n")

    # --- Execute the function ---
    final_results = create_index_for_company(target_company, target_index)
    
    # --- Print the final returned dictionary ---
    print("\n========================================")
    print("Final Results Dictionary:")
    print(json.dumps(final_results, indent=2))
    print("========================================")

    # Clean up the dummy file
    os.remove(dummy_file_path)
