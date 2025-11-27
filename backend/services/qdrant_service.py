"""
Qdrant Service Module
Handles Qdrant vector database operations
"""

import json
from typing import Generator, List, Dict, Any
from qdrant_client.http import models as rest

from core.config import QDRANT_COLLECTION, BATCH_SIZE
from core.clients import qdrant_client
from core.state import notify_processing_update

# ============================================================================
# QDRANT INGESTION
# ============================================================================

def ingest_to_qdrant(
    points_data: List[Dict[str, Any]], 
    company_name: str, 
    source_name: str
) -> Generator[str, None, None]:
    """
    Ingest embedded points to Qdrant with progress tracking
    
    Args:
        points_data: List of point dictionaries with id, vector, and payload
        company_name: Company name
        source_name: Source document name
        
    Yields:
        JSON progress updates
    """
    try:
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
    """
    Queries Qdrant for the full company/document structure and notifies listeners.
    """
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

print("✅ Qdrant service initialized")
