import os
import requests
from flask import Flask, jsonify, request,abort
from flask_cors import CORS
from dotenv import load_dotenv
import threading
from manual_indexer import index_company_worker
import psycopg2
import json
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
import os
from dotenv import load_dotenv # Import load_dotenv
# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)


app = Flask(__name__)
CORS(app)

# Configuration
INTERNAL_API_BASE_URL = "http://backend:5001"
N8N_API_KEY = os.getenv("N8N_API_KEY")
# --- Database Connection ---
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
# List Qdrant Index
# Load environment variables explicitly from .env file
load_dotenv('.env')

# Qdrant Configuration from .env
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")

# API Key for authentication
API_KEY = os.getenv("DOCUMENT_API_KEY")

# Debug: Print API key status
print(f"API Key loaded: {'Yes' if API_KEY else 'No'}")
if API_KEY:
    print(f"API Key: {API_KEY[:5]}...{API_KEY[-5:]}")  # Show first 5 and last 5 chars

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def require_api_key(f):
    """Decorator to require API key for protected endpoints"""
    def decorated_function(*args, **kwargs):
        # Skip API key check for health endpoint
        if request.endpoint == 'health_check':
            return f(*args, **kwargs)
        
        # Debug information
        print(f"Request endpoint: {request.endpoint}")
        print(f"API_KEY from env: {'Set' if API_KEY else 'Not set'}")
        
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        print(f"Provided key: {'Present' if key else 'Missing'}")
        if key:
            print(f"Key comparison: {key == API_KEY}")
        
        if not key or key != API_KEY:
            print("Authentication failed - aborting")
            abort(401, description="Unauthorized: Invalid or missing API key")
        print("Authentication successful")
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def get_documents_by_company():
    """
    Retrieve all documents from Qdrant and group by company
    Returns a list of dictionaries with company name and document sources
    """
    try:
        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Scroll through all points in the collection
        pts, _ = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=10000,  # Adjust as needed
            with_payload=True,
            with_vectors=False
        )
        
        # Group documents by company
        company_documents = {}
        
        for p in pts or []:
            meta = (p.payload or {}).get("metadata", {})
            source = meta.get("source", "Unknown Source")
            company = meta.get("company", "Unknown Company")
            
            # Add source to company's document list
            if company not in company_documents:
                company_documents[company] = []
            
            if source not in company_documents[company]:
                company_documents[company].append(source)
        
        # Convert to the new simplified format
        result = []
        for company, sources in company_documents.items():
            company_data = {
                "Company Name": company,
                "Contract Title": ", ".join(sources)  # Join all sources with comma and space
            }
            result.append(company_data)
        
        return result
    except Exception as e:
        raise Exception(f"Error retrieving documents: {e}")


# --- API Key Authentication Decorator ---
def require_api_key(f):
    def decorated_function(*args, **kwargs):
        if N8N_API_KEY:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'success': False, 'error': 'Authorization header is missing or invalid'}), 401
            
            token = auth_header.split(' ')[1]
            if token != N8N_API_KEY:
                return jsonify({'success': False, 'error': 'Invalid API Key'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f"protected_{f.__name__}"
    return decorated_function
# db Connection
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

# Global variables for SSE
processing_listeners = set()
processing_lock = threading.RLock()

def notify_processing_update(data):
    """Notify all listeners of a processing update"""
    with processing_lock:
        # Create a copy of the listeners set to avoid modification during iteration
        listeners = processing_listeners.copy()
    
    # Send update to all listeners
    disconnected = set()
    for listener_queue in listeners:
        try:
            listener_queue.put(json.dumps(data))
        except:
            disconnected.add(listener_queue)
    
    # Remove disconnected listeners
    if disconnected:
        with processing_lock:
            processing_listeners.difference_update(disconnected)
    
# --- Public Endpoints ---

@app.route('/api/list-indexes', methods=['GET'])
@require_api_key
def forward_list_indexes():
    """
    API endpoint to list all unique index names present in the extracted_data table.
    No authentication required.
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT index_name FROM extracted_data ORDER BY index_name;")
            index_names = [row[0] for row in cur.fetchall()]
            return jsonify({'index_names': index_names})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch index names: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# Load the N8N API Key from environment variables
N8N_API_KEY = os.getenv("API_BEARER_TOKEN")

@app.route('/api/get-index-data', methods=['GET'])
@require_api_key
def get_index_data():
    """
    API endpoint to get all data for a specific index name.
    Expects 'index_name' as a query parameter.
    """
    # Get index_name from query parameters
    index_name = request.args.get('index_name')
    
    if not index_name:
        return jsonify({'success': False, 'error': 'Missing index_name parameter'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        with conn.cursor() as cur:
            # Query to get all data for the specified index_name
            cur.execute("""
                SELECT id, company_name, file_name, index_name, result, created_at 
                FROM extracted_data 
                WHERE index_name = %s 
                ORDER BY created_at DESC
            """, (index_name,))
            
            rows = cur.fetchall()
            
            # Get column names from the cursor description
            column_names = [desc[0] for desc in cur.description]
            
            # Convert rows to a list of dictionaries
            data = [dict(zip(column_names, row)) for row in rows]

            # Convert datetime objects to ISO format strings
            for row in data:
                if 'created_at' in row and hasattr(row['created_at'], 'isoformat'):
                    row['created_at'] = row['created_at'].isoformat()

            # Transform data to include only the requested fields
            transformed_data = []
            for row in data:
                # Parse the result field which contains JSON with page and value
                result_data = row.get('result', {})
                if isinstance(result_data, str):
                    try:
                        import json
                        result_data = json.loads(result_data)
                    except:
                        result_data = {}
                
                transformed_row = {
                    'company_name': row.get('company_name'),
                    'file_name': row.get('file_name'),
                    'index_name': row.get('index_name'),
                    'page': result_data.get('page'),
                    'value': result_data.get('value')
                }
                transformed_data.append(transformed_row)

            return jsonify({'success': True, 'data': transformed_data, 'count': len(transformed_data)})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch data for index '{index_name}': {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/create-index', methods=['POST'])
def create_index_endpoint():
    """
    API endpoint to start a full manual indexing job, protected by an API key.
    Expects 'Authorization: Bearer <YOUR_API_KEY>' in the header.
    """
    # API Key Authentication
    if N8N_API_KEY:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Authorization header is missing or invalid'}), 401
        
        token = auth_header.split(' ')[1]
        if token != N8N_API_KEY:
            return jsonify({'success': False, 'error': 'Invalid API Key'}), 401

    # --- Original logic continues if authentication is successful ---
    # data = request.get_json()
    # index_name = data.get('index_name')
    index_name = request.args.get('index_name')

    if not index_name:
        return jsonify({'success': False, 'error': 'Missing index_name'}), 400

    def job_orchestrator():
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

    # Run the entire orchestration in a single background thread
    orchestrator_thread = threading.Thread(target=job_orchestrator)
    orchestrator_thread.daemon = True
    orchestrator_thread.start()

    return jsonify({'success': True, 'message': f'Indexing job launched for: {index_name}'}), 202
# Qdrant Handling

@app.route('/documents', methods=['GET'])
@require_api_key
def get_documents():
    """Get all documents grouped by company"""
    try:
        documents = get_documents_by_company()
        return jsonify(documents), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/documents/<company_name>', methods=['GET'])
@require_api_key
def get_documents_by_company_name(company_name):
    """Get documents for a specific company"""
    try:
        documents = get_documents_by_company()
        # Find the specific company in the list
        company_data = [item for item in documents if item.get("Company Name") == company_name]
        if company_data:
            return jsonify(company_data), 200
        else:
            return jsonify({"error": f"No documents found for company: {company_name}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # This service will run on port 5000
    app.run(host='0.0.0.0', port=5000)
