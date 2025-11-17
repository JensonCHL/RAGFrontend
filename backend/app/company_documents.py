# backend/app/company_documents.py
"""
Company and document management endpoints for the FastAPI application.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from core.qdrant_client import get_qdrant_client
from core.config import get_settings

router = APIRouter()
settings = get_settings()
qdrant_client = get_qdrant_client()


@router.get("/api/companies-with-documents")
async def get_companies_with_documents():
    """
    Get all unique company names with their associated documents and metadata in a single optimized call
    Returns a dictionary mapping company names to lists of document details
    """
    try:
        # Check if qdrant_client is initialized
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")
        
        # Scroll through all points to get companies and documents
        company_documents = {}
        offset = None

        while True:
            # Fetch points with pagination
            response = qdrant_client.scroll(
                collection_name=settings.QDRANT_COLLECTION,
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
            return JSONResponse(
                content={
                    'success': False,
                    'error': f'Indexing error: Please create an index on "metadata.company" field in Qdrant. {error_msg}'
                },
                status_code=400
            )
        else:
            return JSONResponse(
                content={
                    'success': False,
                    'error': f'Failed to fetch companies with documents: {error_msg}'
                },
                status_code=500
            )