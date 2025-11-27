"""
FastAPI Application for RAG System - COMPLETE VERSION
All endpoints from Flask app.py converted to FastAPI
Uses modular core/services architecture
"""

import os
import json
import queue
import threading
import traceback
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any

# FastAPI imports
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Import from our modular structure
from core.config import (
    get_ocr_cache_path,
    QDRANT_URL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    MAX_CONCURRENT_JOBS,
    get_project_root
)
from core.clients import qdrant_client, deka_client
from core.state import (
    processing_lock,
    processing_states_memory,
    processing_listeners,
    generate_document_id,
    load_processing_states,
    save_processing_states,
    cleanup_processing_state,
    notify_processing_update,
    get_all_processing_states
)
from services.ocr_service import ocr_pdf_pages, build_meta_header
from services.embedding_service import build_embedder, generate_embeddings
from services.qdrant_service import ingest_to_qdrant, notify_qdrant_data_update
from services.processing_pipeline import process_documents_pipeline

# Defer these imports to prevent blocking on startup
# They will be imported inside the functions that need them
# from manual_indexer import index_company_worker
# from db_utils import get_db_connection

# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="RAG System API",
    description="Document processing and management API (FastAPI version)",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global ThreadPoolExecutor for document processing jobs
job_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS, thread_name_prefix="DocProcessor")

# Track active and queued jobs
active_jobs = set()
active_jobs_lock = threading.Lock()

print("✅ FastAPI app initialized with modular structure")

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ProcessDocumentsRequest(BaseModel):
    company_id: str
    files: List[str]

class DeleteDocumentRequest(BaseModel):
    company_name: str
    document_name: str

class CreateIndexRequest(BaseModel):
    index_name: str

# ============================================================================
# COMPANY ENDPOINTS
# ============================================================================

@app.get("/api/companies")
async def get_companies():
    """Get all unique company names from Qdrant metadata"""
    try:
        companies = set()
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
                if company:
                    companies.add(company)
            
            if next_offset is None:
                break
            offset = next_offset
        
        company_list = sorted(list(companies))
        
        return JSONResponse({
            'success': True,
            'companies': company_list
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': f'Failed to fetch companies: {str(e)}'
        }, status_code=500)


@app.get("/api/companies/{company_name}/documents")
async def get_company_documents(company_name: str):
    """Get all documents for a specific company"""
    try:
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.company",
                    match=MatchValue(value=company_name)
                )
            ]
        )
        
        documents = set()
        offset = None
        
        while True:
            response = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                scroll_filter=company_filter
            )
            
            points, next_offset = response
            
            for point in points:
                metadata = point.payload.get('metadata', {}) if point.payload else {}
                source = metadata.get('source')
                if source:
                    documents.add(source)
            
            if next_offset is None:
                break
            offset = next_offset
        
        document_list = sorted(list(documents))
        
        return JSONResponse({
            'success': True,
            'documents': document_list
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': f'Failed to fetch documents: {str(e)}'
        }, status_code=500)


@app.get("/api/companies-with-documents")
async def get_companies_with_documents():
    """Get all companies with their documents from Qdrant"""
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
                doc_id = metadata.get('doc_id')
                upload_time = metadata.get('upload_time')
                page = metadata.get('page')
                
                if company and source:
                    if company not in company_documents:
                        company_documents[company] = {}
                    if source not in company_documents[company]:
                        company_documents[company][source] = {
                            'doc_id': doc_id,
                            'upload_time': upload_time,
                            'pages': []
                        }
                    if page is not None:
                        company_documents[company][source]['pages'].append(page)
            
            if next_offset is None:
                break
            offset = next_offset
        
        for company in company_documents:
            for doc in company_documents[company]:
                company_documents[company][doc]['pages'].sort()
        
        return JSONResponse({
            'success': True,
            'data': company_documents
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': f'Failed to fetch company documents: {str(e)}'
        }, status_code=500)


@app.delete("/api/companies/{company_name}")
async def delete_company_data(company_name: str):
    """Delete all data for a specific company from Qdrant"""
    try:
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.company",
                    match=MatchValue(value=company_name)
                )
            ]
        )
        
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=company_filter
        )
        
        return JSONResponse({
            'success': True,
            'message': f'Successfully deleted all data for company: {company_name}'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': f'Failed to delete company data: {str(e)}'
        }, status_code=500)


@app.delete("/api/companies/{company_name}/documents/{document_name}")
async def delete_document(company_name: str, document_name: str):
    """Delete a specific document from Qdrant"""
    try:
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
        
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=document_filter
        )
        
        return JSONResponse({
            'success': True,
            'message': f'Successfully deleted document: {document_name} from company: {company_name}'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': f'Failed to delete document: {str(e)}'
        }, status_code=500)


# ============================================================================
# DOCUMENT PROCESSING ENDPOINTS
# ============================================================================

@app.post("/api/process-documents")
async def process_documents(request: ProcessDocumentsRequest):
    """
    Process documents through all 3 steps: OCR -> Embedding -> Ingestion
    Returns immediately with job submission status
    """
    try:
        company_id = request.company_id
        files = request.files
        
        if not company_id or not files:
            return JSONResponse({
                'success': False,
                'error': 'Missing company_id or files'
            }, status_code=400)
        
        # Create "queued" states in RAM for all documents
        with processing_lock:
            processing_states = load_processing_states(company_id)
            
            for file_idx, file_name in enumerate(files):
                doc_id = generate_document_id(company_id, file_name)
                
                processing_states[doc_id] = {
                    "doc_id": doc_id,
                    "company_id": company_id,
                    "file_name": file_name,
                    "is_processing": False,
                    "is_queued": True,
                    "current_file": file_name,
                    "file_index": file_idx + 1,
                    "total_files": len(files),
                    "progress": 0,
                    "message": f"Queued: Waiting for available worker...",
                    "steps": {},
                    "queued_time": time.time(),
                    "logs": [{
                        "timestamp": time.time(),
                        "message": f"Document queued for processing",
                        "status": "queued"
                    }]
                }
            
            save_processing_states(company_id, processing_states)
            print(f"📋 QUEUED: {len(files)} documents for {company_id}")
        
        def start_processing_in_background():
            """Wrapper function to run the pipeline with timing"""
            start_time = time.time()
            print(f"🚀 WORKER STARTED: {company_id} | Files: {len(files)}")
            
            try:
                for _ in process_documents_pipeline(company_id, files):
                    pass
                
                duration = time.time() - start_time
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                print(f"✅ WORKER COMPLETED: {company_id} | Duration: {minutes}m {seconds}s | Files processed: {len(files)}")
                
            except Exception as e:
                duration = time.time() - start_time
                print(f"❌ WORKER FAILED: {company_id} | Duration: {duration:.1f}s | Error: {e}")
                traceback.print_exc()
            finally:
                with active_jobs_lock:
                    active_jobs.discard(company_id)
                    remaining_jobs = len(active_jobs)
                    print(f"✅ WORKER FINISHED: {company_id} | Remaining active jobs: {remaining_jobs}/{MAX_CONCURRENT_JOBS}")

        # Check if already processing
        with active_jobs_lock:
            if company_id in active_jobs:
                print(f"⚠️  DUPLICATE JOB REJECTED: {company_id} (already processing)")
                return JSONResponse({
                    'success': False,
                    'error': f'Company {company_id} is already being processed. Please wait for current job to complete.'
                }, status_code=409)
            
            active_jobs.add(company_id)
            queue_size = len(active_jobs)
            
            if queue_size <= MAX_CONCURRENT_JOBS:
                status = "STARTING NOW"
            else:
                status = f"QUEUED (position {queue_size - MAX_CONCURRENT_JOBS} in queue)"
            
            print(f"📥 JOB SUBMITTED: {company_id} | Status: {status} | Active: {queue_size}/{MAX_CONCURRENT_JOBS}")

        # Submit job to thread pool
        try:
            future = job_executor.submit(start_processing_in_background)
        except Exception as submit_error:
            with active_jobs_lock:
                active_jobs.discard(company_id)
            print(f"❌ JOB SUBMISSION FAILED: {company_id} | Error: {submit_error}")
            raise submit_error

        return JSONResponse({
            'success': True,
            'message': f'Document processing started for {company_id}.',
            'queue_position': queue_size,
            'max_workers': MAX_CONCURRENT_JOBS
        }, status_code=202)
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        print(f"ERROR in process_documents: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        return JSONResponse({
            'success': False,
            'error': f'Failed to start processing: {str(e)}'
        }, status_code=500)


@app.get("/api/processing-queue-status")
async def get_processing_queue_status():
    """Get detailed status of the processing queue"""
    with active_jobs_lock:
        active_count = len(active_jobs)
        active_list = list(active_jobs)
    
    with processing_lock:
        all_states = processing_states_memory.copy()
        
        currently_processing = []
        queued_documents = []
        
        for doc_id, state in all_states.items():
            doc_info = {
                'doc_id': doc_id,
                'company_id': state.get('company_id'),
                'file_name': state.get('file_name'),
                'progress': state.get('progress', 0),
                'message': state.get('message', ''),
                'current_page': state.get('current_page'),
                'total_pages': state.get('total_pages')
            }
            
            if state.get('is_processing'):
                currently_processing.append(doc_info)
            elif state.get('is_queued'):
                queued_time = state.get('queued_time', time.time())
                doc_info['wait_time_seconds'] = int(time.time() - queued_time)
                queued_documents.append(doc_info)
    
    return JSONResponse({
        'success': True,
        'active_workers': active_count,
        'max_workers': MAX_CONCURRENT_JOBS,
        'available_workers': MAX_CONCURRENT_JOBS - active_count,
        'queue_full': active_count >= MAX_CONCURRENT_JOBS,
        'active_companies': active_list,
        'currently_processing': currently_processing,
        'queued_documents': queued_documents,
        'total_processing': len(currently_processing),
        'total_queued': len(queued_documents)
    })


@app.get("/api/document-processing-states")
async def get_document_processing_states():
    """Get all document processing states from in-memory storage"""
    with processing_lock:
        all_states = processing_states_memory.copy()
        active_count = sum(1 for state in all_states.values() if state.get("is_processing"))
        print(f"📊 STATES REQUESTED: {len(all_states)} total states ({active_count} active)")
        return JSONResponse(all_states)


# ============================================================================
# SSE ENDPOINT
# ============================================================================

@app.get("/events/processing-updates")
async def processing_updates():
    """Server-Sent Events endpoint for real-time processing updates"""
    async def event_stream():
        listener_queue = queue.Queue()
        
        with processing_lock:
            processing_listeners.add(listener_queue)
        
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to processing updates'})}\n\n"
            
            while True:
                try:
                    data = listener_queue.get(timeout=25)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            pass
        finally:
            with processing_lock:
                processing_listeners.discard(listener_queue)
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ============================================================================
# INDEXING ENDPOINTS
# ============================================================================

@app.post("/api/create-index")
async def create_index_endpoint(request: CreateIndexRequest):
    """API endpoint to start a full manual indexing job"""
    index_name = request.index_name

    if not index_name:
        return JSONResponse({'success': False, 'error': 'Missing index_name'}, status_code=400)

    def job_orchestrator():
        """Discovers companies and launches a worker thread for each"""
        # Import here to avoid blocking on startup
        from manual_indexer import index_company_worker
        from db_utils import get_db_connection
        
        project_root = get_project_root()
        output_file_path = os.path.join(project_root, "backend", "indexing_results.json")
        file_lock = threading.RLock()

        if os.path.exists(output_file_path):
            os.remove(output_file_path)

        def status_callback(message):
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

            for thread in threads:
                thread.join()

            # Check if any index was found
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

            if not any_index_found:
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cur:
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
            error_message = f"FATAL_ERROR: The indexing job failed during orchestration. Error: {str(e)}"
            status_callback(error_message)
            print(error_message)

    orchestrator_thread = threading.Thread(target=job_orchestrator)
    orchestrator_thread.daemon = True
    orchestrator_thread.start()

    return JSONResponse({'success': True, 'message': f'Indexing job launched for: {index_name}'}, status_code=202)


@app.get("/api/get-all-data")
async def get_all_data():
    """Fetches all records from the extracted_data table"""
    from db_utils import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        return JSONResponse({'success': False, 'error': 'Database connection failed'}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, company_name, file_name, index_name, result, created_at FROM extracted_data ORDER BY created_at DESC;")
            rows = cur.fetchall()
            
            column_names = [desc[0] for desc in cur.description]
            data = [dict(zip(column_names, row)) for row in rows]

            for row in data:
                if 'created_at' in row and hasattr(row['created_at'], 'isoformat'):
                    row['created_at'] = row['created_at'].isoformat()

            return JSONResponse({'success': True, 'data': data})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch data: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)
    finally:
        if conn:
            conn.close()


@app.get("/api/list-indexes")
async def list_indexes():
    """List all unique index names"""
    from db_utils import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        return JSONResponse({'success': False, 'error': 'Database connection failed'}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT index_name FROM extracted_data ORDER BY index_name;")
            index_names = [row[0] for row in cur.fetchall()]
            return JSONResponse({'index_names': index_names})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch index names: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)
    finally:
        if conn:
            conn.close()


@app.delete("/api/index/{index_name}")
async def delete_index(index_name: str):
    """Deletes all data associated with a specific index_name"""
    from db_utils import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        return JSONResponse({'success': False, 'error': 'Database connection failed'}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM extracted_data WHERE index_name = %s;", (index_name,))
            conn.commit()
            deleted_count = cur.rowcount
            print(f"[DB_INFO] Deleted {deleted_count} rows for index_name: {index_name}")
            return JSONResponse({'success': True, 'message': f'Successfully deleted {deleted_count} records for index \'{index_name}\''})
    except Exception as e:
        conn.rollback()
        print(f"[DB_ERROR] Failed to delete index data: {e}")
        return JSONResponse({'success': False, 'error': str(e)}, status_code=500)
    finally:
        if conn:
            conn.close()


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "framework": "FastAPI",
        "service": "Qdrant API"
    })


# ============================================================================
# STARTUP EVENT
# ============================================================================

@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("🚀 FastAPI RAG System Started")
    print("=" * 60)
    print(f"📍 Qdrant URL: {QDRANT_URL}")
    print(f"📦 Collection: {QDRANT_COLLECTION}")
    print(f"⚙️  Max Concurrent Jobs: {MAX_CONCURRENT_JOBS}")
    print(f"🔧 Deka AI: {'Connected' if deka_client else 'Not configured'}")
    print("=" * 60)
    print("📖 API Documentation: http://localhost:5001/docs")
    print("📖 ReDoc: http://localhost:5001/redoc")
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
