# backend/app/companies.py
"""
Company management endpoints for the FastAPI application.
"""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
from typing import List
import os
import re
import shutil
from qdrant_client.models import Filter, FieldCondition, MatchValue
from core.qdrant_client import get_qdrant_client
from core.config import get_settings
from core.utils import get_ocr_cache_path, get_log_file_path

router = APIRouter()
settings = get_settings()
qdrant_client = get_qdrant_client()


@router.get("/api/companies")
async def get_companies():
    """
    Get all unique company names from Qdrant metadata
    """
    try:
        # Check if qdrant_client is initialized
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

        # Scroll through all points to get unique companies
        companies = set()
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

            # Extract company names from metadata
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

        return JSONResponse(content={
            'success': True,
            'companies': company_list
        })

    except Exception as e:
        return JSONResponse(
            content={
                'success': False,
                'error': f'Failed to fetch companies: {str(e)}'
            },
            status_code=500
        )


@router.get("/api/companies/{company_name}/documents")
async def get_company_documents(company_name: str = Path(..., description="Name of the company")):
    """
    Get all documents for a specific company
    """
    try:
        # Check if qdrant_client is initialized
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

        # Create filter for the specific company
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
                collection_name=settings.QDRANT_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                scroll_filter=company_filter
            )

            points, next_offset = response

            # Extract document sources from metadata
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
                    'error': f'Failed to fetch documents for company {company_name}: {error_msg}'
                },
                status_code=500
            )


@router.delete("/api/companies/{company_name}")
async def delete_company_data(company_name: str = Path(..., description="Name of the company")):
    """
    Delete all data for a specific company from Qdrant and its OCR cache.
    """
    try:
        # Check if qdrant_client is initialized
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

        # Delete all points for the company from Qdrant
        company_filter = Filter(must=[FieldCondition(key="metadata.company", match=MatchValue(value=company_name))])
        qdrant_client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=company_filter
        )
        print(f"DEBUG: Deleted Qdrant data for company {company_name}")

        # Now, delete the entire OCR cache directory for the company
        try:
            safe_company_id = re.sub(r'[\\/*?:"<>|]', "_", company_name)
            company_cache_dir = os.path.join(settings.OCR_CACHE_DIR, safe_company_id)
            if os.path.exists(company_cache_dir):
                shutil.rmtree(company_cache_dir)
                print(f"DEBUG: Deleted company cache directory: {company_cache_dir}")
        except Exception as e:
            print(f"ERROR: Failed to delete company cache directory for {company_name}: {e}")

        # Also delete the processing log file for the company
        try:
            log_file_path = get_log_file_path(company_name)
            if os.path.exists(log_file_path):
                os.remove(log_file_path)
                print(f"DEBUG: Deleted company log file: {log_file_path}")
        except Exception as e:
            print(f"ERROR: Failed to delete company log file for {company_name}: {e}")

        return JSONResponse(content={
            'success': True,
            'message': f'Successfully deleted documents for company {company_name}'
        })

    except Exception as e:
        error_msg = str(e)
        return JSONResponse(
            content={
                'success': False,
                'error': f'Failed to delete company data: {error_msg}'
            },
            status_code=500
        )


@router.delete("/api/companies/{company_name}/documents/{document_name}")
async def delete_document(
    company_name: str = Path(..., description="Name of the company"),
    document_name: str = Path(..., description="Name of the document")
):
    """
    Delete a specific document for a company from Qdrant using doc_id
    """
    try:
        # Check if qdrant_client is initialized
        if not qdrant_client:
            raise HTTPException(status_code=500, detail="Qdrant client not initialized")

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
                collection_name=settings.QDRANT_COLLECTION,
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
            return JSONResponse(
                content={
                    'success': False,
                    'error': f'Document {document_name} not found for company {company_name}'
                },
                status_code=404
            )

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
            collection_name=settings.QDRANT_COLLECTION,
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

        return JSONResponse(content={
            'success': True,
            'message': f'Successfully deleted document {document_name} with doc_id {doc_id}'
        })

    except Exception as e:
        error_msg = str(e)
        return JSONResponse(
            content={
                'success': False,
                'error': f'Failed to delete document: {error_msg}'
            },
            status_code=500
        )