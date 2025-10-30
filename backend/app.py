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

# Global lock for thread-safe operations on the processing state
processing_lock = threading.RLock()

# File path for processing states
PROCESSING_STATES_FILE = os.path.join(project_root, "document_processing_log.json")

def generate_document_id(company_id, file_name):
    """Generate a unique document ID based on company name and file name (deterministic)"""
    combined = f"{company_id}:{file_name}"
    return hashlib.sha1(combined.encode()).hexdigest()[:16]

def load_processing_states():
    """Load processing states from JSON file"""
    try:
        if os.path.exists(PROCESSING_STATES_FILE):
            with open(PROCESSING_STATES_FILE, 'r') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        print(f"Error loading processing states: {e}")
        return {}

def save_processing_states(states):
    """Save processing states to JSON file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(PROCESSING_STATES_FILE), exist_ok=True)
        with open(PROCESSING_STATES_FILE, 'w') as f:
            json.dump(states, f, indent=2)
        
        # Notify listeners of update
        notify_processing_update({"type": "states_updated", "states": states})
    except Exception as e:
        print(f"Error saving processing states: {e}")

def cleanup_old_processing_states():
    """Clean up completed processing states after a short delay"""
    with processing_lock:
        try:
            states = load_processing_states()
            current_time = time.time()
            updated_states = {}
            cleaned_count = 0
            
            for doc_id, state in states.items():
                # Keep processing states and recently completed states (less than 5 seconds old)
                if state.get("is_processing") or (current_time - state.get("completion_time", current_time)) < 5:
                    updated_states[doc_id] = state
                else:
                    # Remove old completed states
                    cleaned_count += 1
                    print(f"DEBUG: Cleaning up old processing state for {state.get('file_name', 'unknown')} (doc_id: {doc_id})")
            
            # Save cleaned up states if there were changes
            if len(updated_states) != len(states):
                save_processing_states(updated_states)
                print(f"DEBUG: Cleaned up {cleaned_count} old processing states")
                
            return updated_states
        except Exception as e:
            error_traceback = traceback.format_exc()
            print(f"ERROR in cleanup_old_processing_states: {str(e)}")
            print(f"Traceback: {error_traceback}")
            return load_processing_states()

def clear_processing_states_log():
    """Clear all processing states from the JSON file"""
    with processing_lock:
        try:
            if os.path.exists(PROCESSING_STATES_FILE):
                with open(PROCESSING_STATES_FILE, 'w') as f:
                    json.dump({}, f) # Write an empty JSON object
                print(f"DEBUG: Cleared processing states log: {PROCESSING_STATES_FILE}")
            else:
                print(f"DEBUG: Processing states log not found, no need to clear: {PROCESSING_STATES_FILE}")
        except Exception as e:
            print(f"Error clearing processing states log: {e}")

# Clear processing states on application startup
# clear_processing_states_log()

# Initialize processing states from file and clean up old ones
processing_states = cleanup_old_processing_states()

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

def ocr_pdf_pages(pdf_path: str, company: str, source_name: str, doc_id: str):
    """
    OCR PDF pages and yield progress updates - adapted from reference.py
    """
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
        # Update processing state with current page info
        with processing_lock:
            global processing_states
            processing_states = load_processing_states()
            if doc_id in processing_states:
                processing_states[doc_id].update({
                    "current_page": i + 1,
                    "total_pages": total_pages,
                    "message": f"Processing page {i+1}/{total_pages}"
                })
                # Update steps info
                if "steps" in processing_states[doc_id] and "ocr" in processing_states[doc_id]["steps"]:
                    processing_states[doc_id]["steps"]["ocr"].update({
                        "current_page": i + 1,
                        "total_pages": total_pages,
                        "message": f"Processing page {i+1}/{total_pages}"
                    })
                save_processing_states(processing_states)
        
        # Notify real-time listeners of page start
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
        
        # Send progress update that we're starting this page
        # Load current states first (inside a lock)
        with processing_lock:
            processing_states = load_processing_states()
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
                
                # Call DEKA OCR with extended timeout and error handling
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
                        timeout=700  # Extended timeout to 700 seconds
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    text = _clean_text(text)
                    
                    # Basic language check and word counting
                    words = len(text.split())
                    
                    page_result = {
                        "page": i + 1,
                        "text": text,
                        "words": words,
                    }
                    pages_out.append(page_result)
                    success_pages += 1
                    page_success = True
                    
                    # Update processing state with completed page info
                    with processing_lock:
                        processing_states = load_processing_states()
                        if doc_id in processing_states:
                            processing_states[doc_id].update({
                                "completed_pages": success_pages,
                                "message": f"Completed page {i+1}/{total_pages}"
                            })
                            # Update steps info
                            if "steps" in processing_states[doc_id] and "ocr" in processing_states[doc_id]["steps"]:
                                processing_states[doc_id]["steps"]["ocr"].update({
                                    "completed_pages": success_pages,
                                    "message": f"Completed page {i+1}/{total_pages}"
                                })
                            save_processing_states(processing_states)
                    
                    # Notify real-time listeners of page completion
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
                    # Handle API call errors
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
                        time.sleep(2 ** retries)  # Exponential backoff
                    else:
                        raise  # Re-raise if all retries exhausted
                        
            except Exception as e:
                # Handle image processing errors or exhausted retries
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
                    time.sleep(2 ** retries)  # Exponential backoff
                else:
                    # All retries exhausted
                    failed_pages += 1
                    error_msg = f"Failed to process page {i+1} after {MAX_RETRIES} attempts: {last_error}"
                    yield json.dumps({
                        "status": "page_failed",
                        "page": i + 1,
                        "error": error_msg
                    }) + "\n"
                    
                    # Add a placeholder for the failed page
                    pages_out.append({
                        "page": i + 1,
                        "text": f"[OCR FAILED: {error_msg}]",
                        "words": 0,
                    })
                    page_success = True  # Break the retry loop
    
    doc.close()
    
    # Final result
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
        
        # After successful ingestion, notify all clients to refresh Qdrant data
        try:
            # This is a simplified version of get_companies_with_documents
            # to avoid circular imports or re-calling the full Flask route
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
            print("DEBUG: Notified clients of Qdrant data update")
        except Exception as qdrant_notify_error:
            print(f"ERROR notifying Qdrant data update: {qdrant_notify_error}")
        
    except Exception as e:
        yield json.dumps({
            "status": "ingestion_failed",
            "error": f"Qdrant ingestion failed: {str(e)}"
        }) + "\n"

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
    Delete all data for a specific company from Qdrant
    """
    try:
        # Create filter for the specific company
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.company",
                    match=MatchValue(value=company_name)
                )
            ]
        )
        
        # Delete points matching the filter
        response = qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=company_filter
        )
        
        # The response might not have a count attribute, so we'll just return success
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
        global processing_states
        
        def generate():
            try:
                # Store document IDs for this processing session
                document_ids = []
                
                # Process each file
                for file_idx, file_name in enumerate(files):
                    # Construct file path (adjust based on your actual file storage)
                    import urllib.parse
                    # Use absolute path from project root
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

                    # Construct potential paths
                    # 1. Path with URL-encoded components (most robust for special characters)
                    encoded_company_id = urllib.parse.quote(company_id)
                    encoded_file_name = urllib.parse.quote(file_name)
                    potential_pdf_path_encoded = os.path.join(project_root, "knowledge", encoded_company_id, encoded_file_name)

                    # 2. Path with original components (for cases where encoding might not be needed or files were created without encoding)
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
                    
                    # Generate unique document ID ONCE for this file
                    doc_id = generate_document_id(company_id, file_name)
                    document_ids.append((doc_id, file_name))
                    print(f"DEBUG: Generated doc_id {doc_id} for {file_name}")
                    
                    with processing_lock:
                        processing_states = load_processing_states()
                        # Initialize processing state for this document
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
                        
                        # Add log entry
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Started processing document {file_name}",
                            "status": "started"
                        })
                        
                        # Save updated states
                        save_processing_states(processing_states)
                    
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
                        processing_states = load_processing_states()
                        processing_states[doc_id]["steps"]["ocr"] = {
                            "current_step": "ocr",
                            "message": f"Starting OCR for {file_name}",
                            "start_time": time.time()
                        }
                        processing_states[doc_id].update({
                            "message": f"Starting OCR for {file_name}"
                        })
                        
                        # Add log entry
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Starting OCR for {file_name}",
                            "status": "step_started",
                            "step": "ocr"
                        })
                        
                        # Save updated states
                        save_processing_states(processing_states)
                    
                    yield json.dumps({
                        "status": "step_started",
                        "step": "ocr",
                        "currentFile": file_name,
                        "message": f"Starting OCR for {file_name}"
                    }) + "\n"
                    
                    ocr_results = None
                    ocr_pages_data = []
                    
                    # Collect OCR results
                    for ocr_update in ocr_pdf_pages(pdf_path, company_id, file_name, doc_id):
                        yield ocr_update
                        # Parse the JSON to check for completion
                        try:
                            update_data = json.loads(ocr_update.strip())
                            if update_data.get("status") == "completed":
                                ocr_results = update_data
                                ocr_pages_data = update_data.get("pages_data", [])
                        except:
                            pass  # Ignore parsing errors for progress updates
                    
                    if not ocr_results:
                        # Update processing state with error
                        with processing_lock:
                            processing_states = load_processing_states()
                            processing_states[doc_id].update({
                                "is_processing": False,
                                "isError": True,
                                "errorMessage": "OCR processing failed"
                            })
                            save_processing_states(processing_states)
                        
                        yield json.dumps({
                            "status": "step_failed",
                            "step": "ocr",
                            "file_name": file_name,
                            "error": "OCR processing failed"
                        }) + "\n"
                        continue
                    
                    # Prepare chunks for embedding with metadata
                    chunks_data = []
                    for page_data in ocr_pages_data:
                        meta = {
                            "company": company_id,
                            "source": file_name,
                            "page": page_data["page"],
                            "doc_id": doc_id,
                            "words": page_data["words"],
                            "upload_time": time.time() # Use the current processing time
                        }
                        
                        # Add metadata header to text
                        text_with_header = build_meta_header(meta) + page_data["text"]
                        
                        chunks_data.append({
                            "text": text_with_header,
                            "meta": meta,
                            "page": page_data["page"]
                        })
                    
                    # Step 2: Embedding Generation
                    with processing_lock:
                        processing_states = load_processing_states()
                        processing_states[doc_id]["steps"]["embedding"] = {
                            "current_step": "embedding",
                            "message": f"Starting embedding generation for {file_name}",
                            "start_time": time.time()
                        }
                        processing_states[doc_id].update({
                            "message": f"Starting embedding generation for {file_name}"
                        })
                        
                        # Add log entry
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Starting embedding generation for {file_name}",
                            "status": "step_started",
                            "step": "embedding"
                        })
                        
                        # Save updated states
                        save_processing_states(processing_states)
                    
                    yield json.dumps({
                        "status": "step_started",
                        "step": "embedding",
                        "currentFile": file_name,
                        "message": f"Starting embedding generation for {file_name}"
                    }) + "\n"
                    
                    embedding_results = None
                    points_data = []
                    
                    # Generate embeddings
                    for embed_update in generate_embeddings(chunks_data, doc_id):
                        yield embed_update
                        # Parse the JSON to check for completion
                        try:
                            update_data = json.loads(embed_update.strip())
                            if update_data.get("status") == "embedding_completed":
                                embedding_results = update_data
                                points_data = update_data.get("points_data", [])
                        except:
                            pass  # Ignore parsing errors for progress updates
                    
                    if not embedding_results:
                        # Update processing state with error
                        with processing_lock:
                            processing_states = load_processing_states()
                            processing_states[doc_id].update({
                                "is_processing": False,
                                "isError": True,
                                "errorMessage": "Embedding generation failed"
                            })
                            save_processing_states(processing_states)
                        
                        yield json.dumps({
                            "status": "step_failed",
                            "step": "embedding",
                            "file_name": file_name,
                            "error": "Embedding generation failed"
                        }) + "\n"
                        continue
                    
                    # Step 3: Qdrant Ingestion
                    with processing_lock:
                        processing_states = load_processing_states()
                        processing_states[doc_id]["steps"]["ingestion"] = {
                            "current_step": "ingestion",
                            "message": f"Starting Qdrant ingestion for {file_name}",
                            "start_time": time.time()
                        }
                        processing_states[doc_id].update({
                            "message": f"Starting Qdrant ingestion for {file_name}"
                        })
                        
                        # Add log entry
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Starting Qdrant ingestion for {file_name}",
                            "status": "step_started",
                            "step": "ingestion"
                        })
                        
                        # Save updated states
                        save_processing_states(processing_states)
                    
                    yield json.dumps({
                        "status": "step_started",
                        "step": "ingestion",
                        "currentFile": file_name,
                        "message": f"Starting Qdrant ingestion for {file_name}"
                    }) + "\n"
                    
                    # Ingest to Qdrant
                    for ingest_update in ingest_to_qdrant(points_data, company_id, file_name):
                        yield ingest_update
                    
                    # Update processing state for file completion
                    with processing_lock:
                        processing_states = load_processing_states()
                        processing_states[doc_id].update({
                            "message": f"Completed processing for {file_name}",
                            "progress": int(((file_idx + 1) / len(files)) * 100)
                        })
                        
                        # Add log entry
                        processing_states[doc_id]["logs"].append({
                            "timestamp": time.time(),
                            "message": f"Completed processing for {file_name}",
                            "status": "file_completed"
                        })
                        
                        # Save updated states
                        save_processing_states(processing_states)
                    
                    yield json.dumps({
                        "status": "file_completed",
                        "file_index": file_idx + 1,
                        "currentFile": file_name,
                        "file_name": file_name,
                        "message": f"Completed processing for {file_name}",
                        "progress": int(((file_idx + 1) / len(files)) * 100)
                    }) + "\n"
                
                # All files processed - mark as complete
                with processing_lock:
                    processing_states = load_processing_states()
                    for doc_id, file_name in document_ids:
                        if doc_id in processing_states:
                            # Mark as complete but don't remove immediately
                            processing_states[doc_id].update({
                                "is_processing": False,
                                "message": f"Completed processing all {len(files)} files",
                                "progress": 100,
                                "completion_time": time.time()
                            })
                            
                            # Add log entry
                            processing_states[doc_id]["logs"].append({
                                "timestamp": time.time(),
                                "message": f"Completed processing all {len(files)} files",
                                "status": "all_completed"
                            })
                    
                    # Save updated states (keep completed entries so frontend can see them)
                    save_processing_states(processing_states)
                
                yield json.dumps({
                    "status": "all_completed",
                    "currentFile": None,
                    "message": f"Completed processing all {len(files)} files",
                    "files_processed": len(files),
                    "progress": 100
                }) + "\n"
                
            except Exception as e:
                # Log the full error traceback for debugging
                error_traceback = traceback.format_exc()
                print(f"ERROR in document processing generator: {str(e)}")
                print(f"Traceback: {error_traceback}")
                
                # Mark as failed but don't remove immediately
                with processing_lock:
                    processing_states = load_processing_states()
                    for doc_id, file_name in document_ids:
                        if doc_id in processing_states:
                            try:
                                processing_states[doc_id].update({
                                    "is_processing": False,
                                    "isError": True,
                                    "errorMessage": str(e),
                                    "completion_time": time.time()
                                })
                                
                                # Add log entry
                                processing_states[doc_id]["logs"].append({
                                    "timestamp": time.time(),
                                    "message": f"Processing failed: {str(e)}",
                                    "status": "process_error",
                                    "error": str(e),
                                    "traceback": error_traceback
                                })
                            except Exception as gen_error:
                                print(f"ERROR updating state in generator: {str(gen_error)}")
                    
                    # Save updated states (keep failed entries so frontend can see them)
                    save_processing_states(processing_states)
                
                yield json.dumps({
                    "status": "process_error",
                    "error": f"Processing failed: {str(e)}"
                }) + "\n"
        
        def start_processing_in_background():
            # The generate() function contains the core processing logic
            # It yields updates, but in this background context, we just want it to run to completion
            # We iterate through it to ensure all steps are executed
            for _ in generate():
                pass

        # Start the processing in a new thread
        processing_thread = threading.Thread(target=start_processing_in_background)
        processing_thread.daemon = True  # Allow the main program to exit even if this thread is still running
        processing_thread.start()

        return jsonify({
            'success': True,
            'message': 'Document processing started in background.'
        }), 202
        
    except Exception as e:
        # Log the full error traceback for debugging
        error_traceback = traceback.format_exc()
        print(f"ERROR in process_documents: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        # Mark as failed but don't remove immediately
        if 'company_id' in locals() and 'files' in locals():
            with processing_lock:
                processing_states = load_processing_states()
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
                            # Add log entry
                            processing_states[doc_id]["logs"].append({
                                "timestamp": time.time(),
                                "message": f"Failed to start processing: {str(e)}",
                                "status": "start_error",
                                "error": str(e),
                                "traceback": error_traceback
                            })
                    except Exception as gen_error:
                        print(f"ERROR generating doc_id or updating state: {str(gen_error)}")
                save_processing_states(processing_states)
            
        return jsonify({
            'success': False,
            'error': f'Failed to start processing: {str(e)}'
        }), 500

@app.route('/api/document-processing-states', methods=['GET'])
def get_document_processing_states():
    """
    Get all document processing states
    """
    print("DEBUG: Fetching document processing states")
    # Clean up old processing states
    states = cleanup_old_processing_states()
    active_count = sum(1 for state in states.values() if state.get("is_processing"))
    print(f"DEBUG: Returning {len(states)} total states ({active_count} active)")
    return jsonify(states)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)