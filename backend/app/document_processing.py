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

from services.processing_service import generate_document_id, load_processing_states, save_processing_states, get_pdf_path, processing_lock
from core.config import get_settings

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
                    "file_name": file_name,
                    "doc_id": doc_id,
                    "message": f"Started processing {file_name}"
                }) + "\n"

                # TODO: Implement the actual processing steps here
                # This would include:
                # 1. OCR processing
                # 2. Embedding generation
                # 3. Data ingestion into Qdrant

                # For now, we'll simulate the process
                yield json.dumps({
                    "status": "processing_complete",
                    "file_index": file_idx + 1,
                    "total_files": len(files),
                    "file_name": file_name,
                    "doc_id": doc_id,
                    "message": f"Completed processing {file_name}"
                }) + "\n"

            # Final completion message
            yield json.dumps({
                "status": "all_files_complete",
                "message": f"Successfully processed {len(files)} files",
                "document_ids": [doc_id for doc_id, _ in document_ids]
            }) + "\n"

        except Exception as e:
            error_msg = str(e)
            print(f"ERROR in generate(): {error_msg}")
            yield json.dumps({
                "status": "fatal_error",
                "error": f"Fatal error during processing: {error_msg}"
            }) + "\n"

    return StreamingResponse(generate(), media_type="application/json")


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