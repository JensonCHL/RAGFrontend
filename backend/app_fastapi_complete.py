# backend/app_fastapi_complete.py
"""
Complete FastAPI conversion of the Flask app.py
This file replicates all functionality from app.py while using FastAPI instead of Flask.
"""

import os
import json
import uuid
import hashlib
import time
import threading
import traceback
import queue
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from pathlib import Path

# FastAPI imports
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

# External libraries (same as in app.py)
import fitz  # PyMuPDF
from PIL import Image
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from openai import OpenAI
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

# Load environment variables (same as in app.py)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Create FastAPI app
app = FastAPI(title="RAG Backend API", version="1.0.0")

# Add CORS middleware (equivalent to Flask-CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (same as CORS(app) in Flask)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Configuration (same as in app.py)
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION')

# Deka AI configuration (same as in app.py)
DEKA_BASE = os.getenv("DEKA_BASE_URL")
DEKA_KEY = os.getenv("DEKA_KEY")
OCR_MODEL = "meta/llama-4-maverick-instruct"

# Initialize Qdrant client (same as in app.py)
qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
) if QDRANT_URL and QDRANT_API_KEY else None

# Initialize Deka AI client (same as in app.py)
deka_client = OpenAI(api_key=DEKA_KEY, base_url=DEKA_BASE) if DEKA_BASE and DEKA_KEY else None

# OCR Cache Configuration (same as in app.py)
OCR_CACHE_DIR = os.path.join(project_root, "backend", "ocr_cache")
os.makedirs(OCR_CACHE_DIR, exist_ok=True)

def get_ocr_cache_path(company_id, source_name):
    """Constructs the path for an OCR cache file, creating subdirs as needed."""
    import re
    safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_id)

    company_cache_dir = os.path.join(OCR_CACHE_DIR, safe_company_id)
    os.makedirs(company_cache_dir, exist_ok=True)

    return os.path.join(company_cache_dir, f"{source_name}.json")

# Global lock for thread-safe operations (same as in app.py)
processing_lock = threading.RLock()

# Directory for processing logs (same as in app.py)
PROCESSING_LOGS_DIR = os.path.join(project_root, "backend", "processing_logs")
os.makedirs(PROCESSING_LOGS_DIR, exist_ok=True)

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

# Global state for tracking missing indices
missing_indices = set()
missing_indices_lock = threading.Lock()

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
        print(f"ERROR in cleanup_old_processing_states: {e}")

# Utility functions (copied from app.py)
def page_image_base64(pdf_doc, page_index: int, zoom: float = 3.0) -> str:
    """Convert PDF page to base64 image - copied from reference.py"""
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

# OCR Processing function (copied from app.py)
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

# Embedding functions (copied from app.py)
def build_embedder():
    """Build OpenAI embeddings compatible with Deka AI - adapted from reference.py"""
    from langchain_openai import OpenAIEmbeddings

    if not deka_client:
        return None

    return OpenAIEmbeddings(
        api_key=DEKA_KEY,
        base_url=DEKA_BASE,
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

# Qdrant ingestion function (copied from app.py)
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

# Database functions (copied from app.py)
def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "postgres"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
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

# Manual indexer functions (copied from manual_indexer.py)
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

        # If we didn't find anything, set a default value
        if extracted_value is None:
            extracted_value = "No index Found"
            if status_callback:
                status_callback(f"    - INFO: Index '{index_name}' not found in {file_name}. Setting default value.")
        else:
            # If we successfully found the index, remove it from missing indices if it was there
            with missing_indices_lock:
                if index_name in missing_indices:
                    missing_indices.discard(index_name)
                    if status_callback:
                        status_callback(f"    - REMOVED: Index '{index_name}' removed from missing list")

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
                # Check if we're updating a "No index Found" record with actual data
                if extracted_value != "No index Found":
                    # Try to update existing record if it exists
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE extracted_data
                        SET value = %s, page = %s, last_updated = CURRENT_TIMESTAMP
                        WHERE company_name = %s AND file_name = %s AND index_name = %s AND value = 'No index Found'
                    """, (extracted_value, found_on_page, company_name, file_name, index_name))

                    # If no rows were updated, insert a new record
                    if cursor.rowcount == 0:
                        insert_extracted_data(conn, company_name, company_results_for_db)
                else:
                    # For "No index Found" records, always insert (no update needed)
                    insert_extracted_data(conn, company_name, company_results_for_db)
            finally:
                conn.close()

    except Exception as e:
        error_message = f"  - ERROR: Failed during structured indexing for {file_name}. Error: {e}"
        if status_callback:
            status_callback(error_message)
        print(error_message)

        # Check if this is an "index not found" error that we should track
        error_msg = str(e)
        if "Index required but not found" in error_msg or "index not found" in error_msg.lower():
            # Add to missing indices tracking
            with missing_indices_lock:
                missing_indices.add(index_name)
            if status_callback:
                status_callback(f"    - TRACKED: Index '{index_name}' marked as missing")
        else:
            # Re-raise non-index errors
            raise

# Event streaming functions (copied from app.py)
processing_listeners: Set[queue.Queue] = set()

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

# FastAPI endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={"status": "healthy"})


@app.get("/api/companies")
async def get_companies():
    """Get all unique company names from Qdrant metadata"""
    try:
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

        # Scroll through all points to get unique company names
        company_names = set()
        offset = None

        while True:
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            points, offset = response

            # Extract company names from payload
            for point in points:
                if point.payload and 'metadata' in point.payload:
                    company = point.payload['metadata'].get('company')
                    if company:
                        company_names.add(company)

            # Break if no more points
            if offset is None:
                break

        return JSONResponse(content={
            'success': True,
            'companies': sorted(list(company_names))
        })
    except Exception as e:
        print(f"ERROR in get_companies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch companies: {str(e)}")


@app.get("/api/companies/{company_name}/documents")
async def get_company_documents(company_name: str):
    """Get all documents for a specific company"""
    try:
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

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

        return JSONResponse(content={
            'success': True,
            'company': company_name,
            'documents': document_list
        })
    except Exception as e:
        error_msg = str(e)
        # Handle specific indexing error
        if "Index required but not found" in error_msg:
            raise HTTPException(status_code=400, detail=f'Indexing error: Please create an index on "metadata.company" field in Qdrant. {error_msg}')
        else:
            raise HTTPException(status_code=500, detail=f'Failed to fetch documents for company {company_name}: {error_msg}')


@app.get("/api/companies-with-documents")
async def get_companies_with_documents():
    """Get all unique company names with their associated documents and metadata in a single optimized call
    Returns a dictionary mapping company names to lists of document details"""
    try:
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

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

        return JSONResponse(content={
            'success': True,
            'data': result
        })

    except Exception as e:
        error_msg = str(e)
        # Handle specific indexing error
        if "Index required but not found" in error_msg:
            raise HTTPException(status_code=400, detail=f'Indexing error: Please create an index on "metadata.company" field in Qdrant. {error_msg}')
        else:
            raise HTTPException(status_code=500, detail=f'Failed to fetch companies with documents: {error_msg}')


@app.delete("/api/companies/{company_name}")
async def delete_company(company_name: str):
    """Delete all data for a specific company"""
    try:
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

        # Create filter for company
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.company",
                    match=MatchValue(value=company_name)
                )
            ]
        )

        # Delete points from Qdrant
        deleted_count = 0
        while True:
            # Get points to delete (limit to 1000 per batch)
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                scroll_filter=company_filter,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            points, _ = response

            if not points:
                break

            # Extract point IDs
            point_ids = [point.id for point in points]

            # Delete points
            qdrant_client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=point_ids
            )

            deleted_count += len(point_ids)

            # If we deleted less than 1000 points, we're done
            if len(point_ids) < 1000:
                break

        # Clean up processing logs
        log_file_pattern = os.path.join(PROCESSING_LOGS_DIR, f"{company_name}_*.json")
        import glob
        log_files = glob.glob(log_file_pattern)
        for log_file in log_files:
            try:
                os.remove(log_file)
                print(f"INFO: Removed processing log: {log_file}")
            except Exception as e:
                print(f"WARNING: Failed to remove log file {log_file}: {e}")

        # Clean up OCR cache
        company_cache_dir = os.path.join(OCR_CACHE_DIR, company_name)
        if os.path.exists(company_cache_dir):
            import shutil
            try:
                shutil.rmtree(company_cache_dir)
                print(f"INFO: Removed OCR cache directory: {company_cache_dir}")
            except Exception as e:
                print(f"WARNING: Failed to remove OCR cache directory {company_cache_dir}: {e}")

        return JSONResponse(content={
            "message": f"Deleted {deleted_count} points for company '{company_name}'",
            "deleted_count": deleted_count
        })
    except Exception as e:
        print(f"ERROR in delete_company: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete company data: {str(e)}")


@app.delete("/api/companies/{company_name}/documents/{document_name}")
async def delete_document(company_name: str, document_name: str):
    """Delete a specific document"""
    try:
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

        # Create filter for company and document
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

        # Delete points from Qdrant
        deleted_count = 0
        while True:
            # Get points to delete (limit to 1000 per batch)
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                scroll_filter=document_filter,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            points, _ = response

            if not points:
                break

            # Extract point IDs
            point_ids = [point.id for point in points]

            # Delete points
            qdrant_client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=point_ids
            )

            deleted_count += len(point_ids)

            # If we deleted less than 1000 points, we're done
            if len(point_ids) < 1000:
                break

        # Clean up processing log for this document
        doc_id = generate_document_id(company_name, document_name)
        log_file = get_log_file_path(doc_id)
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
                print(f"INFO: Removed processing log: {log_file}")
            except Exception as e:
                print(f"WARNING: Failed to remove log file {log_file}: {e}")

        # Clean up OCR cache for this document
        cache_path = get_ocr_cache_path(company_name, document_name)
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                print(f"INFO: Removed OCR cache: {cache_path}")
            except Exception as e:
                print(f"WARNING: Failed to remove OCR cache {cache_path}: {e}")

        return JSONResponse(content={
            "message": f"Deleted {deleted_count} points for document '{document_name}' of company '{company_name}'",
            "deleted_count": deleted_count
        })
    except Exception as e:
        print(f"ERROR in delete_document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@app.get("/api/document-processing-states")
async def get_document_processing_states():
    """Get all document processing states"""
    try:
        all_states = {}

        # Iterate through all log files in the processing logs directory
        if os.path.exists(PROCESSING_LOGS_DIR):
            for filename in os.listdir(PROCESSING_LOGS_DIR):
                if filename.endswith(".json"):
                    file_path = os.path.join(PROCESSING_LOGS_DIR, filename)
                    try:
                        with open(file_path, 'r') as f:
                            states = json.load(f)
                            # Merge states into all_states
                            for doc_id, state in states.items():
                                all_states[doc_id] = state
                    except Exception as e:
                        print(f"WARNING: Failed to read processing states from {file_path}: {e}")

        return JSONResponse(content=all_states)
    except Exception as e:
        print(f"ERROR in get_document_processing_states: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch document processing states: {str(e)}")


@app.get("/events/processing-updates")
async def events_processing_updates():
    """Server-Sent Events for real-time processing updates"""
    def event_generator():
        # Create a queue for this listener
        listener_queue = queue.Queue()

        # Add to listeners set
        with processing_lock:
            processing_listeners.add(listener_queue)

        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to processing updates'})}\n\n"

        try:
            while True:
                # Wait for updates with a timeout to allow for graceful shutdown
                try:
                    data = listener_queue.get(timeout=30)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    # Send a heartbeat to keep connection alive
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except GeneratorExit:
            print("SSE connection closed by client")
        finally:
            # Remove from listeners set
            with processing_lock:
                processing_listeners.discard(listener_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/get-all-data")
async def get_all_data():
    """Fetch all records from extracted_data table"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, document_id, company_name, file_name, index_name, result, created_at
                    FROM extracted_data
                    ORDER BY company_name, file_name, index_name
                """)

                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

                # Convert to list of dictionaries
                records = []
                for row in rows:
                    record = dict(zip(columns, row))
                    # Convert result from JSON string back to dict if needed
                    if isinstance(record['result'], str):
                        try:
                            import json
                            record['result'] = json.loads(record['result'])
                        except:
                            pass  # Keep as string if parsing fails
                    records.append(record)

                return JSONResponse(content=records)
        finally:
            conn.close()
    except Exception as e:
        print(f"ERROR in get_all_data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {str(e)}")


@app.get("/api/list-indexes")
async def list_indexes():
    """List all unique index names"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT index_name FROM extracted_data ORDER BY index_name")
                rows = cur.fetchall()
                indexes = [row[0] for row in rows]
                return JSONResponse(content=indexes)
        finally:
            conn.close()
    except Exception as e:
        print(f"ERROR in list_indexes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch indexes: {str(e)}")


@app.delete("/api/index/{index_name}")
async def delete_index(index_name: str):
    """Delete all data for a specific index"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM extracted_data WHERE index_name = %s", (index_name,))
                deleted_count = cur.rowcount
                conn.commit()

                return JSONResponse(content={
                    "message": f"Deleted {deleted_count} records for index '{index_name}'",
                    "deleted_count": deleted_count
                })
        finally:
            conn.close()
    except Exception as e:
        print(f"ERROR in delete_index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete index data: {str(e)}")


class ProcessDocumentsRequest(BaseModel):
    files: List[str]
    company: str

# Alternative model for form data
class ProcessDocumentsForm(BaseModel):
    files: str  # JSON string representation of files array
    company: str

@app.post("/api/process-documents")
async def process_documents(request: Request):
    """Process documents through OCR -> Embedding -> Ingestion"""
    try:
        # Log the incoming request for debugging
        print(f"Received process_documents request")

        # Try to get JSON body first
        try:
            body = await request.json()
            print(f"Request body (JSON): {body}")

            # Extract files and company from JSON body
            # Handle both 'company' and 'company_id' keys for compatibility
            files = body.get("files", [])
            company = body.get("company") or body.get("company_id", "")
        except:
            # If JSON parsing fails, try to get form data
            form_data = await request.form()
            print(f"Request form data: {dict(form_data)}")

            # Extract files and company from form data
            # Handle both 'company' and 'company_id' keys for compatibility
            files_raw = form_data.get("files", "[]")
            company = form_data.get("company") or form_data.get("company_id", "")

            # Parse files as JSON if it's a string
            if isinstance(files_raw, str):
                try:
                    files = json.loads(files_raw)
                except:
                    files = [files_raw] if files_raw else []
            else:
                files = [files_raw] if files_raw else []

        print(f"Parsed files: {files}")
        print(f"Parsed company: {company}")

        # Process each file
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate company name
        if not company or not company.strip():
            raise HTTPException(status_code=400, detail="Company name is required")

        company_id = company.strip()

        # Process each file
        processing_results = []

        for file_path in files:
            if not os.path.exists(file_path):
                processing_results.append({
                    "file": file_path,
                    "status": "error",
                    "error": "File not found"
                })
                continue

            # Generate document ID
            file_name = os.path.basename(file_path)
            doc_id = generate_document_id(company_id, file_name)

            # Initialize processing state
            with processing_lock:
                processing_states = load_processing_states(company_id)
                processing_states[doc_id] = {
                    "doc_id": doc_id,
                    "company": company_id,
                    "file_name": file_name,
                    "current_file": file_name,
                    "status": "started",
                    "message": f"Starting processing for {file_name}",
                    "start_time": time.time(),
                    "steps": {
                        "ocr": {"status": "pending"},
                        "embedding": {"status": "pending"},
                        "ingestion": {"status": "pending"}
                    }
                }
                save_processing_states(company_id, processing_states)

            notify_processing_update({
                "type": "processing_started",
                "doc_id": doc_id,
                "file_name": file_name,
                "company": company_id,
                "message": f"Started processing {file_name}"
            })

            try:
                # Step 1: OCR Processing
                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    processing_states[doc_id]["steps"]["ocr"]["status"] = "started"
                    processing_states[doc_id]["steps"]["ocr"]["message"] = "Starting OCR processing"
                    save_processing_states(company_id, processing_states)

                pages_data = None
                async for ocr_update in ocr_pdf_pages_streaming(file_path, company_id, company_id, file_name, doc_id):
                    update_data = json.loads(ocr_update.strip())
                    if update_data.get("status") == "completed":
                        pages_data = update_data.get("pages_data")
                        break
                    elif update_data.get("error"):
                        raise Exception(update_data.get("error"))

                if not pages_data:
                    raise Exception("OCR processing failed to produce pages data")

                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    processing_states[doc_id]["steps"]["ocr"]["status"] = "completed"
                    processing_states[doc_id]["steps"]["ocr"]["message"] = "OCR processing completed"
                    save_processing_states(company_id, processing_states)

                notify_processing_update({
                    "type": "step_completed",
                    "doc_id": doc_id,
                    "step": "ocr",
                    "message": "OCR processing completed"
                })

                # Step 2: Embedding Generation
                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    processing_states[doc_id]["steps"]["embedding"]["status"] = "started"
                    processing_states[doc_id]["steps"]["embedding"]["message"] = "Starting embedding generation"
                    save_processing_states(company_id, processing_states)

                # Prepare chunks for embedding
                chunks_data = []
                for page_data in pages_data:
                    meta_header = build_meta_header({
                        "company": company_id,
                        "source": file_name,
                        "page": page_data["page"]
                    })

                    chunk_text = meta_header + page_data["text"]
                    chunks_data.append({
                        "text": chunk_text,
                        "meta": {
                            "company": company_id,
                            "source": file_name,
                            "page": page_data["page"],
                            "upload_time": datetime.now().isoformat()
                        }
                    })

                points_data = None
                async for embedding_update in generate_embeddings_streaming(chunks_data, doc_id):
                    update_data = json.loads(embedding_update.strip())
                    if update_data.get("status") == "embedding_completed":
                        points_data = update_data.get("points_data")
                        break
                    elif update_data.get("error"):
                        raise Exception(update_data.get("error"))

                if not points_data:
                    raise Exception("Embedding generation failed to produce points data")

                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    processing_states[doc_id]["steps"]["embedding"]["status"] = "completed"
                    processing_states[doc_id]["steps"]["embedding"]["message"] = "Embedding generation completed"
                    save_processing_states(company_id, processing_states)

                notify_processing_update({
                    "type": "step_completed",
                    "doc_id": doc_id,
                    "step": "embedding",
                    "message": "Embedding generation completed"
                })

                # Step 3: Qdrant Ingestion
                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    processing_states[doc_id]["steps"]["ingestion"]["status"] = "started"
                    processing_states[doc_id]["steps"]["ingestion"]["message"] = "Starting Qdrant ingestion"
                    save_processing_states(company_id, processing_states)

                async for ingestion_update in ingest_to_qdrant_streaming(points_data, company_id, file_name):
                    update_data = json.loads(ingestion_update.strip())
                    if update_data.get("status") == "ingestion_completed":
                        break
                    elif update_data.get("error"):
                        raise Exception(update_data.get("error"))

                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    processing_states[doc_id]["steps"]["ingestion"]["status"] = "completed"
                    processing_states[doc_id]["steps"]["ingestion"]["message"] = "Qdrant ingestion completed"
                    processing_states[doc_id]["status"] = "completed"
                    processing_states[doc_id]["message"] = "All processing steps completed successfully"
                    processing_states[doc_id]["end_time"] = time.time()
                    save_processing_states(company_id, processing_states)

                notify_processing_update({
                    "type": "processing_completed",
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "company": company_id,
                    "message": f"Completed processing {file_name}"
                })

                processing_results.append({
                    "file": file_path,
                    "status": "completed",
                    "doc_id": doc_id
                })

            except Exception as e:
                # Handle processing error
                error_msg = str(e)
                print(f"ERROR processing {file_name}: {error_msg}")

                with processing_lock:
                    processing_states = load_processing_states(company_id)
                    processing_states[doc_id]["status"] = "error"
                    processing_states[doc_id]["error"] = error_msg
                    processing_states[doc_id]["message"] = f"Processing failed: {error_msg}"
                    processing_states[doc_id]["end_time"] = time.time()
                    save_processing_states(company_id, processing_states)

                notify_processing_update({
                    "type": "processing_error",
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "company": company_id,
                    "error": error_msg,
                    "message": f"Failed processing {file_name}: {error_msg}"
                })

                processing_results.append({
                    "file": file_path,
                    "status": "error",
                    "error": error_msg,
                    "doc_id": doc_id
                })

        return JSONResponse(content={
            "message": "Document processing completed",
            "results": processing_results
        })

    except Exception as e:
        print(f"ERROR in process_documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process documents: {str(e)}")


# Streaming helpers for process_documents
async def ocr_pdf_pages_streaming(pdf_path: str, company_id: str, company: str, source_name: str, doc_id: str):
    """Streaming wrapper for OCR processing"""
    for update in ocr_pdf_pages(pdf_path, company_id, company, source_name, doc_id):
        yield update


async def generate_embeddings_streaming(chunks_data, doc_id):
    """Streaming wrapper for embedding generation"""
    for update in generate_embeddings(chunks_data, doc_id):
        yield update


async def ingest_to_qdrant_streaming(points_data, company_name, source_name):
    """Streaming wrapper for Qdrant ingestion"""
    for update in ingest_to_qdrant(points_data, company_name, source_name):
        yield update


class CreateIndexRequest(BaseModel):
    index_definitions: Dict[str, Any]

# Alternative model for form data
class CreateIndexForm(BaseModel):
    index_definitions: str  # JSON string representation

@app.post("/api/create-index")
async def create_index(request: Request):
    """Start a full manual indexing job"""
    try:
        # Log the incoming request for debugging
        print(f"Received create_index request")

        # Try to get JSON body first
        try:
            body = await request.json()
            print(f"Request body (JSON): {body}")

            # Extract index_definitions from JSON body
            # Handle both 'index_definitions' and other possible keys for compatibility
            index_defs = body.get("index_definitions", {})
        except:
            # If JSON parsing fails, try to get form data
            form_data = await request.form()
            print(f"Request form data: {dict(form_data)}")

            # Extract index_definitions from form data
            # Handle both 'index_definitions' and other possible keys for compatibility
            index_defs_raw = form_data.get("index_definitions", "{}")

            # Parse index_definitions as JSON if it's a string
            if isinstance(index_defs_raw, str):
                try:
                    index_defs = json.loads(index_defs_raw)
                except:
                    raise HTTPException(status_code=400, detail="Invalid index_definitions format")
            else:
                index_defs = index_defs_raw

        print(f"Parsed index_definitions: {index_defs}")

        # Validate input
        if not index_defs or not isinstance(index_defs, dict):
            raise HTTPException(status_code=400, detail="Invalid index definitions format")

        # Process each index definition
        results = []

        for index_name, index_config in index_defs.items():
            try:
                # Validate index config
                if not isinstance(index_config, dict) or 'companies' not in index_config:
                    results.append({
                        "index": index_name,
                        "status": "error",
                        "error": "Invalid index configuration: missing 'companies' key"
                    })
                    continue

                companies = index_config['companies']
                if not isinstance(companies, list):
                    results.append({
                        "index": index_name,
                        "status": "error",
                        "error": "Invalid companies format: expected list"
                    })
                    continue

                # Process each company
                company_results = {}
                for company_name in companies:
                    try:
                        # Get all documents for this company from OCR cache
                        company_cache_dir = os.path.join(OCR_CACHE_DIR, company_name)
                        if not os.path.exists(company_cache_dir):
                            company_results[company_name] = {
                                "status": "warning",
                                "message": f"No OCR cache found for company {company_name}"
                            }
                            continue

                        # Process each document in the company's cache
                        document_results = {}
                        for filename in os.listdir(company_cache_dir):
                            if filename.endswith('.json'):
                                doc_name = filename[:-5]  # Remove .json extension

                                def status_callback(msg):
                                    print(f"      [{company_name}/{doc_name}] {msg}")

                                try:
                                    index_single_document(company_name, doc_name, index_name, status_callback)
                                    document_results[doc_name] = {
                                        "status": "completed",
                                        "message": f"Successfully indexed {doc_name} for index {index_name}"
                                    }
                                except Exception as e:
                                    document_results[doc_name] = {
                                        "status": "error",
                                        "error": str(e)
                                    }

                        company_results[company_name] = {
                            "status": "completed",
                            "documents": document_results
                        }

                    except Exception as e:
                        company_results[company_name] = {
                            "status": "error",
                            "error": str(e)
                        }

                results.append({
                    "index": index_name,
                    "status": "completed",
                    "companies": company_results
                })

            except Exception as e:
                results.append({
                    "index": index_name,
                    "status": "error",
                    "error": str(e)
                })

        return JSONResponse(content={
            "message": "Indexing job completed",
            "results": results
        })

    except Exception as e:
        print(f"ERROR in create_index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create index: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server on port 5001...")
    uvicorn.run(
        "app_fastapi_complete:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        workers=1
    )