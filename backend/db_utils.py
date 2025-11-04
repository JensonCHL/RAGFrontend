
import os
import psycopg2
import hashlib
import json
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# --- Database Connection ---
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"[DB_ERROR] Could not connect to the database: {e}")
        return None

# --- Schema Management ---
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS extracted_data (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    index_name VARCHAR(255) NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_id, index_name)
);
"""

def create_table_if_not_exists(conn):
    """Creates the 'extracted_data' table if it doesn't already exist."""
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()
            print("[DB_INFO] 'extracted_data' table checked/created successfully.")
    except Exception as e:
        print(f"[DB_ERROR] Failed to create table: {e}")
        conn.rollback()

# --- Data Insertion ---
INSERT_DATA_SQL = """
INSERT INTO extracted_data (document_id, company_name, file_name, index_name, result)
VALUES %s
ON CONFLICT (document_id, index_name) DO NOTHING;
"""

def insert_extracted_data(conn, company_name, company_results):
    """
    Inserts a batch of extracted data for a company into the database.

    Args:
        conn: The database connection object.
        company_name (str): The name of the company being processed.
        company_results (dict): The dictionary of results from the indexing worker.
                                  e.g., {"doc1.pdf.json": {"value": "...", "page": ...}}
    """
    records_to_insert = []
    for doc_filename, result_data in company_results.items():
        # Skip if the result is null
        if result_data is None or result_data.get('value') is None:
            continue

        # Create a consistent, unique ID for the document
        doc_id_str = f"{company_name}-{doc_filename}"
        document_id = hashlib.sha256(doc_id_str.encode('utf-8')).hexdigest()

        # The index name is stored in the top-level key of the original JSON file,
        # which we don't have here. We assume the caller will pass this.
        # For now, this needs to be handled in the worker.
        # This function expects `result_data` to contain the index_name.
        index_name = result_data.get("index_name")
        if not index_name:
            # This is a fallback, the worker should provide the index name.
            print(f"[DB_WARNING] Missing 'index_name' in result for {doc_filename}. Skipping.")
            continue

        # The result column is JSONB, so we dump the dict to a JSON string
        result_json = json.dumps(result_data)

        records_to_insert.append((
            document_id,
            company_name,
            doc_filename, # Storing the raw filename from the cache
            index_name,
            result_json
        ))

    if not records_to_insert:
        print(f"[DB_INFO] No new data to insert for company {company_name}.")
        return

    try:
        with conn.cursor() as cur:
            execute_values(cur, INSERT_DATA_SQL, records_to_insert)
            conn.commit()
            print(f"[DB_INFO] Successfully inserted/updated {len(records_to_insert)} records for {company_name}.")
    except Exception as e:
        print(f"[DB_ERROR] Failed to insert data for {company_name}: {e}")
        conn.rollback()

