import os
import requests
from fastapi import FastAPI, HTTPException, Header, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import threading
from typing import Optional
import psycopg2
import json
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
import uuid

# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Load environment variables explicitly from .env file
load_dotenv('.env')

# Configuration
INTERNAL_API_BASE_URL = "http://backend:5001"

# --- Database Connection ---
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# Qdrant Configuration from .env
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")

# Deka AI Configuration from .env (for consistent embeddings)
DEKA_BASE = os.getenv("DEKA_BASE_URL")
DEKA_KEY = os.getenv("DEKA_KEY")
EMBED_MODEL = os.getenv("EMBED_MODEL", "baai/bge-multilingual-gemma2")

# API Key for authentication (using API_BEARER_TOKEN as in original)
N8N_API_KEY = os.getenv("API_BEARER_TOKEN")

# Debug: Print API key status
print(f"API Key loaded: {'Yes' if N8N_API_KEY else 'No'}")
if N8N_API_KEY:
    print(f"API Key: {N8N_API_KEY[:5]}...{N8N_API_KEY[-5:]}")  # Show first 5 and last 5 chars

# Import the worker function
from manual_indexer import index_company_worker

app = FastAPI(title="n8n API Gateway", description="API Gateway for n8n workflows")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def build_embedder():
    """Build OpenAI embeddings compatible with Deka AI - consistent with app.py"""
    if not DEKA_KEY or not DEKA_BASE:
        return None

    return OpenAIEmbeddings(
        api_key=DEKA_KEY,
        base_url=DEKA_BASE,
        model=EMBED_MODEL,
        model_kwargs={"encoding_format": "float"}
    )

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

# --- API Key Authentication Dependency ---
async def verify_api_key(authorization: Optional[str] = Header(None)):
    """Dependency to verify API key for protected endpoints"""
    if N8N_API_KEY:
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail='Authorization header is missing or invalid')
        
        token = authorization.split(' ')[1]
        if token != N8N_API_KEY:
            raise HTTPException(status_code=401, detail='Invalid API Key')
    
    return True

# --- Create Index Endpoint (Converted to FastAPI) ---
@app.post("/api/create-index")
async def create_index_endpoint(
    background_tasks: BackgroundTasks,
    index_name: str = Query(..., description="Name of the index to create"),
    api_key_verified: bool = Depends(verify_api_key)
):
    """
    API endpoint to start a full manual indexing job, protected by an API key.
    Expects 'Authorization: Bearer <YOUR_API_KEY>' in the header.
    """

    if not index_name:
        raise HTTPException(status_code=400, detail='Missing index_name')

    # Convert index name to uppercase
    original_index_name = index_name
    index_name = index_name.upper()

    # Check if this index name already exists in the database
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM extracted_data WHERE index_name = %s",
                    (index_name,)
                )
                count = cur.fetchone()[0]
                if count > 0:
                    # Index name already exists, return error
                    raise HTTPException(status_code=400, detail='Duplicate Index name')
        finally:
            conn.close()

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

            # Check if any index was found across all companies
            any_index_found = False
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT COUNT(*) FROM extracted_data WHERE index_name = %s AND result IS NOT NULL AND result::text != %s",
                            (index_name, '"No deep search found on this index"')
                        )
                        count = cur.fetchone()[0]
                        any_index_found = count > 0
                finally:
                    conn.close()

            # If no index was found anywhere, add a single "No deep search found on this index" record
            if not any_index_found:
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cur:
                            # Generate a unique document_id for this aggregate record
                            import hashlib
                            document_id = hashlib.md5(f"aggregate_{index_name}".encode()).hexdigest()

                            cur.execute(
                                "INSERT INTO extracted_data (document_id, company_name, file_name, index_name, result) VALUES (%s, %s, %s, %s, %s)",
                                (document_id, "", index_name, index_name, '"No deep search found on this index"')
                            )
                            conn.commit()
                    finally:
                        conn.close()

            status_callback("SUCCESS: All company workers have finished. Job complete.")
        except Exception as e:
            # Broad exception to catch any error during orchestration
            error_message = f"FATAL_ERROR: The indexing job failed during orchestration. Error: {str(e)}"
            status_callback(error_message)
            print(error_message) # Also print to server logs for debugging

    # Add the job orchestration as a background task
    background_tasks.add_task(job_orchestrator)

    return JSONResponse(
        content={'success': True, 'message': f'Indexing job launched for: {index_name}'},
        status_code=202
    )

# --- List Indexes Endpoint (Converted to FastAPI) ---
@app.get("/api/list-indexes")
async def list_indexes(api_key_verified: bool = Depends(verify_api_key)):
    """
    API endpoint to list all unique index names present in the extracted_data table.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail='Database connection failed')

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT index_name FROM extracted_data ORDER BY index_name;")
            index_names = [row[0] for row in cur.fetchall()]
            return JSONResponse({'index_names': index_names})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch index names: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

# --- Get Index Data Endpoint (Converted to FastAPI) ---
@app.get("/api/get-index-data")
async def get_index_data(
    index_name: str = Query(..., description="Name of the index to retrieve data for"),
    api_key_verified: bool = Depends(verify_api_key)
):
    """
    API endpoint to get all data for a specific index name.
    Expects 'index_name' as a query parameter.
    """
    if not index_name:
        raise HTTPException(status_code=400, detail='Missing index_name parameter')

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail='Database connection failed')

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

            return JSONResponse({'success': True, 'data': transformed_data, 'count': len(transformed_data)})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch data for index '{index_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

def get_documents_by_company():
    """
    Retrieve all documents from Qdrant and group by company
    Returns a dictionary with statistics and company documents list
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
        total_contracts = 0

        for p in pts or []:
            meta = (p.payload or {}).get("metadata", {})
            source = meta.get("source", "Unknown Source")
            company = meta.get("company", "Unknown Company")

            # Add source to company's document list
            if company not in company_documents:
                company_documents[company] = []

            if source not in company_documents[company]:
                company_documents[company].append(source)
                total_contracts += 1

        # Calculate total companies
        total_companies = len(company_documents)

        # Convert to the new simplified format
        company_list = []
        for company, sources in company_documents.items():
            company_data = {
                "Company Name": company,
                "Contract Title": ", ".join(sources)  # Join all sources with comma and space
            }
            company_list.append(company_data)

        # Return statistics and company list
        result = {
            "total_companies": total_companies,
            "total_contracts": total_contracts,
            "companies": company_list
        }

        return result
    except Exception as e:
        raise Exception(f"Error retrieving documents: {e}")

# --- Documents Endpoints (Converted to FastAPI) ---
@app.get("/documents")
async def get_documents(api_key_verified: bool = Depends(verify_api_key)):
    """Get all documents grouped by company"""
    try:
        documents_data = get_documents_by_company()
        return JSONResponse(documents_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{company_name}")
async def get_documents_by_company_name(
    company_name: str,
    api_key_verified: bool = Depends(verify_api_key)
):
    """Get documents for a specific company"""
    try:
        documents_data = get_documents_by_company()
        # Find the specific company in the list
        company_data = [item for item in documents_data["companies"] if item.get("Company Name") == company_name]
        if company_data:
            # Return the same structure but with only the requested company
            result = {
                "total_companies": 1,
                "total_contracts": len(company_data[0].get("Contract Title", "").split(", ")) if company_data[0].get("Contract Title") else 0,
                "companies": company_data
            }
            return JSONResponse(result)
        else:
            raise HTTPException(status_code=404, detail=f"No documents found for company: {company_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Search Documents Endpoint (Converted to FastAPI) ---
@app.get("/api/search")
async def search_documents(
    query: str = Query(..., description="Search query text"),
    limit: int = Query(5, description="Maximum number of results to return"),
    api_key_verified: bool = Depends(verify_api_key)
):
    """Search documents using consistent embedding pipeline"""
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Missing 'query' parameter")

        # Build embedder (same as in app.py)
        embedder = build_embedder()
        if not embedder:
            raise HTTPException(status_code=500, detail="Embedder not configured")

        # Generate query vector
        query_vector = embedder.embed_query(query)

        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

        # Build filter if company specified
        search_filter = None
        # if company_filter:
        #     search_filter = rest.Filter(
        #         must=[
        #             rest.FieldCondition(
        #                 key="metadata.company",
        #                 match=rest.MatchValue(value=company_filter)
        #             )
        #         ]
        #     )

        # Perform search
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
            # query_filter=search_filter
        )

        # Format results with limited metadata
        formatted_results = []
        for result in results:
            # Extract only the specified metadata fields
            metadata = result.payload.get("metadata", {})
            limited_metadata = {
                "company": metadata.get("company", "Unknown"),
                "page": metadata.get("page", "Unknown"),
                "source": metadata.get("source", "Unknown"),
                "words": metadata.get("words", 0)
            }

            formatted_results.append({
                "score": result.score,
                "content": result.payload.get("content", ""),
                "metadata": limited_metadata
            })

        return JSONResponse({
            "succeass": True,
            # "query": query,
            "results": formatted_results,
            "count": len(formatted_results)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# --- Get Document Chunks Endpoint (Converted to FastAPI) ---
@app.get("/api/documents/chunks")
async def get_document_chunks(
    document: str = Query(..., description="Document name"),
    api_key_verified: bool = Depends(verify_api_key)
):
    """
    Retrieve all chunks for a specific document name.
    Query parameters:
    - document: Document name (unique identifier)
    """
    try:
        if not document:
            raise HTTPException(status_code=400, detail="Missing required parameter: 'document'")

        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

        # Build filter for document only (since document names are unique)
        search_filter = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="metadata.source",
                    match=rest.MatchValue(value=document)
                )
            ]
        )

        # Retrieve all matching points
        points = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=search_filter,
            limit=1000,  # Adjust as needed
            with_payload=True,
            with_vectors=False
        )[0]  # Get points, ignore offset

        # Sort points by page number
        sorted_points = sorted(points, key=lambda p: p.payload.get("metadata", {}).get("page", 0))

        # Check if no points were found
        if not sorted_points:
            return JSONResponse({
                "success": False,
                "error": "Wrong document name or File name",
                "document": document,
                "chunks": [],
                "count": 0
            })

        # Get company name from first chunk (since all chunks belong to same document)
        company = sorted_points[0].payload.get("metadata", {}).get("company", "")

        # Format results
        chunks = []
        for point in sorted_points:
            payload = point.payload or {}
            metadata = payload.get("metadata", {})

            chunks.append({
                # "id": str(point.id),
                "content": payload.get("content", ""),
                "metadata": {
                    "company": metadata.get("company", ""),
                    "source": metadata.get("source", ""),
                    "page": metadata.get("page", 0),
                    # "doc_id": metadata.get("doc_id", ""),
                    "words": metadata.get("words", 0),
                    # "upload_time": metadata.get("upload_time", 0)
                }
            })

        return JSONResponse({
            "success": True,
            "company": company,
            "document": document,
            "chunks": chunks,
            "count": len(chunks)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document chunks: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # This service will run on port 5000
    uvicorn.run(app, host="0.0.0.0", port=5000)