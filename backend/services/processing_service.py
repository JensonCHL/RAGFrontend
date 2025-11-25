# backend/services/processing_service.py
"""
Document processing service for the FastAPI application.
Handles the complex workflow of OCR -> Embedding -> Ingestion.
"""

import os
import json
import time
import urllib.parse
import hashlib
from typing import List, Dict, Any, Generator
import threading
from pathlib import Path

from core.config import get_settings
from core.utils import get_log_file_path
from core.database import get_db_connection

settings = get_settings()

# Global lock for thread-safe operations on the processing state
processing_lock = threading.RLock()


def generate_document_id(company_id: str, file_name: str) -> str:
    """Generate a unique document ID based on company and file name."""
    combined = f"{company_id}:{file_name}"
    return hashlib.md5(combined.encode()).hexdigest()


def load_processing_states(company_id: str) -> Dict[str, Any]:
    """Load processing states from file for a company."""
    log_file_path = get_log_file_path(company_id)
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_processing_states(company_id: str, states: Dict[str, Any]) -> None:
    """Save processing states to file for a company."""
    log_file_path = get_log_file_path(company_id)
    try:
        with open(log_file_path, 'w') as f:
            json.dump(states, f, indent=2)
    except IOError as e:
        print(f"ERROR: Failed to save processing states: {e}")


def get_pdf_path(project_root: str, company_id: str, file_name: str) -> str:
    """Get the path to a PDF file, trying both encoded and original paths."""
    encoded_company_id = urllib.parse.quote(company_id)
    encoded_file_name = urllib.parse.quote(file_name)
    potential_pdf_path_encoded = os.path.join(project_root, "knowledge", encoded_company_id, encoded_file_name)
    potential_pdf_path_original = os.path.join(project_root, "knowledge", company_id, file_name)

    if os.path.exists(potential_pdf_path_encoded):
        return potential_pdf_path_encoded
    elif os.path.exists(potential_pdf_path_original):
        return potential_pdf_path_original

    return None


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


def get_ocr_cache_path(company_id: str, source_name: str) -> str:
    """Constructs the path for an OCR cache file, creating subdirs as needed."""
    import re
    safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_id)

    # Use settings for OCR cache directory
    ocr_cache_dir = os.path.join(settings.PROJECT_ROOT, "backend", "ocr_cache")
    os.makedirs(ocr_cache_dir, exist_ok=True)

    company_cache_dir = os.path.join(ocr_cache_dir, safe_company_id)
    os.makedirs(company_cache_dir, exist_ok=True)

    return os.path.join(company_cache_dir, f"{source_name}.json")


def ocr_pdf_pages(pdf_path: str, company_id: str, company: str, source_name: str, doc_id: str):
    """OCR PDF pages and yield progress updates - adapted from reference.py"""
    # Import required modules inside function to avoid circular imports
    from core.qdrant_client import get_qdrant_client

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

    # Get Deka AI client from config
    from core.config import get_deka_client
    deka_client = get_deka_client()
    OCR_MODEL = "meta/llama-4-maverick-instruct"

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

        yield json.dumps({
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

                    yield json.dumps({
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
    from core.config import get_deka_client
    from langchain_openai import OpenAIEmbeddings

    deka_client = get_deka_client()
    if not deka_client:
        return None

    from core.config import get_settings
    settings = get_settings()

    return OpenAIEmbeddings(
        api_key=settings.DEKA_KEY,
        base_url=settings.DEKA_BASE,
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
        from core.config import get_settings
        settings = get_settings()
        BATCH_SIZE = int(getattr(settings, 'BATCH_SIZE', "64"))
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
        # Get Qdrant client from core
        from core.qdrant_client import get_qdrant_client
        from qdrant_client.http import models as rest

        qdrant_client = get_qdrant_client()

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
        from core.config import get_settings
        settings = get_settings()

        try:
            # Check if collection exists by trying to get its info
            qdrant_client.get_collection(settings.QDRANT_COLLECTION)
        except Exception as e:
            # Collection doesn't exist, create it
            try:
                # Get dimension from first vector if available
                dim = len(points_data[0]["vector"]) if points_data and points_data[0]["vector"] else 768

                qdrant_client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=rest.VectorParams(
                        size=dim, distance=rest.Distance.COSINE),
                )
                yield json.dumps({
                    "status": "collection_created",
                    "message": f"Created collection {settings.QDRANT_COLLECTION} with dimension {dim}"
                }) + "\n"
            except Exception as create_error:
                # Handle case where collection was created by another process
                if "already exists" in str(create_error):
                    yield json.dumps({
                        "status": "collection_exists",
                        "message": f"Collection {settings.QDRANT_COLLECTION} already exists"
                    }) + "\n"
                else:
                    raise create_error

        # Batch upload points
        BATCH_SIZE = int(getattr(settings, 'BATCH_SIZE', "64"))
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
                    collection_name=settings.QDRANT_COLLECTION,
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