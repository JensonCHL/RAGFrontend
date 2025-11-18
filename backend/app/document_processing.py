# backend/app/document_processing.py
"""
Document processing endpoints for the FastAPI application.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import time
import threading
import traceback

from services.processing_service import (
    generate_document_id, load_processing_states, save_processing_states,
    get_pdf_path, processing_lock, ocr_pdf_pages, generate_embeddings,
    ingest_to_qdrant, build_meta_header
)
from core.config import get_settings
from core.utils import get_log_file_path

router = APIRouter()
settings = get_settings()


class ProcessDocumentsRequest(BaseModel):
    company_id: str
    files: List[str]


@router.post("/api/process-documents")
async def process_documents(request: ProcessDocumentsRequest):
    """
    Process documents through all 3 steps: OCR -> Embedding -> Ingestion
    Expects JSON with company_id and files list
    Returns streaming progress updates for all steps
    """
    print("DEBUG: Received request to /api/process-documents", flush=True)

    company_id = request.company_id
    files = request.files

    if not company_id or not files:
        raise HTTPException(status_code=400, detail="Missing company_id or files")

    def generate():
        print("Try def block Executed")
        log_file_path = get_log_file_path(company_id)
        document_ids = []
        try:
            print("DEBUG: Entered generate() try block.", flush=True)
            print(f"DEBUG: Files to process: {files}", flush=True)

            # Process each file
            for file_idx, file_name in enumerate(files):
                project_root = settings.PROJECT_ROOT
                pdf_path = get_pdf_path(project_root, company_id, file_name)

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

                # Step 4: Structured Indexing
                from services.indexing_service import index_single_document

                yield json.dumps({
                    "status": "step_started",
                    "step": "structured_indexing",
                    "currentFile": file_name,
                    "message": f"Starting automatic structured indexing for {file_name}"
                }) + "\n"

                from core.database import get_db_connection
                db_conn = get_db_connection()
                if not db_conn:
                    print(f"[DB_ERROR] Could not connect to DB for structured indexing of {file_name}.")
                else:
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
                            # This function is in indexing_service.py and handles its own logic
                            index_single_document(company_id, file_name, index_name,
                                                status_callback=lambda msg_data: None)  # TODO: Implement proper callback
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

    return JSONResponse(content={
        'success': True,
        'message': 'Document processing started in background.'
    }, status_code=202)


@router.get("/api/document-processing-states")
async def get_document_processing_states():
    """
    Get all document processing states by aggregating all active log files.
    """
    print("DEBUG: Fetching document processing states from log directory")
    all_states: Dict[str, Any] = {}
    try:
        for filename in os.listdir(settings.PROCESSING_LOGS_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(settings.PROCESSING_LOGS_DIR, filename)
                try:
                    with open(file_path, 'r') as f:
                        states = json.load(f)
                        all_states.update(states)
                except Exception as e:
                    print(f"ERROR: Failed to read or parse log file {filename}: {e}")

        active_count = sum(1 for state in all_states.values() if state.get("is_processing"))
        print(f"DEBUG: Returning {len(all_states)} total states ({active_count} active) from {len(os.listdir(settings.PROCESSING_LOGS_DIR))} files.")
        return JSONResponse(content=all_states)
    except Exception as e:
        print(f"ERROR: Could not list processing logs directory: {e}")
        return JSONResponse(content={})