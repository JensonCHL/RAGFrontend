import os
import json
import uuid
import hashlib
import time
from datetime import datetime
from flask import Flask, jsonify, request, stream_with_context, Response, send_file
from flask_cors import CORS
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import threading
import traceback # Import the traceback module



# Load environment variables
import os
from dotenv import load_dotenv # Import load_dotenv
# Load .env from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# OCR Cache Configuration
OCR_CACHE_DIR = os.path.join(project_root, "backend", "ocr_cache")
os.makedirs(OCR_CACHE_DIR, exist_ok=True)

def get_ocr_cache_path(company_id, source_name):
    """Constructs the path for an OCR cache file, creating subdirs as needed."""
    import re
    safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_id)
    
    company_cache_dir = os.path.join(OCR_CACHE_DIR, safe_company_id)
    os.makedirs(company_cache_dir, exist_ok=True)
    
    return os.path.join(company_cache_dir, f"{source_name}.json")

# Global lock for thread-safe operations on the processing state
processing_lock = threading.RLock()

# Directory for processing logs
PROCESSING_LOGS_DIR = os.path.join(project_root, "backend", "processing_logs")
os.makedirs(PROCESSING_LOGS_DIR, exist_ok=True)  # Ensure directory exists at startup

def get_log_file_path(company_id):
    """Constructs the path for a company's log file."""
    import re
    # Sanitize company_id to make it a valid filename
    safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_id)
    return os.path.join(PROCESSING_LOGS_DIR, f"{safe_company_id}.json")

def generate_document_id(company_id, file_name):
    """Generate a unique document ID based on company name and file name (deterministic)"""
    combined = f"{company_id}:{file_name}"
    return hashlib.sha1(combined.encode()).hexdigest()[:16]

def load_processing_states(company_id):
    """Load processing states from a company-specific JSON file"""
    file_path = get_log_file_path(company_id)
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading processing states from {file_path}: {e}")
        return {}

def save_processing_states(company_id, states):
    """Save processing states to a company-specific JSON file"""
    file_path = get_log_file_path(company_id)
    try:
        with open(file_path, 'w') as f:
            json.dump(states, f, indent=2)
        
        # Notify listeners of update
        notify_processing_update({"type": "states_updated", "states": states})
    except Exception as e:
        print(f"Error saving processing states to {file_path}: {e}")

def cleanup_old_processing_states():
    """
    This function is now used to clean up orphaned log files that might be left
    over from a crashed process. It deletes any log file older than a set threshold.
    """
    ORPHAN_THRESHOLD_SECONDS = 3600 # 1 hour
    try:
        now = time.time()
        for filename in os.listdir(PROCESSING_LOGS_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(PROCESSING_LOGS_DIR, filename)
                try:
                    if now - os.path.getmtime(file_path) > ORPHAN_THRESHOLD_SECONDS:
                        os.remove(file_path)
                        print(f"INFO: Removed orphaned processing log: {filename}")
                except OSError as e:
                    print(f"ERROR: Failed to remove orphaned log {filename}: {e}")
    except Exception as e:
        print(f"ERROR: An error occurred during orphaned log cleanup: {e}")

def clear_processing_states_log():
    """Clear all processing states from the log directory"""
    with processing_lock:
        try:
            for filename in os.listdir(PROCESSING_LOGS_DIR):
                if filename.endswith(".json"):
                    file_path = os.path.join(PROCESSING_LOGS_DIR, filename)
                    os.remove(file_path)
            print(f"DEBUG: Cleared all processing logs from: {PROCESSING_LOGS_DIR}")
        except Exception as e:
            print(f"Error clearing processing states log directory: {e}")

# Clean up any orphaned logs from previous runs at startup
cleanup_old_processing_states()

# This global variable is no longer loaded at startup, but managed within requests.
processing_states = {}

# Qdrant configuration
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION')

# Deka AI configuration
DEKA_BASE = os.getenv("DEKA_BASE_URL")
DEKA_KEY = os.getenv("DEKA_KEY")
OCR_MODEL = "meta/llama-4-maverick-instruct"

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)

# Initialize Deka AI client
from openai import OpenAI
deka_client = OpenAI(api_key=DEKA_KEY, base_url=DEKA_BASE) if DEKA_BASE and DEKA_KEY else None

def page_image_base64(pdf_doc, page_index: int, zoom: float = 3.0) -> str:
    """Convert PDF page to base64 image - copied from reference.py"""
    import fitz  # PyMuPDF
    from PIL import Image
    import io
    import base64
    
    page = pdf_doc[page_index]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def _clean_text(s: str) -> str:
    """Text cleaning function - copied from reference.py"""
    if not s:
        return ""
    s = s.replace("\x00", " ")
    import re
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\u200b|\u200c|\u200d|\ufeff", "", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()

def build_meta_header(meta: dict) -> str:
    """Build metadata header for document chunks - copied from reference.py"""
    company = (meta or {}).get("company", "N/A")
    source = (meta or {}).get("source", "N/A")
    page = (meta or {}).get("page", "N/A")
    return f"Company: {company}\nDocument: {source}\nPage: {page}\n---\n"



def ocr_pdf_pages(pdf_path: str, company_id: str, company: str, source_name: str, doc_id: str):

    # OCR PDF pages and yield progress updates - adapted from reference.py
    cache_path = get_ocr_cache_path(company_id, source_name)
    if os.path.exists(cache_path):
        print(f"DEBUG: Found side-by-side OCR cache for {source_name}. Loading from file.")
        try:
            with open(cache_path, 'r') as f:
                cached_pages_data = json.load(f)
            
            yield json.dumps({"status": "started", "message": f"Loading {source_name} from cache..."}) + "\n"
            yield json.dumps({
                "status": "completed",
                "success_pages": len(cached_pages_data),
                "failed_pages": 0,
                "total_pages": len(cached_pages_data),
                "pages_data": cached_pages_data,
                "message": f"OCR completed for {source_name} from cache."
            }) + "\n"
            return
        except Exception as e:
            print(f"ERROR: Failed to load OCR cache for {source_name}: {e}. Re-processing.")

    import fitz  # PyMuPDF
    
    print(f"DEBUG: Starting OCR for {source_name} (doc_id: {doc_id})")
    
    if not deka_client:
        yield json.dumps({"error": "Deka AI client not configured"}) + "\n"
        return
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    success_pages = 0
    failed_pages = 0
    MAX_RETRIES = 3
    
    yield json.dumps({
        "status": "started",
        "message": f"Starting OCR for {source_name} ({total_pages} pages)",
        "total_pages": total_pages,
        "ocrProgress": {
            "current_page": 0,
            "total_pages": total_pages
        }
    }) + "\n"
    
    pages_out = []
    
    for i in range(total_pages):
        with processing_lock:
            processing_states = load_processing_states(company_id)
            if doc_id in processing_states:
                processing_states[doc_id].update({
                    "current_page": i + 1,
                    "total_pages": total_pages,
                    "message": f"Processing page {i+1}/{total_pages}"
                })
                if "steps" in processing_states[doc_id] and "ocr" in processing_states[doc_id]["steps"]:
                    processing_states[doc_id]["steps"]["ocr"].update({
                        "current_page": i + 1,
                        "total_pages": total_pages,
                        "message": f"Processing page {i+1}/{total_pages}"
                    })
                save_processing_states(company_id, processing_states)
        
        notify_processing_update({
            "type": "page_started",
            "doc_id": doc_id,
            "page": i + 1,
            "total_pages": total_pages
        })
        
        yield json.dumps({
            "status": "processing",
            "current_page": i + 1,
            "total_pages": total_pages,
            "message": f"Processing page {i+1}/{total_pages}",
            "ocrProgress": {
                "current_page": i + 1,
                "total_pages": total_pages
            }
        }) + "\n"
        
        retries = 0
        page_success = False
        last_error = None
        
        with processing_lock:
            processing_states = load_processing_states(company_id)
            current_file_name = processing_states.get(doc_id, {}).get("current_file") if 'doc_id' in locals() else source_name

        yield json.dumps({
            "status": "page_started",
            "page": i + 1,
            "total_pages": total_pages,
            "currentFile": current_file_name,
            "message": f"Starting OCR for page {i+1}/{total_pages}",
            "ocrProgress": {
                "current_page": i + 1,
                "total_pages": total_pages
            }
        }) + "\n"
        
        while retries < MAX_RETRIES and not page_success:
            try:
                b64_image = page_image_base64(doc, i, zoom=3.0)
                
                yield json.dumps({
                    "status": "page_api_call",
                    "page": i + 1,
                    "total_pages": total_pages,
                    "currentFile": source_name,
                    "message": f"Sending page {i+1}/{total_pages} to OCR service",
                    "ocrProgress": {
                        "current_page": i + 1,
                        "total_pages": total_pages
                    }
                }) + "\n"
                
                try:
                    resp = deka_client.chat.completions.create(
                        model=OCR_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are an OCR engine specialized in Indonesian/English legal and technical contracts. "
                                    "Your task is to extract text *exactly as it appears* in the document image, without rewriting or summarizing.\n\n"
                                    "Guidelines:\n"
                                    "- Preserve all line breaks, numbering, and indentation.\n"
                                    "- Keep all headers, footers, and notes if they appear in the image.\n"
                                    "- Preserve tables as text: keep rows and columns aligned with | separators. output it in Markdown table format Pad cells so that columns align visually.\n"
                                    "- Do not translate text — output exactly as in the document.\n"
                                    "- If a cell or field is blank, or contains only dots/dashes (e.g., '.....', '—'), write N/A.\n"
                                    "- Keep units, percentages, currency (e.g., m², kVA, %, Rp.) exactly as written.\n"
                                    "- If text is unclear, output it as ??? instead of guessing."
                                )
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Extract the text from this page {i+1} of the PDF."},
                                    {"type": "image_url", "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64_image}"}}
                                ]
                            }
                        ],
                        max_tokens=8000,
                        temperature=0,
                        timeout=700
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    text = _clean_text(text)
                    
                    words = len(text.split())
                    
                    page_result = {
                        "page": i + 1,
                        "text": text,
                        "words": words,
                    }
                    pages_out.append(page_result)
                    success_pages += 1
                    page_success = True
                    
                    with processing_lock:
                        processing_states = load_processing_states(company_id)
                        if doc_id in processing_states:
                            processing_states[doc_id].update({
                                "completed_pages": success_pages,
                                "message": f"Completed page {i+1}/{total_pages}"
                            })
                            if "steps" in processing_states[doc_id] and "ocr" in processing_states[doc_id]["steps"]:
                                processing_states[doc_id]["steps"]["ocr"].update({
                                    "completed_pages": success_pages,
                                    "message": f"Completed page {i+1}/{total_pages}"
                                })
                            save_processing_states(company_id, processing_states)
                    
                    notify_processing_update({
                        "type": "page_completed",
                        "doc_id": doc_id,
                        "page": i + 1,
                        "total_pages": total_pages,
                        "completed_pages": success_pages
                    })
                    
                    yield json.dumps({
                        "status": "page_completed",
                        "page": i + 1,
                        "words": words,
                        "message": f"Completed page {i+1}/{total_pages}",
                        "ocrProgress": {
                            "current_page": i + 1,
                            "total_pages": total_pages
                        }
                    }) + "\n"
                    
                except Exception as e:
                    retries += 1
                    last_error = str(e)
                    if retries < MAX_RETRIES:
                        yield json.dumps({
                            "status": "retry",
                            "page": i + 1,
                            "currentFile": source_name,
                            "retry": retries,
                            "message": f"Retrying page {i+1} (attempt {retries+1}/{MAX_RETRIES})"
                        }) + "\n"
                        time.sleep(2 ** retries)
                    else:
                        raise
                        
            except Exception as e:
                retries += 1
                last_error = str(e)
                if retries < MAX_RETRIES:
                    yield json.dumps({
                        "status": "retry",
                        "page": i + 1,
                        "currentFile": source_name,
                        "retry": retries,
                        "message": f"Retrying page {i+1} (attempt {retries+1}/{MAX_RETRIES})"
                    }) + "\n"
                    time.sleep(2 ** retries)
                else:
                    failed_pages += 1
                    error_msg = f"Failed to process page {i+1} after {MAX_RETRIES} attempts: {last_error}"
                    yield json.dumps({
                        "status": "page_failed",
                        "page": i + 1,
                        "error": error_msg
                    }) + "\n"
                    
                    pages_out.append({
                        "page": i + 1,
                        "text": f"[OCR FAILED: {error_msg}]",
                        "words": 0,
                    })
                    page_success = True
    
    doc.close()

    try:
        with open(cache_path, 'w') as f:
            json.dump(pages_out, f, indent=2)
        print(f"DEBUG: Saved OCR results for {source_name} to cache.")
    except Exception as e:
        print(f"ERROR: Failed to save OCR cache for {source_name}: {e}")

    yield json.dumps({
        "status": "completed",
        "success_pages": success_pages,
        "failed_pages": failed_pages,
        "total_pages": total_pages,
        "pages_data": pages_out,
        "message": f"OCR completed for {source_name}: {success_pages}/{total_pages} pages successful"
    }) + "\n"

def build_embedder():
    """Build OpenAI embeddings compatible with Deka AI - adapted from reference.py"""
    from langchain_openai import OpenAIEmbeddings
    
    if not deka_client:
        return None
        
    return OpenAIEmbeddings(
        api_key=DEKA_KEY,
        base_url=DEKA_BASE,
        model=os.getenv("EMBED_MODEL", "baai/bge-multilingual-gemma2"),
        model_kwargs={"encoding_format": "float"}
    )

def generate_embeddings(chunks_data, doc_id):
    """Generate embeddings for document chunks with progress tracking"""
    try:
        # Build embedder
        embedder = build_embedder()
        if not embedder:
            yield json.dumps({"error": "Embedder not configured"}) + "\n"
            return
            
        # Detect embedding dimension
        dim = len(embedder.embed_query("hello world"))
        yield json.dumps({
            "status": "embedding_started",
            "message": f"Generating embeddings for {len(chunks_data)} chunks",
            "dimension": dim,
            "chunk_count": len(chunks_data)
        }) + "\n"
        
        # Prepare chunks for embedding
        texts = [chunk["text"] for chunk in chunks_data]
        total_chunks = len(texts)
        
        # Generate embeddings in batches
        BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
        vectors = []
        
        for i in range(0, total_chunks, BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
            
            yield json.dumps({
                "status": "embedding_batch",
                "batch": batch_num,
                "total_batches": total_batches,
                "message": f"Generating embeddings for batch {batch_num}/{total_batches}",
                "embeddingProgress": {
                    "batch": batch_num,
                    "total_batches": total_batches
                }
            }) + "\n"
            
            try:
                # Generate embeddings for batch
                batch_vectors = embedder.embed_documents(batch)
                vectors.extend(batch_vectors)
                
                yield json.dumps({
                    "status": "embedding_batch_completed",
                    "batch": batch_num,
                    "processed": len(batch_vectors),
                    "message": f"Completed batch {batch_num}/{total_batches}",
                    "embeddingProgress": {
                        "batch": batch_num,
                        "total_batches": total_batches
                    }
                }) + "\n"
                
            except Exception as e:
                yield json.dumps({
                    "status": "embedding_error",
                    "batch": batch_num,
                    "error": f"Failed to generate embeddings for batch {batch_num}: {str(e)}"
                }) + "\n"
                return
        
        # Prepare final result with IDs and payloads
        result_data = []
        for i, chunk in enumerate(chunks_data):
            # Generate point ID using UUIDv5 (similar to reference.py)
            import uuid
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk['page']}"))
            
            result_data.append({
                "id": point_id,
                "vector": vectors[i] if i < len(vectors) else None,
                "payload": {
                    "content": chunk["text"],
                    "metadata": chunk.get("meta", {})
                }
            })
        
        yield json.dumps({
            "status": "embedding_completed",
            "vectors_generated": len(vectors),
            "points_data": result_data,
            "message": f"Embedding completed: {len(vectors)} vectors generated"
        }) + "\n"
        
    except Exception as e:
        yield json.dumps({
            "status": "embedding_failed",
            "error": f"Embedding generation failed: {str(e)}"
        }) + "\n"

def ingest_to_qdrant(points_data, company_name, source_name):
    """Ingest embedded points to Qdrant with progress tracking"""
    try:
        from qdrant_client.http import models as rest
        
        total_points = len(points_data)
        yield json.dumps({
            "status": "ingestion_started",
            "message": f"Starting ingestion of {total_points} points to Qdrant",
            "total_points": total_points,
            "ingestionProgress": {
                "points_ingested": 0,
                "total_points": total_points
            }
        }) + "\n"
        
        # Ensure collection exists
        try:
            # Check if collection exists by trying to get its info
            qdrant_client.get_collection(QDRANT_COLLECTION)
        except Exception as e:
            # Collection doesn't exist, create it
            try:
                # Get dimension from first vector if available
                dim = len(points_data[0]["vector"]) if points_data and points_data[0]["vector"] else 768
                
                qdrant_client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=rest.VectorParams(
                        size=dim, distance=rest.Distance.COSINE),
                )
                yield json.dumps({
                    "status": "collection_created",
                    "message": f"Created collection {QDRANT_COLLECTION} with dimension {dim}"
                }) + "\n"
            except Exception as create_error:
                # Handle case where collection was created by another process
                if "already exists" in str(create_error):
                    yield json.dumps({
                        "status": "collection_exists",
                        "message": f"Collection {QDRANT_COLLECTION} already exists"
                    }) + "\n"
                else:
                    raise create_error
        
        # Batch upload points
        BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
        uploaded_count = 0
        
        for i in range(0, total_points, BATCH_SIZE):
            batch = points_data[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_points + BATCH_SIZE - 1) // BATCH_SIZE
            
            yield json.dumps({
                "status": "ingestion_batch",
                "batch": batch_num,
                "total_batches": total_batches,
                "message": f"Ingesting batch {batch_num}/{total_batches} to Qdrant",
                "ingestionProgress": {
                    "batch": batch_num,
                    "total_batches": total_batches
                }
            }) + "\n"
            
            try:
                # Create PointStruct objects for batch
                points = [
                    rest.PointStruct(
                        id=point["id"],
                        vector=point["vector"],
                        payload=point["payload"]
                    )
                    for point in batch
                ]
                
                # Upload batch to Qdrant
                qdrant_client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=points,
                    wait=True
                )
                
                uploaded_count += len(points)
                
                yield json.dumps({
                    "status": "ingestion_batch_completed",
                    "batch": batch_num,
                    "uploaded": len(points),
                    "total_uploaded": uploaded_count,
                    "message": f"Completed ingestion batch {batch_num}/{total_batches}",
                    "ingestionProgress": {
                        "points_ingested": uploaded_count,
                        "total_points": total_points
                    }
                }) + "\n"
                
            except Exception as e:
                yield json.dumps({
                    "status": "ingestion_error",
                    "batch": batch_num,
                    "error": f"Failed to ingest batch {batch_num}: {str(e)}"
                }) + "\n"
                return
        
        yield json.dumps({
            "status": "ingestion_completed",
            "total_points": uploaded_count,
            "company": company_name,
            "document": source_name,
            "message": f"Ingestion completed: {uploaded_count} points uploaded to Qdrant",
            "ingestionProgress": {
                "points_ingested": uploaded_count,
                "total_points": uploaded_count
            }
        }) + "\n"
    except Exception as e:
        yield json.dumps({
            "status": "ingestion_failed",
            "error": f"Ingestion to Qdrant failed: {str(e)}"
        }) + "\n"
        
def notify_qdrant_data_update():
    """Queries Qdrant for the full company/document structure and notifies listeners."""
    try:
        company_documents = {}
        offset = None
        while True:
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            points, next_offset = response
            for point in points:
                metadata = point.payload.get('metadata', {}) if point.payload else {}
                company = metadata.get('company')
                source = metadata.get('source')
                doc_id_meta = metadata.get('doc_id')
                upload_time = metadata.get('upload_time')
                page = metadata.get('page')
                
                if company and source:
                    if company not in company_documents:
                        company_documents[company] = {}
                    if source not in company_documents[company]:
                        company_documents[company][source] = {
                            'doc_id': doc_id_meta,
                            'upload_time': upload_time,
                            'pages': []
                        }
                    if page is not None:
                        company_documents[company][source]['pages'].append(page)
            if next_offset is None:
                break
            offset = next_offset
        
        result = {}
        for comp, docs in company_documents.items():
            result[comp] = {}
            for doc_name, doc_info in docs.items():
                doc_info['pages'].sort()
                result[comp][doc_name] = doc_info
        
        notify_processing_update({
            "type": "qdrant_data_updated",
            "data": result
        })
        print("DEBUG: Notified clients of Qdrant data update after job completion")
    except Exception as qdrant_notify_error:
        print(f"ERROR notifying Qdrant data update: {qdrant_notify_error}")

@app.route('/api/companies', methods=['GET'])
def get_companies():
    """
    Get all unique company names from Qdrant metadata
    """
    try:
        # Scroll through all points to get unique companies
        companies = set()
        offset = None
        
        while True:
            # Fetch points with pagination
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_offset = response
            
            # Extract company names from metadata (matching document_api.py structure)
            for point in points:
                metadata = point.payload.get('metadata', {}) if point.payload else {}
                company = metadata.get('company')
                if company:
                    companies.add(company)
            
            # Break if no more points
            if next_offset is None:
                break
                
            offset = next_offset
        
        # Convert to sorted list
        company_list = sorted(list(companies))
        
        return jsonify({
            'success': True,
            'companies': company_list
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to fetch companies: {str(e)}'
        }), 500

@app.route('/api/companies/<company_name>/documents', methods=['GET'])
def get_company_documents(company_name):
    """
    Get all documents for a specific company
    """
    try:
        # Create filter for the specific company (matching document_api.py structure)
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.company",
                    match=MatchValue(value=company_name)
                )
            ]
        )
        
        # Scroll through points filtered by company
        documents = set()
        offset = None
        
        while True:
            # Fetch points with pagination
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                scroll_filter=company_filter
            )
            
            points, next_offset = response
            
            # Extract document sources from metadata (matching document_api.py structure)
            for point in points:
                metadata = point.payload.get('metadata', {}) if point.payload else {}
                source = metadata.get('source')
                if source:
                    documents.add(source)
            
            # Break if no more points
            if next_offset is None:
                break
                
            offset = next_offset
        
        # Convert to sorted list
        document_list = sorted(list(documents))
        
        return jsonify({
            'success': True,
            'company': company_name,
            'documents': document_list
        })
        
    except Exception as e:
        error_msg = str(e)
        # Handle specific indexing error
        if "Index required but not found" in error_msg:
            return jsonify({
                'success': False,
                'error': f'Indexing error: Please create an index on "metadata.company" field in Qdrant. {error_msg}'
            }), 400
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to fetch documents for company {company_name}: {error_msg}'
            }), 500

@app.route('/api/companies-with-documents', methods=['GET'])
def get_companies_with_documents():
    """
    Get all unique company names with their associated documents and metadata in a single optimized call
    Returns a dictionary mapping company names to lists of document details
    """
    try:
        # Scroll through all points to get companies and documents
        company_documents = {}
        offset = None
        
        while True:
            # Fetch points with pagination
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_offset = response
            
            # Extract company names and documents from metadata
            for point in points:
                metadata = point.payload.get('metadata', {}) if point.payload else {}
                company = metadata.get('company')
                source = metadata.get('source')
                doc_id = metadata.get('doc_id')
                upload_time = metadata.get('upload_time')
                page = metadata.get('page')
                
                if company and source:
                    # Add company to dict if not exists
                    if company not in company_documents:
                        company_documents[company] = {}
                    
                    # Add document to company's document dict if not exists
                    if source not in company_documents[company]:
                        company_documents[company][source] = {
                            'doc_id': doc_id,
                            'upload_time': upload_time,
                            'pages': []
                        }
                    
                    # Add page info
                    if page is not None:
                        company_documents[company][source]['pages'].append(page)
            
            # Break if no more points
            if next_offset is None:
                break
                
            offset = next_offset
        
        # Convert to the required format with sorted pages
        result = {}
        for company, documents in company_documents.items():
            result[company] = {}
            for doc_name, doc_info in documents.items():
                # Sort pages numerically
                doc_info['pages'].sort()
                result[company][doc_name] = doc_info
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        error_msg = str(e)
        # Handle specific indexing error
        if "Index required but not found" in error_msg:
            return jsonify({
                'success': False,
                'error': f'Indexing error: Please create an index on "metadata.company" field in Qdrant. {error_msg}'
            }), 400
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to fetch companies with documents: {error_msg}'
            }), 500

@app.route('/api/companies/<company_name>', methods=['DELETE'])
def delete_company_data(company_name):
    """
    Delete all data for a specific company from Qdrant and its OCR cache.
    """
    try:
        # Delete all points for the company from Qdrant
        company_filter = Filter(must=[FieldCondition(key="metadata.company", match=MatchValue(value=company_name))])
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=company_filter
        )
        print(f"DEBUG: Deleted Qdrant data for company {company_name}")

        # Now, delete the entire OCR cache directory for the company
        try:
            import re
            import shutil
            safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_name)
            company_cache_dir = os.path.join(OCR_CACHE_DIR, safe_company_id)
            if os.path.exists(company_cache_dir):
                shutil.rmtree(company_cache_dir)
                print(f"DEBUG: Deleted company cache directory: {company_cache_dir}")
        except Exception as e:
            print(f"ERROR: Failed to delete company cache directory for {company_name}: {e}")

        return jsonify({
            'success': True,
            'message': f'Successfully deleted documents for company {company_name}'
        })
        
    except Exception as e:
        error_msg = str(e)
        return jsonify({
            'success': False,
            'error': f'Failed to delete company data: {error_msg}'
        }), 500

@app.route('/api/companies/<company_name>/documents/<document_name>', methods=['DELETE'])
def delete_document(company_name, document_name):
    """
    Delete a specific document for a company from Qdrant using doc_id
    """
    try:
        # First, we need to get the doc_id for this document
        # Scroll through points to find the doc_id
        doc_id = None
        offset = None
        
        while True:
            # Create filter for the specific company and document
            document_filter = Filter(
                must=[
                    FieldCondition(
                        key="metadata.company",
                        match=MatchValue(value=company_name)
                    ),
                    FieldCondition(
                        key="metadata.source",
                        match=MatchValue(value=document_name)
                    )
                ]
            )
            
            # Fetch points with pagination
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                scroll_filter=document_filter
            )
            
            points, next_offset = response
            
            # Extract doc_id from the first point we find
            if points and not doc_id:
                for point in points:
                    metadata = point.payload.get('metadata', {}) if point.payload else {}
                    doc_id = metadata.get('doc_id')
                    if doc_id:
                        break
            
            # Break if no more points or we found the doc_id
            if next_offset is None or doc_id:
                break
                
            offset = next_offset
        
        if not doc_id:
            return jsonify({
                'success': False,
                'error': f'Document {document_name} not found for company {company_name}'
            }), 404
        
        # Now delete all points with this doc_id
        doc_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_id",
                    match=MatchValue(value=doc_id)
                )
            ]
        )
        
        # Delete points matching the filter
        response = qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=doc_filter
        )
        
        # The response might not have a count attribute, so we'll just return success
        
        # Also delete the OCR cache file
        try:
            cache_path = get_ocr_cache_path(company_name, document_name)
            if os.path.exists(cache_path):
                os.remove(cache_path)
                print(f"DEBUG: Deleted OCR cache file: {cache_path}")
        except Exception as e:
            print(f"ERROR: Failed to delete OCR cache file for {document_name}: {e}")

        return jsonify({
            'success': True,
            'message': f'Successfully deleted document {document_name} with doc_id {doc_id}'
        })
        
    except Exception as e:
        error_msg = str(e)
        return jsonify({
            'success': False,
            'error': f'Failed to delete document: {error_msg}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'service': 'Qdrant API'
    })

@app.route('/api/process-documents', methods=['POST'])
def process_documents():
    """
    Process documents through all 3 steps: OCR -> Embedding -> Ingestion
    Expects JSON with company_id and files list
    Returns streaming progress updates for all steps
    """
    try:
        data = request.get_json()
        company_id = data.get('company_id')
        files = data.get('files', [])
        
        if not company_id or not files:
            return jsonify({
                'success': False,
                'error': 'Missing company_id or files'
            }), 400
        
        def generate():
            log_file_path = get_log_file_path(company_id)
            document_ids = []
            try:
                # Process each file
                for file_idx, file_name in enumerate(files):
                    import urllib.parse
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    encoded_company_id = urllib.parse.quote(company_id)
                    encoded_file_name = urllib.parse.quote(file_name)
                    potential_pdf_path_encoded = os.path.join(project_root, "knowledge", encoded_company_id, encoded_file_name)
                    potential_pdf_path_original = os.path.join(project_root, "knowledge", company_id, file_name)
                    pdf_path = None
                    if os.path.exists(potential_pdf_path_encoded):
                        pdf_path = potential_pdf_path_encoded
                    elif os.path.exists(potential_pdf_path_original):
                        pdf_path = potential_pdf_path_original

                    if pdf_path is None:
                        yield json.dumps({
                            "status": "file_error",
                            "file_name": file_name,
                            "error": f"File not found: {file_name} in expected knowledge paths."
                        }) + "\n"
                        continue
                    
                    doc_id = generate_document_id(company_id, file_name)
                    document_ids.append((doc_id, file_name))
                    print(f"DEBUG: Generated doc_id {doc_id} for {file_name}")
                    
                    with processing_lock:
                        processing_states = load_processing_states(company_id)
                        processing_states[doc_id] = {
                            "doc_id": doc_id,
                            "company_id": company_id,
                            "file_name": file_name,
                            "is_processing": True,
                            "current_file": file_name,
                            "file_index": file_idx + 1,
                            "total_files": len(files),
                            "progress": 0,
                            "message": f"Initializing processing for {file_name}",
                            "steps": {},
                            "start_time": time.time(),
                            "logs": []
                        }
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Started processing document {file_name}",
                            "status": "started"
                        })
                        save_processing_states(company_id, processing_states)
                    
                    yield json.dumps({
                        "status": "file_started",
                        "file_index": file_idx + 1,
                        "total_files": len(files),
                        "currentFile": file_name,
                        "file_name": file_name,
                        "message": f"Starting processing for file {file_idx + 1}/{len(files)}: {file_name}",
                        "progress": int(((file_idx) / len(files)) * 100)
                    }) + "\n"
                    
                    # Step 1: OCR Processing
                    with processing_lock:
                        processing_states = load_processing_states(company_id)
                        processing_states[doc_id]["steps"]["ocr"] = {
                            "current_step": "ocr",
                            "message": f"Starting OCR for {file_name}",
                            "start_time": time.time()
                        }
                        processing_states[doc_id].update({
                            "message": f"Starting OCR for {file_name}"
                        })
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Starting OCR for {file_name}",
                            "status": "step_started",
                            "step": "ocr"
                        })
                        save_processing_states(company_id, processing_states)
                    
                    yield json.dumps({
                        "status": "step_started",
                        "step": "ocr",
                        "currentFile": file_name,
                        "message": f"Starting OCR for {file_name}"
                    }) + "\n"
                    
                    ocr_results = None
                    ocr_pages_data = []
                    for ocr_update in ocr_pdf_pages(pdf_path, company_id, company_id, file_name, doc_id):
                        yield ocr_update
                        try:
                            update_data = json.loads(ocr_update.strip())
                            if update_data.get("status") == "completed":
                                ocr_results = update_data
                                ocr_pages_data = update_data.get("pages_data", [])
                        except:
                            pass
                    
                    if not ocr_results:
                        with processing_lock:
                            processing_states = load_processing_states(company_id)
                            processing_states[doc_id].update({
                                "is_processing": False,
                                "isError": True,
                                "errorMessage": "OCR processing failed"
                            })
                            save_processing_states(company_id, processing_states)
                        yield json.dumps({
                            "status": "step_failed",
                            "step": "ocr",
                            "file_name": file_name,
                            "error": "OCR processing failed"
                        }) + "\n"
                        continue
                    
                    chunks_data = []
                    for page_data in ocr_pages_data:
                        meta = {
                            "company": company_id,
                            "source": file_name,
                            "page": page_data["page"],
                            "doc_id": doc_id,
                            "words": page_data["words"],
                            "upload_time": time.time()
                        }
                        text_with_header = build_meta_header(meta) + page_data["text"]
                        chunks_data.append({
                            "text": text_with_header,
                            "meta": meta,
                            "page": page_data["page"]
                        })
                    
                    # Step 2: Embedding Generation
                    with processing_lock:
                        processing_states = load_processing_states(company_id)
                        processing_states[doc_id]["steps"]["embedding"] = {
                            "current_step": "embedding",
                            "message": f"Starting embedding generation for {file_name}",
                            "start_time": time.time()
                        }
                        processing_states[doc_id].update({
                            "message": f"Starting embedding generation for {file_name}"
                        })
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Starting embedding generation for {file_name}",
                            "status": "step_started",
                            "step": "embedding"
                        })
                        save_processing_states(company_id, processing_states)
                    
                    yield json.dumps({
                        "status": "step_started",
                        "step": "embedding",
                        "currentFile": file_name,
                        "message": f"Starting embedding generation for {file_name}"
                    }) + "\n"
                    
                    embedding_results = None
                    points_data = []
                    for embed_update in generate_embeddings(chunks_data, doc_id):
                        yield embed_update
                        try:
                            update_data = json.loads(embed_update.strip())
                            if update_data.get("status") == "embedding_completed":
                                embedding_results = update_data
                                points_data = update_data.get("points_data", [])
                        except:
                            pass
                    
                    if not embedding_results:
                        with processing_lock:
                            processing_states = load_processing_states(company_id)
                            processing_states[doc_id].update({
                                "is_processing": False,
                                "isError": True,
                                "errorMessage": "Embedding generation failed"
                            })
                            save_processing_states(company_id, processing_states)
                        yield json.dumps({
                            "status": "step_failed",
                            "step": "embedding",
                            "file_name": file_name,
                            "error": "Embedding generation failed"
                        }) + "\n"
                        continue
                    
                    # Step 3: Qdrant Ingestion
                    with processing_lock:
                        processing_states = load_processing_states(company_id)
                        processing_states[doc_id]["steps"]["ingestion"] = {
                            "current_step": "ingestion",
                            "message": f"Starting Qdrant ingestion for {file_name}",
                            "start_time": time.time()
                        }
                        processing_states[doc_id].update({
                            "message": f"Starting Qdrant ingestion for {file_name}"
                        })
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Starting Qdrant ingestion for {file_name}",
                            "status": "step_started",
                            "step": "ingestion"
                        })
                        save_processing_states(company_id, processing_states)
                    
                    yield json.dumps({
                        "status": "step_started",
                        "step": "ingestion",
                        "currentFile": file_name,
                        "message": f"Starting Qdrant ingestion for {file_name}"
                    }) + "\n"
                    
                    for ingest_update in ingest_to_qdrant(points_data, company_id, file_name):
                        yield ingest_update
                    
                    with processing_lock:
                        processing_states = load_processing_states(company_id)
                        processing_states[doc_id].update({
                            "message": f"Completed processing for {file_name}",
                            "progress": int(((file_idx + 1) / len(files)) * 100)
                        })
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Completed processing for {file_name}",
                            "status": "file_completed"
                        })
                        save_processing_states(company_id, processing_states)
                    
                    yield json.dumps({
                        "status": "file_completed",
                        "file_index": file_idx + 1,
                        "currentFile": file_name,
                        "file_name": file_name,
                        "message": f"Completed processing for {file_name}",
                        "progress": int(((file_idx + 1) / len(files)) * 100)
                    }) + "\n"
                    
                    # Step 4 here for manual indexing?
                    from manual_indexer import index_single_document
                    from db_utils import get_db_connection

                    yield json.dumps({
                        "status": "step_started",
                        "step": "structured_indexing",
                        "currentFile": file_name,
                        "message": f"Starting automatic structured indexing for {file_name}"
                    }) + "\n"

                    db_conn = get_db_connection()
                    if not db_conn:
                        print(f"[DB_ERROR] Could not connect to DB for structured indexing of {file_name}.")
                        continue # Go to the next file in the list

                    try:
                        with db_conn.cursor() as cur:
                            cur.execute("SELECT DISTINCT index_name FROM extracted_data ORDER BY index_name;")
                            existing_index_names = [row[0] for row in cur.fetchall()]
                    except Exception as e:
                        print(f"[DB_ERROR] Failed to fetch existing index names: {e}")
                        existing_index_names = []
                    finally:
                        db_conn.close()

                    if existing_index_names:
                        print(f"DEBUG: Found {len(existing_index_names)} existing indexes. Back-filling for {file_name}.")
                        for index_name in existing_index_names:
                            # This function is in manual_indexer.py and handles its own logic
                            index_single_document(company_id, file_name, index_name, status_callback=lambda msg_data: notify_processing_update(msg_data) if isinstance(msg_data, dict) else notify_processing_update({'type': 'indexing_status', 'message': msg_data}))
                    else:
                        print(f"INFO: No existing structured indexes to process for {file_name}.")

                    yield json.dumps({
                        "status": "step_completed",
                        "step": "structured_indexing",
                        "currentFile": file_name,
                        "message": f"Completed automatic structured indexing for {file_name}"
                    }) + "\n"
                        
                
                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    for doc_id, file_name in document_ids:
                        if doc_id in processing_states:
                            processing_states[doc_id].update({
                                "is_processing": False,
                                "message": f"Completed processing all {len(files)} files",
                                "progress": 100,
                                "completion_time": time.time()
                            })
                            processing_states[doc_id]["logs"].append({
                                "timestamp": time.time(),
                                "message": f"Completed processing all {len(files)} files",
                                "status": "all_completed"
                            })
                    save_processing_states(company_id, processing_states)
                
                # Notify frontend to refresh its Qdrant data now that the whole job is done
                notify_qdrant_data_update()

                yield json.dumps({
                    "status": "all_completed",
                    "currentFile": None,
                    "message": f"Completed processing all {len(files)} files",
                    "files_processed": len(files),
                    "progress": 100
                }) + "\n"
            
            except Exception as e:
                error_traceback = traceback.format_exc()
                print(f"ERROR in document processing generator: {str(e)}")
                print(f"Traceback: {error_traceback}")
                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    for doc_id, file_name in document_ids:
                        if doc_id in processing_states:
                            try:
                                processing_states[doc_id].update({
                                    "is_processing": False,
                                    "isError": True,
                                    "errorMessage": str(e),
                                    "completion_time": time.time()
                                })
                                processing_states[doc_id]["logs"].append({
                                    "timestamp": time.time(),
                                    "message": f"Processing failed: {str(e)}",
                                    "status": "process_error",
                                    "error": str(e),
                                    "traceback": error_traceback
                                })
                            except Exception as gen_error:
                                print(f"ERROR updating state in generator: {str(gen_error)}")
                    save_processing_states(company_id, processing_states)
                
                yield json.dumps({
                    "status": "process_error",
                    "error": f"Processing failed: {str(e)}"
                }) + "\n"
            
            finally:
                if os.path.exists(log_file_path):
                    try:
                        time.sleep(5)
                        os.remove(log_file_path)
                        print(f"DEBUG: Removed processing log file: {log_file_path}")
                    except OSError as e:
                        print(f"ERROR: Failed to remove log file {log_file_path}: {e}")

        def start_processing_in_background():
            for _ in generate():
                pass

        processing_thread = threading.Thread(target=start_processing_in_background)
        processing_thread.daemon = True
        processing_thread.start()

        return jsonify({
            'success': True,
            'message': 'Document processing started in background.'
        }), 202
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"ERROR in process_documents: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        if 'company_id' in locals() and 'files' in locals():
            with processing_lock:
                processing_states = load_processing_states(company_id)
                for file_name in files:
                    try:
                        doc_id = generate_document_id(company_id, file_name)
                        if doc_id in processing_states:
                            processing_states[doc_id].update({
                                "is_processing": False,
                                "isError": True,
                                "errorMessage": str(e),
                                "completion_time": time.time()
                            })
                            processing_states[doc_id]["logs"].append({
                                "timestamp": time.time(),
                                "message": f"Failed to start processing: {str(e)}",
                                "status": "start_error",
                                "error": str(e),
                                "traceback": error_traceback
                            })
                    except Exception as gen_error:
                        print(f"ERROR generating doc_id or updating state: {str(gen_error)}")
                save_processing_states(company_id, processing_states)
            
        return jsonify({
            'success': False,
            'error': f'Failed to start processing: {str(e)}'
        }), 500
        

@app.route('/api/document-processing-states', methods=['GET'])
def get_document_processing_states():
    """
    Get all document processing states by aggregating all active log files.
    """
    print("DEBUG: Fetching document processing states from log directory")
    all_states = {}
    try:
        for filename in os.listdir(PROCESSING_LOGS_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(PROCESSING_LOGS_DIR, filename)
                try:
                    with open(file_path, 'r') as f:
                        states = json.load(f)
                        all_states.update(states)
                except Exception as e:
                    print(f"ERROR: Failed to read or parse log file {filename}: {e}")
        
        active_count = sum(1 for state in all_states.values() if state.get("is_processing"))
        print(f"DEBUG: Returning {len(all_states)} total states ({active_count} active) from {len(os.listdir(PROCESSING_LOGS_DIR))} files.")
        return jsonify(all_states)
    except Exception as e:
        print(f"ERROR: Could not list processing logs directory: {e}")
        return jsonify({})

# Global variables for SSE
processing_listeners = set()

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

# SSE endpoint for processing updates
@app.route('/events/processing-updates')
def processing_updates():
    """Server-Sent Events endpoint for real-time processing updates"""
    def event_stream():
        # Create a queue for this connection
        import queue
        listener_queue = queue.Queue()
        
        # Add this connection to listeners
        with processing_lock:
            processing_listeners.add(listener_queue)
        
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to processing updates'})}\n\n"
            
            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for update (with timeout to keep connection alive)
                    data = listener_queue.get(timeout=25)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    # Send keep-alive
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            pass
        finally:
            # Remove this connection from listeners
            with processing_lock:
                processing_listeners.discard(listener_queue)
    
    return Response(event_stream(), mimetype="text/event-stream")

from manual_indexer import index_company_worker

# Load the N8N API Key from environment variables
N8N_API_KEY = os.getenv("API_BEARER_TOKEN")

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
    data = request.get_json()
    index_name = data.get('index_name')

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

from db_utils import get_db_connection

@app.route('/api/get-all-data', methods=['GET'])
def get_all_data():
    """Fetches all records from the extracted_data table for debugging."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, company_name, file_name, index_name, result, created_at FROM extracted_data ORDER BY created_at DESC;")
            rows = cur.fetchall()
            
            # Get column names from the cursor description
            column_names = [desc[0] for desc in cur.description]
            
            # Convert rows to a list of dictionaries
            data = [dict(zip(column_names, row)) for row in rows]

            # Convert datetime objects to ISO format strings
            for row in data:
                if 'created_at' in row and hasattr(row['created_at'], 'isoformat'):
                    row['created_at'] = row['created_at'].isoformat()

            return jsonify({'success': True, 'data': data})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/list-indexes', methods=['GET'])
def list_indexes():
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

@app.route('/api/index/<string:index_name>', methods=['DELETE'])
def delete_index(index_name):
    """
    Deletes all data associated with a specific index_name from the database.
    (Authentication temporarily removed for testing/debugging purposes)
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM extracted_data WHERE index_name = %s;", (index_name,))
            conn.commit()
            deleted_count = cur.rowcount
            print(f"[DB_INFO] Deleted {deleted_count} rows for index_name: {index_name}")
            return jsonify({'success': True, 'message': f'Successfully deleted {deleted_count} records for index \'{index_name}\''})
    except Exception as e:
        conn.rollback()
        print(f"[DB_ERROR] Failed to delete index data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# --- Existing SSE and other routes ---

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)