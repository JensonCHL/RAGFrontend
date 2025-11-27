"""
Document Processing Service Module
Handles the complete document processing pipeline orchestration
"""

import os
import json
import time
import traceback
import urllib.parse
from typing import Generator, List, Tuple

from core.config import get_project_root
from core.state import (
    processing_lock,
    generate_document_id,
    load_processing_states,
    save_processing_states,
    cleanup_processing_state,
    notify_processing_update
)
from services.ocr_service import ocr_pdf_pages, build_meta_header
from services.embedding_service import generate_embeddings
from services.qdrant_service import ingest_to_qdrant

# ============================================================================
# DOCUMENT PROCESSING PIPELINE
# ============================================================================

def process_documents_pipeline(
    company_id: str,
    files: List[str]
) -> Generator[str, None, None]:
    """
    Complete document processing pipeline: OCR -> Embedding -> Ingestion
    
    Args:
        company_id: Company identifier
        files: List of file names to process
        
    Yields:
        JSON progress updates for all steps
    """
    print(f"DEBUG: Starting pipeline for {company_id} with {len(files)} files")
    document_ids = []
    
    try:
        print(f"DEBUG: Files to process: {files}", flush=True)
        
        # Process each file
        for file_idx, file_name in enumerate(files):
            project_root = get_project_root()
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
            
            # Update state from "queued" to "processing"
            with processing_lock:
                processing_states = load_processing_states(company_id)
                
                if doc_id in processing_states:
                    queued_time = processing_states[doc_id].get("queued_time")
                    processing_states[doc_id].update({
                        "is_processing": True,
                        "is_queued": False,
                        "progress": 0,
                        "message": f"Initializing processing for {file_name}",
                        "start_time": time.time()
                    })
                else:
                    # Fallback: create new state if not queued
                    processing_states[doc_id] = {
                        "doc_id": doc_id,
                        "company_id": company_id,
                        "file_name": file_name,
                        "is_processing": True,
                        "is_queued": False,
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
            
            # Prepare chunks with metadata
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
            
            # Update completion status
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
            
            # Step 4: Structured Indexing (optional)
            try:
                from manual_indexer import index_single_document
                from db_utils import get_db_connection
                
                yield json.dumps({
                    "status": "step_started",
                    "step": "structured_indexing",
                    "currentFile": file_name,
                    "message": f"Starting automatic structured indexing for {file_name}"
                }) + "\n"

                db_conn = get_db_connection()
                if db_conn:
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
                            index_single_document(
                                company_id, 
                                file_name, 
                                index_name, 
                                status_callback=lambda msg_data: notify_processing_update(msg_data) if isinstance(msg_data, dict) else notify_processing_update({'type': 'indexing_status', 'message': msg_data})
                            )
                    else:
                        print(f"INFO: No existing structured indexes to process for {file_name}.")

                yield json.dumps({
                    "status": "step_completed",
                    "step": "structured_indexing",
                    "currentFile": file_name,
                    "message": f"Completed automatic structured indexing for {file_name}"
                }) + "\n"
            except Exception as idx_error:
                print(f"WARNING: Structured indexing failed for {file_name}: {idx_error}")
        
        # Mark all documents as completed
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
        print(f"ERROR in document processing pipeline: {str(e)}")
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
                        print(f"ERROR updating state in pipeline: {str(gen_error)}")
            save_processing_states(company_id, processing_states)
        
        yield json.dumps({
            "status": "process_error",
            "error": f"Processing failed: {str(e)}"
        }) + "\n"
    
    finally:
        # Clean up processing states from memory
        for doc_id, file_name in document_ids:
            cleanup_processing_state(doc_id)

print("✅ Document processing service initialized")
